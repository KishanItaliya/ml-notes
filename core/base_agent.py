"""
Base Agent class that orchestrates the content processing pipeline.
Topic-agnostic and configurable for any domain.
"""

import json
import re
import time
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

import requests

from .llm_provider import LLMProvider, LLMProviderFactory
from .prompt_template import PromptTemplateRegistry, create_default_registry
from .content_processor import (
    ContentProcessorRegistry, 
    ProcessedContent,
    create_default_processor_registry
)


class BaseAgent:
    """
    Generic agent for processing educational content and generating study materials.
    
    Configurable for any domain (ML, Web Dev, Finance, etc.) through:
    - Domain-specific prompt templates
    - Custom content processors
    - Pluggable LLM providers
    - Flexible output generators
    
    Usage:
        agent = BaseAgent(
            domain="machine_learning",
            llm_provider="groq",
            config={...}
        )
        result = agent.process("https://youtube.com/watch?v=...")
    """
    
    def __init__(
        self,
        domain: str = "generic",
        llm_provider: str = "groq",
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the agent.
        
        Args:
            domain: The knowledge domain (e.g., "machine_learning", "web_development")
            llm_provider: LLM provider name ("groq", "claude", etc.)
            config: Configuration dictionary
        """
        self.domain = domain
        self.config = config or {}
        
        # Initialize LLM provider
        self.llm = LLMProviderFactory.create(llm_provider)
        
        # Initialize registries
        self.prompt_registry = create_default_registry()
        self.processor_registry = create_default_processor_registry(config)
        
        # Load domain-specific prompts if available
        self._load_domain_prompts()
        
        # Research configuration
        self.research_enabled = self.config.get("research_enabled", True)
        self.research_queries = self.config.get("research_queries", 2)
        
        # Output configuration
        self.docs_folder = self.config.get("docs_folder", "docs")
        self.examples_folder = self.config.get("examples_folder", "examples")
        
        # GitHub configuration (optional)
        self.github_config = self.config.get("github", {})
    
    def _load_domain_prompts(self):
        """Load domain-specific prompt templates if they exist."""
        prompts_dir = Path(__file__).parent.parent / "prompts" / self.domain
        if prompts_dir.exists():
            self.prompt_registry.load_from_directory(prompts_dir)
    
    def process(self, source: str) -> Dict[str, Any]:
        """
        Main entry point: process a content source end-to-end.
        
        Args:
            source: URL, file path, or content identifier
            
        Returns:
            Dictionary with generated outputs and metadata
        """
        print(f"\n[*] Agent starting for domain: {self.domain}")
        print(f"    Source: {source}")
        print(f"    LLM: {self.llm.get_model_name()}")
        
        # Step 1: Extract content
        print("\n  [1/5] Extracting content...")
        content = self.processor_registry.process(source)
        print(f"   [OK] Title: {content.metadata.title}")
        print(f"   [OK] Content length: {len(content.content)} chars")
        
        # Step 2: Analyze and summarize
        print("\n  [2/5] Analyzing content...")
        content = self._analyze_content(content)
        print(f"   [OK] Topic: {content.metadata.title}")
        print(f"   [OK] Key concepts: {len(content.key_concepts)}")
        
        # Step 3: Research (optional)
        research = ""
        if self.research_enabled:
            print("\n  [3/5] Researching context...")
            research = self._research_topic(content)
            print(f"   [OK] Found {len(research.split(chr(10)*2))} research snippets")
        
        # Step 4: Generate outputs
        print("\n  [4/5] Generating study materials...")
        
        notes = self._generate_notes(content, research)
        print("   [OK] Notes generated")
        
        code = None
        if content.needs_code:
            code = self._generate_code(content)
            print("   [OK] Code examples generated")
        
        # Step 5: Publish (optional)
        result = {
            "domain": self.domain,
            "topic": content.metadata.title,
            "notes": notes,
            "code": code,
            "metadata": content.to_dict(),
        }
        
        if self.github_config:
            print("\n  [5/5] Publishing to GitHub...")
            result["urls"] = self._publish_to_github(content, notes, code)
        
        print("\n[DONE] Processing complete!\n")
        return result
    
    def _analyze_content(self, content: ProcessedContent) -> ProcessedContent:
        """Use LLM to analyze content and extract structured information."""
        template = self.prompt_registry.get(task="summarize")
        
        prompts = template.render(
            domain=self.domain.replace("_", " ").title(),
            title=content.metadata.title,
            source=content.metadata.source,
            content_type=content.metadata.source_type,
            content=content.content_excerpt,
        )
        
        response = self.llm.chat([
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": prompts["user"]},
        ], max_tokens=1024, temperature=0.2)
        
        # Parse JSON response
        try:
            raw = re.sub(r"```json|```", "", response).strip()
            analysis = json.loads(raw)
            
            # Update content with analysis results
            content.key_concepts = analysis.get("key_concepts", [])
            content.summary = analysis.get("summary", "")
            content.prerequisites = analysis.get("prerequisites", [])
            content.needs_code = analysis.get("needs_code", False)
            content.code_topics = analysis.get("code_topics", [])
            
            # Update title if topic is more specific
            if analysis.get("topic"):
                content.metadata.title = analysis["topic"]
                
        except json.JSONDecodeError as e:
            print(f"   [!] Warning: Failed to parse analysis: {e}")
            # Use defaults
            content.key_concepts = []
            content.summary = "Analysis failed."
            content.prerequisites = []
            content.needs_code = False
            content.code_topics = []
        
        return content
    
    def _research_topic(self, content: ProcessedContent) -> str:
        """Research topic using web search."""
        queries = [
            f"{content.metadata.title} {self.domain} best practices",
            f"{content.metadata.title} real world use cases",
        ]
        
        snippets = []
        seen = set()
        
        for query in queries[:self.research_queries]:
            try:
                # Simple DuckDuckGo search
                url = "https://html.duckduckgo.com/html/"
                response = requests.post(
                    url,
                    data={"q": query, "b": ""},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10,
                )
                
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                results = soup.select(".result__snippet")[:2]
                
                for res in results:
                    text = res.get_text(" ", strip=True)
                    if len(text) > 60 and text not in seen:
                        seen.add(text)
                        snippets.append(text)
                
                time.sleep(0.5)
            except Exception as e:
                print(f"   [!] Research query failed: {e}")
        
        return "\n\n".join(snippets) if snippets else "No research results found."
    
    def _generate_notes(self, content: ProcessedContent, research: str) -> str:
        """Generate markdown notes."""
        template = self.prompt_registry.get(task="generate_notes")
        
        prompts = template.render(
            domain=self.domain.replace("_", " ").title(),
            topic=content.metadata.title,
            title=content.metadata.title,
            source=content.metadata.source,
            date=datetime.now().strftime("%Y-%m-%d"),
            key_concepts=content.key_concepts,
            prerequisites=content.prerequisites,
            summary=content.summary,
            content_excerpt=content.content_excerpt,
            research=research,
        )
        
        return self.llm.chat([
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": prompts["user"]},
        ], max_tokens=4000, temperature=0.4)
    
    def _generate_code(self, content: ProcessedContent) -> str:
        """Generate code examples."""
        template = self.prompt_registry.get(task="generate_code")
        
        prompts = template.render(
            domain=self.domain.replace("_", " ").title(),
            code_topics=", ".join(content.code_topics),
            title=content.metadata.title,
            source=content.metadata.source,
            code_topics_list=content.code_topics,
            content_excerpt=content.content_excerpt,
        )
        
        return self.llm.chat([
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": prompts["user"]},
        ], max_tokens=4000, temperature=0.3)
    
    def _publish_to_github(
        self, 
        content: ProcessedContent, 
        notes: str, 
        code: Optional[str]
    ) -> Dict[str, str]:
        """Publish outputs to GitHub repository."""
        if not self.github_config:
            return {}
        
        token = self.github_config.get("token")
        repo = self.github_config.get("repo")
        
        if not token or not repo:
            print("   [!] GitHub credentials not configured")
            return {}
        
        urls = {}
        date_str = datetime.now().strftime("%Y%m%d")
        slug = self._slugify(content.metadata.title)
        
        # Push notes
        md_filename = f"{slug}.md"
        md_url = self._github_push(
            token, repo, self.docs_folder, md_filename, notes,
            f"notes: add {content.metadata.title} ({date_str})"
        )
        urls["notes"] = md_url
        print(f"   [OK] Notes: {md_url}")
        
        # Push code if exists
        if code:
            py_filename = f"{slug}.py"
            py_url = self._github_push(
                token, repo, self.examples_folder, py_filename, code,
                f"code: add {content.metadata.title} examples ({date_str})"
            )
            urls["code"] = py_url
            print(f"   [OK] Code: {py_url}")
        
        return urls
    
    def _github_push(
        self, 
        token: str, 
        repo: str, 
        folder: str, 
        filename: str, 
        content: str, 
        message: str
    ) -> str:
        """Push a file to GitHub repository."""
        encoded = base64.b64encode(content.encode()).decode()
        path = f"{folder}/{filename}"
        api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        
        # Check if file exists
        sha = None
        try:
            existing = requests.get(api_url, headers=headers, timeout=10)
            if existing.status_code == 200:
                sha = existing.json().get("sha")
        except:
            pass
        
        payload = {
            "message": message,
            "content": encoded,
        }
        if sha:
            payload["sha"] = sha
        
        response = requests.put(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        return response.json()["content"]["html_url"]
    
    def _slugify(self, text: str) -> str:
        """Convert text to safe filename."""
        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_-]+", "_", slug)
        return slug[:60]
