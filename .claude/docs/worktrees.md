# Git Worktrees for Parallel Agent Development

## Overview

This repository uses **git worktrees** to enable multiple AI agents to work on different features simultaneously without conflicts. Each agent works in an isolated directory with its own branch, while sharing the same git history.

## Why Worktrees?

### The Problem
When multiple agents work on the same repository:
- File conflicts arise when agents modify the same files
- Branch switching disrupts in-progress work
- Agents must wait for each other to finish before starting new tasks

### The Solution
Git worktrees create **separate working directories**, each checked out to a different branch:
- **Isolation**: Each agent has its own files - no stepping on each other
- **Parallelism**: Multiple features can be developed simultaneously
- **Shared History**: All worktrees share the same git database - commits are instantly visible across all worktrees
- **Clean Merges**: Each feature branch merges independently when ready

## Current Structure

```
C:\Users\fbrun\Documents\GitHub\
├── AgenticContextBuilder/       # PRIMARY - main branch
├── AgenticContextBuilder-wt1/   # Worktree slot 1
├── AgenticContextBuilder-wt2/   # Worktree slot 2
└── AgenticContextBuilder-wt3/   # Worktree slot 3
```

| Directory | Purpose | Default Branch |
|-----------|---------|----------------|
| `AgenticContextBuilder/` | Primary repo, main branch, releases | `main` |
| `AgenticContextBuilder-wt1/` | Feature work slot 1 | `worktree/slot-1` |
| `AgenticContextBuilder-wt2/` | Feature work slot 2 | `worktree/slot-2` |
| `AgenticContextBuilder-wt3/` | Feature work slot 3 | `worktree/slot-3` |

## Agent Instructions

### 1. Identify Your Worktree

When you start a session, check your working directory:

```bash
pwd
# Should show something like:
# C:/Users/fbrun/Documents/GitHub/AgenticContextBuilder-wt1
```

**Critical**: Confirm you are in the correct worktree before making changes. If you're in the wrong directory, ask the user to redirect you.

### 2. Check Your Branch Status

At the start of any session:

```bash
git status
git branch --show-current
git log --oneline -5
```

This tells you:
- What branch you're on
- Whether there are uncommitted changes from a previous session
- Recent commit history

### 3. Starting New Work

If the slot has a generic branch name (`worktree/slot-N`), rename it to describe your task:

```bash
# First, ensure you're up to date with main
git fetch origin
git rebase origin/main

# Rename the branch to describe your feature
git branch -m worktree/slot-1 feature/add-export-functionality
```

### 4. During Development

Work normally - edit files, run tests, commit changes:

```bash
# Stage and commit your changes frequently
git add -A
git commit -m "feat: add CSV export option"

# Run tests from your worktree
python -m pytest tests/unit/ --no-cov -q
cd ui && npm run dev  # if working on frontend
```

### 5. Syncing with Main

Periodically sync with main to avoid drift:

```bash
git fetch origin
git rebase origin/main
```

If there are conflicts, resolve them before continuing.

### 6. When Work is Complete

When your feature is done and tested:

1. **Push your branch** (if you have push access):
   ```bash
   git push -u origin feature/add-export-functionality
   ```

2. **Notify the user** that the feature is ready for review/merge

3. **Do NOT merge to main yourself** - let the user control merges to the primary branch

### 7. Resetting a Slot for Reuse

After a feature is merged, reset the slot for the next task:

```bash
# Switch back to main and update
git checkout main
git pull origin main

# Create a new generic branch for the slot
git checkout -b worktree/slot-1

# Delete the old feature branch (if merged)
git branch -d feature/add-export-functionality
```

## Important Rules for Agents

### DO:
- Always verify your working directory at session start
- Commit frequently with descriptive messages
- Run tests before considering work complete
- Keep the user informed of your progress
- Ask if unsure which worktree you should use

### DO NOT:
- Switch to a different worktree without user permission
- Merge branches to main without explicit user approval
- Push to remote without user permission (unless clearly authorized)
- Delete branches without user confirmation
- Assume your worktree - always verify

## Useful Commands Reference

```bash
# List all worktrees
git worktree list

# See which branch each worktree is on
git worktree list --porcelain

# Check status across all branches
git branch -vv

# See if your branch is ahead/behind main
git log main..HEAD --oneline    # commits you have that main doesn't
git log HEAD..main --oneline    # commits main has that you don't

# Fetch latest from remote without changing your files
git fetch origin
```

## Handling Common Scenarios

### Scenario: Previous Agent Left Uncommitted Changes

```bash
git status
# If there are changes, review them:
git diff

# Option A: Commit them if they look good
git add -A && git commit -m "WIP: continue previous work"

# Option B: Stash them if you need to start fresh
git stash push -m "Previous agent WIP"

# Option C: Discard if they're not needed (ask user first!)
git checkout -- .
```

### Scenario: Your Branch Has Diverged from Main

```bash
git fetch origin
git rebase origin/main
# Resolve any conflicts, then:
git rebase --continue
```

### Scenario: Need to See What Other Agents Are Working On

```bash
# From any worktree, see all branches
git branch -a

# See recent commits across all branches
git log --all --oneline --graph -20
```

### Scenario: Wrong Worktree

If you discover you're in the wrong worktree:
1. Stop immediately
2. Do not make changes
3. Ask the user which worktree you should be using
4. The user will redirect you to the correct directory

## Port Assignments (MANDATORY)

Each worktree has **dedicated ports** to prevent conflicts and ensure you're testing your own code:

| Worktree | Backend Port | Frontend Port | Frontend API Target |
|----------|--------------|---------------|---------------------|
| Main (AgenticContextBuilder) | 8000 | 5173 | http://localhost:8000 |
| wt1 | 8001 | 5174 | http://localhost:8001 |
| wt2 | 8002 | 5175 | http://localhost:8002 |
| wt3 | 8003 | 5176 | http://localhost:8003 |

### Starting Dev Servers in Your Worktree

**CRITICAL**: Always use YOUR assigned ports. Never use another worktree's ports.

#### Automated Startup (Recommended)

Each worktree has a startup script that handles port configuration automatically:

```powershell
# Start both backend and frontend
.\scripts\start-dev.ps1

# Start only backend
.\scripts\start-dev.ps1 -BackendOnly

# Start only frontend
.\scripts\start-dev.ps1 -FrontendOnly

# Stop all dev servers for this worktree
.\scripts\start-dev.ps1 -Stop
```

The script:
- Auto-detects which worktree you're in
- Uses the correct ports from the table above
- Opens separate terminal windows for each server
- Checks if servers are already running

#### Configuration Files

Each worktree has a `ui/.env` file with its port settings:
```
# Example: ui/.env for wt1
VITE_PORT=5174
VITE_API_PORT=8001
```

The `vite.config.ts` automatically reads from this `.env` file.

#### Manual Startup (if needed)

```powershell
# Backend (from repo root)
python -m uvicorn context_builder.api.main:app --reload --port <backend-port>

# Frontend (from ui folder) - reads ports from .env
cd ui
npm run dev
```

### Verification Checklist Before Testing

1. ✅ Confirm your worktree: `pwd`
2. ✅ Check your assigned ports in the table above
3. ✅ Verify backend is running on YOUR port: `curl http://localhost:800X/health`
4. ✅ Verify frontend is pointing to YOUR backend (check browser dev tools Network tab)

### Why This Matters

- Testing on the wrong server = testing wrong code = false results
- Each worktree is a separate codebase - ports must match
- Never assume - always verify before testing

## Frontend Development Notes

Each worktree needs its own `node_modules` for the UI:

```bash
cd ui
npm install
```

Then start with your assigned ports (see Port Assignments above).

## Summary

| Task | Command |
|------|---------|
| Verify worktree | `pwd && git branch --show-current` |
| Start new feature | `git branch -m worktree/slot-N feature/your-feature` |
| Sync with main | `git fetch origin && git rebase origin/main` |
| See all worktrees | `git worktree list` |
| Reset slot | `git checkout main && git pull && git checkout -b worktree/slot-N` |
