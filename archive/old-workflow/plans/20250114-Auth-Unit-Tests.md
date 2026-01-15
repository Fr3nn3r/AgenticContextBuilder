# Unit Testing Plan: Authentication & Permissions

## Overview

Unit tests for the authentication and permissions MVP implemented in the codebase.

**Files to Test:**
- `src/context_builder/api/services/users.py` - User CRUD and password hashing
- `src/context_builder/api/services/auth.py` - Session management
- `src/context_builder/api/main.py` - Auth and admin API endpoints

## Test Files to Create

### 1. `tests/unit/test_users_service.py`

**Test Class: `TestUsersService`**

| Test | Description |
|------|-------------|
| `test_init_creates_default_superuser` | First init creates `su` user with admin role |
| `test_init_does_not_overwrite_existing_users` | Second init preserves existing users |
| `test_hash_password_is_deterministic` | Same password produces same hash |
| `test_verify_password_correct` | Correct password returns True |
| `test_verify_password_incorrect` | Wrong password returns False |
| `test_create_user_success` | Creates user with correct fields |
| `test_create_user_duplicate_fails` | Duplicate username returns None |
| `test_create_user_invalid_role_fails` | Invalid role returns None |
| `test_get_user_exists` | Returns user object for existing user |
| `test_get_user_not_found` | Returns None for nonexistent user |
| `test_list_users_returns_all` | Returns all users in list |
| `test_authenticate_valid_credentials` | Returns user for valid login |
| `test_authenticate_invalid_password` | Returns None for wrong password |
| `test_authenticate_nonexistent_user` | Returns None for unknown user |
| `test_update_user_password` | Updates password hash |
| `test_update_user_role` | Updates role field |
| `test_update_user_not_found` | Returns None for nonexistent user |
| `test_delete_user_success` | Removes user from list |
| `test_delete_user_not_found` | Returns False for nonexistent user |
| `test_delete_last_admin_fails` | Cannot delete last admin user |

### 2. `tests/unit/test_auth_service.py`

**Test Class: `TestAuthService`**

| Test | Description |
|------|-------------|
| `test_login_valid_credentials` | Returns (token, user) tuple |
| `test_login_invalid_credentials` | Returns None |
| `test_login_creates_session_file` | Session persisted to sessions.json |
| `test_validate_session_valid_token` | Returns user for valid token |
| `test_validate_session_invalid_token` | Returns None for unknown token |
| `test_validate_session_expired` | Returns None for expired token |
| `test_validate_session_deleted_user` | Returns None if user was deleted |
| `test_logout_removes_session` | Token no longer valid after logout |
| `test_logout_nonexistent_token` | Returns False gracefully |
| `test_session_cleanup_on_validate` | Expired sessions removed during validate |
| `test_invalidate_user_sessions` | All sessions for user removed |
| `test_get_user_sessions` | Returns active sessions for user |

### 3. `tests/unit/test_auth_endpoints.py`

**Test Class: `TestAuthEndpoints`** (using FastAPI TestClient)

| Test | Description |
|------|-------------|
| `test_login_success` | POST /api/auth/login returns token + user |
| `test_login_invalid_credentials` | Returns 401 with error message |
| `test_logout_success` | POST /api/auth/logout returns success |
| `test_logout_no_token` | Logout without token still succeeds |
| `test_me_authenticated` | GET /api/auth/me returns current user |
| `test_me_unauthenticated` | GET /api/auth/me returns 401 |
| `test_me_expired_token` | GET /api/auth/me returns 401 for expired |

**Test Class: `TestAdminEndpoints`**

| Test | Description |
|------|-------------|
| `test_list_users_as_admin` | GET /api/admin/users returns user list |
| `test_list_users_as_non_admin` | Returns 403 for reviewer/operator/auditor |
| `test_list_users_unauthenticated` | Returns 401 |
| `test_create_user_as_admin` | POST /api/admin/users creates user |
| `test_create_user_duplicate` | Returns 400 for duplicate username |
| `test_create_user_invalid_role` | Returns 400 for invalid role |
| `test_update_user_as_admin` | PUT /api/admin/users/{username} updates |
| `test_update_user_not_found` | Returns 404 for nonexistent user |
| `test_update_self_demotion_blocked` | Cannot demote self from admin |
| `test_delete_user_as_admin` | DELETE /api/admin/users/{username} works |
| `test_delete_self_blocked` | Cannot delete own account |
| `test_delete_last_admin_blocked` | Returns 400 for last admin |

## Implementation Details

### Fixtures (`tests/conftest.py` additions)

```python
@pytest.fixture
def auth_config_dir(tmp_path):
    """Isolated config directory for auth tests."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir

@pytest.fixture
def users_service(auth_config_dir):
    """Fresh UsersService instance."""
    from context_builder.api.services.users import UsersService
    return UsersService(auth_config_dir)

@pytest.fixture
def auth_service(auth_config_dir, users_service):
    """Fresh AuthService instance."""
    from context_builder.api.services.auth import AuthService
    return AuthService(auth_config_dir, users_service)

@pytest.fixture
def test_client(auth_config_dir):
    """FastAPI TestClient with isolated auth services."""
    from fastapi.testclient import TestClient
    from context_builder.api.main import app
    # Patch the service getters to use test instances
    with patch(...):
        yield TestClient(app)
```

### Mocking Strategy

1. **UsersService tests**: Use `tmp_path` fixture for isolated file storage
2. **AuthService tests**: Use `tmp_path` + mock `UsersService` where needed
3. **Endpoint tests**: Use `TestClient` + patch service getters

### Test Data

```python
# Sample users for testing
ADMIN_USER = {"username": "admin", "password": "admin123", "role": "admin"}
REVIEWER_USER = {"username": "reviewer", "password": "rev123", "role": "reviewer"}
OPERATOR_USER = {"username": "operator", "password": "op123", "role": "operator"}
AUDITOR_USER = {"username": "auditor", "password": "aud123", "role": "auditor"}
```

## Verification

### Run Tests
```bash
# Run all auth tests
pytest tests/unit/test_users_service.py tests/unit/test_auth_service.py tests/unit/test_auth_endpoints.py -v

# Run with coverage
pytest tests/unit/test_*_service.py tests/unit/test_auth_endpoints.py --cov=src/context_builder/api/services --cov-report=term-missing
```

### Expected Coverage
- `users.py`: 90%+ (all CRUD paths)
- `auth.py`: 90%+ (all session paths)
- Auth endpoints in `main.py`: 80%+ (all endpoint handlers)

## Notes

- Tests use `tmp_path` fixture to avoid file permission issues on Windows
- Session expiry tests may need to mock `datetime.utcnow()`
- FastAPI TestClient handles async endpoints synchronously
