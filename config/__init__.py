"""Configuration management for Notes Agent."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_config(config_name: str = "default", config_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_name: Name of config file (without .yaml extension)
        config_dir: Directory containing config files (default: this directory)
        
    Returns:
        Configuration dictionary
    """
    if config_dir is None:
        config_dir = Path(__file__).parent
    
    config_file = config_dir / f"{config_name}.yaml"
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Override with environment variables
    config = _apply_env_overrides(config)
    
    return config


def _apply_env_overrides(config: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Apply environment variable overrides to config."""
    result = config.copy()
    
    for key, value in config.items():
        env_key = f"{prefix}{key.upper()}" if prefix else key.upper()
        
        if isinstance(value, dict):
            result[key] = _apply_env_overrides(value, f"{env_key}_")
        else:
            env_value = os.getenv(env_key)
            if env_value is not None:
                # Try to parse as JSON for complex types
                try:
                    import json
                    result[key] = json.loads(env_value)
                except json.JSONDecodeError:
                    result[key] = env_value
    
    return result


def get_config_with_env(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge config with environment variables.
    
    Environment variables take precedence over config file values.
    Format: SECTION_KEY (e.g., LLM_PROVIDER, GITHUB_TOKEN)
    """
    # Load from environment
    env_mapping = {
        "llm.provider": "LLM_PROVIDER",
        "llm.model": "LLM_MODEL",
        "github.token": "GITHUB_TOKEN",
        "github.repo": "GITHUB_REPO",
    }
    
    result = config.copy()
    
    for path, env_var in env_mapping.items():
        value = os.getenv(env_var)
        if value:
            keys = path.split(".")
            target = result
            for key in keys[:-1]:
                target = target.setdefault(key, {})
            target[keys[-1]] = value
    
    return result


# Available configurations
AVAILABLE_CONFIGS = ["default", "machine_learning"]
