"""Unit tests for workspace config override behavior.

Tests the tenant configuration override mechanism where workspace-scoped
config files take precedence over repo defaults.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from context_builder.utils.prompt_loader import load_prompt, _resolve_prompt_path, PROMPTS_DIR
from context_builder.extraction.spec_loader import (
    load_spec,
    list_available_specs,
    clear_spec_cache,
    _resolve_spec_path,
    SPECS_DIR,
)
from context_builder.classification.openai_classifier import (
    load_doc_type_catalog,
    _resolve_catalog_path,
)
from context_builder.config.tenant import (
    TenantConfig,
    IngestionRouteRule,
    load_tenant_config,
    get_tenant_config,
    reset_tenant_config_cache,
    VALID_INGESTION_PROVIDERS,
)


class TestPromptLoaderOverride:
    """Tests for prompt loader workspace override behavior."""

    def test_resolve_prompt_path_uses_workspace_override(self, tmp_path):
        """Test that workspace prompt overrides repo default."""
        # Create workspace config structure
        workspace_prompts = tmp_path / "config" / "prompts"
        workspace_prompts.mkdir(parents=True)

        # Create override prompt
        override_prompt = workspace_prompts / "test_prompt.md"
        override_prompt.write_text("""---
name: Test Override
model: gpt-4o
---
system:
Override system message

user:
Override user message
""")

        with patch("context_builder.utils.prompt_loader.get_workspace_config_dir") as mock_config:
            mock_config.return_value = tmp_path / "config"

            resolved = _resolve_prompt_path("test_prompt")
            assert resolved == override_prompt
            assert "config" in str(resolved)

    def test_resolve_prompt_path_falls_back_to_repo(self, tmp_path):
        """Test that prompt falls back to repo when no workspace override."""
        # Create empty workspace config (no prompts)
        workspace_config = tmp_path / "config"
        workspace_config.mkdir(parents=True)

        with patch("context_builder.utils.prompt_loader.get_workspace_config_dir") as mock_config:
            mock_config.return_value = workspace_config

            # Should fall back to repo default for existing prompt
            resolved = _resolve_prompt_path("claims_document_classification")
            assert resolved == PROMPTS_DIR / "claims_document_classification.md"

    def test_load_prompt_uses_workspace_override(self, tmp_path):
        """Test that load_prompt uses workspace override when available."""
        workspace_prompts = tmp_path / "config" / "prompts"
        workspace_prompts.mkdir(parents=True)

        # Create a valid override prompt with proper format
        override_content = """---
name: Custom Classification
model: gpt-4o-mini
temperature: 0.0
max_tokens: 500
---
system:
You are a custom classifier for tenant X.

user:
Classify this: {{ text_content }}
"""
        override_prompt = workspace_prompts / "custom_classifier.md"
        override_prompt.write_text(override_content)

        with patch("context_builder.utils.prompt_loader.get_workspace_config_dir") as mock_config:
            mock_config.return_value = tmp_path / "config"

            result = load_prompt("custom_classifier", text_content="test document")

            assert result["config"]["name"] == "Custom Classification"
            assert result["config"]["model"] == "gpt-4o-mini"
            assert len(result["messages"]) == 2
            assert "custom classifier for tenant X" in result["messages"][0]["content"]

    def test_load_prompt_falls_back_to_repo_default(self, tmp_path):
        """Test that load_prompt falls back to repo when no override."""
        workspace_config = tmp_path / "config"
        workspace_config.mkdir(parents=True)

        with patch("context_builder.utils.prompt_loader.get_workspace_config_dir") as mock_config:
            mock_config.return_value = workspace_config

            # Should load repo default
            result = load_prompt("claims_document_classification",
                               text_content="test",
                               filename="test.pdf",
                               doc_type_catalog="test catalog")

            # Check that it loaded something from repo (name contains "Classification")
            assert "Classification" in result["config"]["name"]
            assert len(result["messages"]) >= 1


class TestSpecLoaderOverride:
    """Tests for spec loader workspace override behavior."""

    def setup_method(self):
        """Clear spec cache before each test."""
        clear_spec_cache()

    def test_resolve_spec_path_uses_workspace_override(self, tmp_path):
        """Test that workspace spec overrides repo default."""
        workspace_specs = tmp_path / "config" / "extraction_specs"
        workspace_specs.mkdir(parents=True)

        # Create override spec
        override_spec = workspace_specs / "custom_doc.yaml"
        override_spec.write_text("""
doc_type: custom_doc
version: v1
required_fields:
  - field_a
optional_fields:
  - field_b
field_rules: {}
quality_gate: {}
""")

        with patch("context_builder.extraction.spec_loader.get_workspace_config_dir") as mock_config:
            mock_config.return_value = tmp_path / "config"

            resolved = _resolve_spec_path("custom_doc")
            assert resolved == override_spec

    def test_resolve_spec_path_falls_back_to_repo(self, tmp_path):
        """Test that spec falls back to repo when no workspace override."""
        workspace_config = tmp_path / "config"
        workspace_config.mkdir(parents=True)

        with patch("context_builder.extraction.spec_loader.get_workspace_config_dir") as mock_config:
            mock_config.return_value = workspace_config

            resolved = _resolve_spec_path("fnol_form")
            assert resolved == SPECS_DIR / "fnol_form.yaml"

    def test_load_spec_uses_workspace_override(self, tmp_path):
        """Test that load_spec uses workspace override when available."""
        workspace_specs = tmp_path / "config" / "extraction_specs"
        workspace_specs.mkdir(parents=True)

        # Create override spec with custom fields
        override_spec = workspace_specs / "tenant_fnol.yaml"
        override_spec.write_text("""
doc_type: tenant_fnol
version: v1
required_fields:
  - tenant_specific_field
  - custom_id
optional_fields:
  - extra_notes
field_rules:
  tenant_specific_field:
    normalize: uppercase_trim
    validate: non_empty
    hints:
      - tenant field
quality_gate:
  pass_if:
    - tenant_specific_field
""")

        with patch("context_builder.extraction.spec_loader.get_workspace_config_dir") as mock_config:
            mock_config.return_value = tmp_path / "config"

            spec = load_spec("tenant_fnol")

            assert spec.doc_type == "tenant_fnol"
            assert "tenant_specific_field" in spec.required_fields
            assert "custom_id" in spec.required_fields

    def test_list_available_specs_unions_both_locations(self, tmp_path):
        """Test that list_available_specs returns union of workspace and repo specs."""
        workspace_specs = tmp_path / "config" / "extraction_specs"
        workspace_specs.mkdir(parents=True)

        # Create a workspace-only spec
        custom_spec = workspace_specs / "workspace_only_doc.yaml"
        custom_spec.write_text("""
doc_type: workspace_only_doc
version: v1
required_fields:
  - field_x
optional_fields: []
field_rules: {}
quality_gate: {}
""")

        with patch("context_builder.extraction.spec_loader.get_workspace_config_dir") as mock_config:
            mock_config.return_value = tmp_path / "config"

            specs = list_available_specs()

            # Should include both repo specs and workspace-only spec
            assert "fnol_form" in specs  # repo default
            assert "workspace_only_doc" in specs  # workspace only


class TestCatalogOverride:
    """Tests for doc type catalog workspace override behavior."""

    def test_resolve_catalog_path_uses_workspace_override(self, tmp_path):
        """Test that workspace catalog overrides repo default."""
        workspace_specs = tmp_path / "config" / "extraction_specs"
        workspace_specs.mkdir(parents=True)

        # Create override catalog
        override_catalog = workspace_specs / "doc_type_catalog.yaml"
        override_catalog.write_text("""
doc_types:
  - doc_type: tenant_doc_a
    description: Tenant-specific document A
    cues:
      - tenant keyword
""")

        with patch("context_builder.classification.openai_classifier.get_workspace_config_dir") as mock_config:
            mock_config.return_value = tmp_path / "config"

            resolved = _resolve_catalog_path()
            assert resolved == override_catalog

    def test_resolve_catalog_path_returns_none_without_workspace_catalog(self, tmp_path):
        """Test that catalog returns None when no workspace catalog exists."""
        workspace_config = tmp_path / "config"
        workspace_config.mkdir(parents=True)

        with patch("context_builder.classification.openai_classifier.get_workspace_config_dir") as mock_config:
            mock_config.return_value = workspace_config

            resolved = _resolve_catalog_path()
            assert resolved is None

    def test_load_doc_type_catalog_uses_workspace_override(self, tmp_path):
        """Test that load_doc_type_catalog uses workspace override."""
        workspace_specs = tmp_path / "config" / "extraction_specs"
        workspace_specs.mkdir(parents=True)

        # Create override catalog with tenant-specific types
        override_catalog = workspace_specs / "doc_type_catalog.yaml"
        override_catalog.write_text("""
doc_types:
  - doc_type: tenant_claim_form
    description: Tenant-specific claim form
    cues:
      - tenant claim
      - custom form
  - doc_type: tenant_invoice
    description: Tenant invoice format
    cues:
      - tenant invoice
""")

        with patch("context_builder.classification.openai_classifier.get_workspace_config_dir") as mock_config:
            mock_config.return_value = tmp_path / "config"

            doc_types = load_doc_type_catalog()

            assert len(doc_types) == 2
            assert doc_types[0]["doc_type"] == "tenant_claim_form"
            assert doc_types[1]["doc_type"] == "tenant_invoice"


class TestTenantConfig:
    """Tests for tenant configuration loading."""

    def setup_method(self):
        """Reset tenant config cache before each test."""
        reset_tenant_config_cache()

    def test_tenant_config_validation(self):
        """Test TenantConfig validates correctly."""
        config = TenantConfig(
            tenant_id="test-tenant",
            tenant_name="Test Tenant",
            feature_flags={"pii_enabled": True},
        )
        assert config.tenant_id == "test-tenant"
        assert config.is_feature_enabled("pii_enabled") is True
        assert config.is_feature_enabled("unknown_flag") is False

    def test_tenant_config_invalid_id(self):
        """Test TenantConfig rejects invalid tenant_id."""
        with pytest.raises(ValueError):
            TenantConfig(tenant_id="invalid id with spaces")

        with pytest.raises(ValueError):
            TenantConfig(tenant_id="invalid@id")

    def test_tenant_config_provider_check(self):
        """Test is_provider_allowed method."""
        config = TenantConfig(
            tenant_id="test",
            allowed_ingestion_providers=["azure-di", "openai"],
        )
        assert config.is_provider_allowed("azure-di") is True
        assert config.is_provider_allowed("openai") is True
        assert config.is_provider_allowed("other") is False

    def test_tenant_config_no_provider_restriction(self):
        """Test that empty provider list allows all."""
        config = TenantConfig(
            tenant_id="test",
            allowed_ingestion_providers=[],
        )
        assert config.is_provider_allowed("any-provider") is True

    def test_load_tenant_config_from_file(self, tmp_path):
        """Test loading tenant config from YAML file."""
        config_file = tmp_path / "tenant.yaml"
        config_file.write_text("""
tenant_id: acme-insurance
tenant_name: ACME Insurance Corp
feature_flags:
  pii_enabled: true
  strict_quality_gate: false
allowed_ingestion_providers:
  - azure-di
metadata:
  region: us-west
""")

        config = load_tenant_config(config_file)

        assert config is not None
        assert config.tenant_id == "acme-insurance"
        assert config.tenant_name == "ACME Insurance Corp"
        assert config.is_feature_enabled("pii_enabled") is True
        assert config.is_feature_enabled("strict_quality_gate") is False
        assert config.is_provider_allowed("azure-di") is True
        assert config.metadata["region"] == "us-west"

    def test_load_tenant_config_missing_file(self, tmp_path):
        """Test that missing config file returns None."""
        config = load_tenant_config(tmp_path / "nonexistent.yaml")
        assert config is None

    def test_load_tenant_config_invalid_yaml(self, tmp_path):
        """Test that invalid YAML raises ValueError."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [")

        with pytest.raises(ValueError, match="Invalid YAML"):
            load_tenant_config(config_file)

    def test_load_tenant_config_missing_required_field(self, tmp_path):
        """Test that missing required field raises ValueError."""
        config_file = tmp_path / "incomplete.yaml"
        config_file.write_text("""
tenant_name: Missing ID Tenant
""")

        with pytest.raises(ValueError):
            load_tenant_config(config_file)

    def test_get_tenant_config_caches_result(self, tmp_path):
        """Test that get_tenant_config caches the result."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "tenant.yaml"
        config_file.write_text("""
tenant_id: cached-tenant
""")

        with patch("context_builder.config.tenant.get_workspace_config_dir") as mock_config:
            mock_config.return_value = config_dir

            config1 = get_tenant_config()
            config2 = get_tenant_config()

            assert config1 is config2
            assert config1.tenant_id == "cached-tenant"

    def test_get_tenant_config_force_reload(self, tmp_path):
        """Test that force_reload bypasses cache."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "tenant.yaml"
        config_file.write_text("""
tenant_id: original-tenant
""")

        with patch("context_builder.config.tenant.get_workspace_config_dir") as mock_config:
            mock_config.return_value = config_dir

            config1 = get_tenant_config()
            assert config1.tenant_id == "original-tenant"

            # Update the file
            config_file.write_text("""
tenant_id: updated-tenant
""")

            # Without force_reload, should return cached
            config2 = get_tenant_config()
            assert config2.tenant_id == "original-tenant"

            # With force_reload, should return new value
            config3 = get_tenant_config(force_reload=True)
            assert config3.tenant_id == "updated-tenant"


class TestWorkspaceConfigHash:
    """Tests for workspace config hash computation."""

    def test_compute_workspace_config_hash_empty_dir(self, tmp_path):
        """Test hash computation with empty config dir."""
        from context_builder.pipeline.helpers.metadata import compute_workspace_config_hash

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        with patch("context_builder.pipeline.helpers.metadata.get_workspace_config_dir") as mock_config:
            mock_config.return_value = config_dir

            result = compute_workspace_config_hash()
            assert result is None  # Empty dir returns None

    def test_compute_workspace_config_hash_with_files(self, tmp_path):
        """Test hash computation with config files."""
        from context_builder.pipeline.helpers.metadata import compute_workspace_config_hash

        config_dir = tmp_path / "config"
        prompts_dir = config_dir / "prompts"
        prompts_dir.mkdir(parents=True)

        # Create some config files
        (prompts_dir / "test.md").write_text("test prompt content")
        (config_dir / "tenant.yaml").write_text("tenant_id: test")

        with patch("context_builder.pipeline.helpers.metadata.get_workspace_config_dir") as mock_config:
            mock_config.return_value = config_dir

            result = compute_workspace_config_hash()
            assert result is not None
            assert len(result) == 64  # SHA-256 hex length

    def test_compute_workspace_config_hash_deterministic(self, tmp_path):
        """Test that hash is deterministic for same content."""
        from context_builder.pipeline.helpers.metadata import compute_workspace_config_hash

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "test.yaml").write_text("content: same")

        with patch("context_builder.pipeline.helpers.metadata.get_workspace_config_dir") as mock_config:
            mock_config.return_value = config_dir

            hash1 = compute_workspace_config_hash()
            hash2 = compute_workspace_config_hash()
            assert hash1 == hash2

    def test_compute_workspace_config_hash_changes_with_content(self, tmp_path):
        """Test that hash changes when content changes."""
        from context_builder.pipeline.helpers.metadata import compute_workspace_config_hash

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        test_file = config_dir / "test.yaml"
        test_file.write_text("content: original")

        with patch("context_builder.pipeline.helpers.metadata.get_workspace_config_dir") as mock_config:
            mock_config.return_value = config_dir

            hash1 = compute_workspace_config_hash()

            test_file.write_text("content: modified")
            hash2 = compute_workspace_config_hash()

            assert hash1 != hash2


class TestWorkspaceConfigSnapshot:
    """Tests for workspace config snapshot functionality."""

    def test_snapshot_workspace_config_creates_copy(self, tmp_path):
        """Test that snapshot creates a copy of config dir."""
        from context_builder.pipeline.helpers.metadata import snapshot_workspace_config
        from context_builder.pipeline.paths import RunPaths

        # Create config dir with files
        config_dir = tmp_path / "workspace" / "config"
        prompts_dir = config_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "test.md").write_text("test prompt")
        (config_dir / "tenant.yaml").write_text("tenant_id: test")

        # Create run paths
        run_root = tmp_path / "runs" / "run_001"
        run_root.mkdir(parents=True)
        run_paths = RunPaths(
            run_root=run_root,
            manifest_json=run_root / "manifest.json",
            summary_json=run_root / "summary.json",
            metrics_json=run_root / "metrics.json",
            context_dir=run_root / "context",
            extraction_dir=run_root / "extraction",
            logs_dir=run_root / "logs",
            run_log=run_root / "logs" / "run.log",
            complete_marker=run_root / ".complete",
        )

        with patch("context_builder.pipeline.helpers.metadata.get_workspace_config_dir") as mock_config:
            mock_config.return_value = config_dir

            snapshot_path = snapshot_workspace_config(run_paths)

            assert snapshot_path is not None
            assert snapshot_path.exists()
            assert (snapshot_path / "tenant.yaml").exists()
            assert (snapshot_path / "prompts" / "test.md").exists()

            # Verify content matches
            assert (snapshot_path / "tenant.yaml").read_text() == "tenant_id: test"
            assert (snapshot_path / "prompts" / "test.md").read_text() == "test prompt"

    def test_snapshot_workspace_config_empty_returns_none(self, tmp_path):
        """Test that snapshot returns None for empty config dir."""
        from context_builder.pipeline.helpers.metadata import snapshot_workspace_config
        from context_builder.pipeline.paths import RunPaths

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        run_root = tmp_path / "runs" / "run_001"
        run_root.mkdir(parents=True)
        run_paths = RunPaths(
            run_root=run_root,
            manifest_json=run_root / "manifest.json",
            summary_json=run_root / "summary.json",
            metrics_json=run_root / "metrics.json",
            context_dir=run_root / "context",
            extraction_dir=run_root / "extraction",
            logs_dir=run_root / "logs",
            run_log=run_root / "logs" / "run.log",
            complete_marker=run_root / ".complete",
        )

        with patch("context_builder.pipeline.helpers.metadata.get_workspace_config_dir") as mock_config:
            mock_config.return_value = config_dir

            result = snapshot_workspace_config(run_paths)
            assert result is None


class TestIngestionRouteRule:
    """Tests for IngestionRouteRule model and validation."""

    def test_valid_route_rule(self):
        """Test creating a valid ingestion route rule."""
        rule = IngestionRouteRule(
            pattern=r"^SCAN_.*\.pdf$",
            provider="tesseract",
            description="Legacy scanned PDFs",
        )
        assert rule.pattern == r"^SCAN_.*\.pdf$"
        assert rule.provider == "tesseract"
        assert rule.description == "Legacy scanned PDFs"

    def test_route_rule_without_description(self):
        """Test route rule with optional description omitted."""
        rule = IngestionRouteRule(
            pattern=r".*\.tiff?$",
            provider="azure-di",
        )
        assert rule.description is None

    def test_route_rule_invalid_provider(self):
        """Test that invalid provider name raises error."""
        with pytest.raises(ValueError, match="Unknown provider"):
            IngestionRouteRule(
                pattern=r".*\.pdf$",
                provider="invalid-provider",
            )

    def test_route_rule_invalid_regex(self):
        """Test that invalid regex pattern raises error."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            IngestionRouteRule(
                pattern=r"[invalid(regex",
                provider="tesseract",
            )

    def test_route_rule_empty_pattern(self):
        """Test that empty pattern raises error."""
        with pytest.raises(ValueError):
            IngestionRouteRule(
                pattern="",
                provider="tesseract",
            )

    def test_all_valid_providers(self):
        """Test that all documented providers are valid."""
        for provider in ["azure-di", "openai", "tesseract"]:
            rule = IngestionRouteRule(pattern=r".*", provider=provider)
            assert rule.provider == provider

    def test_valid_providers_constant(self):
        """Test that VALID_INGESTION_PROVIDERS matches expected providers."""
        expected = {"azure-di", "openai", "tesseract"}
        assert VALID_INGESTION_PROVIDERS == expected


class TestIngestionRouting:
    """Tests for tenant config ingestion routing."""

    def setup_method(self):
        """Reset tenant config cache before each test."""
        reset_tenant_config_cache()

    def test_get_provider_for_filename_first_match_wins(self):
        """Test that first matching rule is used."""
        config = TenantConfig(
            tenant_id="test",
            ingestion_routes=[
                IngestionRouteRule(pattern=r"^SCAN_.*", provider="tesseract"),
                IngestionRouteRule(pattern=r".*\.pdf$", provider="azure-di"),
            ],
        )
        # SCAN_report.pdf matches both patterns, but first rule wins
        assert config.get_provider_for_filename("SCAN_report.pdf") == "tesseract"
        # regular.pdf only matches second pattern
        assert config.get_provider_for_filename("regular.pdf") == "azure-di"

    def test_get_provider_for_filename_no_match_returns_none(self):
        """Test that no match returns None for default routing."""
        config = TenantConfig(
            tenant_id="test",
            ingestion_routes=[
                IngestionRouteRule(pattern=r"^SCAN_.*", provider="tesseract"),
            ],
        )
        # This filename doesn't match any pattern
        assert config.get_provider_for_filename("regular_doc.pdf") is None

    def test_get_provider_for_filename_empty_routes(self):
        """Test that empty routes list returns None."""
        config = TenantConfig(
            tenant_id="test",
            ingestion_routes=[],
        )
        assert config.get_provider_for_filename("anything.pdf") is None

    def test_get_provider_for_filename_case_sensitive(self):
        """Test that regex matching is case-sensitive by default."""
        config = TenantConfig(
            tenant_id="test",
            ingestion_routes=[
                IngestionRouteRule(pattern=r"^SCAN_.*", provider="tesseract"),
            ],
        )
        assert config.get_provider_for_filename("SCAN_doc.pdf") == "tesseract"
        assert config.get_provider_for_filename("scan_doc.pdf") is None

    def test_get_provider_for_filename_case_insensitive_pattern(self):
        """Test case-insensitive matching via regex flag."""
        config = TenantConfig(
            tenant_id="test",
            ingestion_routes=[
                IngestionRouteRule(pattern=r"(?i)^scan_.*", provider="tesseract"),
            ],
        )
        assert config.get_provider_for_filename("SCAN_doc.pdf") == "tesseract"
        assert config.get_provider_for_filename("scan_doc.pdf") == "tesseract"
        assert config.get_provider_for_filename("Scan_doc.pdf") == "tesseract"

    def test_get_provider_for_filename_extension_patterns(self):
        """Test routing based on file extensions."""
        config = TenantConfig(
            tenant_id="test",
            ingestion_routes=[
                IngestionRouteRule(pattern=r".*\.tiff?$", provider="tesseract"),
                IngestionRouteRule(pattern=r".*\.png$", provider="openai"),
            ],
        )
        assert config.get_provider_for_filename("scan.tif") == "tesseract"
        assert config.get_provider_for_filename("scan.tiff") == "tesseract"
        assert config.get_provider_for_filename("photo.png") == "openai"
        assert config.get_provider_for_filename("doc.pdf") is None

    def test_load_tenant_config_with_ingestion_routes(self, tmp_path):
        """Test loading tenant config with ingestion routes from YAML."""
        config_file = tmp_path / "tenant.yaml"
        config_file.write_text("""
tenant_id: acme-insurance
tenant_name: ACME Insurance Corp
ingestion_routes:
  - pattern: "^SCAN_.*\\\\.pdf$"
    provider: tesseract
    description: Legacy scanned PDFs use local OCR
  - pattern: ".*\\\\.tiff?$"
    provider: tesseract
    description: All TIFF files use Tesseract
  - pattern: "^MEDICAL_.*"
    provider: azure-di
    description: Medical documents need high-quality OCR
""")

        config = load_tenant_config(config_file)

        assert config is not None
        assert len(config.ingestion_routes) == 3
        assert config.ingestion_routes[0].provider == "tesseract"
        assert config.ingestion_routes[1].pattern == r".*\.tiff?$"
        assert config.ingestion_routes[2].description == "Medical documents need high-quality OCR"

        # Test routing
        assert config.get_provider_for_filename("SCAN_claim.pdf") == "tesseract"
        assert config.get_provider_for_filename("archive.tiff") == "tesseract"
        assert config.get_provider_for_filename("MEDICAL_report.pdf") == "azure-di"
        assert config.get_provider_for_filename("regular.pdf") is None

    def test_load_tenant_config_invalid_provider_in_yaml(self, tmp_path):
        """Test that invalid provider in YAML raises error."""
        config_file = tmp_path / "tenant.yaml"
        config_file.write_text("""
tenant_id: test
ingestion_routes:
  - pattern: ".*"
    provider: invalid-provider
""")

        with pytest.raises(ValueError, match="Unknown provider"):
            load_tenant_config(config_file)

    def test_load_tenant_config_invalid_regex_in_yaml(self, tmp_path):
        """Test that invalid regex in YAML raises error."""
        config_file = tmp_path / "tenant.yaml"
        config_file.write_text("""
tenant_id: test
ingestion_routes:
  - pattern: "[invalid(regex"
    provider: tesseract
""")

        with pytest.raises(ValueError, match="Invalid regex pattern"):
            load_tenant_config(config_file)
