"""
Content Processor abstraction for different input types.
Supports YouTube videos, articles, PDFs, etc.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ContentMetadata:
    """Standardized metadata for any content source."""
    title: str
    source: str
    source_type: str  # "youtube", "article", "pdf", etc.
    url: Optional[str] = None
    author: Optional[str] = None
    duration: Optional[str] = None
    language: Optional[str] = None
    published_date: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "source": self.source,
            "source_type": self.source_type,
            "url": self.url,
            "author": self.author,
            "duration": self.duration,
            "language": self.language,
            "published_date": self.published_date,
        }


@dataclass
class ProcessedContent:
    """Standardized output from any content processor."""
    metadata: ContentMetadata
    content: str  # Full text content
    content_excerpt: str  # First N characters for prompts
    key_concepts: List[str]
    summary: str
    prerequisites: List[str]
    needs_code: bool
    code_topics: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "content": self.content,
            "content_excerpt": self.content_excerpt,
            "key_concepts": self.key_concepts,
            "summary": self.summary,
            "prerequisites": self.prerequisites,
            "needs_code": self.needs_code,
            "code_topics": self.code_topics,
        }


class ContentProcessor(ABC):
    """
    Abstract base class for content processors.
    
    Each processor handles a specific content type (YouTube, PDF, etc.)
    and converts it to standardized ProcessedContent.
    """
    
    # Supported source types
    SOURCE_TYPES: List[str] = []
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    
    @abstractmethod
    def can_process(self, source: str) -> bool:
        """
        Check if this processor can handle the given source.
        
        Args:
            source: URL, file path, or identifier
            
        Returns:
            True if this processor can handle the source
        """
        pass
    
    @abstractmethod
    def extract_metadata(self, source: str) -> ContentMetadata:
        """Extract metadata from the source."""
        pass
    
    @abstractmethod
    def extract_content(self, source: str) -> str:
        """Extract full text content from the source."""
        pass
    
    def process(self, source: str) -> ProcessedContent:
        """
        Process source and return standardized content.
        
        This is the main entry point - subclasses typically don't override this.
        """
        if not self.can_process(source):
            raise ValueError(f"Cannot process source: {source}")
        
        metadata = self.extract_metadata(source)
        content = self.extract_content(source)
        
        # Create excerpt (first 8000 chars)
        excerpt_length = self.config.get("excerpt_length", 8000)
        content_excerpt = content[:excerpt_length]
        if len(content) > excerpt_length:
            content_excerpt += "..."
        
        # Initialize with empty values - will be filled by LLM
        return ProcessedContent(
            metadata=metadata,
            content=content,
            content_excerpt=content_excerpt,
            key_concepts=[],
            summary="",
            prerequisites=[],
            needs_code=False,
            code_topics=[],
        )


class ContentProcessorRegistry:
    """Registry for managing content processors."""
    
    def __init__(self):
        self._processors: List[ContentProcessor] = []
    
    def register(self, processor: ContentProcessor):
        """Register a content processor."""
        self._processors.append(processor)
    
    def get_processor(self, source: str) -> ContentProcessor:
        """
        Find a processor that can handle the source.
        
        Returns:
            First matching processor
            
        Raises:
            ValueError: If no processor can handle the source
        """
        for processor in self._processors:
            if processor.can_process(source):
                return processor
        
        raise ValueError(f"No processor available for source: {source}")
    
    def process(self, source: str) -> ProcessedContent:
        """Process source using appropriate processor."""
        processor = self.get_processor(source)
        return processor.process(source)
    
    def list_processors(self) -> List[str]:
        """List registered processor types."""
        types = []
        for p in self._processors:
            types.extend(p.SOURCE_TYPES)
        return types


# YouTube Processor Implementation

import re
import requests
from urllib.parse import urlparse, parse_qs


class YouTubeProcessor(ContentProcessor):
    """Processor for YouTube videos."""
    
    SOURCE_TYPES = ["youtube"]
    
    # Language code fallbacks
    LANGUAGE_FALLBACKS = ['hi', 'en', 'en-IN', 'en-US', 'en-GB', 'es', 'fr', 'de']
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.max_chars = config.get("max_transcript_chars", 12000) if config else 12000
        
        # Import here to avoid dependency if not using YouTube
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            self.ytt_api = YouTubeTranscriptApi()
        except ImportError:
            self.ytt_api = None
    
    def can_process(self, source: str) -> bool:
        """Check if source is a YouTube URL."""
        patterns = [
            r'^https?://(www\.)?youtube\.com/watch\?v=',
            r'^https?://youtu\.be/',
            r'^https?://(www\.)?youtube\.com/shorts/',
        ]
        return any(re.match(pattern, source) for pattern in patterns)
    
    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from various YouTube URL formats."""
        parsed = urlparse(url)
        
        if parsed.hostname in ("youtu.be",):
            return parsed.path.lstrip("/")
        
        if parsed.hostname in ("www.youtube.com", "youtube.com"):
            qs = parse_qs(parsed.query)
            if "v" in qs:
                return qs["v"][0]
            
            # Handle /shorts/ and /live/ paths
            path_match = re.match(r'/(shorts|live)/(\w+)', parsed.path)
            if path_match:
                return path_match.group(2)
        
        raise ValueError(f"Cannot extract video ID from: {url}")
    
    def extract_metadata(self, source: str) -> ContentMetadata:
        """Fetch video metadata from YouTube oEmbed."""
        video_id = self._extract_video_id(source)
        
        oembed_url = f"https://www.youtube.com/oembed?url=https://youtube.com/watch?v={video_id}&format=json"
        
        try:
            response = requests.get(oembed_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return ContentMetadata(
                title=data.get("title", "Unknown Title"),
                source=data.get("author_name", "Unknown Channel"),
                source_type="youtube",
                url=source,
                author=data.get("author_name"),
            )
        except Exception:
            return ContentMetadata(
                title="Unknown Title",
                source="Unknown Channel",
                source_type="youtube",
                url=source,
            )
    
    def extract_content(self, source: str) -> str:
        """Fetch transcript from YouTube video."""
        if not self.ytt_api:
            raise RuntimeError("youtube-transcript-api not installed")
        
        video_id = self._extract_video_id(source)
        
        # Get available languages from config or use defaults
        languages = self.config.get("languages", self.LANGUAGE_FALLBACKS)
        
        try:
            transcript = self.ytt_api.fetch(video_id, languages=languages)
            text = " ".join(chunk.text for chunk in transcript)
            
            # Trim to context budget
            if len(text) > self.max_chars:
                text = text[:self.max_chars] + "\n[... transcript truncated ...]"
            
            return text
        except Exception as e:
            raise RuntimeError(f"Failed to fetch transcript: {e}")


class TextFileProcessor(ContentProcessor):
    """Processor for text files (.txt, .md, etc.)."""
    
    SOURCE_TYPES = ["text", "txt", "md", "markdown"]
    
    def can_process(self, source: str) -> bool:
        """Check if source is a text file path."""
        path = Path(source)
        return path.exists() and path.suffix.lower() in ['.txt', '.md', '.markdown']
    
    def extract_metadata(self, source: str) -> ContentMetadata:
        """Extract metadata from file."""
        path = Path(source)
        
        # Try to extract title from first line
        try:
            with open(path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                title = first_line.lstrip('#').strip() if first_line.startswith('#') else path.stem
        except:
            title = path.stem
        
        return ContentMetadata(
            title=title,
            source=path.name,
            source_type="text",
            url=str(path.absolute()),
        )
    
    def extract_content(self, source: str) -> str:
        """Read text file content."""
        path = Path(source)
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()


def create_default_processor_registry(config: Optional[Dict[str, Any]] = None) -> ContentProcessorRegistry:
    """Create a registry with default processors."""
    registry = ContentProcessorRegistry()
    
    # Register YouTube processor if dependencies available
    try:
        registry.register(YouTubeProcessor(config))
    except Exception as e:
        print(f"Warning: YouTube processor not available: {e}")
    
    # Register text file processor
    registry.register(TextFileProcessor(config))
    
    return registry
