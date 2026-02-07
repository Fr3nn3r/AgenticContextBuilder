# MVP Workspace Permissions Spec

Minimal permission model for workspace-scoped screen access. Two hardcoded roles, no custom permission editor.

## Requirements

- Reviewer role can access only: New Claim, Evaluation, Claim Explorer, Compliance
- Admin role has full access per workspace
- System already has full workspace isolation

## MVP Scope

- Screen-level access control only
- Two hardcoded roles: `admin` and `reviewer`
- No permission management UI (roles are fixed)
- Enforce access in both UI and API

---

## Permission Model

### Hardcoded Role Definitions

```python
# Single source of truth - backend config
ROLE_SCREENS = {
    "admin": ["*"],  # All screens
    "reviewer": ["new_claim", "evaluation", "claim_explorer", "compliance"]
}

SCREEN_KEYS = [
    "new_claim",
    "evaluation",
    "claim_explorer",
    "compliance",
    "documents",
    "insights",
    "admin_users",
    "admin_workspaces"
]
```

### User-Workspace Assignment

Each user has a role per workspace. Stored in existing user/workspace data:

```json
{
  "user_id": "user-123",
  "workspace_id": "ws-456",
  "role": "reviewer"
}
```

No separate permission tables needed.

---

## UI Enforcement

### Sidebar Filtering

```typescript
// Frontend filters nav items based on role from /api/auth/me
const allowedScreens = user.role === 'admin'
  ? ALL_SCREENS
  : ['new_claim', 'evaluation', 'claim_explorer', 'compliance'];

// Only render nav items where screen is in allowedScreens
```

### Route Guards

- If user navigates to blocked screen, redirect to first allowed screen
- Show brief toast: "Access not available"

---

## API Enforcement

### Auth Response

`GET /api/auth/me` returns:

```json
{
  "user_id": "user-123",
  "workspace_id": "ws-456",
  "role": "reviewer",
  "allowed_screens": ["new_claim", "evaluation", "claim_explorer", "compliance"]
}
```

### Protected Routes

Simple decorator check:

```python
@require_screen("compliance")
def get_compliance_logs():
    ...
```

If role doesn't include screen, return 403.

---

## What's NOT in MVP

- No permission management UI (roles are fixed)
- No custom role creation
- No action-level permissions (approve, export, etc.)
- No per-workspace role customization
- No audit log of permission changes (nothing changes)

These can be added later if customers request custom roles.

---

## Implementation Checklist

1. [ ] Add `role` field to user-workspace assignment
2. [ ] Update `/api/auth/me` to return `role` and `allowed_screens`
3. [ ] Add `require_screen()` decorator for protected API routes
4. [ ] Filter sidebar nav items in frontend based on `allowed_screens`
5. [ ] Add route guard redirect for blocked screens

Estimated scope: ~100 lines backend, ~50 lines frontend.
