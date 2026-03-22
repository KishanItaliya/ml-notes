"""
Prompt Template System for configurable, topic-agnostic prompts.
Supports variable substitution and template inheritance.
"""

import json
import re
from typing import Dict, Any, Optional, List
from pathlib import Path


class PromptTemplate:
    """
    A configurable prompt template with variable substitution.
    
    Usage:
        template = PromptTemplate(
            system="You are an expert in {{domain}}.",
            user="Explain {{topic}} to a {{audience}}."
        )
        result = template.render(domain="ML", topic="Gradient Descent", audience="beginner")
    """
    
    def __init__(
        self,
        system: str,
        user: str,
        template_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.system = system
        self.user = user
        self.template_id = template_id or self._generate_id()
        self.metadata = metadata or {}
    
    def _generate_id(self) -> str:
        """Generate a unique template ID from content hash."""
        import hashlib
        content = f"{self.system}:{self.user}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def render(self, **kwargs) -> Dict[str, str]:
        """
        Render the template with variable substitution.
        
        Args:
            **kwargs: Variables to substitute in the template
            
        Returns:
            Dict with 'system' and 'user' keys containing rendered prompts
        """
        system_rendered = self._substitute(self.system, kwargs)
        user_rendered = self._substitute(self.user, kwargs)
        
        return {
            "system": system_rendered,
            "user": user_rendered,
        }
    
    def _substitute(self, template: str, variables: Dict[str, Any]) -> str:
        """Substitute {{variable}} placeholders with values."""
        result = template
        
        # Handle simple variables: {{name}}
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in result:
                # Convert lists to formatted strings
                if isinstance(value, list):
                    formatted = self._format_list(value)
                    result = result.replace(placeholder, formatted)
                else:
                    result = result.replace(placeholder, str(value))
        
        # Handle conditional blocks: {{#if condition}}...{{/if}}
        result = self._process_conditionals(result, variables)
        
        return result
    
    def _format_list(self, items: List[str], bullet: str = "-") -> str:
        """Format a list as a bulleted string."""
        return "\n".join(f"{bullet} {item}" for item in items)
    
    def _process_conditionals(self, template: str, variables: Dict[str, Any]) -> str:
        """Process {{#if var}}...{{/if}} conditional blocks."""
        pattern = r'\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}'
        
        def replace_conditional(match):
            var_name = match.group(1)
            content = match.group(2)
            
            # Check if variable exists and is truthy
            if var_name in variables and variables[var_name]:
                return content
            return ""
        
        return re.sub(pattern, replace_conditional, template, flags=re.DOTALL)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize template to dictionary."""
        return {
            "template_id": self.template_id,
            "system": self.system,
            "user": self.user,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptTemplate":
        """Create template from dictionary."""
        return cls(
            system=data["system"],
            user=data["user"],
            template_id=data.get("template_id"),
            metadata=data.get("metadata", {})
        )
    
    def save(self, filepath: Path):
        """Save template to JSON file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: Path) -> "PromptTemplate":
        """Load template from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


class PromptTemplateRegistry:
    """
    Registry for managing multiple prompt templates.
    Supports loading from directory and template selection by task.
    """
    
    def __init__(self):
        self._templates: Dict[str, PromptTemplate] = {}
        self._task_mappings: Dict[str, str] = {}
    
    def register(self, name: str, template: PromptTemplate, tasks: Optional[List[str]] = None):
        """
        Register a template with optional task associations.
        
        Args:
            name: Unique template identifier
            template: The PromptTemplate instance
            tasks: List of task types this template handles (e.g., ['summarize', 'extract'])
        """
        self._templates[name] = template
        
        if tasks:
            for task in tasks:
                self._task_mappings[task] = name
    
    def get(self, name: Optional[str] = None, task: Optional[str] = None) -> PromptTemplate:
        """
        Get a template by name or task type.
        
        Args:
            name: Template name (exact match)
            task: Task type (looks up mapped template)
            
        Returns:
            PromptTemplate instance
            
        Raises:
            KeyError: If template not found
        """
        if name:
            if name not in self._templates:
                raise KeyError(f"Template '{name}' not found. Available: {list(self._templates.keys())}")
            return self._templates[name]
        
        if task:
            if task not in self._task_mappings:
                raise KeyError(f"No template mapped for task '{task}'")
            return self._templates[self._task_mappings[task]]
        
        raise ValueError("Must provide either 'name' or 'task'")
    
    def load_from_directory(self, directory: Path):
        """Load all templates from a directory."""
        if not directory.exists():
            return
        
        for filepath in directory.glob("*.json"):
            try:
                template = PromptTemplate.load(filepath)
                name = filepath.stem
                self.register(name, template)
            except Exception as e:
                print(f"Warning: Failed to load template {filepath}: {e}")
    
    def list_templates(self) -> List[str]:
        """List all registered template names."""
        return list(self._templates.keys())
    
    def list_tasks(self) -> Dict[str, str]:
        """List task-to-template mappings."""
        return self._task_mappings.copy()


# Pre-built generic templates for common tasks

SUMMARIZE_TEMPLATE = PromptTemplate(
    template_id="generic_summarize",
    system="""
You are an expert {{domain}} educator analyzing educational content.
Extract structured information for creating study materials.

Return ONLY a JSON object with these exact keys:
{
  "topic": "<specific, searchable topic name, 2-5 words>",
  "summary": "<3-4 sentence summary: what, why, key takeaway>",
  "key_concepts": ["<concept 1>", "<concept 2>", ...],
  "prerequisites": ["<prereq 1>", "<prereq 2>", ...],
  "needs_code": true or false,
  "code_topics": ["<implementation topic 1>", ...]
}

GUIDELINES:
- topic: Use standard {{domain}} terminology
- key_concepts: 5-8 specific concepts covered
- prerequisites: 2-4 things needed BEFORE this content
- needs_code: true if algorithms, formulas, or implementations shown
- code_topics: Specific coding tasks

Output valid JSON only, no markdown.
""".strip(),
    user="""
Analyze this {{domain}} educational content:

**Title**: {{title}}
**Source**: {{source}}
**Content Type**: {{content_type}}

**CONTENT**:
{{content}}

Extract structured information as JSON.
""".strip(),
    metadata={"domain": "generic", "tasks": ["summarize", "extract"]}
)


GENERATE_NOTES_TEMPLATE = PromptTemplate(
    template_id="generic_notes",
    system="""
You are writing technical blog posts for developers. Style: concise, practical, no fluff.

STRUCTURE:
# {{topic}}

> One-line hook explaining what this is and why care.

## The simplest way to think about it

2-3 sentences + ASCII diagram if it helps visualize.

```
Example:
Parent Concept
└── This Topic
└── Sub-concept
```

## What it is

### Definition
Clear, one-paragraph explanation. No buzzwords.

### Key point
The one thing to remember.

### Example
Concrete, real-world example (not foo/bar).

| What it needs | How it works |
| --- | --- |
| Requirement | Mechanism |

## How it works (if applicable)

1. Step one
2. Step two  
3. Step three

```python
# Minimal code example
```

## When to use / When to avoid

| Use this | Don't use this |
| --- | --- |
| Scenario | Scenario |

## Real-world examples

| Product/Use case | Why this fits |
| --- | --- |
| Example | Explanation |

## The honest limitations / Gotchas

| Limitation | What to do |
| --- | --- |
| Problem | Solution/workaround |

## TL;DR

- Bullet 1
- Bullet 2
- Bullet 3

## You might also like

- [Related topic 1](#)
- [Related topic 2](#)

STYLE RULES:
- NO mermaid diagrams (use ASCII art only)
- NO "essentially", "basically", "in order to"
- Use > for key quotes/hooks
- Use tables for comparisons (3-4 columns max)
- Code blocks: show real examples, not pseudocode
- Bold key terms once
- Keep paragraphs short (2-3 sentences)
- Add emoji sparingly (🚀 💡 ⚠️) for visual breaks
""".strip(),
    user="""
Write a blog post about: {{topic}}

**Source**: {{title}} by {{source}}
**Date**: {{date}}

**Key Concepts to cover**:
{{key_concepts}}

**Core idea**:
{{summary}}

**Details from source**:
{{content_excerpt}}

**Industry context**:
{{research}}

Target: Developers who want practical understanding, not academic deep-dive.
""".strip(),
    metadata={"domain": "generic", "tasks": ["generate_notes"]}
)


GENERATE_CODE_TEMPLATE = PromptTemplate(
    template_id="generic_code",
    system='''
You are a senior {{domain}} engineer creating production-ready educational code.
Write code that teaches through implementation.

CODE STYLE:
- Clean, readable Python (3.10+)
- Type hints on function signatures
- Docstrings: what it does, args, returns
- Comments only for non-obvious logic
- Real variable names (not x, y, z)

STRUCTURE:
```python
"""
One-liner what this does.
"""

import numpy as np
from sklearn import something

def main_function(data: np.ndarray) -> result:
    """
    What this does.
    
    Args:
        data: Description
        
    Returns:
        Description
    """
    # Implementation
    return result

if __name__ == "__main__":
    # Runnable example with real data
    pass
```

RULES:
- Use standard libraries (numpy, pandas, sklearn, torch)
- Skip from-scratch implementations unless educational
- No visualization unless essential
- Keep it under 100 lines if possible

Output valid Python only, no markdown fences.
'''.strip(),
    user='''
Generate Python code for: {{code_topics}}

**From**: {{title}} by {{source}}

**Implement these**:
{{code_topics_list}}

**Key details**:
{{content_excerpt}}

Write clean, working code with one runnable example.
'''.strip(),
    metadata={"domain": "generic", "tasks": ["generate_code"]}
)


# Create default registry with generic templates
def create_default_registry() -> PromptTemplateRegistry:
    """Create a registry with default generic templates."""
    registry = PromptTemplateRegistry()
    
    registry.register("summarize", SUMMARIZE_TEMPLATE, tasks=["summarize", "extract"])
    registry.register("generate_notes", GENERATE_NOTES_TEMPLATE, tasks=["generate_notes"])
    registry.register("generate_code", GENERATE_CODE_TEMPLATE, tasks=["generate_code"])
    
    return registry
