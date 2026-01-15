"""Unit tests for PII config loader.

Tests:
- Loading config from YAML file
- Pattern matching for field names
- Exclusions handling
- Doc-type overrides
- Cache behavior
"""

from pathlib import Path
from typing import Dict, Any

import pytest

from context_builder.services.compliance.pii.config_loader import (
    PIIConfigLoader,
    PIIConfig,
    PIICategory,
)


@pytest.fixture
def sample_config_yaml(tmp_path: Path) -> Path:
    """Create a sample pii_config.yaml for testing."""
    config_content = """
schema_version: "1.0"

categories:
  names:
    description: "Personal names"
    vault: true
    redaction_strategy: "reference"
    field_patterns:
      - "^full_name$"
      - "^first_name$"
      - "_name$"

  contact:
    description: "Contact information"
    vault: true
    redaction_strategy: "mask"
    field_patterns:
      - "phone"
      - "email"
      - "^address$"

  financial:
    description: "Financial data"
    vault: true
    redaction_strategy: "mask"
    field_patterns:
      - "^account_number$"
      - "^bank_account$"

exclusions:
  - pattern: "^vendor_name$"
    reason: "Business entity"
  - pattern: "^event_date$"
    reason: "Not PII"

doc_type_overrides:
  invoice:
    vendor_name:
      vault: false
      reason: "Business entity on invoice"
  medical_report:
    patient_name:
      vault: true
      reason: "Always PII in medical docs"

settings:
  default_vault: false
  log_vault_operations: true
  strict_matching: true
  case_insensitive: true
"""
    config_path = tmp_path / "pii_config.yaml"
    config_path.write_text(config_content)
    return config_path


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear config cache before each test."""
    PIIConfigLoader.clear_cache()
    yield
    PIIConfigLoader.clear_cache()


class TestPIIConfigLoading:
    """Tests for loading PII configuration."""

    def test_load_from_file(self, sample_config_yaml: Path):
        """Config loads successfully from YAML file."""
        config = PIIConfigLoader.load(sample_config_yaml)
        assert config.schema_version == "1.0"
        assert len(config.categories) == 3
        assert "names" in config.categories
        assert "contact" in config.categories
        assert "financial" in config.categories

    def test_load_missing_file_raises(self, tmp_path: Path):
        """Loading missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            PIIConfigLoader.load(tmp_path / "nonexistent.yaml")

    def test_load_caches_result(self, sample_config_yaml: Path):
        """Repeated loads return cached config."""
        config1 = PIIConfigLoader.load(sample_config_yaml)
        config2 = PIIConfigLoader.load(sample_config_yaml)
        assert config1 is config2

    def test_clear_cache(self, sample_config_yaml: Path):
        """clear_cache resets the cache."""
        config1 = PIIConfigLoader.load(sample_config_yaml)
        PIIConfigLoader.clear_cache()
        config2 = PIIConfigLoader.load(sample_config_yaml)
        assert config1 is not config2


class TestPIIPatternMatching:
    """Tests for field pattern matching."""

    def test_exact_match(self, sample_config_yaml: Path):
        """Exact field name matches pattern."""
        config = PIIConfigLoader.load(sample_config_yaml)
        should_vault, category, strategy = config.should_vault_field("full_name")
        assert should_vault is True
        assert category == "names"
        assert strategy == "reference"

    def test_suffix_match(self, sample_config_yaml: Path):
        """Field ending with _name matches pattern."""
        config = PIIConfigLoader.load(sample_config_yaml)
        should_vault, category, _ = config.should_vault_field("claimant_name")
        assert should_vault is True
        assert category == "names"

    def test_substring_match(self, sample_config_yaml: Path):
        """Field containing pattern matches."""
        config = PIIConfigLoader.load(sample_config_yaml)
        should_vault, category, strategy = config.should_vault_field("home_phone")
        assert should_vault is True
        assert category == "contact"
        assert strategy == "mask"

    def test_case_insensitive_match(self, sample_config_yaml: Path):
        """Matching is case-insensitive by default."""
        config = PIIConfigLoader.load(sample_config_yaml)
        should_vault, _, _ = config.should_vault_field("FULL_NAME")
        assert should_vault is True

    def test_non_matching_field(self, sample_config_yaml: Path):
        """Non-matching field returns default (false)."""
        config = PIIConfigLoader.load(sample_config_yaml)
        should_vault, category, strategy = config.should_vault_field("claim_number")
        assert should_vault is False
        assert category is None
        assert strategy is None


class TestPIIExclusions:
    """Tests for exclusion patterns."""

    def test_exclusion_overrides_category(self, sample_config_yaml: Path):
        """Exclusion pattern prevents vaulting even if category matches."""
        config = PIIConfigLoader.load(sample_config_yaml)
        # vendor_name matches _name pattern but is excluded
        should_vault, _, _ = config.should_vault_field("vendor_name")
        assert should_vault is False

    def test_non_excluded_field_still_vaults(self, sample_config_yaml: Path):
        """Fields not in exclusions are still vaulted if they match."""
        config = PIIConfigLoader.load(sample_config_yaml)
        should_vault, _, _ = config.should_vault_field("owner_name")
        assert should_vault is True


class TestDocTypeOverrides:
    """Tests for document-type-specific overrides."""

    def test_doc_type_override_applies(self, sample_config_yaml: Path):
        """Doc-type override takes precedence."""
        config = PIIConfigLoader.load(sample_config_yaml)
        # vendor_name is overridden to not vault for invoices
        should_vault, _, _ = config.should_vault_field("vendor_name", doc_type="invoice")
        assert should_vault is False

    def test_doc_type_override_force_vault(self, sample_config_yaml: Path):
        """Doc-type override can force vaulting."""
        config = PIIConfigLoader.load(sample_config_yaml)
        should_vault, _, _ = config.should_vault_field("patient_name", doc_type="medical_report")
        assert should_vault is True

    def test_no_override_for_other_doc_types(self, sample_config_yaml: Path):
        """Override only applies to specified doc type."""
        config = PIIConfigLoader.load(sample_config_yaml)
        # vendor_name in non-invoice doc follows normal exclusion
        should_vault, _, _ = config.should_vault_field("vendor_name", doc_type="police_report")
        assert should_vault is False  # Still excluded by global exclusion


class TestPIICategories:
    """Tests for PII category configuration."""

    def test_category_has_correct_strategy(self, sample_config_yaml: Path):
        """Category returns correct redaction strategy."""
        config = PIIConfigLoader.load(sample_config_yaml)

        _, _, strategy = config.should_vault_field("full_name")
        assert strategy == "reference"

        _, _, strategy = config.should_vault_field("email")
        assert strategy == "mask"

    def test_category_has_description(self, sample_config_yaml: Path):
        """Category has description from config."""
        config = PIIConfigLoader.load(sample_config_yaml)
        assert config.categories["names"].description == "Personal names"


class TestInvalidConfig:
    """Tests for invalid configuration handling."""

    def test_invalid_regex_raises(self, tmp_path: Path):
        """Invalid regex pattern raises ValueError."""
        config_content = """
categories:
  bad:
    vault: true
    redaction_strategy: "reference"
    field_patterns:
      - "[invalid"
"""
        config_path = tmp_path / "bad_config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ValueError, match="Invalid regex"):
            PIIConfigLoader.load(config_path)

    def test_missing_categories_ok(self, tmp_path: Path):
        """Config with no categories still loads."""
        config_content = """
schema_version: "1.0"
settings:
  default_vault: false
"""
        config_path = tmp_path / "minimal.yaml"
        config_path.write_text(config_content)

        config = PIIConfigLoader.load(config_path)
        assert len(config.categories) == 0
