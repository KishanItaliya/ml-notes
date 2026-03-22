"""
LLM Provider abstraction layer.
Supports multiple providers with unified interface.
"""

import os
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or self._get_api_key_from_env()
    
    @abstractmethod
    def _get_api_key_from_env(self) -> str:
        """Get API key from environment variable."""
        pass
    
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send chat completion request."""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier."""
        pass


class GroqProvider(LLMProvider):
    """Groq LLM provider implementation."""
    
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(api_key)
        self.model = model or self.DEFAULT_MODEL
    
    def _get_api_key_from_env(self) -> str:
        return os.getenv("GROQ_API_KEY", "")
    
    def get_model_name(self) -> str:
        return self.model
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send request to Groq API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.4),
        }
        
        # Add optional parameters
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "stop" in kwargs:
            payload["stop"] = kwargs["stop"]
        
        response = requests.post(
            self.API_URL, 
            headers=headers, 
            json=payload, 
            timeout=kwargs.get("timeout", 60)
        )
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"].strip()


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider implementation."""
    
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    API_URL = "https://api.anthropic.com/v1/messages"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(api_key)
        self.model = model or self.DEFAULT_MODEL
    
    def _get_api_key_from_env(self) -> str:
        return os.getenv("ANTHROPIC_API_KEY", "")
    
    def get_model_name(self) -> str:
        return self.model
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send request to Claude API."""
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        
        # Extract system message and convert roles
        system = None
        chat_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                role = "assistant" if msg["role"] == "assistant" else "user"
                chat_messages.append({"role": role, "content": msg["content"]})
        
        # Ensure at least one user message
        if not chat_messages:
            chat_messages.append({"role": "user", "content": "Hello"})
        
        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.5),
            "messages": chat_messages,
        }
        
        if system:
            payload["system"] = system
        
        response = requests.post(
            self.API_URL,
            headers=headers,
            json=payload,
            timeout=kwargs.get("timeout", 120)
        )
        response.raise_for_status()
        
        return response.json()["content"][0]["text"].strip()


class LLMProviderFactory:
    """Factory for creating LLM provider instances."""
    
    _providers = {
        "groq": GroqProvider,
        "claude": ClaudeProvider,
    }
    
    @classmethod
    def create(cls, provider_name: str, **kwargs) -> LLMProvider:
        """Create a provider instance by name."""
        provider_name = provider_name.lower()
        
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown provider: {provider_name}. "
                           f"Available: {list(cls._providers.keys())}")
        
        return cls._providers[provider_name](**kwargs)
    
    @classmethod
    def register(cls, name: str, provider_class: type):
        """Register a new provider type."""
        cls._providers[name.lower()] = provider_class
    
    @classmethod
    def list_providers(cls) -> list:
        """List available provider names."""
        return list(cls._providers.keys())
