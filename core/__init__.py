"""
Core module for the Notes Agent System.
Provides base classes and interfaces for building topic-agnostic content processors.
"""

from .base_agent import BaseAgent
from .content_processor import ContentProcessor
from .llm_provider import LLMProvider, GroqProvider, ClaudeProvider, LLMProviderFactory
from .prompt_template import PromptTemplate

__all__ = [
    "BaseAgent",
    "ContentProcessor", 
    "LLMProvider",
    "GroqProvider",
    "ClaudeProvider",
    "LLMProviderFactory",
    "PromptTemplate",
]
