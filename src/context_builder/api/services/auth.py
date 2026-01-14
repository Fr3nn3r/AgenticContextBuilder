"""Service for authentication and session management."""

import json
import logging
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .users import User, UsersService

logger = logging.getLogger(__name__)

# Session timeout in hours
SESSION_TIMEOUT_HOURS = 8


@dataclass
class Session:
    """Session record."""

    token: str
    username: str
    created_at: str
    expires_at: str


class AuthService:
    """Service for authentication and session management."""

    def __init__(self, config_dir: Path, users_service: UsersService):
        """
        Initialize the auth service.

        Args:
            config_dir: Directory to store session files (e.g., output/config/)
            users_service: Users service for authentication
        """
        self.config_dir = config_dir
        self.sessions_file = config_dir / "sessions.json"
        self.users_service = users_service
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Ensure sessions file exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.sessions_file.exists():
            self._save_all({})

    def _load_all(self) -> dict[str, Session]:
        """Load all sessions from disk."""
        if not self.sessions_file.exists():
            return {}

        try:
            with open(self.sessions_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {token: Session(**session_data) for token, session_data in data.items()}
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")
            return {}

    def _save_all(self, sessions: dict[str, Session]) -> None:
        """Save all sessions to disk."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.sessions_file, "w", encoding="utf-8") as f:
                json.dump(
                    {token: asdict(session) for token, session in sessions.items()},
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")
            raise

    def _generate_token(self) -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)

    def _cleanup_expired(self, sessions: dict[str, Session]) -> dict[str, Session]:
        """Remove expired sessions."""
        now = datetime.utcnow()
        valid_sessions = {}
        for token, session in sessions.items():
            expires_at = datetime.fromisoformat(session.expires_at.rstrip("Z"))
            if expires_at > now:
                valid_sessions[token] = session
        return valid_sessions

    def login(self, username: str, password: str) -> Optional[tuple[str, User]]:
        """
        Authenticate user and create session.

        Returns:
            Tuple of (token, user) on success, None on failure.
        """
        user = self.users_service.authenticate(username, password)
        if not user:
            logger.warning(f"Failed login attempt for user: {username}")
            return None

        # Create new session
        token = self._generate_token()
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=SESSION_TIMEOUT_HOURS)

        session = Session(
            token=token,
            username=username,
            created_at=now.isoformat() + "Z",
            expires_at=expires_at.isoformat() + "Z",
        )

        # Load, cleanup, add new session, save
        sessions = self._load_all()
        sessions = self._cleanup_expired(sessions)
        sessions[token] = session
        self._save_all(sessions)

        logger.info(f"User logged in: {username}")
        return (token, user)

    def validate_session(self, token: str) -> Optional[User]:
        """
        Validate a session token and return the associated user.

        Returns:
            User on success, None if session is invalid or expired.
        """
        sessions = self._load_all()

        session = sessions.get(token)
        if not session:
            return None

        # Check expiry
        expires_at = datetime.fromisoformat(session.expires_at.rstrip("Z"))
        if expires_at <= datetime.utcnow():
            # Session expired, cleanup and return None
            sessions = self._cleanup_expired(sessions)
            self._save_all(sessions)
            return None

        # Get user from users service
        user = self.users_service.get_user(session.username)
        if not user:
            # User was deleted, invalidate session
            del sessions[token]
            self._save_all(sessions)
            return None

        return user

    def logout(self, token: str) -> bool:
        """
        Invalidate a session token.

        Returns:
            True if session was found and removed, False otherwise.
        """
        sessions = self._load_all()

        if token in sessions:
            username = sessions[token].username
            del sessions[token]
            sessions = self._cleanup_expired(sessions)
            self._save_all(sessions)
            logger.info(f"User logged out: {username}")
            return True

        return False

    def get_user_sessions(self, username: str) -> list[Session]:
        """Get all active sessions for a user."""
        sessions = self._load_all()
        sessions = self._cleanup_expired(sessions)
        return [s for s in sessions.values() if s.username == username]

    def invalidate_user_sessions(self, username: str) -> int:
        """Invalidate all sessions for a user. Returns count of sessions removed."""
        sessions = self._load_all()
        original_count = len(sessions)

        sessions = {t: s for t, s in sessions.items() if s.username != username}
        sessions = self._cleanup_expired(sessions)

        self._save_all(sessions)
        removed = original_count - len(sessions)
        if removed > 0:
            logger.info(f"Invalidated {removed} sessions for user: {username}")
        return removed
