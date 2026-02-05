---
name: backlog
description: "Manage project backlog (plans/backlog.json). Use /backlog status, /backlog add, /backlog doing, /backlog done, /backlog priorities, /backlog search, /backlog clean, or /backlog import."
argument-hint: "[status|add|doing|done|priorities|search|clean|import] [args...]"
allowed-tools: Read, Write, Edit, Glob, Bash(python *)
---

# Backlog Manager

**Action requested**: $ARGUMENTS

Manage the project backlog stored in `plans/backlog.json`.

## Data file

`plans/backlog.json` — JSON with `meta` (schema_version, created, last_modified, archive_after_days) and `items` array.

Each item has: `id`, `title`, `description`, `status` (todo|doing|done), `priority` (P0–P9), `category`, `effort` (low|medium|high), `plan_file`, `created`, `started`, `completed`, `notes`, `tags`.

## Commands

### `/backlog` or `/backlog status`

1. Read `plans/backlog.json`
2. Show all items with status `doing` (with their ID, title, priority, started date)
3. Show top 10 `todo` items sorted by priority (P0 first)
4. Show summary stats: total items, by status counts, by priority distribution

### `/backlog add "title" [priority] [category]`

1. Read `plans/backlog.json`
2. Generate ID using category prefix mapping (see below) + next number in sequence
3. Add new item with status=todo, created=now, default priority=P5 if not specified, default category=feature
4. Write back to `plans/backlog.json`
5. Confirm the new item

### `/backlog doing ID`

1. Read `plans/backlog.json`
2. Find item by ID (case-insensitive)
3. Set status=doing, started=now (ISO timestamp)
4. Write back and confirm

### `/backlog done ID [notes]`

1. Read `plans/backlog.json`
2. Find item by ID (case-insensitive)
3. Set status=done, completed=now (ISO timestamp), append notes if provided
4. Write back and confirm

### `/backlog priorities`

1. Read `plans/backlog.json`
2. Show all `todo` items grouped by priority (P0, P1, ... P9)
3. Within each group, sort alphabetically by title

### `/backlog search "term"`

1. Read `plans/backlog.json`
2. Search across title, description, notes, and tags (case-insensitive)
3. Show matching items with their status and priority

### `/backlog clean`

1. Read `plans/backlog.json`
2. Find `done` items where completed date is older than `meta.archive_after_days` (default 14)
3. Remove them from items array
4. Write back and report how many items were archived

### `/backlog import`

**One-time migration from BACKLOG.md to JSON.**

1. Check if `plans/backlog.json` already has items — if so, warn and skip (unless user confirms override)
2. Read `BACKLOG.md`
3. Parse items from Doing, Todo, and Done sections
4. Apply migration rules:
   - "Doing" items marked `COMPLETE` → status: done
   - "Doing" items not complete → status: doing
   - "Todo" items → status: todo
   - "Done (Recent)" items → status: done
   - Priority from section heading (P0, P1, etc.) or P5 default
   - Category inferred from ID prefix
   - Effort from description if mentioned, else medium
5. Write `plans/backlog.json`
6. Report migration stats

## ID prefix mapping

| Category | Prefix |
|----------|--------|
| feature | FEAT- |
| security | SEC- |
| discussion | DISC- |
| refactoring | REFACTOR- |
| performance | PERF- |
| infrastructure | INFRA- |
| bug | BUG- |
| fe-security | FE-SEC- |
| fe-performance | FE-PERF- |
| fe-refactoring | FE-REFACTOR- |
| fe-accessibility | FE-A11Y- |

## Rules

- Always update `meta.last_modified` on any write
- Use ISO 8601 timestamps (e.g., `2026-02-05T14:30:00Z`)
- Keep JSON formatted with 2-space indent
- When generating new IDs, scan all existing items to find the max number for that prefix
- Read the file fresh before every operation (don't cache)
