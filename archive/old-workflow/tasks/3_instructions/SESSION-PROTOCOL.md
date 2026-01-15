# Session Protocol for Multi-Window/Agent Coordination

This document defines how to manage Claude Code sessions across multiple windows, worktrees, and agents.

---

## Core Principles

1. **Tasks are persistent, context is ephemeral** - All important state lives in task files, not context windows
2. **One owner per task** - Only one window/agent works on a task at a time
3. **Handoff before clear** - Always write handoff notes before clearing context
4. **File-based coordination** - Use files (not memory) to coordinate between sessions

---

## Session Lifecycle

### Starting a Session

1. **Identify what to work on**:
   ```
   > Read tasks/1_in-progress/ to see active work
   > Read tasks/0_todo/ to pick new work
   ```

2. **Claim a task** (for new work):
   - Move file from `0_todo/` to `1_in-progress/`
   - Set `Owner: [your-window-id]` in the task file
   - Set `Status: in_progress`

3. **Resume a task** (for continuing work):
   - Read the task file's "Handoff Notes" section
   - Follow "Resume Instructions"
   - Add new Progress Log entry

### During a Session

1. **Update progress regularly**:
   - Add Progress Log entries for significant milestones
   - Update Acceptance Criteria checkboxes as completed

2. **Monitor context usage**:
   - Use `/context` to check usage
   - At 50%+ context: consider whether to checkpoint
   - At 70%+ context: definitely write handoff and consider clearing

3. **Track blockers immediately**:
   - Add to Progress Log with `Blocked:` prefix
   - Update Status to `blocked` if work cannot continue

### Ending a Session

**Before clearing context or closing window:**

1. Update the task file:
   - Fill "Handoff Notes" section completely
   - Update "Last Session" timestamp
   - List all files modified
   - Write clear "Resume Instructions"

2. Update task status:
   - If done: Move to `2_done/`, set `Status: done`
   - If pausing: Keep in `1_in-progress/`, ensure handoff is complete
   - If blocked: Set `Status: blocked`, document blocker

3. Commit task file changes:
   ```
   git add tasks/
   git commit -m "Update task status: [task-name]"
   ```

---

## Multi-Window Coordination

### Option A: Branch Isolation (Recommended for independent features)

```
Window 1: main branch          -> small fixes, reviews
Window 2: feature/auth         -> auth system work
Window 3: feature/dashboard    -> dashboard work
```

**Setup**:
```powershell
# From main repo
./scripts/worktree-new.ps1 auth
./scripts/worktree-new.ps1 dashboard

# Each window opens its own worktree folder
# Changes are isolated until merged
```

**Coordination**:
- Each worktree has its own copy of files
- No conflicts during development
- Merge via PR when ready

### Option B: File Locking (For shared-branch work)

When multiple windows must work on the same branch:

1. **Claim files in task**:
   ```markdown
   **Locked Files** (do not edit in other windows):
   - src/auth/*
   - src/api/routes/auth.py
   ```

2. **Check before editing**:
   - Read active tasks in `1_in-progress/`
   - Check "Locked Files" sections
   - If conflict: coordinate with owner or wait

3. **Release when done**:
   - Remove "Locked Files" section
   - Commit changes
   - Update task status

---

## When to Clear vs Continue

| Situation | Action | Why |
|-----------|--------|-----|
| Task complete, context >50% | Clear | Fresh start for next task |
| Task incomplete, context >70% | Handoff + Clear | Compaction may lose details |
| Same task, context <50% | Continue | History is valuable |
| Switching to unrelated task | Clear | Irrelevant context hurts |
| Debugging same issue | Continue | Debug history critical |
| Compaction losing important info | Add to CLAUDE.md + Clear | Persist critical context |

---

## What Goes Where

| Information | Location | Survives Clear? |
|-------------|----------|-----------------|
| Project conventions | `CLAUDE.md` | Yes (always loaded) |
| Task requirements | `tasks/*/task-file.md` | Yes (re-readable) |
| Implementation plans | `plans/*.md` | Yes (re-readable) |
| Reusable instructions | `tasks/3_instructions/*.md` | Yes (re-readable) |
| Session-specific debugging | Context window | No |
| Critical decisions | Task file "Progress Log" | Yes |

---

## Handoff Template (Quick Copy)

```markdown
### [DATE] [TIME] - [OWNER]

**Done**:
- [What was completed]

**In Progress**:
- [What's partially done - include file:line references]

**Files Modified**:
- `path/file.py` - [what changed]

**Tests**: [passing/failing/not run]

**Resume Instructions**:
1. Read [specific file or section]
2. Run [specific command]
3. Continue with [specific next step]
```

---

## Common Scenarios

### Scenario: Long-running feature development

1. Create worktree: `./scripts/worktree-new.ps1 my-feature`
2. Open Claude Code in worktree folder
3. Work in isolation
4. Write handoffs when clearing context
5. When done: PR, merge, `./scripts/worktree-remove.ps1 my-feature`

### Scenario: Quick hotfix while feature in progress

1. Keep feature window as-is
2. Open new window in main repo (main branch)
3. Make fix, commit, push
4. Close hotfix window
5. Resume feature window (may need to rebase)

### Scenario: Multiple people/agents on same codebase

1. Use worktrees (different branches)
2. Each agent owns specific tasks
3. Coordinate via task files in shared `tasks/` folder
4. Merge via PRs to avoid conflicts

### Scenario: Context getting too large mid-task

1. Stop current work at a clean point
2. Write detailed handoff in task file
3. Commit the task file
4. Clear context: `/clear`
5. Resume: "Read tasks/1_in-progress/[task].md and continue"

---

## Checklist: Before Clearing Context

- [ ] Task file has updated Progress Log
- [ ] Handoff Notes section is complete
- [ ] Resume Instructions are specific and actionable
- [ ] Files Modified list is accurate
- [ ] Tests status is noted
- [ ] Task file is saved
- [ ] Changes committed (if appropriate)
