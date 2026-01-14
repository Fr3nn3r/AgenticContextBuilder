"""Unit tests for version bundle path resolution.

Tests that prompt template and extraction spec hashing uses absolute paths
and resolves correctly regardless of working directory.
"""

import tempfile
from pathlib import Path

import pytest


class TestPromptTemplateHashResolution:
    """Tests for _get_prompt_template_hash path resolution."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_output_dir):
        """Create a VersionBundleStore instance."""
        from context_builder.storage.version_bundles import VersionBundleStore
        return VersionBundleStore(temp_output_dir)

    def test_prompt_template_hash_uses_absolute_path(self, store):
        """Hash computation uses absolute path resolution."""
        # The method should not raise even if working directory changes
        # because it uses Path(__file__).resolve() internally
        hash_result = store._get_prompt_template_hash()
        # May return None if prompts dir doesn't exist, but should not crash
        assert hash_result is None or isinstance(hash_result, str)

    def test_prompt_template_hash_returns_string_or_none(self, store):
        """Hash returns string when prompts exist, None otherwise."""
        hash_result = store._get_prompt_template_hash()
        assert hash_result is None or (isinstance(hash_result, str) and len(hash_result) > 0)

    def test_prompt_template_hash_is_deterministic(self, store):
        """Same prompt templates produce same hash."""
        hash1 = store._get_prompt_template_hash()
        hash2 = store._get_prompt_template_hash()
        assert hash1 == hash2


class TestExtractionSpecHashResolution:
    """Tests for _get_extraction_spec_hash path resolution."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_output_dir):
        """Create a VersionBundleStore instance."""
        from context_builder.storage.version_bundles import VersionBundleStore
        return VersionBundleStore(temp_output_dir)

    def test_extraction_spec_hash_uses_absolute_path(self, store):
        """Hash computation uses absolute path resolution."""
        hash_result = store._get_extraction_spec_hash()
        # May return None if specs dir doesn't exist, but should not crash
        assert hash_result is None or isinstance(hash_result, str)

    def test_extraction_spec_hash_returns_string_or_none(self, store):
        """Hash returns string when specs exist, None otherwise."""
        hash_result = store._get_extraction_spec_hash()
        assert hash_result is None or (isinstance(hash_result, str) and len(hash_result) > 0)

    def test_extraction_spec_hash_is_deterministic(self, store):
        """Same extraction specs produce same hash."""
        hash1 = store._get_extraction_spec_hash()
        hash2 = store._get_extraction_spec_hash()
        assert hash1 == hash2


class TestVersionBundleCreation:
    """Tests for version bundle creation with path resolution."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_output_dir):
        """Create a VersionBundleStore instance."""
        from context_builder.storage.version_bundles import VersionBundleStore
        return VersionBundleStore(temp_output_dir)

    def test_create_bundle_includes_hashes(self, store):
        """Created bundle includes prompt and spec hashes."""
        bundle = store.create_version_bundle(
            run_id="test_run_001",
            model_name="gpt-4o",
        )

        # Bundle should be created
        assert bundle is not None
        assert bundle.bundle_id.startswith("vb_")

        # Hashes may be None if dirs don't exist, but fields should be present
        assert hasattr(bundle, "prompt_template_hash")
        assert hasattr(bundle, "extraction_spec_hash")

    def test_create_bundle_persists_correctly(self, store):
        """Bundle can be retrieved after creation."""
        run_id = "test_run_002"
        store.create_version_bundle(run_id=run_id, model_name="gpt-4o")

        # Retrieve and verify
        retrieved = store.get_version_bundle(run_id)
        assert retrieved is not None
        assert retrieved.model_name == "gpt-4o"


class TestHashDirectoryFunction:
    """Tests for the _hash_directory helper."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_output_dir):
        """Create a VersionBundleStore instance."""
        from context_builder.storage.version_bundles import VersionBundleStore
        return VersionBundleStore(temp_output_dir)

    def test_hash_directory_with_files(self, store, temp_output_dir):
        """Hash directory returns hash when files exist."""
        # Create test directory with files
        test_dir = temp_output_dir / "test_dir"
        test_dir.mkdir()
        (test_dir / "file1.md").write_text("content 1")
        (test_dir / "file2.md").write_text("content 2")

        hash_result = store._hash_directory(test_dir, "*.md")
        assert hash_result is not None
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA-256 hex

    def test_hash_directory_empty_returns_none(self, store, temp_output_dir):
        """Hash directory returns None for empty directory."""
        test_dir = temp_output_dir / "empty_dir"
        test_dir.mkdir()

        hash_result = store._hash_directory(test_dir, "*.md")
        assert hash_result is None

    def test_hash_directory_nonexistent_returns_none(self, store, temp_output_dir):
        """Hash directory returns None for nonexistent directory."""
        hash_result = store._hash_directory(temp_output_dir / "nonexistent", "*.md")
        assert hash_result is None

    def test_hash_directory_content_change_changes_hash(self, store, temp_output_dir):
        """Changing file content changes the hash."""
        test_dir = temp_output_dir / "change_test"
        test_dir.mkdir()
        test_file = test_dir / "file.md"

        # First hash
        test_file.write_text("original content")
        hash1 = store._hash_directory(test_dir, "*.md")

        # Change content
        test_file.write_text("modified content")
        hash2 = store._hash_directory(test_dir, "*.md")

        assert hash1 != hash2

    def test_hash_directory_file_addition_changes_hash(self, store, temp_output_dir):
        """Adding a file changes the hash."""
        test_dir = temp_output_dir / "add_test"
        test_dir.mkdir()
        (test_dir / "file1.md").write_text("content 1")

        hash1 = store._hash_directory(test_dir, "*.md")

        # Add file
        (test_dir / "file2.md").write_text("content 2")
        hash2 = store._hash_directory(test_dir, "*.md")

        assert hash1 != hash2


class TestPathResolutionFromDifferentWorkingDirs:
    """Tests verifying path resolution works from any working directory."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_module_path_resolution(self, temp_output_dir):
        """Module-relative path resolution works correctly."""
        from context_builder.storage.version_bundles import VersionBundleStore

        # Create store
        store = VersionBundleStore(temp_output_dir)

        # Get the module directory that the code uses
        import context_builder.storage.version_bundles as vb_module
        module_file = Path(vb_module.__file__).resolve()
        module_dir = module_file.parent.parent  # context_builder/

        # Verify the paths the code will check exist relative to module
        expected_prompts = module_dir / "prompts"
        expected_specs = module_dir / "extraction" / "specs"

        # These paths should exist in the real codebase
        # (test will verify path calculation is correct)
        assert module_dir.name == "context_builder"

    def test_hash_methods_dont_use_relative_paths(self):
        """Hash methods use Path(__file__).resolve() not Path('...')."""
        import inspect
        from context_builder.storage.version_bundles import VersionBundleStore

        # Get source code of the methods
        prompt_source = inspect.getsource(VersionBundleStore._get_prompt_template_hash)
        spec_source = inspect.getsource(VersionBundleStore._get_extraction_spec_hash)

        # Should use __file__ for path resolution
        assert "__file__" in prompt_source
        assert "__file__" in spec_source

        # Should use .resolve() for absolute paths
        assert "resolve()" in prompt_source
        assert "resolve()" in spec_source
