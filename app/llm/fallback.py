"""
LLM fallback chain with multiple providers.
"""

from typing import Optional, List
from app.llm.models import BaseLLM, OpenRouterLLM, GeminiLLM
from app.config import settings


class LLMFallbackChain:
    """Fallback chain that tries multiple LLM providers."""
    
    def __init__(self):
        self.providers: List[BaseLLM] = []
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available LLM providers in priority order."""
        # Primary: Gemini (often faster)
        if settings.GEMINI_API_KEY:
            self.providers.append(GeminiLLM())
            print("✅ Gemini LLM initialized")
        
        # Secondary: OpenRouter
        if settings.OPENROUTER_API_KEY:
            self.providers.append(OpenRouterLLM())
            print("✅ OpenRouter LLM initialized")
        
        if not self.providers:
            print("⚠️ No LLM providers configured! Responses will be limited.")
    
    def generate(
        self, 
        context: str, 
        query: str,
        system_prompt: str = None
    ) -> Optional[str]:
        """
        Generate response with fallback.
        
        Tries each provider in order until one succeeds.
        """
        if not self.providers:
            return "I apologize, but the AI service is currently unavailable. Please try again later."
        
        last_error = None
        
        for provider in self.providers:
            try:
                response = provider.generate(context, query, system_prompt)
                if response:
                    return response
            except Exception as e:
                last_error = e
                print(f"⚠️ Provider {type(provider).__name__} failed: {e}")
                continue
        
        print(f"❌ All LLM providers failed. Last error: {last_error}")
        return None
    
    def generate_grounded_response(
        self,
        context: str,
        query: str,
        fallback_message: str = "This information is not available in the provided documentation."
    ) -> str:
        """
        Generate document-grounded response.
        
        Returns fallback message if context is empty or generation fails.
        """
        if not context or not context.strip():
            return fallback_message
        
        response = self.generate(context, query)
        
        if not response:
            return "I apologize, but I'm unable to process your request at the moment. Please try again."
        
        return response
    
    def generate_document_grounded(
        self,
        context: str,
        query: str,
        sources: List[str] = None
    ) -> Optional[str]:
        """
        Generate response strictly grounded in document context.
        
        Args:
            context: Retrieved document content
            query: User's question
            sources: List of source document names
        
        Returns:
            Generated response or None if failed
        """
        if not context or not context.strip():
            return None
        
        # Build source context
        source_info = ""
        if sources:
            source_info = f"\nSources: {', '.join(sources[:3])}"
        
        system_prompt = f"""You are a helpful customer support assistant answering based on company documentation.

RULES:
1. Answer ONLY using the provided documentation context
2. Be direct, clear, and professional
3. Use bullet points for step-by-step instructions
4. If the documentation is unclear, say so honestly
5. Keep responses concise (under 400 characters)
{source_info}"""
        
        return self.generate(context, query, system_prompt)
    
    def generate_general_response(
        self,
        query: str,
        intent: str = "general_question"
    ) -> Optional[str]:
        """
        Generate a general LLM response when documents don't have the answer.
        
        This is the fallback when documents lack relevant information.
        
        Args:
            query: User's question
            intent: Detected intent category
        
        Returns:
            Generated response or None if failed
        """
        system_prompt = """You are a helpful customer support assistant.

RULES:
1. Be helpful, accurate, and professional
2. Provide general guidance when asked
3. If you don't know something specific, say so honestly
4. Keep responses concise and practical (under 400 characters)
5. Never make up specific policies, prices, or technical specs
6. For account-specific questions, suggest contacting support

Respond helpfully to the user's question."""
        
        # For general questions, we don't have document context
        context = f"User intent: {intent}. No specific documentation available for this query."
        
        return self.generate(context, query, system_prompt)


# Singleton instance
_llm_chain: Optional[LLMFallbackChain] = None


def get_llm() -> LLMFallbackChain:
    """Get singleton LLM chain."""
    global _llm_chain
    if _llm_chain is None:
        _llm_chain = LLMFallbackChain()
    return _llm_chain


def generate_response(
    context: str,
    query: str,
    system_prompt: str = None
) -> Optional[str]:
    """Convenience function to generate LLM response."""
    llm = get_llm()
    return llm.generate(context, query, system_prompt)
