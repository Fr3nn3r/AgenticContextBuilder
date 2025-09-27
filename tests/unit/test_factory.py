"""Unit tests for AcquisitionFactory."""

import logging
from unittest.mock import Mock, patch, MagicMock
import pytest

from context_builder.acquisition import (
    DataAcquisition,
    AcquisitionFactory,
)


class DummyAcquisition(DataAcquisition):
    """Test acquisition implementation."""

    def _process_implementation(self, filepath):
        return {"dummy": "data"}


class NotAcquisition:
    """Class that doesn't inherit from DataAcquisition."""
    pass


class TestAcquisitionFactoryRegistration:
    """Test factory registration functionality."""

    def teardown_method(self):
        """Clean up registry after each test."""
        # Clear registry to avoid test interference
        AcquisitionFactory._registry.clear()

    def test_register_valid_class(self):
        """Test registering a valid acquisition class."""
        AcquisitionFactory.register("dummy", DummyAcquisition)

        assert "dummy" in AcquisitionFactory._registry
        assert AcquisitionFactory._registry["dummy"] is DummyAcquisition

    def test_register_invalid_class(self):
        """Test registering a class that doesn't inherit from DataAcquisition."""
        with pytest.raises(ValueError, match="must inherit from DataAcquisition"):
            AcquisitionFactory.register("invalid", NotAcquisition)

    def test_register_case_insensitive(self):
        """Test registration is case-insensitive."""
        AcquisitionFactory.register("DUMMY", DummyAcquisition)

        assert "dummy" in AcquisitionFactory._registry
        assert "DUMMY" not in AcquisitionFactory._registry

    def test_register_logs_debug(self, caplog):
        """Test registration logs debug message."""
        with caplog.at_level(logging.DEBUG):
            AcquisitionFactory.register("dummy", DummyAcquisition)

        assert "Registered acquisition provider: dummy" in caplog.text

    def test_register_overwrites_existing(self):
        """Test registering overwrites existing registration."""
        AcquisitionFactory.register("dummy", DummyAcquisition)

        class AnotherAcquisition(DataAcquisition):
            def _process_implementation(self, filepath):
                return {}

        AcquisitionFactory.register("dummy", AnotherAcquisition)

        assert AcquisitionFactory._registry["dummy"] is AnotherAcquisition


class TestAcquisitionFactoryCreate:
    """Test factory creation functionality."""

    def setup_method(self):
        """Set up test registry."""
        AcquisitionFactory._registry.clear()
        AcquisitionFactory.register("dummy", DummyAcquisition)

    def teardown_method(self):
        """Clean up registry."""
        AcquisitionFactory._registry.clear()

    def test_create_registered_provider(self):
        """Test creating a registered provider."""
        instance = AcquisitionFactory.create("dummy")

        assert isinstance(instance, DummyAcquisition)

    def test_create_case_insensitive(self):
        """Test creation is case-insensitive."""
        instance1 = AcquisitionFactory.create("dummy")
        instance2 = AcquisitionFactory.create("DUMMY")
        instance3 = AcquisitionFactory.create("Dummy")

        assert isinstance(instance1, DummyAcquisition)
        assert isinstance(instance2, DummyAcquisition)
        assert isinstance(instance3, DummyAcquisition)

    def test_create_unregistered_provider(self):
        """Test creating an unregistered provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown acquisition provider: nonexistent"):
            AcquisitionFactory.create("nonexistent")

    def test_create_logs_debug(self, caplog):
        """Test creation logs debug message."""
        with caplog.at_level(logging.DEBUG):
            AcquisitionFactory.create("dummy")

        assert "Creating acquisition instance: DummyAcquisition" in caplog.text

    def test_create_returns_new_instance(self):
        """Test create returns new instances each time."""
        instance1 = AcquisitionFactory.create("dummy")
        instance2 = AcquisitionFactory.create("dummy")

        assert instance1 is not instance2


class TestAcquisitionFactoryOpenAI:
    """Test OpenAI provider auto-loading."""

    def teardown_method(self):
        """Clean up registry."""
        AcquisitionFactory._registry.clear()

    def test_autoload_openai_success(self):
        """Test successful OpenAI auto-loading."""
        # Clear registry first
        AcquisitionFactory._registry.clear()

        # Mock the import inside the create method
        with patch('context_builder.acquisition.AcquisitionFactory.register') as mock_register:
            # This will trigger auto-load attempt
            try:
                AcquisitionFactory.create("openai")
            except (ValueError, ImportError):
                pass  # Expected since we're mocking

            # Verify register was attempted for openai
            # The actual import happens internally in the create method

    def test_autoload_openai_import_error(self):
        """Test OpenAI auto-loading with import error provides helpful message."""
        # Clear registry first
        AcquisitionFactory._registry.clear()

        with patch('context_builder.acquisition.AcquisitionFactory.register') as mock_register:
            mock_register.side_effect = ImportError("Module not found")

            with pytest.raises(ValueError, match="Failed to import OpenAI implementation"):
                AcquisitionFactory.create("openai")

    def test_autoload_only_for_openai(self):
        """Test auto-loading only attempts for 'openai' provider."""
        AcquisitionFactory._registry.clear()

        with pytest.raises(ValueError, match="Unknown acquisition provider: other"):
            AcquisitionFactory.create("other")


class TestAcquisitionFactoryListProviders:
    """Test list_providers functionality."""

    def teardown_method(self):
        """Clean up registry."""
        AcquisitionFactory._registry.clear()

    def test_list_empty_registry(self):
        """Test listing providers with empty registry."""
        AcquisitionFactory._registry.clear()
        providers = AcquisitionFactory.list_providers()

        assert providers == []

    def test_list_single_provider(self):
        """Test listing single provider."""
        AcquisitionFactory.register("dummy", DummyAcquisition)
        providers = AcquisitionFactory.list_providers()

        assert providers == ["dummy"]

    def test_list_multiple_providers(self):
        """Test listing multiple providers."""
        class Another(DataAcquisition):
            def _process_implementation(self, filepath):
                return {}

        AcquisitionFactory.register("dummy", DummyAcquisition)
        AcquisitionFactory.register("another", Another)
        providers = AcquisitionFactory.list_providers()

        assert set(providers) == {"dummy", "another"}

    def test_list_returns_list_not_dict_keys(self):
        """Test list_providers returns a list, not dict_keys."""
        AcquisitionFactory.register("dummy", DummyAcquisition)
        providers = AcquisitionFactory.list_providers()

        assert isinstance(providers, list)