"""Unit tests for AuthService.clear_all_sessions."""

import json
from pathlib import Path

import pytest

from context_builder.api.services.auth import AuthService
from context_builder.api.services.users import UsersService


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Create a temp config directory."""
    config = tmp_path / "config"
    config.mkdir()
    return config


@pytest.fixture
def users_service(config_dir: Path) -> UsersService:
    """Create a UsersService with test data."""
    service = UsersService(config_dir)
    # Create a test user
    service.create_user("testuser", "password123", "admin")
    return service


@pytest.fixture
def auth_service(config_dir: Path, users_service: UsersService) -> AuthService:
    """Create an AuthService."""
    return AuthService(config_dir, users_service)


class TestClearAllSessions:
    """Tests for clear_all_sessions method."""

    def test_clear_all_sessions_with_no_sessions(self, auth_service: AuthService):
        """Clearing sessions when none exist should return 0."""
        count = auth_service.clear_all_sessions()
        assert count == 0

    def test_clear_all_sessions_with_one_session(self, auth_service: AuthService):
        """Clearing sessions should remove all sessions."""
        # Create a session
        result = auth_service.login("testuser", "password123")
        assert result is not None
        token, user = result

        # Verify session exists
        user = auth_service.validate_session(token)
        assert user is not None

        # Clear all sessions
        count = auth_service.clear_all_sessions()
        assert count == 1

        # Verify session is gone
        user = auth_service.validate_session(token)
        assert user is None

    def test_clear_all_sessions_with_multiple_sessions(
        self, auth_service: AuthService, users_service: UsersService
    ):
        """Clearing sessions should remove sessions from all users."""
        # Create another user
        users_service.create_user("user2", "password456", "reviewer")

        # Create sessions for both users
        result1 = auth_service.login("testuser", "password123")
        result2 = auth_service.login("user2", "password456")

        assert result1 is not None
        assert result2 is not None

        token1, _ = result1
        token2, _ = result2

        # Verify both sessions exist
        assert auth_service.validate_session(token1) is not None
        assert auth_service.validate_session(token2) is not None

        # Clear all sessions
        count = auth_service.clear_all_sessions()
        assert count == 2

        # Verify both sessions are gone
        assert auth_service.validate_session(token1) is None
        assert auth_service.validate_session(token2) is None

    def test_clear_all_sessions_empties_file(
        self, auth_service: AuthService, config_dir: Path
    ):
        """Sessions file should be empty after clearing."""
        # Create a session
        auth_service.login("testuser", "password123")

        # Clear sessions
        auth_service.clear_all_sessions()

        # Check file contents
        sessions_file = config_dir / "sessions.json"
        with open(sessions_file) as f:
            data = json.load(f)

        assert data == {}
