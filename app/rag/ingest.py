"""
PDF document ingestion using LangChain.
Processes PDF documents for client knowledge bases.
"""

import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.rag.vectorstore import VectorStoreManager, DocumentChunk


# File extensions to process (prioritize PDF)
SUPPORTED_EXTENSIONS = {".pdf"}


class DocumentIngester:
    """Handles PDF ingestion for a specific client."""
    
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.documents_path = settings.DOCUMENTS_DIR / client_id
        self.processed_path = self.documents_path / ".processed"
        
        self.documents_path.mkdir(parents=True, exist_ok=True)
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Generate hash of file content for change detection."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _load_processed_hashes(self) -> Dict[str, str]:
        """Load previously processed file hashes."""
        if not self.processed_path.exists():
            return {}
        
        hashes = {}
        try:
            with open(self.processed_path, "r") as f:
                for line in f:
                    if ":" in line:
                        filename, hash_val = line.strip().split(":", 1)
                        hashes[filename] = hash_val
        except Exception:
            return {}
        return hashes
    
    def _save_processed_hashes(self, hashes: Dict[str, str]):
        """Save processed file hashes."""
        with open(self.processed_path, "w") as f:
            for filename, hash_val in hashes.items():
                f.write(f"{filename}:{hash_val}\n")
    
    def _process_pdf(self, file_path: Path) -> List[DocumentChunk]:
        """Process a single PDF into chunks."""
        chunks = []
        
        try:
            loader = PyPDFLoader(str(file_path))
            pages = loader.load()
            
            split_docs = self.text_splitter.split_documents(pages)
            
            for i, doc in enumerate(split_docs):
                content = doc.page_content.strip()
                if not content or len(content) < 20:
                    continue
                
                chunks.append(DocumentChunk(
                    content=content,
                    metadata={
                        "client_id": self.client_id,
                        "source": file_path.name,
                        "page": doc.metadata.get("page", 0),
                        "chunk_index": i,
                        "ingested_at": datetime.utcnow().isoformat()
                    }
                ))
            
            print(f"📄 Processed {file_path.name}: {len(chunks)} chunks")
            
        except Exception as e:
            print(f"❌ Failed to process {file_path.name}: {e}")
        
        return chunks
    
    def ingest_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Ingest all PDF documents in the client's document directory.
        
        Only processes PDF files - other formats are ignored.
        
        Args:
            force: If True, reprocess all files regardless of hash
            
        Returns:
            Summary of ingestion results
        """
        results = {
            "client_id": self.client_id,
            "processed": [],
            "skipped": [],
            "errors": [],
            "total_chunks": 0
        }
        
        # Get only PDF files
        pdf_files = list(self.documents_path.glob("*.pdf"))
        
        if not pdf_files:
            print(f"📂 No PDF files found for client: {self.client_id}")
            return results
        
        processed_hashes = {} if force else self._load_processed_hashes()
        new_hashes = {}
        all_chunks = []
        
        for file_path in pdf_files:
            file_hash = self._get_file_hash(file_path)
            filename = file_path.name
            
            if not force and filename in processed_hashes:
                if processed_hashes[filename] == file_hash:
                    results["skipped"].append(filename)
                    new_hashes[filename] = file_hash
                    continue
            
            try:
                chunks = self._process_pdf(file_path)
                all_chunks.extend(chunks)
                results["processed"].append(filename)
                new_hashes[filename] = file_hash
            except Exception as e:
                results["errors"].append({"file": filename, "error": str(e)})
        
        if all_chunks:
            store = VectorStoreManager.get_store(self.client_id)
            if force:
                store.clear()
            store.add_chunks(all_chunks)
            results["total_chunks"] = len(all_chunks)
        
        self._save_processed_hashes(new_hashes)
        
        return results
    
    def ingest_file(self, filename: str) -> Dict[str, Any]:
        """Ingest a single PDF file."""
        file_path = self.documents_path / filename
        
        if not file_path.exists():
            return {"error": f"File not found: {filename}"}
        
        if file_path.suffix.lower() != ".pdf":
            return {"error": "Only PDF files are supported"}
        
        chunks = self._process_pdf(file_path)
        
        if chunks:
            store = VectorStoreManager.get_store(self.client_id)
            store.add_chunks(chunks)
            
            hashes = self._load_processed_hashes()
            hashes[filename] = self._get_file_hash(file_path)
            self._save_processed_hashes(hashes)
        
        return {
            "file": filename,
            "chunks": len(chunks),
            "success": bool(chunks)
        }


def ingest_client_documents(client_id: str, force: bool = False) -> Dict[str, Any]:
    """Convenience function to ingest all PDF documents for a client."""
    ingester = DocumentIngester(client_id)
    return ingester.ingest_all(force=force)


def ingest_all_clients(force: bool = False) -> Dict[str, Any]:
    """Ingest PDF documents for all clients."""
    results = {}
    
    if not settings.DOCUMENTS_DIR.exists():
        return {"error": "Documents directory does not exist"}
    
    for client_dir in settings.DOCUMENTS_DIR.iterdir():
        if client_dir.is_dir() and not client_dir.name.startswith("."):
            client_id = client_dir.name
            results[client_id] = ingest_client_documents(client_id, force=force)
    
    return results
