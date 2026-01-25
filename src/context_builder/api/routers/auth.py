"""Authentication endpoints: login, logout, current user."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from context_builder.api.dependencies import (
    CurrentUser,
    get_auth_service,
    get_current_user,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class LoginRequest(BaseModel):
    """Login request body."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response body."""

    token: str
    user: CurrentUser


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """
    Authenticate user and create session.

    Returns token and user info on success.
    """
    auth_service = get_auth_service()
    result = auth_service.login(request.username, request.password)

    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token, user = result
    return LoginResponse(
        token=token,
        user=CurrentUser(username=user.username, role=user.role),
    )


@router.post("/logout")
def logout(authorization: Optional[str] = Header(None)):
    """
    Logout user and invalidate session.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return {"success": True}  # Already logged out

    token = authorization[7:]
    auth_service = get_auth_service()
    auth_service.logout(token)
    return {"success": True}


@router.get("/me", response_model=CurrentUser)
def get_me(current_user: CurrentUser = Depends(get_current_user)):
    """
    Get current authenticated user info.
    """
    return current_user
