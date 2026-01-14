"""Service for managing prompt configurations.

Includes compliance features:
- Append-only change history for audit trails
- Version tracking for config changes
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PromptConfig:
    """Prompt configuration for extraction."""

    id: str
    name: str
    model: str = "gpt-4o"
    temperature: float = 0.2
    max_tokens: int = 4096
    is_default: bool = False
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.utcnow().isoformat() + "Z"
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


class PromptConfigService:
    """Service for CRUD operations on prompt configurations.

    Compliance features:
    - Append-only history log for all config changes
    - Change tracking with timestamps and action types
    """

    def __init__(self, config_dir: Path):
        """
        Initialize the prompt config service.

        Args:
            config_dir: Directory to store config files (e.g., output/config/)
        """
        self.config_dir = config_dir
        self.config_file = config_dir / "prompt_configs.json"
        self.history_file = config_dir / "prompt_configs_history.jsonl"
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        """Ensure default configurations exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.config_file.exists():
            # Create default configs
            defaults = [
                PromptConfig(
                    id="generic_extraction_v1",
                    name="generic_extraction_v1",
                    model="gpt-4o",
                    temperature=0.2,
                    max_tokens=4096,
                    is_default=True,
                ),
                PromptConfig(
                    id="fast_extraction_v1",
                    name="fast_extraction_v1",
                    model="gpt-4o-mini",
                    temperature=0.1,
                    max_tokens=2048,
                    is_default=False,
                ),
            ]
            self._save_all(defaults, action="init", changed_config_id=None)
            logger.info(f"Created default prompt configs at {self.config_file}")

    def _load_all(self) -> List[PromptConfig]:
        """Load all configs from disk."""
        if not self.config_file.exists():
            return []

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [PromptConfig(**item) for item in data]
        except Exception as e:
            logger.error(f"Failed to load prompt configs: {e}")
            return []

    def _save_all(
        self,
        configs: List[PromptConfig],
        action: str = "update",
        changed_config_id: Optional[str] = None,
    ) -> None:
        """Save all configs to disk with history logging."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump([asdict(c) for c in configs], f, indent=2)

            # Log to history for compliance (append-only)
            self._log_change(action, changed_config_id, configs)
        except Exception as e:
            logger.error(f"Failed to save prompt configs: {e}")
            raise

    def _log_change(
        self,
        action: str,
        config_id: Optional[str],
        configs: List[PromptConfig],
    ) -> None:
        """Append change entry to history log (append-only for compliance)."""
        try:
            entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": action,
                "config_id": config_id,
                "snapshot": [asdict(c) for c in configs],
            }
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except IOError as exc:
            logger.warning(f"Failed to log config change: {exc}")

    def get_config_history(self) -> List[Dict[str, Any]]:
        """Get all historical config changes (oldest to newest)."""
        if not self.history_file.exists():
            return []

        history = []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        history.append(json.loads(line))
        except (json.JSONDecodeError, IOError) as exc:
            logger.warning(f"Failed to load config history: {exc}")

        return history

    def list_configs(self) -> List[PromptConfig]:
        """List all prompt configurations."""
        return self._load_all()

    def get_config(self, config_id: str) -> Optional[PromptConfig]:
        """Get a single config by ID."""
        configs = self._load_all()
        for config in configs:
            if config.id == config_id:
                return config
        return None

    def get_default(self) -> Optional[PromptConfig]:
        """Get the default configuration."""
        configs = self._load_all()
        for config in configs:
            if config.is_default:
                return config
        # Return first config if no default set
        return configs[0] if configs else None

    def create_config(
        self,
        name: str,
        model: str = "gpt-4o",
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> PromptConfig:
        """Create a new configuration."""
        configs = self._load_all()

        # Generate ID from name (slugified)
        config_id = name.lower().replace(" ", "_").replace("-", "_")

        # Ensure unique ID
        existing_ids = {c.id for c in configs}
        if config_id in existing_ids:
            counter = 1
            while f"{config_id}_{counter}" in existing_ids:
                counter += 1
            config_id = f"{config_id}_{counter}"

        config = PromptConfig(
            id=config_id,
            name=name,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            is_default=False,
        )

        configs.append(config)
        self._save_all(configs, action="create", changed_config_id=config_id)
        logger.info(f"Created prompt config: {config_id}")
        return config

    def update_config(
        self,
        config_id: str,
        updates: Dict[str, Any],
    ) -> Optional[PromptConfig]:
        """Update an existing configuration."""
        configs = self._load_all()

        for i, config in enumerate(configs):
            if config.id == config_id:
                # Apply updates
                if "name" in updates:
                    config.name = updates["name"]
                if "model" in updates:
                    config.model = updates["model"]
                if "temperature" in updates:
                    config.temperature = updates["temperature"]
                if "max_tokens" in updates:
                    config.max_tokens = updates["max_tokens"]

                config.updated_at = datetime.utcnow().isoformat() + "Z"
                configs[i] = config
                self._save_all(configs, action="update", changed_config_id=config_id)
                logger.info(f"Updated prompt config: {config_id}")
                return config

        return None

    def delete_config(self, config_id: str) -> bool:
        """Delete a configuration."""
        configs = self._load_all()

        # Find and remove
        new_configs = [c for c in configs if c.id != config_id]

        if len(new_configs) == len(configs):
            return False  # Not found

        # Don't allow deleting the last config
        if len(new_configs) == 0:
            logger.warning("Cannot delete the last prompt config")
            return False

        # If we deleted the default, make first remaining config default
        if not any(c.is_default for c in new_configs):
            new_configs[0].is_default = True
            new_configs[0].updated_at = datetime.utcnow().isoformat() + "Z"

        self._save_all(new_configs, action="delete", changed_config_id=config_id)
        logger.info(f"Deleted prompt config: {config_id}")
        return True

    def set_default(self, config_id: str) -> Optional[PromptConfig]:
        """Set a configuration as the default."""
        configs = self._load_all()

        found_config = None
        for config in configs:
            if config.id == config_id:
                config.is_default = True
                config.updated_at = datetime.utcnow().isoformat() + "Z"
                found_config = config
            else:
                config.is_default = False

        if found_config:
            self._save_all(configs, action="set_default", changed_config_id=config_id)
            logger.info(f"Set default prompt config: {config_id}")
            return found_config

        return None
