"""System endpoints: health check and version info."""

import subprocess
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from context_builder.api.dependencies import get_data_dir, get_project_root


router = APIRouter(tags=["system"])


# =============================================================================
# VERSION INFO
# =============================================================================


def _get_app_version() -> str:
    """Read version from pyproject.toml."""
    pyproject_path = get_project_root() / "pyproject.toml"
    if not pyproject_path.exists():
        return "unknown"

    try:
        content = pyproject_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("version"):
                # Parse: version = "0.1.0"
                parts = line.split("=", 1)
                if len(parts) == 2:
                    return parts[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "unknown"


def _get_git_commit_short() -> Optional[str]:
    """Get short git commit hash (7 chars)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(get_project_root()),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


# Cache version info at module load
_APP_VERSION = _get_app_version()
_GIT_COMMIT = _get_git_commit_short()


class VersionInfo(BaseModel):
    """Application version information."""

    version: str
    git_commit: Optional[str] = None
    display: str  # Formatted for UI display


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("/api/health")
@router.get("/health")  # Keep both for compatibility
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "data_dir": str(get_data_dir())}


@router.get("/api/version", response_model=VersionInfo)
def get_version():
    """Get application version info.

    Returns version from pyproject.toml and git commit hash.
    """
    display = f"v{_APP_VERSION}"
    if _GIT_COMMIT:
        display = f"v{_APP_VERSION} ({_GIT_COMMIT})"

    return VersionInfo(
        version=_APP_VERSION,
        git_commit=_GIT_COMMIT,
        display=display,
    )
