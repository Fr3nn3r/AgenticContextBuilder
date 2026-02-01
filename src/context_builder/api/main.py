"""
FastAPI backend for Extraction QA Console.

Provides endpoints for:
- Listing claims and documents
- Getting document content with extraction results
- Saving human labels
- Re-running extraction
- Run metrics dashboard

File-based storage (no database).

Data structure expected:
  output/claims/{claim_id}/
    docs/{doc_id}/
      meta/doc.json
      text/pages.json
    runs/{run_id}/
      extraction/{doc_id}.json
      logs/summary.json
      labels/{doc_id}.labels.json
"""

import os as _os

# Initialize startup (loads .env and workspace)
from context_builder.startup import ensure_initialized as _ensure_initialized
_ensure_initialized()

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from context_builder.api.dependencies import (
    get_data_dir,
    get_project_root,
    get_staging_dir,
)
from context_builder.api.routers import (
    admin_users as admin_users_router,
    admin_workspaces as admin_workspaces_router,
    auth as auth_router,
    claims as claims_router,
    classification as classification_router,
    compliance as compliance_router,
    documents as documents_router,
    evolution as evolution_router,
    insights as insights_router,
    pipeline as pipeline_router,
    system as system_router,
    upload as upload_router,
)


# =============================================================================
# APP SETUP
# =============================================================================

app = FastAPI(
    title="Extraction QA Console API",
    description="Backend for reviewing and labeling document extractions",
    version="1.0.0",
)

# CORS for React frontend
# In production (Render), frontend is served from same origin, so CORS is less critical
# But we keep localhost for development
_cors_origins = ["http://localhost:5173", "http://localhost:3000"]
if _os.getenv("RENDER_WORKSPACE_PATH"):
    # On Render, allow any onrender.com subdomain for preview deploys
    _cors_origins.append("https://*.onrender.com")

# Support extra origins via env var (e.g. Azure deployment URL)
_extra = _os.getenv("CORS_EXTRA_ORIGINS", "")
if _extra:
    _cors_origins.extend(o.strip() for o in _extra.split(",") if o.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.(onrender\.com|azurewebsites\.net)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# ROUTERS
# =============================================================================

app.include_router(system_router.router)
app.include_router(auth_router.router)
app.include_router(admin_users_router.router)
app.include_router(admin_workspaces_router.router)
app.include_router(claims_router.router)
app.include_router(classification_router.router)
app.include_router(compliance_router.router)
app.include_router(documents_router.router)
app.include_router(evolution_router.router)
app.include_router(insights_router.router)
app.include_router(pipeline_router.router)
app.include_router(upload_router.router)

def _resolve_workspace_path(path: str | Path) -> Path:
    """Resolve a workspace path, handling relative paths.

    Args:
        path: Workspace path (absolute or relative to project root).

    Returns:
        Resolved absolute path.
    """
    workspace_path = Path(path)
    if not workspace_path.is_absolute():
        workspace_path = get_project_root() / workspace_path
    return workspace_path


# =============================================================================
# BACKWARDS COMPATIBILITY
# =============================================================================
# Module-level variables for backwards compatibility with existing imports.
# New code should use get_data_dir() and get_staging_dir() from dependencies.


def __getattr__(name: str):
    """Provide backwards compatibility for DATA_DIR and STAGING_DIR imports."""
    if name == "DATA_DIR":
        return get_data_dir()
    if name == "STAGING_DIR":
        return get_staging_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# =============================================================================
# STATIC FILE SERVING (Production)
# =============================================================================
# Serve React frontend in production when ui/dist exists

_UI_DIST_DIR = get_project_root() / "ui" / "dist"

if _UI_DIST_DIR.exists() and _UI_DIST_DIR.is_dir():
    print(f"[startup] Serving static frontend from {_UI_DIST_DIR}")

    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=_UI_DIST_DIR / "assets"), name="assets")

    # Catch-all route for SPA - must be last
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA for all non-API routes."""
        # Don't intercept API routes or WebSocket
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404)

        # Serve static files from dist root (e.g. images from public/)
        if full_path:
            static_file = (_UI_DIST_DIR / full_path).resolve()
            if static_file.is_relative_to(_UI_DIST_DIR) and static_file.is_file():
                return FileResponse(static_file)

        # Serve index.html for SPA routing
        index_path = _UI_DIST_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path, media_type="text/html")
        raise HTTPException(status_code=404, detail="Frontend not found")
else:
    print(f"[startup] No frontend build found at {_UI_DIST_DIR} (dev mode)")
