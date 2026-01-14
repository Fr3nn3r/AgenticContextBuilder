"""Unit tests for UsersService."""

import json
import pytest
from pathlib import Path

from context_builder.api.services.users import UsersService, User, Role


class TestUsersServiceInit:
    """Tests for UsersService initialization."""

    def test_init_creates_default_superuser(self, tmp_path: Path):
        """First init creates 'su' user with admin role."""
        service = UsersService(tmp_path)

        users = service.list_users()
        assert len(users) == 1
        assert users[0].username == "su"
        assert users[0].role == Role.ADMIN.value

    def test_init_does_not_overwrite_existing_users(self, tmp_path: Path):
        """Second init preserves existing users."""
        # First init creates default user
        service1 = UsersService(tmp_path)
        service1.create_user("testuser", "password", Role.REVIEWER.value)

        # Second init should preserve users
        service2 = UsersService(tmp_path)
        users = service2.list_users()

        assert len(users) == 2
        usernames = [u.username for u in users]
        assert "su" in usernames
        assert "testuser" in usernames


class TestPasswordHashing:
    """Tests for password hashing functionality."""

    def test_hash_password_is_deterministic(self, tmp_path: Path):
        """Same password produces same hash."""
        service = UsersService(tmp_path)

        hash1 = service._hash_password("mypassword")
        hash2 = service._hash_password("mypassword")

        assert hash1 == hash2

    def test_hash_password_different_for_different_passwords(self, tmp_path: Path):
        """Different passwords produce different hashes."""
        service = UsersService(tmp_path)

        hash1 = service._hash_password("password1")
        hash2 = service._hash_password("password2")

        assert hash1 != hash2

    def test_verify_password_correct(self, tmp_path: Path):
        """Correct password returns True."""
        service = UsersService(tmp_path)
        password = "testpassword"
        hashed = service._hash_password(password)

        assert service._verify_password(password, hashed) is True

    def test_verify_password_incorrect(self, tmp_path: Path):
        """Wrong password returns False."""
        service = UsersService(tmp_path)
        hashed = service._hash_password("correct")

        assert service._verify_password("wrong", hashed) is False


class TestCreateUser:
    """Tests for user creation."""

    def test_create_user_success(self, tmp_path: Path):
        """Creates user with correct fields."""
        service = UsersService(tmp_path)

        user = service.create_user("newuser", "password123", Role.REVIEWER.value)

        assert user is not None
        assert user.username == "newuser"
        assert user.role == Role.REVIEWER.value
        assert user.password_hash != "password123"  # Should be hashed
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_create_user_duplicate_fails(self, tmp_path: Path):
        """Duplicate username returns None."""
        service = UsersService(tmp_path)

        service.create_user("user1", "pass1", Role.REVIEWER.value)
        result = service.create_user("user1", "pass2", Role.OPERATOR.value)

        assert result is None

    def test_create_user_invalid_role_fails(self, tmp_path: Path):
        """Invalid role returns None."""
        service = UsersService(tmp_path)

        result = service.create_user("user1", "pass1", "invalid_role")

        assert result is None

    def test_create_user_all_valid_roles(self, tmp_path: Path):
        """All valid roles can be assigned."""
        service = UsersService(tmp_path)

        for role in Role:
            user = service.create_user(f"user_{role.value}", "pass", role.value)
            assert user is not None
            assert user.role == role.value


class TestGetUser:
    """Tests for getting a user."""

    def test_get_user_exists(self, tmp_path: Path):
        """Returns user object for existing user."""
        service = UsersService(tmp_path)
        service.create_user("testuser", "pass", Role.REVIEWER.value)

        user = service.get_user("testuser")

        assert user is not None
        assert user.username == "testuser"

    def test_get_user_not_found(self, tmp_path: Path):
        """Returns None for nonexistent user."""
        service = UsersService(tmp_path)

        user = service.get_user("nonexistent")

        assert user is None

    def test_get_user_default_superuser(self, tmp_path: Path):
        """Can get default superuser."""
        service = UsersService(tmp_path)

        user = service.get_user("su")

        assert user is not None
        assert user.role == Role.ADMIN.value


class TestListUsers:
    """Tests for listing users."""

    def test_list_users_returns_all(self, tmp_path: Path):
        """Returns all users in list."""
        service = UsersService(tmp_path)
        service.create_user("user1", "pass", Role.REVIEWER.value)
        service.create_user("user2", "pass", Role.OPERATOR.value)

        users = service.list_users()

        assert len(users) == 3  # su + 2 created
        usernames = [u.username for u in users]
        assert "su" in usernames
        assert "user1" in usernames
        assert "user2" in usernames

    def test_list_users_empty_returns_default(self, tmp_path: Path):
        """Even empty list has default superuser."""
        service = UsersService(tmp_path)

        users = service.list_users()

        assert len(users) == 1
        assert users[0].username == "su"


class TestAuthenticate:
    """Tests for user authentication."""

    def test_authenticate_valid_credentials(self, tmp_path: Path):
        """Returns user for valid login."""
        service = UsersService(tmp_path)
        service.create_user("testuser", "correctpass", Role.REVIEWER.value)

        user = service.authenticate("testuser", "correctpass")

        assert user is not None
        assert user.username == "testuser"

    def test_authenticate_invalid_password(self, tmp_path: Path):
        """Returns None for wrong password."""
        service = UsersService(tmp_path)
        service.create_user("testuser", "correctpass", Role.REVIEWER.value)

        user = service.authenticate("testuser", "wrongpass")

        assert user is None

    def test_authenticate_nonexistent_user(self, tmp_path: Path):
        """Returns None for unknown user."""
        service = UsersService(tmp_path)

        user = service.authenticate("nonexistent", "anypass")

        assert user is None

    def test_authenticate_default_superuser(self, tmp_path: Path):
        """Can authenticate as default superuser su/su."""
        service = UsersService(tmp_path)

        user = service.authenticate("su", "su")

        assert user is not None
        assert user.username == "su"
        assert user.role == Role.ADMIN.value


class TestUpdateUser:
    """Tests for updating users."""

    def test_update_user_password(self, tmp_path: Path):
        """Updates password hash."""
        service = UsersService(tmp_path)
        service.create_user("testuser", "oldpass", Role.REVIEWER.value)

        # Update password
        updated = service.update_user("testuser", password="newpass")

        assert updated is not None
        # Old password should no longer work
        assert service.authenticate("testuser", "oldpass") is None
        # New password should work
        assert service.authenticate("testuser", "newpass") is not None

    def test_update_user_role(self, tmp_path: Path):
        """Updates role field."""
        service = UsersService(tmp_path)
        service.create_user("testuser", "pass", Role.REVIEWER.value)

        updated = service.update_user("testuser", role=Role.OPERATOR.value)

        assert updated is not None
        assert updated.role == Role.OPERATOR.value

        # Verify persisted
        user = service.get_user("testuser")
        assert user.role == Role.OPERATOR.value

    def test_update_user_not_found(self, tmp_path: Path):
        """Returns None for nonexistent user."""
        service = UsersService(tmp_path)

        result = service.update_user("nonexistent", password="newpass")

        assert result is None

    def test_update_user_invalid_role(self, tmp_path: Path):
        """Returns None for invalid role."""
        service = UsersService(tmp_path)
        service.create_user("testuser", "pass", Role.REVIEWER.value)

        result = service.update_user("testuser", role="invalid_role")

        assert result is None

    def test_update_user_updates_timestamp(self, tmp_path: Path):
        """Updated_at timestamp changes on update."""
        service = UsersService(tmp_path)
        user = service.create_user("testuser", "pass", Role.REVIEWER.value)
        original_updated = user.updated_at

        updated = service.update_user("testuser", role=Role.OPERATOR.value)

        assert updated.updated_at >= original_updated


class TestDeleteUser:
    """Tests for deleting users."""

    def test_delete_user_success(self, tmp_path: Path):
        """Removes user from list."""
        service = UsersService(tmp_path)
        service.create_user("testuser", "pass", Role.REVIEWER.value)

        result = service.delete_user("testuser")

        assert result is True
        assert service.get_user("testuser") is None

    def test_delete_user_not_found(self, tmp_path: Path):
        """Returns False for nonexistent user."""
        service = UsersService(tmp_path)

        result = service.delete_user("nonexistent")

        assert result is False

    def test_delete_last_admin_fails(self, tmp_path: Path):
        """Cannot delete last admin user."""
        service = UsersService(tmp_path)
        # Only 'su' exists as admin

        result = service.delete_user("su")

        assert result is False
        assert service.get_user("su") is not None

    def test_delete_admin_when_other_admins_exist(self, tmp_path: Path):
        """Can delete admin if other admins exist."""
        service = UsersService(tmp_path)
        service.create_user("admin2", "pass", Role.ADMIN.value)

        result = service.delete_user("su")

        assert result is True
        assert service.get_user("su") is None
        # admin2 still exists
        assert service.get_user("admin2") is not None


class TestUserDataclass:
    """Tests for User dataclass."""

    def test_user_to_public_dict(self, tmp_path: Path):
        """to_public_dict excludes password hash."""
        service = UsersService(tmp_path)
        user = service.create_user("testuser", "secret", Role.REVIEWER.value)

        public = user.to_public_dict()

        assert "username" in public
        assert "role" in public
        assert "created_at" in public
        assert "updated_at" in public
        assert "password_hash" not in public
        assert "secret" not in str(public)


class TestPersistence:
    """Tests for file persistence."""

    def test_users_persisted_to_file(self, tmp_path: Path):
        """Users are saved to users.json."""
        service = UsersService(tmp_path)
        service.create_user("testuser", "pass", Role.REVIEWER.value)

        # Read file directly
        users_file = tmp_path / "users.json"
        assert users_file.exists()

        with open(users_file) as f:
            data = json.load(f)

        assert len(data) == 2  # su + testuser
        usernames = [u["username"] for u in data]
        assert "testuser" in usernames

    def test_users_loaded_from_file(self, tmp_path: Path):
        """Users are loaded from existing file."""
        # Create file manually
        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps([
            {
                "username": "existing",
                "password_hash": "somehash",
                "role": "reviewer",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        ]))

        service = UsersService(tmp_path)

        user = service.get_user("existing")
        assert user is not None
        assert user.username == "existing"
