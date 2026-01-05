"""Load and parse DocType specification YAML files."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any
import yaml


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


def load_spec(doc_type: str, version: str = "v0") -> DocTypeSpec:
    """
    Load a DocTypeSpec from YAML file.

    Args:
        doc_type: Document type name (e.g., 'loss_notice')
        version: Spec version (default 'v0')

    Returns:
        DocTypeSpec loaded from YAML

    Raises:
        FileNotFoundError: If spec file doesn't exist
        ValueError: If spec file is invalid
    """
    # Find specs directory relative to this file
    specs_dir = Path(__file__).parent / "specs"
    spec_file = specs_dir / f"{doc_type}_{version}.yaml"

    if not spec_file.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_file}")

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


def list_available_specs() -> List[str]:
    """List all available doc type specs."""
    specs_dir = Path(__file__).parent / "specs"
    if not specs_dir.exists():
        return []

    specs = []
    for spec_file in specs_dir.glob("*_v*.yaml"):
        # Extract doc_type from filename (e.g., loss_notice_v0.yaml -> loss_notice)
        name = spec_file.stem
        if "_v" in name:
            doc_type = name.rsplit("_v", 1)[0]
            if doc_type not in specs:
                specs.append(doc_type)

    return sorted(specs)


# Cache loaded specs for performance
_spec_cache: Dict[str, DocTypeSpec] = {}


def get_spec(doc_type: str, version: str = "v0", use_cache: bool = True) -> DocTypeSpec:
    """
    Get a DocTypeSpec, using cache by default.

    Args:
        doc_type: Document type name
        version: Spec version
        use_cache: Whether to use cached specs

    Returns:
        DocTypeSpec instance
    """
    cache_key = f"{doc_type}_{version}"

    if use_cache and cache_key in _spec_cache:
        return _spec_cache[cache_key]

    spec = load_spec(doc_type, version)

    if use_cache:
        _spec_cache[cache_key] = spec

    return spec


def clear_spec_cache():
    """Clear the spec cache."""
    _spec_cache.clear()
