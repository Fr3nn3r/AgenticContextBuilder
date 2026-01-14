"""Service for managing users and authentication."""

import hashlib
import json
import logging
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Literal, Optional

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """User roles with different permission levels."""

    ADMIN = "admin"
    REVIEWER = "reviewer"
    OPERATOR = "operator"
    AUDITOR = "auditor"


@dataclass
class User:
    """User record."""

    username: str
    password_hash: str
    role: str  # Role enum value as string
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.utcnow().isoformat() + "Z"
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_public_dict(self) -> dict:
        """Return user data without password hash."""
        return {
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class UsersService:
    """Service for CRUD operations on users."""

    def __init__(self, config_dir: Path):
        """
        Initialize the users service.

        Args:
            config_dir: Directory to store user files (e.g., output/config/)
        """
        self.config_dir = config_dir
        self.users_file = config_dir / "users.json"
        self._ensure_defaults()

    def _hash_password(self, password: str) -> str:
        """Hash a password using SHA-256 with salt."""
        # For MVP, use simple SHA-256. In production, upgrade to bcrypt.
        salt = "contextbuilder_salt_"  # Fixed salt for MVP simplicity
        return hashlib.sha256((salt + password).encode()).hexdigest()

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        return self._hash_password(password) == password_hash

    def _ensure_defaults(self) -> None:
        """Ensure default users exist (one per role)."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.users_file.exists():
            # Create default users: one per role, all with password "su"
            default_users = [
                User(
                    username="su",
                    password_hash=self._hash_password("su"),
                    role=Role.ADMIN.value,
                ),
                User(
                    username="ted",
                    password_hash=self._hash_password("su"),
                    role=Role.REVIEWER.value,
                ),
                User(
                    username="seb",
                    password_hash=self._hash_password("su"),
                    role=Role.OPERATOR.value,
                ),
                User(
                    username="tod",
                    password_hash=self._hash_password("su"),
                    role=Role.AUDITOR.value,
                ),
            ]
            self._save_all(default_users)
            logger.info(f"Created default users (su, ted, seb, tod) at {self.users_file}")

    def _load_all(self) -> List[User]:
        """Load all users from disk."""
        if not self.users_file.exists():
            return []

        try:
            with open(self.users_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [User(**item) for item in data]
        except Exception as e:
            logger.error(f"Failed to load users: {e}")
            return []

    def _save_all(self, users: List[User]) -> None:
        """Save all users to disk."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.users_file, "w", encoding="utf-8") as f:
                json.dump([asdict(u) for u in users], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save users: {e}")
            raise

    def list_users(self) -> List[User]:
        """List all users."""
        return self._load_all()

    def get_user(self, username: str) -> Optional[User]:
        """Get a user by username."""
        users = self._load_all()
        for user in users:
            if user.username == username:
                return user
        return None

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user by username and password."""
        user = self.get_user(username)
        if user and self._verify_password(password, user.password_hash):
            return user
        return None

    def create_user(
        self,
        username: str,
        password: str,
        role: str = Role.REVIEWER.value,
    ) -> Optional[User]:
        """Create a new user."""
        users = self._load_all()

        # Check if username already exists
        if any(u.username == username for u in users):
            logger.warning(f"User already exists: {username}")
            return None

        # Validate role
        valid_roles = [r.value for r in Role]
        if role not in valid_roles:
            logger.warning(f"Invalid role: {role}")
            return None

        user = User(
            username=username,
            password_hash=self._hash_password(password),
            role=role,
        )

        users.append(user)
        self._save_all(users)
        logger.info(f"Created user: {username} with role {role}")
        return user

    def update_user(
        self,
        username: str,
        password: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Optional[User]:
        """Update an existing user."""
        users = self._load_all()

        for i, user in enumerate(users):
            if user.username == username:
                if password:
                    user.password_hash = self._hash_password(password)
                if role:
                    # Validate role
                    valid_roles = [r.value for r in Role]
                    if role not in valid_roles:
                        logger.warning(f"Invalid role: {role}")
                        return None
                    user.role = role

                user.updated_at = datetime.utcnow().isoformat() + "Z"
                users[i] = user
                self._save_all(users)
                logger.info(f"Updated user: {username}")
                return user

        return None

    def delete_user(self, username: str) -> bool:
        """Delete a user."""
        users = self._load_all()

        new_users = [u for u in users if u.username != username]

        if len(new_users) == len(users):
            return False  # Not found

        # Don't allow deleting the last admin
        remaining_admins = [u for u in new_users if u.role == Role.ADMIN.value]
        if len(remaining_admins) == 0:
            logger.warning("Cannot delete the last admin user")
            return False

        self._save_all(new_users)
        logger.info(f"Deleted user: {username}")
        return True
