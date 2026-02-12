"""Processing stage for claim-level pipeline.

This stage applies business logic to reconciled claim facts. Processing types
are auto-discovered from the workspace config directory.

Supported processing types (auto-discovered from {workspace}/config/processing/):
- assessment: Claim assessment and decision making
- payout: Payout calculation (future)
- fraud: Fraud detection (future)

Each processing type has its own config and prompt in the workspace:
    {workspace}/config/processing/{type}/
        ├── config.yaml     # Processing configuration
        └── prompt.md       # LLM prompt with version in frontmatter
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

import yaml

from context_builder.pipeline.claim_stages.context import ClaimContext

logger = logging.getLogger(__name__)


@dataclass
class ProcessorConfig:
    """Configuration for a processing type."""

    type: str
    version: str
    model: str = "gpt-4o"
    temperature: float = 0.2
    max_tokens: int = 4096
    prompt_file: str = "prompt.md"
    prompt_content: Optional[str] = None
    prompt_version: Optional[str] = None  # From frontmatter
    config_path: Optional[Path] = None


class Processor(Protocol):
    """Protocol for processing implementations.

    Each processing type (assessment, payout, etc.) implements this protocol.
    """

    processor_type: str

    def process(
        self,
        context: ClaimContext,
        config: ProcessorConfig,
        on_token_update: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """Execute the processing logic.

        Args:
            context: The claim context with aggregated facts.
            config: The processor configuration.
            on_token_update: Optional callback for token streaming updates.

        Returns:
            Processing result dictionary.
        """
        ...


# Registry of processor implementations
_PROCESSOR_REGISTRY: Dict[str, Processor] = {}


def register_processor(processor_type: str, processor: Processor) -> None:
    """Register a processor implementation.

    Args:
        processor_type: The type name (e.g., "assessment").
        processor: The processor implementation.
    """
    _PROCESSOR_REGISTRY[processor_type] = processor
    logger.info(f"Registered processor: {processor_type}")


def get_processor(processor_type: str) -> Optional[Processor]:
    """Get a registered processor by type.

    Args:
        processor_type: The type name.

    Returns:
        The processor implementation, or None if not found.
    """
    return _PROCESSOR_REGISTRY.get(processor_type)


@dataclass
class ProcessingStage:
    """Processing stage: apply business logic to reconciled facts.

    Auto-discovers processor configurations from workspace config directory.
    Delegates to registered processor implementations for actual processing.
    """

    name: str = "processing"
    _discovered_configs: Dict[str, ProcessorConfig] = field(default_factory=dict)

    def run(self, context: ClaimContext) -> ClaimContext:
        """Execute processing and return updated context.

        Args:
            context: The claim context with aggregated_facts loaded.

        Returns:
            Updated context with processing_result set.
        """
        context.current_stage = self.name
        context.notify_stage_update(self.name, "running")
        start = time.time()

        if not context.stage_config.run_processing:
            logger.info(f"Processing skipped for claim {context.claim_id}")
            context.notify_stage_update(self.name, "skipped")
            context.timings.processing_ms = 0
            return context

        processing_type = context.stage_config.processing_type
        logger.info(
            f"Running processing type '{processing_type}' for claim {context.claim_id}"
        )

        try:
            # Discover available processors
            self._discover_processors(context.workspace_path)

            # Get config for requested processing type
            config = self._discovered_configs.get(processing_type)
            if not config:
                raise ValueError(
                    f"Processing type '{processing_type}' not found. "
                    f"Available: {list(self._discovered_configs.keys())}"
                )

            # Store version info in context
            context.prompt_version = config.prompt_version
            context.processing_type = processing_type

            # Get processor implementation
            processor = get_processor(processing_type)
            if not processor:
                raise ValueError(
                    f"No processor implementation registered for '{processing_type}'. "
                    f"Registered processors: {list(_PROCESSOR_REGISTRY.keys())}"
                )

            # Execute processing
            result = processor.process(
                context=context,
                config=config,
                on_token_update=context.on_token_update,
            )

            context.processing_result = result
            context.notify_stage_update(self.name, "complete")
            logger.info(f"Processing complete for claim {context.claim_id}")

        except Exception as e:
            logger.error(f"Processing failed for {context.claim_id}: {e}")
            context.notify_stage_update(self.name, "warning")
            context.status = "error"
            context.error = f"Processing failed: {str(e)}"
            return context

        context.timings.processing_ms = int((time.time() - start) * 1000)
        return context

    def _discover_processors(self, workspace_path: Path) -> None:
        """Discover processor configurations from workspace config directory.

        Scans {workspace}/config/processing/ for subdirectories containing
        either config.yaml or prompt.md files. Supports two patterns:
        1. config.yaml + prompt.md (legacy pattern)
        2. prompt.md only with config in YAML frontmatter (single-file pattern)

        Args:
            workspace_path: Path to the workspace root.
        """
        processing_dir = workspace_path / "config" / "processing"
        if not processing_dir.exists():
            logger.debug(f"No processing config directory at {processing_dir}")
            return

        for subdir in processing_dir.iterdir():
            if not subdir.is_dir():
                continue

            config_file = subdir / "config.yaml"
            prompt_file = subdir / "prompt.md"

            # Skip if neither config.yaml nor prompt.md exists
            if not config_file.exists() and not prompt_file.exists():
                continue

            try:
                config = self._load_processor_config(subdir)
                self._discovered_configs[config.type] = config
                logger.info(
                    f"Discovered processor: {config.type} v{config.version} "
                    f"(prompt v{config.prompt_version})"
                )
            except Exception as e:
                logger.warning(f"Failed to load processor config from {subdir}: {e}")

    def _load_processor_config(self, config_dir: Path) -> ProcessorConfig:
        """Load processor configuration from a directory.

        Supports two patterns:
        1. config.yaml + prompt.md (legacy): Config from YAML file, prompt separate
        2. prompt.md only (single-file): Config extracted from prompt frontmatter

        Args:
            config_dir: Directory containing config.yaml and/or prompt.md

        Returns:
            ProcessorConfig with loaded configuration.
        """
        config_file = config_dir / "config.yaml"
        prompt_file = config_dir / "prompt.md"

        if config_file.exists():
            # Legacy pattern: config.yaml + prompt.md
            with open(config_file, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)

            config = ProcessorConfig(
                type=raw_config.get("type", config_dir.name),
                version=raw_config.get("version", "0.0.0"),
                model=raw_config.get("model", "gpt-4o"),
                temperature=raw_config.get("temperature", 0.2),
                max_tokens=raw_config.get("max_tokens", 4096),
                prompt_file=raw_config.get("prompt_file", "prompt.md"),
                config_path=config_dir,
            )

            # Load prompt content and extract version from frontmatter
            prompt_path = config_dir / config.prompt_file
            if prompt_path.exists():
                config.prompt_content, config.prompt_version = self._load_prompt(
                    prompt_path
                )
            else:
                logger.warning(f"Prompt file not found: {prompt_path}")

        elif prompt_file.exists():
            # Single-file pattern: extract config from prompt frontmatter
            prompt_content, frontmatter = self._load_prompt_with_frontmatter(
                prompt_file
            )

            config = ProcessorConfig(
                type=frontmatter.get("type", config_dir.name),
                version=frontmatter.get("version", "0.0.0"),
                model=frontmatter.get("model", "gpt-4o"),
                temperature=frontmatter.get("temperature", 0.2),
                max_tokens=frontmatter.get("max_tokens", 4096),
                prompt_file="prompt.md",
                prompt_content=prompt_content,
                prompt_version=frontmatter.get("version"),
                config_path=config_dir,
            )
        else:
            raise ValueError(
                f"No config.yaml or prompt.md found in {config_dir}"
            )

        return config

    def _load_prompt(self, prompt_path: Path) -> tuple[Optional[str], Optional[str]]:
        """Load prompt content and extract version from YAML frontmatter.

        Args:
            prompt_path: Path to the prompt markdown file.

        Returns:
            Tuple of (prompt_content, prompt_version).
        """
        prompt_content, frontmatter = self._load_prompt_with_frontmatter(prompt_path)
        prompt_version = frontmatter.get("version") if frontmatter else None
        return prompt_content, prompt_version

    def _load_prompt_with_frontmatter(
        self, prompt_path: Path
    ) -> tuple[Optional[str], Dict[str, Any]]:
        """Load prompt content and full YAML frontmatter.

        Args:
            prompt_path: Path to the prompt markdown file.

        Returns:
            Tuple of (prompt_content, frontmatter_dict).
        """
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter: Dict[str, Any] = {}

        # Parse YAML frontmatter if present
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter_str = parts[1].strip()
                prompt_content = parts[2].strip()

                try:
                    parsed = yaml.safe_load(frontmatter_str)
                    if isinstance(parsed, dict):
                        frontmatter = parsed
                except yaml.YAMLError:
                    prompt_content = content
            else:
                prompt_content = content
        else:
            prompt_content = content

        return prompt_content, frontmatter

    @classmethod
    def list_available_processors(cls, workspace_path: Path) -> List[str]:
        """List available processing types in a workspace.

        Supports both config.yaml and single-file prompt.md patterns.

        Args:
            workspace_path: Path to the workspace root.

        Returns:
            List of available processing type names.
        """
        processing_dir = workspace_path / "config" / "processing"
        if not processing_dir.exists():
            return []

        types = []
        for subdir in processing_dir.iterdir():
            if not subdir.is_dir():
                continue
            # Support both patterns: config.yaml or prompt.md only
            has_config = (subdir / "config.yaml").exists()
            has_prompt = (subdir / "prompt.md").exists()
            if has_config or has_prompt:
                types.append(subdir.name)

        return sorted(types)
