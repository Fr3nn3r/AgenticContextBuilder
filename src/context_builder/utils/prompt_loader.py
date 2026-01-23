"""Utility for loading and rendering prompt templates from markdown files."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

import frontmatter
from jinja2 import Template

from context_builder.storage.workspace_paths import get_workspace_config_dir

logger = logging.getLogger(__name__)

# Point to prompts directory relative to this file (repo default)
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _resolve_prompt_path(prompt_name: str) -> Path:
    """Resolve prompt file path with workspace override support.

    Checks workspace config first, then falls back to repo default.

    Args:
        prompt_name: Name of the prompt file (without .md extension)

    Returns:
        Path to the prompt file (may not exist - caller should check)
    """
    # Check workspace config first
    workspace_config = get_workspace_config_dir()
    workspace_prompt = workspace_config / "prompts" / f"{prompt_name}.md"

    if workspace_prompt.exists():
        logger.debug(f"Using workspace prompt override: {workspace_prompt}")
        return workspace_prompt

    # Fall back to repo default
    repo_prompt = PROMPTS_DIR / f"{prompt_name}.md"
    logger.debug(f"Using repo default prompt: {repo_prompt}")
    return repo_prompt


def load_prompt(prompt_name: str, **kwargs) -> Dict[str, Any]:
    """
    Load a markdown prompt file, parse frontmatter config, and render Jinja2 template.

    This function implements the "Prompts in Markdown" pattern, separating
    prompt content from code logic.

    Args:
        prompt_name: Name of the prompt file (without .md extension)
        **kwargs: Variables to pass to Jinja2 template rendering

    Returns:
        Dictionary with two keys:
            - config: Dictionary of YAML frontmatter configuration
            - messages: List of message dictionaries for OpenAI API

    Raises:
        FileNotFoundError: If prompt file does not exist
        ValueError: If prompt format is invalid

    Example:
        >>> prompt_data = load_prompt("document_analysis", page_number=1, total_pages=5)
        >>> config = prompt_data["config"]
        >>> messages = prompt_data["messages"]
    """
    prompt_path = _resolve_prompt_path(prompt_name)

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path}. "
            f"Checked workspace config and repo default at: {PROMPTS_DIR}"
        )

    logger.debug(f"Loading prompt from: {prompt_path}")

    # Load file and parse frontmatter (YAML config) from markdown body
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            post = frontmatter.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse prompt file {prompt_path}: {e}")

    # Get configuration from YAML frontmatter
    config = post.metadata
    logger.debug(f"Loaded prompt config: {config.get('name', 'unnamed')}")

    # Render the markdown body with Jinja2
    try:
        template = Template(post.content)
        rendered_content = template.render(**kwargs)
    except Exception as e:
        raise ValueError(f"Failed to render Jinja2 template: {e}")

    # Parse the rendered content into system/user messages
    messages = _parse_messages(rendered_content)

    return {
        "config": config,
        "messages": messages,
    }


def _parse_messages(content: str) -> list:
    """
    Parse rendered prompt content into OpenAI message format.

    Expects content with role markers:
        system:
        <system message content>

        user:
        <user message content>

    Args:
        content: Rendered prompt content with role markers

    Returns:
        List of message dictionaries with 'role' and 'content' keys

    Raises:
        ValueError: If content format is invalid
    """
    messages = []
    current_role = None
    current_content = []

    for line in content.split("\n"):
        line_stripped = line.strip()

        # Check for role markers
        if line_stripped == "system:":
            # Save previous message if exists
            if current_role and current_content:
                messages.append({
                    "role": current_role,
                    "content": "\n".join(current_content).strip()
                })
            current_role = "system"
            current_content = []
        elif line_stripped == "user:":
            # Save previous message if exists
            if current_role and current_content:
                messages.append({
                    "role": current_role,
                    "content": "\n".join(current_content).strip()
                })
            current_role = "user"
            current_content = []
        elif current_role:
            # Add content to current message
            current_content.append(line)

    # Add final message
    if current_role and current_content:
        messages.append({
            "role": current_role,
            "content": "\n".join(current_content).strip()
        })

    if not messages:
        raise ValueError(
            "Invalid prompt format. Expected 'system:' and/or 'user:' markers"
        )

    logger.debug(f"Parsed {len(messages)} messages from prompt")
    return messages
