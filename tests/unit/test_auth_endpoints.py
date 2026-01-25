"""Unit tests for authentication and admin API endpoints."""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


# Helper to patch service instances for testing
@pytest.fixture
def test_app(tmp_path: Path):
    """Create a test FastAPI app with isolated auth services."""
    from context_builder.api.services.users import UsersService
    from context_builder.api.services.auth import AuthService

    # Create test services with temp directory
    users_service = UsersService(tmp_path)
    auth_service = AuthService(tmp_path, users_service)

    # Patch in dependencies and routers (for endpoints)
    with patch("context_builder.api.dependencies.get_users_service", return_value=users_service), \
         patch("context_builder.api.dependencies.get_auth_service", return_value=auth_service), \
         patch("context_builder.api.routers.auth.get_auth_service", return_value=auth_service), \
         patch("context_builder.api.routers.admin_users.get_users_service", return_value=users_service), \
         patch("context_builder.api.routers.admin_users.get_auth_service", return_value=auth_service):
        from context_builder.api.main import app
        yield TestClient(app), users_service, auth_service


class TestLoginEndpoint:
    """Tests for POST /api/auth/login."""

    def test_login_success(self, test_app):
        """Returns token and user on successful login."""
        client, users_service, auth_service = test_app

        response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["username"] == "su"
        assert data["user"]["role"] == "admin"

    def test_login_invalid_password(self, test_app):
        """Returns 401 for invalid password."""
        client, users_service, auth_service = test_app

        response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "wrongpassword"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Invalid" in data["detail"]

    def test_login_nonexistent_user(self, test_app):
        """Returns 401 for nonexistent user."""
        client, users_service, auth_service = test_app

        response = client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": "anypassword"},
        )

        assert response.status_code == 401


class TestLogoutEndpoint:
    """Tests for POST /api/auth/logout."""

    def test_logout_success(self, test_app):
        """Logout with valid token returns success."""
        client, users_service, auth_service = test_app

        # Login first
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Logout
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_logout_no_token(self, test_app):
        """Logout without token still succeeds."""
        client, users_service, auth_service = test_app

        response = client.post("/api/auth/logout")

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_logout_invalid_token(self, test_app):
        """Logout with invalid token still succeeds."""
        client, users_service, auth_service = test_app

        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_logout_invalidates_token(self, test_app):
        """Token is no longer valid after logout."""
        client, users_service, auth_service = test_app

        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Verify token works
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_response.status_code == 200

        # Logout
        client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify token no longer works
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_response.status_code == 401


class TestMeEndpoint:
    """Tests for GET /api/auth/me."""

    def test_me_authenticated(self, test_app):
        """Returns current user info for valid token."""
        client, users_service, auth_service = test_app

        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Get current user
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "su"
        assert data["role"] == "admin"

    def test_me_unauthenticated(self, test_app):
        """Returns 401 without token."""
        client, users_service, auth_service = test_app

        response = client.get("/api/auth/me")

        assert response.status_code == 401

    def test_me_invalid_token(self, test_app):
        """Returns 401 for invalid token."""
        client, users_service, auth_service = test_app

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )

        assert response.status_code == 401

    def test_me_expired_token(self, test_app, tmp_path: Path):
        """Returns 401 for expired token."""
        client, users_service, auth_service = test_app

        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Manually expire the session
        sessions_file = tmp_path / "sessions.json"
        with open(sessions_file) as f:
            data = json.load(f)

        past_time = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        data[token]["expires_at"] = past_time

        with open(sessions_file, "w") as f:
            json.dump(data, f)

        # Try to use expired token
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401


class TestListUsersEndpoint:
    """Tests for GET /api/admin/users."""

    def test_list_users_as_admin(self, test_app):
        """Admin can list all users."""
        client, users_service, auth_service = test_app

        # Create some users
        users_service.create_user("reviewer1", "pass", "reviewer")
        users_service.create_user("operator1", "pass", "operator")

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # List users
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        users = response.json()
        assert len(users) == 6  # 4 defaults (su, ted, seb, tod) + reviewer1 + operator1
        usernames = [u["username"] for u in users]
        assert "su" in usernames
        assert "reviewer1" in usernames
        assert "operator1" in usernames

    def test_list_users_as_non_admin(self, test_app):
        """Non-admin gets 403."""
        client, users_service, auth_service = test_app

        # Create a reviewer
        users_service.create_user("reviewer1", "pass", "reviewer")

        # Login as reviewer
        login_response = client.post(
            "/api/auth/login",
            json={"username": "reviewer1", "password": "pass"},
        )
        token = login_response.json()["token"]

        # Try to list users
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    def test_list_users_unauthenticated(self, test_app):
        """Unauthenticated gets 401."""
        client, users_service, auth_service = test_app

        response = client.get("/api/admin/users")

        assert response.status_code == 401


class TestCreateUserEndpoint:
    """Tests for POST /api/admin/users."""

    def test_create_user_as_admin(self, test_app):
        """Admin can create a new user."""
        client, users_service, auth_service = test_app

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Create user
        response = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": "newuser", "password": "newpass", "role": "reviewer"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert data["role"] == "reviewer"
        assert "password" not in data
        assert "password_hash" not in data

    def test_create_user_duplicate(self, test_app):
        """Returns 400 for duplicate username."""
        client, users_service, auth_service = test_app

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Create user
        client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": "testuser", "password": "pass", "role": "reviewer"},
        )

        # Try to create duplicate
        response = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": "testuser", "password": "pass2", "role": "operator"},
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_user_invalid_role(self, test_app):
        """Returns 400 for invalid role."""
        client, users_service, auth_service = test_app

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Try to create user with invalid role
        response = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": "testuser", "password": "pass", "role": "invalid_role"},
        )

        assert response.status_code == 400
        assert "Invalid role" in response.json()["detail"]


class TestUpdateUserEndpoint:
    """Tests for PUT /api/admin/users/{username}."""

    def test_update_user_as_admin(self, test_app):
        """Admin can update user."""
        client, users_service, auth_service = test_app

        # Create a user
        users_service.create_user("testuser", "oldpass", "reviewer")

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Update user role
        response = client.put(
            "/api/admin/users/testuser",
            headers={"Authorization": f"Bearer {token}"},
            json={"role": "operator"},
        )

        assert response.status_code == 200
        assert response.json()["role"] == "operator"

    def test_update_user_not_found(self, test_app):
        """Returns 404 for nonexistent user."""
        client, users_service, auth_service = test_app

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Try to update nonexistent user
        response = client.put(
            "/api/admin/users/nonexistent",
            headers={"Authorization": f"Bearer {token}"},
            json={"role": "operator"},
        )

        assert response.status_code == 404

    def test_update_self_demotion_blocked(self, test_app):
        """Cannot demote self from admin."""
        client, users_service, auth_service = test_app

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Try to demote self
        response = client.put(
            "/api/admin/users/su",
            headers={"Authorization": f"Bearer {token}"},
            json={"role": "reviewer"},
        )

        assert response.status_code == 400
        assert "demote yourself" in response.json()["detail"]

    def test_update_user_password(self, test_app):
        """Can update user password."""
        client, users_service, auth_service = test_app

        # Create a user
        users_service.create_user("testuser", "oldpass", "reviewer")

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Update user password
        response = client.put(
            "/api/admin/users/testuser",
            headers={"Authorization": f"Bearer {token}"},
            json={"password": "newpass"},
        )

        assert response.status_code == 200

        # Verify old password no longer works
        old_login = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "oldpass"},
        )
        assert old_login.status_code == 401

        # Verify new password works
        new_login = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "newpass"},
        )
        assert new_login.status_code == 200


class TestDeleteUserEndpoint:
    """Tests for DELETE /api/admin/users/{username}."""

    def test_delete_user_as_admin(self, test_app):
        """Admin can delete user."""
        client, users_service, auth_service = test_app

        # Create a user
        users_service.create_user("testuser", "pass", "reviewer")

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Delete user
        response = client.delete(
            "/api/admin/users/testuser",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify user is deleted
        assert users_service.get_user("testuser") is None

    def test_delete_self_blocked(self, test_app):
        """Cannot delete self."""
        client, users_service, auth_service = test_app

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Try to delete self
        response = client.delete(
            "/api/admin/users/su",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        assert "delete yourself" in response.json()["detail"]

    def test_delete_last_admin_blocked(self, test_app):
        """Cannot delete last admin via service."""
        client, users_service, auth_service = test_app

        # Create another admin
        users_service.create_user("admin2", "pass", "admin")

        # Login as admin2
        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin2", "password": "pass"},
        )
        token = login_response.json()["token"]

        # Delete su (should work - admin2 still exists)
        response = client.delete(
            "/api/admin/users/su",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        # Now try to delete admin2 (as admin2, should fail - can't delete self)
        response = client.delete(
            "/api/admin/users/admin2",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    def test_delete_user_not_found(self, test_app):
        """Returns 400 for nonexistent user."""
        client, users_service, auth_service = test_app

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        token = login_response.json()["token"]

        # Try to delete nonexistent user
        response = client.delete(
            "/api/admin/users/nonexistent",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_delete_user_invalidates_sessions(self, test_app):
        """Deleted user's sessions are invalidated."""
        client, users_service, auth_service = test_app

        # Create a user
        users_service.create_user("testuser", "pass", "reviewer")

        # Login as testuser to create a session
        testuser_login = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "pass"},
        )
        testuser_token = testuser_login.json()["token"]

        # Verify session works
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {testuser_token}"},
        )
        assert me_response.status_code == 200

        # Login as admin
        admin_login = client.post(
            "/api/auth/login",
            json={"username": "su", "password": "su"},
        )
        admin_token = admin_login.json()["token"]

        # Delete testuser
        client.delete(
            "/api/admin/users/testuser",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Verify testuser's session is invalid
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {testuser_token}"},
        )
        assert me_response.status_code == 401


class TestRoleBasedAccess:
    """Tests for role-based access across different roles."""

    @pytest.mark.parametrize("role", ["reviewer", "operator", "auditor"])
    def test_non_admin_cannot_manage_users(self, test_app, role):
        """Non-admin roles cannot access admin endpoints."""
        client, users_service, auth_service = test_app

        # Create user with role
        users_service.create_user(f"{role}user", "pass", role)

        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"username": f"{role}user", "password": "pass"},
        )
        token = login_response.json()["token"]

        # Try to list users
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

        # Try to create user
        response = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": "newuser", "password": "pass", "role": "reviewer"},
        )
        assert response.status_code == 403

        # Try to update user
        response = client.put(
            "/api/admin/users/su",
            headers={"Authorization": f"Bearer {token}"},
            json={"role": "reviewer"},
        )
        assert response.status_code == 403

        # Try to delete user
        response = client.delete(
            "/api/admin/users/su",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
