"""Utility for loading and rendering prompt templates from markdown files."""

import logging
from pathlib import Path
from typing import Dict, Any

import frontmatter
from jinja2 import Template

logger = logging.getLogger(__name__)

# Point to prompts directory relative to this file
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


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
    prompt_path = PROMPTS_DIR / f"{prompt_name}.md"

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path}. "
            f"Expected location: {PROMPTS_DIR}"
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
