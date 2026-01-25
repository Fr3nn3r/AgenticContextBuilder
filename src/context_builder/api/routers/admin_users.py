"""Admin user management endpoints: CRUD operations for users."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from context_builder.api.dependencies import (
    CurrentUser,
    get_auth_service,
    get_users_service,
    require_admin,
)
from context_builder.api.services import Role


router = APIRouter(prefix="/api/admin/users", tags=["admin"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class UserResponse(BaseModel):
    """User response body (without password)."""

    username: str
    role: str
    created_at: str
    updated_at: str


class CreateUserRequest(BaseModel):
    """Create user request body."""

    username: str
    password: str
    role: str = "reviewer"


class UpdateUserRequest(BaseModel):
    """Update user request body."""

    password: Optional[str] = None
    role: Optional[str] = None


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("", response_model=List[UserResponse])
def list_users(current_user: CurrentUser = Depends(require_admin)):
    """
    List all users. Requires admin role.
    """
    users_service = get_users_service()
    users = users_service.list_users()
    return [UserResponse(**u.to_public_dict()) for u in users]


@router.post("", response_model=UserResponse)
def create_user(
    request: CreateUserRequest,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Create a new user. Requires admin role.
    """
    users_service = get_users_service()

    # Validate role
    valid_roles = [r.value for r in Role]
    if request.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}",
        )

    user = users_service.create_user(
        username=request.username,
        password=request.password,
        role=request.role,
    )

    if not user:
        raise HTTPException(status_code=400, detail="Username already exists")

    return UserResponse(**user.to_public_dict())


@router.put("/{username}", response_model=UserResponse)
def update_user(
    username: str,
    request: UpdateUserRequest,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Update an existing user. Requires admin role.

    Cannot demote self from admin.
    """
    # Prevent self-demotion from admin
    if username == current_user.username and request.role and request.role != Role.ADMIN.value:
        raise HTTPException(status_code=400, detail="Cannot demote yourself from admin")

    users_service = get_users_service()
    user = users_service.update_user(
        username=username,
        password=request.password,
        role=request.role,
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # If password was changed, invalidate user's sessions (except if updating self)
    if request.password and username != current_user.username:
        auth_service = get_auth_service()
        auth_service.invalidate_user_sessions(username)

    return UserResponse(**user.to_public_dict())


@router.delete("/{username}")
def delete_user(
    username: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Delete a user. Requires admin role.

    Cannot delete self or last admin.
    """
    if username == current_user.username:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    users_service = get_users_service()
    success = users_service.delete_user(username)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="User not found or cannot delete (last admin)",
        )

    # Invalidate deleted user's sessions
    auth_service = get_auth_service()
    auth_service.invalidate_user_sessions(username)

    return {"success": True, "username": username}
