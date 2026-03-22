#!/usr/bin/env python3
"""
Notes Agent - Generic Educational Content Processor

A scalable, topic-agnostic system for processing educational content
and generating study materials (notes + code examples).

Usage:
    # Using default config
    python main.py "https://youtube.com/watch?v=..."
    
    # Using specific domain config
    python main.py --config machine_learning "https://youtube.com/watch?v=..."
    
    # Process text file
    python main.py ./lecture.txt
    
    # With custom LLM provider
    python main.py --provider claude "https://youtube.com/watch?v=..."

Environment Variables:
    GROQ_API_KEY        - Groq API key
    ANTHROPIC_API_KEY   - Anthropic API key
    GITHUB_TOKEN        - GitHub personal access token
    GITHUB_REPO         - Target repo (format: username/repo-name)
"""

import argparse
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env file
from dotenv import load_dotenv
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from core import BaseAgent, LLMProviderFactory
from config import load_config, get_config_with_env


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate study notes from educational content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://youtube.com/watch?v=ZftI2fEz0Fw"
  %(prog)s --config machine_learning "https://youtube.com/watch?v=..."
  %(prog)s --provider claude --output ./notes ./lecture.txt
  %(prog)s --no-github --save-local "https://youtube.com/watch?v=..."
        """
    )
    
    parser.add_argument(
        "source",
        help="Content source (YouTube URL, file path, etc.)"
    )
    
    parser.add_argument(
        "-c", "--config",
        default="default",
        help="Configuration profile to use (default: default)"
    )
    
    parser.add_argument(
        "-p", "--provider",
        choices=LLMProviderFactory.list_providers(),
        help="Override LLM provider from config"
    )
    
    parser.add_argument(
        "-d", "--domain",
        help="Override domain from config (e.g., machine_learning, web_development)"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Save outputs to directory (implies --no-github)"
    )
    
    parser.add_argument(
        "--no-github",
        action="store_true",
        help="Disable GitHub publishing"
    )
    
    parser.add_argument(
        "--no-research",
        action="store_true",
        help="Disable web research step"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process without publishing/saving"
    )
    
    return parser


def build_agent_config(args: argparse.Namespace, config: dict) -> dict:
    """Build agent configuration from args and config file."""
    agent_config = {
        "domain": args.domain or config.get("domain", "generic"),
        "llm_provider": args.provider or config.get("llm", {}).get("provider", "groq"),
        
        # Content settings
        "max_transcript_chars": config.get("content", {}).get("max_transcript_chars", 12000),
        "excerpt_length": config.get("content", {}).get("excerpt_length", 8000),
        "languages": config.get("content", {}).get("languages", ["en"]),
        
        # Research settings
        "research_enabled": not args.no_research and config.get("research", {}).get("enabled", True),
        "research_queries": config.get("research", {}).get("max_queries", 2),
        
        # Output settings
        "docs_folder": config.get("output", {}).get("docs_folder", "docs"),
        "examples_folder": config.get("output", {}).get("examples_folder", "examples"),
        "save_locally": bool(args.output) or config.get("output", {}).get("save_locally", False),
        "local_output_dir": args.output or config.get("output", {}).get("local_output_dir", "./output"),
        
        # GitHub settings
        "github": None if args.no_github else {
            "enabled": config.get("github", {}).get("enabled", False) and not args.no_github,
            "token": config.get("github", {}).get("token"),
            "repo": config.get("github", {}).get("repo"),
        }
    }
    
    return agent_config


def save_outputs_locally(result: dict, output_dir: Path):
    """Save generated outputs to local directory."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    topic = result.get("topic", "untitled")
    safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in topic)
    safe_name = safe_name.replace(' ', '_').lower()[:60]
    
    # Save notes
    if result.get("notes"):
        notes_path = output_dir / f"{safe_name}.md"
        with open(notes_path, 'w', encoding='utf-8') as f:
            f.write(result["notes"])
        print(f"   [SAVED] Notes: {notes_path}")
    
    # Save code
    if result.get("code"):
        code_path = output_dir / f"{safe_name}.py"
        with open(code_path, 'w', encoding='utf-8') as f:
            f.write(result["code"])
        print(f"   [SAVED] Code: {code_path}")
    
    # Save metadata
    meta_path = output_dir / f"{safe_name}_meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(result.get("metadata", {}), f, indent=2, ensure_ascii=False)
    print(f"   [SAVED] Metadata: {meta_path}")


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(args.config)
        config = get_config_with_env(config)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        print(f"        Available configs: default, machine_learning")
        sys.exit(1)
    
    # Build agent configuration
    agent_config = build_agent_config(args, config)
    
    # Override GitHub if output directory specified
    if args.output:
        args.no_github = True
        agent_config["github"] = None
    
    # Validate LLM provider
    provider_name = agent_config["llm_provider"]
    if provider_name not in LLMProviderFactory.list_providers():
        print(f"[ERROR] Unknown LLM provider: {provider_name}")
        print(f"        Available: {LLMProviderFactory.list_providers()}")
        sys.exit(1)
    
    # Create and run agent
    try:
        agent = BaseAgent(
            domain=agent_config["domain"],
            llm_provider=provider_name,
            config=agent_config
        )
        
        result = agent.process(args.source)
        
        # Save locally if requested
        if agent_config.get("save_locally") and not args.dry_run:
            output_dir = Path(agent_config["local_output_dir"])
            save_outputs_locally(result, output_dir)
        
        # Output as JSON if requested
        if args.json:
            # Remove large content for cleaner JSON
            output_result = {
                "domain": result["domain"],
                "topic": result["topic"],
                "urls": result.get("urls", {}),
                "metadata": result.get("metadata", {}),
            }
            print(json.dumps(output_result, indent=2))
        
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
