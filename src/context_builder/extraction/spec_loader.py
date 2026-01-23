"""Load and parse DocType specification YAML files."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any
import yaml

from context_builder.storage.workspace_paths import get_workspace_config_dir

logger = logging.getLogger(__name__)

# Repo default specs directory
SPECS_DIR = Path(__file__).parent / "specs"


@dataclass
class FieldRule:
    """Rules for extracting and validating a single field."""
    name: str
    normalize: str = "uppercase_trim"
    validate: str = "non_empty"
    hints: List[str] = field(default_factory=list)


@dataclass
class QualityGateRules:
    """Quality gate evaluation rules."""
    pass_if: List[str] = field(default_factory=list)
    warn_if: List[str] = field(default_factory=list)
    fail_if: List[str] = field(default_factory=list)


@dataclass
class DocTypeSpec:
    """Specification for extracting fields from a document type."""
    doc_type: str
    version: str
    required_fields: List[str]
    optional_fields: List[str]
    field_rules: Dict[str, FieldRule]
    quality_gate: QualityGateRules

    @property
    def all_fields(self) -> List[str]:
        """Get all field names (required + optional)."""
        return self.required_fields + self.optional_fields

    @property
    def all_hints(self) -> List[str]:
        """Get all hint keywords across all fields."""
        hints = []
        for rule in self.field_rules.values():
            hints.extend(rule.hints)
        return hints

    def get_field_hints(self, field_name: str) -> List[str]:
        """Get hints for a specific field."""
        if field_name in self.field_rules:
            return self.field_rules[field_name].hints
        return []

    def is_required(self, field_name: str) -> bool:
        """Check if a field is required."""
        return field_name in self.required_fields


def _resolve_spec_path(doc_type: str, version: str = None) -> Optional[Path]:
    """Resolve spec file path with workspace override support.

    Checks workspace config first, then falls back to repo default.

    Args:
        doc_type: Document type name (e.g., 'fnol_form')
        version: Spec version (optional, for legacy format)

    Returns:
        Path to the spec file, or None if not found
    """
    # Check workspace config first
    workspace_config = get_workspace_config_dir()
    workspace_specs = workspace_config / "extraction_specs"

    # Try workspace new format: {doc_type}.yaml
    workspace_spec = workspace_specs / f"{doc_type}.yaml"
    if workspace_spec.exists():
        logger.debug(f"Using workspace spec override: {workspace_spec}")
        return workspace_spec

    # Try workspace legacy format: {doc_type}_{version}.yaml
    ver = version or "v0"
    workspace_legacy = workspace_specs / f"{doc_type}_{ver}.yaml"
    if workspace_legacy.exists():
        logger.debug(f"Using workspace spec override (legacy): {workspace_legacy}")
        return workspace_legacy

    # Fall back to repo default - new format
    repo_spec = SPECS_DIR / f"{doc_type}.yaml"
    if repo_spec.exists():
        logger.debug(f"Using repo default spec: {repo_spec}")
        return repo_spec

    # Fall back to repo default - legacy format
    repo_legacy = SPECS_DIR / f"{doc_type}_{ver}.yaml"
    if repo_legacy.exists():
        logger.debug(f"Using repo default spec (legacy): {repo_legacy}")
        return repo_legacy

    return None


def load_spec(doc_type: str, version: str = None) -> DocTypeSpec:
    """
    Load a DocTypeSpec from YAML file.

    Supports two naming conventions:
    1. New format: {doc_type}.yaml (version in metadata)
    2. Legacy format: {doc_type}_{version}.yaml

    Checks workspace config first, then falls back to repo default.

    Args:
        doc_type: Document type name (e.g., 'fnol_form')
        version: Spec version (optional, ignored for new format)

    Returns:
        DocTypeSpec loaded from YAML

    Raises:
        FileNotFoundError: If spec file doesn't exist
        ValueError: If spec file is invalid
    """
    spec_file = _resolve_spec_path(doc_type, version)

    if spec_file is None:
        raise FileNotFoundError(
            f"Spec file not found for doc_type: {doc_type}. "
            f"Checked workspace config and repo default at: {SPECS_DIR}"
        )

    with open(spec_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return _parse_spec(data)


def _parse_spec(data: Dict[str, Any]) -> DocTypeSpec:
    """Parse raw YAML data into DocTypeSpec."""
    # Parse field rules
    field_rules = {}
    raw_rules = data.get("field_rules", {})
    for field_name, rule_data in raw_rules.items():
        field_rules[field_name] = FieldRule(
            name=field_name,
            normalize=rule_data.get("normalize", "uppercase_trim"),
            validate=rule_data.get("validate", "non_empty"),
            hints=rule_data.get("hints", [])
        )

    # Parse quality gate rules
    qg_data = data.get("quality_gate", {})
    quality_gate = QualityGateRules(
        pass_if=qg_data.get("pass_if", []),
        warn_if=qg_data.get("warn_if", []),
        fail_if=qg_data.get("fail_if", [])
    )

    return DocTypeSpec(
        doc_type=data.get("doc_type", "unknown"),
        version=data.get("version", "v0"),
        required_fields=data.get("required_fields", []),
        optional_fields=data.get("optional_fields", []),
        field_rules=field_rules,
        quality_gate=quality_gate
    )


def _collect_specs_from_dir(specs_dir: Path) -> set:
    """Collect spec names from a directory."""
    specs = set()
    if not specs_dir.exists():
        return specs

    # New format: {doc_type}.yaml (exclude special files like doc_type_catalog.yaml)
    for spec_file in specs_dir.glob("*.yaml"):
        name = spec_file.stem
        # Skip catalog, pii_config, and other non-spec files
        if name in ("doc_type_catalog", "pii_config") or "_v" in name:
            continue
        # Verify it's a valid spec by checking for doc_type key
        try:
            with open(spec_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data and "doc_type" in data:
                specs.add(name)
        except Exception:
            pass

    # Legacy format: {doc_type}_{version}.yaml
    for spec_file in specs_dir.glob("*_v*.yaml"):
        name = spec_file.stem
        if "_v" in name:
            doc_type = name.rsplit("_v", 1)[0]
            specs.add(doc_type)

    return specs


def list_available_specs() -> List[str]:
    """List all available doc type specs.

    Returns union of workspace config and repo default specs.
    Workspace overrides take precedence when loading.
    """
    specs = set()

    # Collect from repo default
    specs.update(_collect_specs_from_dir(SPECS_DIR))

    # Collect from workspace config (adds any additional specs)
    workspace_config = get_workspace_config_dir()
    workspace_specs = workspace_config / "extraction_specs"
    specs.update(_collect_specs_from_dir(workspace_specs))

    return sorted(specs)


# Cache loaded specs for performance
_spec_cache: Dict[str, DocTypeSpec] = {}


def get_spec(doc_type: str, version: str = None, use_cache: bool = True) -> DocTypeSpec:
    """
    Get a DocTypeSpec, using cache by default.

    Args:
        doc_type: Document type name
        version: Spec version (optional, for legacy format)
        use_cache: Whether to use cached specs

    Returns:
        DocTypeSpec instance
    """
    cache_key = doc_type

    if use_cache and cache_key in _spec_cache:
        return _spec_cache[cache_key]

    spec = load_spec(doc_type, version)

    if use_cache:
        _spec_cache[cache_key] = spec

    return spec


def clear_spec_cache():
    """Clear the spec cache."""
    _spec_cache.clear()
