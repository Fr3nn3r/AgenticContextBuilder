"""FastAPI routers for the Extraction QA Console API.

Each router handles a specific domain of endpoints:
- system: Health check, version info
- auth: Login, logout, current user
- admin_users: User management (admin only)
- admin_workspaces: Workspace management (admin only)
- claims: Claims listing and details
- documents: Document endpoints
- pipeline: Pipeline execution and status
- insights: Analysis and insights
- classification: Document classification
- upload: File uploads
- compliance: Audit and compliance logs
- evolution: Schema evolution
- token_costs: Token usage tracking
"""
