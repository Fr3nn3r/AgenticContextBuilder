"""Unit tests for AuthService."""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from context_builder.api.services.auth import AuthService, Session, SESSION_TIMEOUT_HOURS
from context_builder.api.services.users import UsersService, Role


class TestLogin:
    """Tests for login functionality."""

    def test_login_valid_credentials(self, tmp_path: Path):
        """Returns (token, user) tuple for valid login."""
        users_service = UsersService(tmp_path)
        users_service.create_user("testuser", "password123", Role.REVIEWER.value)
        auth_service = AuthService(tmp_path, users_service)

        result = auth_service.login("testuser", "password123")

        assert result is not None
        token, user = result
        assert isinstance(token, str)
        assert len(token) > 0
        assert user.username == "testuser"
        assert user.role == Role.REVIEWER.value

    def test_login_invalid_credentials(self, tmp_path: Path):
        """Returns None for invalid credentials."""
        users_service = UsersService(tmp_path)
        users_service.create_user("testuser", "password123", Role.REVIEWER.value)
        auth_service = AuthService(tmp_path, users_service)

        result = auth_service.login("testuser", "wrongpassword")

        assert result is None

    def test_login_nonexistent_user(self, tmp_path: Path):
        """Returns None for nonexistent user."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        result = auth_service.login("nonexistent", "anypassword")

        assert result is None

    def test_login_creates_session_file(self, tmp_path: Path):
        """Session is persisted to sessions.json."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        result = auth_service.login("su", "su")

        assert result is not None
        token, _ = result

        # Verify session file exists and contains the session
        sessions_file = tmp_path / "sessions.json"
        assert sessions_file.exists()

        with open(sessions_file) as f:
            data = json.load(f)

        assert token in data
        assert data[token]["username"] == "su"

    def test_login_default_superuser(self, tmp_path: Path):
        """Can login as default superuser su/su."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        result = auth_service.login("su", "su")

        assert result is not None
        token, user = result
        assert user.username == "su"
        assert user.role == Role.ADMIN.value


class TestValidateSession:
    """Tests for session validation."""

    def test_validate_session_valid_token(self, tmp_path: Path):
        """Returns user for valid token."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        result = auth_service.login("su", "su")
        token, _ = result

        user = auth_service.validate_session(token)

        assert user is not None
        assert user.username == "su"

    def test_validate_session_invalid_token(self, tmp_path: Path):
        """Returns None for unknown token."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        user = auth_service.validate_session("invalid_token_12345")

        assert user is None

    def test_validate_session_expired(self, tmp_path: Path):
        """Returns None for expired token."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        # Login to get a token
        result = auth_service.login("su", "su")
        token, _ = result

        # Manually expire the session by modifying the file
        sessions_file = tmp_path / "sessions.json"
        with open(sessions_file) as f:
            data = json.load(f)

        # Set expiry to past
        past_time = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        data[token]["expires_at"] = past_time

        with open(sessions_file, "w") as f:
            json.dump(data, f)

        # Validation should fail
        user = auth_service.validate_session(token)

        assert user is None

    def test_validate_session_deleted_user(self, tmp_path: Path):
        """Returns None if user was deleted after login."""
        users_service = UsersService(tmp_path)
        users_service.create_user("tempuser", "password", Role.REVIEWER.value)
        auth_service = AuthService(tmp_path, users_service)

        # Login as temp user
        result = auth_service.login("tempuser", "password")
        token, _ = result

        # Delete the user
        users_service.delete_user("tempuser")

        # Validation should fail
        user = auth_service.validate_session(token)

        assert user is None

    def test_validate_session_removes_deleted_user_session(self, tmp_path: Path):
        """Session is removed when validating for deleted user."""
        users_service = UsersService(tmp_path)
        users_service.create_user("tempuser", "password", Role.REVIEWER.value)
        auth_service = AuthService(tmp_path, users_service)

        # Login as temp user
        result = auth_service.login("tempuser", "password")
        token, _ = result

        # Delete the user
        users_service.delete_user("tempuser")

        # Validate (should fail and remove session)
        auth_service.validate_session(token)

        # Verify session is removed from file
        sessions_file = tmp_path / "sessions.json"
        with open(sessions_file) as f:
            data = json.load(f)

        assert token not in data


class TestLogout:
    """Tests for logout functionality."""

    def test_logout_removes_session(self, tmp_path: Path):
        """Token no longer valid after logout."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        result = auth_service.login("su", "su")
        token, _ = result

        # Verify session is valid before logout
        assert auth_service.validate_session(token) is not None

        # Logout
        logout_result = auth_service.logout(token)

        assert logout_result is True
        assert auth_service.validate_session(token) is None

    def test_logout_nonexistent_token(self, tmp_path: Path):
        """Returns False gracefully for unknown token."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        result = auth_service.logout("nonexistent_token_12345")

        assert result is False

    def test_logout_removes_from_file(self, tmp_path: Path):
        """Session is removed from sessions.json."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        result = auth_service.login("su", "su")
        token, _ = result

        # Logout
        auth_service.logout(token)

        # Verify removed from file
        sessions_file = tmp_path / "sessions.json"
        with open(sessions_file) as f:
            data = json.load(f)

        assert token not in data


class TestSessionCleanup:
    """Tests for session cleanup functionality."""

    def test_session_cleanup_on_validate(self, tmp_path: Path):
        """Expired sessions are removed during validation."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        # Create two sessions
        result1 = auth_service.login("su", "su")
        token1, _ = result1

        result2 = auth_service.login("su", "su")
        token2, _ = result2

        # Expire the first session
        sessions_file = tmp_path / "sessions.json"
        with open(sessions_file) as f:
            data = json.load(f)

        past_time = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        data[token1]["expires_at"] = past_time

        with open(sessions_file, "w") as f:
            json.dump(data, f)

        # Validate the expired session (triggers cleanup)
        auth_service.validate_session(token1)

        # Verify expired session is removed
        with open(sessions_file) as f:
            data = json.load(f)

        assert token1 not in data
        assert token2 in data  # Valid session should remain


class TestUserSessions:
    """Tests for user session management."""

    def test_get_user_sessions(self, tmp_path: Path):
        """Returns active sessions for user."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        # Create multiple sessions for same user
        auth_service.login("su", "su")
        auth_service.login("su", "su")

        sessions = auth_service.get_user_sessions("su")

        assert len(sessions) == 2
        for session in sessions:
            assert session.username == "su"

    def test_get_user_sessions_excludes_other_users(self, tmp_path: Path):
        """Only returns sessions for specified user."""
        users_service = UsersService(tmp_path)
        users_service.create_user("user2", "pass", Role.REVIEWER.value)
        auth_service = AuthService(tmp_path, users_service)

        # Create sessions for different users
        auth_service.login("su", "su")
        auth_service.login("user2", "pass")

        sessions = auth_service.get_user_sessions("su")

        assert len(sessions) == 1
        assert sessions[0].username == "su"

    def test_get_user_sessions_empty(self, tmp_path: Path):
        """Returns empty list for user with no sessions."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        sessions = auth_service.get_user_sessions("su")

        assert sessions == []

    def test_invalidate_user_sessions(self, tmp_path: Path):
        """All sessions for user are removed."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        # Create multiple sessions
        result1 = auth_service.login("su", "su")
        token1, _ = result1
        result2 = auth_service.login("su", "su")
        token2, _ = result2

        # Invalidate all sessions
        removed = auth_service.invalidate_user_sessions("su")

        assert removed == 2
        assert auth_service.validate_session(token1) is None
        assert auth_service.validate_session(token2) is None

    def test_invalidate_user_sessions_preserves_others(self, tmp_path: Path):
        """Other user sessions are not affected."""
        users_service = UsersService(tmp_path)
        users_service.create_user("user2", "pass", Role.REVIEWER.value)
        auth_service = AuthService(tmp_path, users_service)

        # Create sessions for different users
        auth_service.login("su", "su")
        result2 = auth_service.login("user2", "pass")
        token2, _ = result2

        # Invalidate su's sessions
        auth_service.invalidate_user_sessions("su")

        # user2's session should still be valid
        assert auth_service.validate_session(token2) is not None

    def test_invalidate_user_sessions_none(self, tmp_path: Path):
        """Returns 0 for user with no sessions."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        removed = auth_service.invalidate_user_sessions("su")

        assert removed == 0


class TestSessionTimeout:
    """Tests for session timeout configuration."""

    def test_session_expires_after_timeout(self, tmp_path: Path):
        """Session expires after SESSION_TIMEOUT_HOURS."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        result = auth_service.login("su", "su")
        token, _ = result

        # Check session file for correct expiry time
        sessions_file = tmp_path / "sessions.json"
        with open(sessions_file) as f:
            data = json.load(f)

        session = data[token]
        created_at = datetime.fromisoformat(session["created_at"].rstrip("Z"))
        expires_at = datetime.fromisoformat(session["expires_at"].rstrip("Z"))

        expected_delta = timedelta(hours=SESSION_TIMEOUT_HOURS)
        actual_delta = expires_at - created_at

        # Allow 1 second tolerance
        assert abs((actual_delta - expected_delta).total_seconds()) < 1


class TestPersistence:
    """Tests for session file persistence."""

    def test_sessions_persisted_to_file(self, tmp_path: Path):
        """Sessions are saved to sessions.json."""
        users_service = UsersService(tmp_path)
        auth_service = AuthService(tmp_path, users_service)

        auth_service.login("su", "su")

        sessions_file = tmp_path / "sessions.json"
        assert sessions_file.exists()

    def test_sessions_loaded_from_file(self, tmp_path: Path):
        """Sessions are loaded from existing file."""
        users_service = UsersService(tmp_path)

        # Create session with first auth service instance
        auth_service1 = AuthService(tmp_path, users_service)
        result = auth_service1.login("su", "su")
        token, _ = result

        # Create new auth service instance (simulates restart)
        auth_service2 = AuthService(tmp_path, users_service)

        # Session should still be valid
        user = auth_service2.validate_session(token)

        assert user is not None
        assert user.username == "su"

    def test_init_creates_empty_sessions_file(self, tmp_path: Path):
        """Init creates empty sessions.json if it doesn't exist."""
        users_service = UsersService(tmp_path)
        AuthService(tmp_path, users_service)

        sessions_file = tmp_path / "sessions.json"
        assert sessions_file.exists()

        with open(sessions_file) as f:
            data = json.load(f)

        assert data == {}
