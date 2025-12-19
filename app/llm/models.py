"""
LLM model abstraction with strict document-grounded prompting.
"""

from typing import Optional
from abc import ABC, abstractmethod

from app.config import settings


# Document-grounded system prompt
DOCUMENT_GROUNDED_SYSTEM_PROMPT = """You are a customer support assistant that ONLY answers based on the provided documentation.

CRITICAL RULES:
1. You MUST ONLY use information from the "CONTEXT FROM DOCUMENTATION" section below
2. If the answer is NOT in the documentation, respond EXACTLY with: "This information is not available in the provided documentation."
3. NEVER make up information or use general knowledge
4. NEVER say "based on my knowledge" or "generally speaking"
5. Keep answers factual, concise, and professional
6. Maximum response length: 500 characters
7. Do not use marketing language or promotional content
8. If asked about actions (refunds, deletion, etc.), explain the process from docs if available, but do NOT perform any action

RESPONSE FORMAT:
- Be direct and helpful
- Use bullet points for multi-step information
- Include source document name if relevant
- If uncertain, ask for clarification rather than guessing"""


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate(
        self, 
        context: str, 
        query: str,
        system_prompt: str = None
    ) -> Optional[str]:
        """Generate response from context and query."""
        pass
    
    def _build_prompt(
        self, 
        context: str, 
        query: str,
        system_prompt: str = None
    ) -> str:
        """Build the full prompt with context."""
        system = system_prompt or DOCUMENT_GROUNDED_SYSTEM_PROMPT
        
        return f"""{system}

---
CONTEXT FROM DOCUMENTATION:
{context if context else "No relevant documentation found."}
---

USER QUESTION:
{query}

RESPONSE:"""


class OpenRouterLLM(BaseLLM):
    """OpenRouter API LLM implementation."""
    
    def __init__(self):
        import httpx
        self.client = httpx.Client(timeout=30)
        self.url = settings.OPENROUTER_URL
        self.model = settings.OPENROUTER_MODEL
    
    def generate(
        self, 
        context: str, 
        query: str,
        system_prompt: str = None
    ) -> Optional[str]:
        """Generate response using OpenRouter."""
        if not settings.OPENROUTER_API_KEY:
            print("❌ OpenRouter API key not configured")
            return None
        
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AI Support Platform"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt or DOCUMENT_GROUNDED_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"CONTEXT FROM DOCUMENTATION:\n{context}\n\nUSER QUESTION:\n{query}"
                }
            ],
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS
        }
        
        try:
            response = self.client.post(
                self.url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            
            # Enforce max length
            if len(content) > settings.MAX_ANSWER_LENGTH:
                content = content[:settings.MAX_ANSWER_LENGTH] + "..."
            
            return content
            
        except Exception as e:
            print(f"❌ OpenRouter error: {e}")
            return None


class GeminiLLM(BaseLLM):
    """Google Gemini LLM implementation."""
    
    def __init__(self):
        import google.generativeai as genai
        
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            # Use gemini-1.5-flash without 'models/' prefix
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.model = None
    
    def generate(
        self, 
        context: str, 
        query: str,
        system_prompt: str = None
    ) -> Optional[str]:
        """Generate response using Gemini."""
        if not self.model:
            print("❌ Gemini API key not configured")
            return None
        
        prompt = self._build_prompt(context, query, system_prompt)
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": settings.LLM_TEMPERATURE,
                    "max_output_tokens": settings.LLM_MAX_TOKENS,
                }
            )
            
            content = response.text
            
            # Enforce max length
            if len(content) > settings.MAX_ANSWER_LENGTH:
                content = content[:settings.MAX_ANSWER_LENGTH] + "..."
            
            return content
            
        except Exception as e:
            print(f"❌ Gemini error: {e}")
            return None
