"""PII Configuration Loader.

Loads pii_config.yaml and provides pattern matching for field names
to determine which fields contain PII and how to handle them.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# Default path to pii_config.yaml
DEFAULT_CONFIG_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "extraction"
    / "specs"
    / "pii_config.yaml"
)


@dataclass
class PIICategory:
    """A category of PII fields with matching patterns."""

    name: str
    description: str
    vault: bool
    redaction_strategy: Literal["reference", "mask", "hash"]
    patterns: List[re.Pattern]

    def matches(self, field_name: str, case_insensitive: bool = True) -> bool:
        """Check if a field name matches this category."""
        test_name = field_name.lower() if case_insensitive else field_name
        return any(p.search(test_name) for p in self.patterns)


@dataclass
class PIIExclusion:
    """An explicit exclusion from PII vaulting."""

    pattern: re.Pattern
    reason: str


@dataclass
class DocTypeOverride:
    """Override for a specific field in a doc type."""

    field_name: str
    vault: bool
    reason: str


@dataclass
class PIIConfig:
    """Parsed PII configuration."""

    schema_version: str
    categories: Dict[str, PIICategory]
    exclusions: List[PIIExclusion]
    doc_type_overrides: Dict[str, Dict[str, DocTypeOverride]]
    default_vault: bool
    log_vault_operations: bool
    strict_matching: bool
    case_insensitive: bool

    def should_vault_field(
        self, field_name: str, doc_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Determine if a field should be vaulted.

        Args:
            field_name: The field name to check.
            doc_type: Optional document type for doc-specific overrides.

        Returns:
            Tuple of (should_vault, pii_category, redaction_strategy).
            If should_vault is False, category and strategy will be None.
        """
        test_name = field_name.lower() if self.case_insensitive else field_name

        # Check doc-type specific overrides first
        if doc_type and doc_type in self.doc_type_overrides:
            overrides = self.doc_type_overrides[doc_type]
            if field_name in overrides or test_name in overrides:
                override = overrides.get(field_name) or overrides.get(test_name)
                if override:
                    if override.vault:
                        # Find matching category for strategy
                        for cat_name, cat in self.categories.items():
                            if cat.matches(field_name, self.case_insensitive):
                                return (True, cat_name, cat.redaction_strategy)
                        return (True, "override", "reference")
                    else:
                        return (False, None, None)

        # Check exclusions (takes precedence over category matches)
        for exclusion in self.exclusions:
            if exclusion.pattern.search(test_name):
                if self.log_vault_operations:
                    logger.debug(
                        f"Field '{field_name}' excluded from vault: {exclusion.reason}"
                    )
                return (False, None, None)

        # Check categories
        for cat_name, category in self.categories.items():
            if category.matches(field_name, self.case_insensitive):
                if category.vault:
                    if self.log_vault_operations:
                        logger.debug(
                            f"Field '{field_name}' matched category '{cat_name}' - will vault"
                        )
                    return (True, cat_name, category.redaction_strategy)
                else:
                    return (False, None, None)

        # Default behavior
        return (self.default_vault, None, "reference" if self.default_vault else None)


class PIIConfigLoader:
    """Loader for PII configuration from YAML."""

    _cached_config: Optional[PIIConfig] = None
    _cache_path: Optional[Path] = None

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> PIIConfig:
        """Load PII configuration from YAML file.

        Args:
            config_path: Path to pii_config.yaml. Uses default if not specified.

        Returns:
            Parsed PIIConfig object.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            ValueError: If config is invalid.
        """
        path = config_path or DEFAULT_CONFIG_PATH

        # Return cached config if same path
        if cls._cached_config is not None and cls._cache_path == path:
            return cls._cached_config

        if not path.exists():
            raise FileNotFoundError(f"PII config not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        config = cls._parse_config(raw)

        # Cache the config
        cls._cached_config = config
        cls._cache_path = path

        return config

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the cached configuration."""
        cls._cached_config = None
        cls._cache_path = None

    @classmethod
    def _parse_config(cls, raw: Dict) -> PIIConfig:
        """Parse raw YAML dict into PIIConfig.

        Args:
            raw: Raw YAML dictionary.

        Returns:
            Parsed PIIConfig.

        Raises:
            ValueError: If config is invalid.
        """
        # Parse settings
        settings = raw.get("settings", {})
        case_insensitive = settings.get("case_insensitive", True)
        flags = re.IGNORECASE if case_insensitive else 0

        # Parse categories
        categories = {}
        for cat_name, cat_data in raw.get("categories", {}).items():
            patterns = []
            for pattern_str in cat_data.get("field_patterns", []):
                try:
                    patterns.append(re.compile(pattern_str, flags))
                except re.error as e:
                    raise ValueError(
                        f"Invalid regex in category '{cat_name}': {pattern_str}: {e}"
                    )

            categories[cat_name] = PIICategory(
                name=cat_name,
                description=cat_data.get("description", ""),
                vault=cat_data.get("vault", True),
                redaction_strategy=cat_data.get("redaction_strategy", "reference"),
                patterns=patterns,
            )

        # Parse exclusions
        exclusions = []
        for excl_data in raw.get("exclusions", []):
            pattern_str = excl_data.get("pattern", "")
            try:
                pattern = re.compile(pattern_str, flags)
            except re.error as e:
                raise ValueError(f"Invalid regex in exclusion: {pattern_str}: {e}")

            exclusions.append(
                PIIExclusion(
                    pattern=pattern,
                    reason=excl_data.get("reason", ""),
                )
            )

        # Parse doc-type overrides
        doc_type_overrides: Dict[str, Dict[str, DocTypeOverride]] = {}
        for doc_type, fields in raw.get("doc_type_overrides", {}).items():
            doc_type_overrides[doc_type] = {}
            for field_name, field_data in fields.items():
                doc_type_overrides[doc_type][field_name] = DocTypeOverride(
                    field_name=field_name,
                    vault=field_data.get("vault", True),
                    reason=field_data.get("reason", ""),
                )

        return PIIConfig(
            schema_version=raw.get("schema_version", "1.0"),
            categories=categories,
            exclusions=exclusions,
            doc_type_overrides=doc_type_overrides,
            default_vault=settings.get("default_vault", False),
            log_vault_operations=settings.get("log_vault_operations", True),
            strict_matching=settings.get("strict_matching", True),
            case_insensitive=case_insensitive,
        )
