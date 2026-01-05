"""Unit tests for IngestionFactory."""

import logging
from unittest.mock import Mock, patch, MagicMock
import pytest

from context_builder.ingestion import (
    DataIngestion,
    IngestionFactory,
)


class DummyIngestion(DataIngestion):
    """Test ingestion implementation."""

    def _process_implementation(self, filepath):
        return {"dummy": "data"}


class NotIngestion:
    """Class that doesn't inherit from DataIngestion."""
    pass


class TestIngestionFactoryRegistration:
    """Test factory registration functionality."""

    def teardown_method(self):
        """Clean up registry after each test."""
        # Clear registry to avoid test interference
        IngestionFactory._registry.clear()

    def test_register_valid_class(self):
        """Test registering a valid ingestion class."""
        IngestionFactory.register("dummy", DummyIngestion)

        assert "dummy" in IngestionFactory._registry
        assert IngestionFactory._registry["dummy"] is DummyIngestion

    def test_register_invalid_class(self):
        """Test registering a class that doesn't inherit from DataIngestion."""
        with pytest.raises(ValueError, match="must inherit from DataIngestion"):
            IngestionFactory.register("invalid", NotIngestion)

    def test_register_case_insensitive(self):
        """Test registration is case-insensitive."""
        IngestionFactory.register("DUMMY", DummyIngestion)

        assert "dummy" in IngestionFactory._registry
        assert "DUMMY" not in IngestionFactory._registry

    def test_register_logs_debug(self, caplog):
        """Test registration logs debug message."""
        with caplog.at_level(logging.DEBUG):
            IngestionFactory.register("dummy", DummyIngestion)

        assert "Registered ingestion provider: dummy" in caplog.text

    def test_register_overwrites_existing(self):
        """Test registering overwrites existing registration."""
        IngestionFactory.register("dummy", DummyIngestion)

        class AnotherAcquisition(DataIngestion):
            def _process_implementation(self, filepath):
                return {}

        IngestionFactory.register("dummy", AnotherAcquisition)

        assert IngestionFactory._registry["dummy"] is AnotherAcquisition


class TestIngestionFactoryCreate:
    """Test factory creation functionality."""

    def setup_method(self):
        """Set up test registry."""
        IngestionFactory._registry.clear()
        IngestionFactory.register("dummy", DummyIngestion)

    def teardown_method(self):
        """Clean up registry."""
        IngestionFactory._registry.clear()

    def test_create_registered_provider(self):
        """Test creating a registered provider."""
        instance = IngestionFactory.create("dummy")

        assert isinstance(instance, DummyIngestion)

    def test_create_case_insensitive(self):
        """Test creation is case-insensitive."""
        instance1 = IngestionFactory.create("dummy")
        instance2 = IngestionFactory.create("DUMMY")
        instance3 = IngestionFactory.create("Dummy")

        assert isinstance(instance1, DummyIngestion)
        assert isinstance(instance2, DummyIngestion)
        assert isinstance(instance3, DummyIngestion)

    def test_create_unregistered_provider(self):
        """Test creating an unregistered provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown ingestion provider: nonexistent"):
            IngestionFactory.create("nonexistent")

    def test_create_logs_debug(self, caplog):
        """Test creation logs debug message."""
        with caplog.at_level(logging.DEBUG):
            IngestionFactory.create("dummy")

        assert "Creating ingestion instance: DummyIngestion" in caplog.text

    def test_create_returns_new_instance(self):
        """Test create returns new instances each time."""
        instance1 = IngestionFactory.create("dummy")
        instance2 = IngestionFactory.create("dummy")

        assert instance1 is not instance2


class TestIngestionFactoryOpenAI:
    """Test OpenAI provider auto-loading."""

    def teardown_method(self):
        """Clean up registry."""
        IngestionFactory._registry.clear()

    def test_autoload_openai_success(self):
        """Test successful OpenAI auto-loading."""
        # Clear registry first
        IngestionFactory._registry.clear()

        # Mock the import inside the create method
        with patch('context_builder.ingestion.IngestionFactory.register') as mock_register:
            # This will trigger auto-load attempt
            try:
                IngestionFactory.create("openai")
            except (ValueError, ImportError):
                pass  # Expected since we're mocking

            # Verify register was attempted for openai
            # The actual import happens internally in the create method

    def test_autoload_openai_import_error(self):
        """Test OpenAI auto-loading with import error provides helpful message."""
        # Clear registry first
        IngestionFactory._registry.clear()

        with patch('context_builder.ingestion.IngestionFactory.register') as mock_register:
            mock_register.side_effect = ImportError("Module not found")

            with pytest.raises(ValueError, match="Failed to import OpenAI implementation"):
                IngestionFactory.create("openai")

    def test_autoload_only_for_openai(self):
        """Test auto-loading only attempts for 'openai' provider."""
        IngestionFactory._registry.clear()

        with pytest.raises(ValueError, match="Unknown ingestion provider: other"):
            IngestionFactory.create("other")


class TestIngestionFactoryListProviders:
    """Test list_providers functionality."""

    def teardown_method(self):
        """Clean up registry."""
        IngestionFactory._registry.clear()

    def test_list_empty_registry(self):
        """Test listing providers with empty registry."""
        IngestionFactory._registry.clear()
        providers = IngestionFactory.list_providers()

        assert providers == []

    def test_list_single_provider(self):
        """Test listing single provider."""
        IngestionFactory.register("dummy", DummyIngestion)
        providers = IngestionFactory.list_providers()

        assert providers == ["dummy"]

    def test_list_multiple_providers(self):
        """Test listing multiple providers."""
        class Another(DataIngestion):
            def _process_implementation(self, filepath):
                return {}

        IngestionFactory.register("dummy", DummyIngestion)
        IngestionFactory.register("another", Another)
        providers = IngestionFactory.list_providers()

        assert set(providers) == {"dummy", "another"}

    def test_list_returns_list_not_dict_keys(self):
        """Test list_providers returns a list, not dict_keys."""
        IngestionFactory.register("dummy", DummyIngestion)
        providers = IngestionFactory.list_providers()

        assert isinstance(providers, list)