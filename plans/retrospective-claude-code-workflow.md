# Retrospective: Claude Code Workflow Analysis

**Date**: 2026-02-05
**Scope**: Full audit of Claude Code configuration, documentation, workflow patterns, and improvement opportunities

---

## Executive Summary

You've built a **mature and well-organized** Claude Code setup. Your CLAUDE.md is comprehensive, your `.claude/docs/` are accurate, and your planning discipline is strong. However, the analysis reveals several patterns that are costing you efficiency and some Claude Code features you're not using at all. The biggest wins are: tightening the planning-execution loop, modernizing your `settings.local.json`, and establishing a lightweight continuous improvement cadence.

**Overall Grade: B+** — Strong foundation, clear improvement path.

---

## 1. How Often Are `.claude/docs/` Actually Consulted?

### The Files

| File | Last Updated | Staleness | Usefulness |
|------|-------------|-----------|------------|
| `architecture.md` | Jan 15 | Moderate — missing eval dashboard, new routers from Jan 25+ | Medium — too high-level for most tasks |
| `compliance.md` | Jan 15 | Fresh — code matches perfectly | High — 733 lines of actionable patterns |
| `testing.md` | Jan 15 | Fresh but thin — 77 lines | Low — mostly duplicates CLAUDE.md |
| `customer-config.md` | Jan 28 | Fresh — detailed commit procedure added | High — critical for NSA workflow |
| `worktrees.md` | Jan 18 | Fresh — port assignments are static | Medium — consulted at session start |

### Are They Being Used?

**Honest assessment: compliance.md and customer-config.md justify their existence. The other three provide marginal value.**

Evidence:
- `compliance.md` (733 lines) is the most actionable — it documents exact code patterns that agents need when touching compliance features. This pays for itself.
- `customer-config.md` was updated Jan 28 with a detailed commit procedure, suggesting it was consulted during a session and found lacking — then improved. This is the right maintenance cycle.
- `architecture.md` is a 92-line overview that doesn't tell an agent anything CLAUDE.md doesn't already cover. It hasn't been updated since Jan 15 despite significant new features (eval dashboard, screening pipeline, coverage analyzer).
- `testing.md` at 77 lines mostly repeats `CLAUDE.md`'s testing section. An agent would get the same info from CLAUDE.md.
- `worktrees.md` is comprehensive but the port table is already in CLAUDE.md. The additional detail (troubleshooting, scenarios) is useful but rarely needed.

### Recommendation

**Keep**: `compliance.md`, `customer-config.md`
**Merge into CLAUDE.md or archive**: `testing.md` (redundant)
**Update or archive**: `architecture.md` (stale, too generic)
**Keep but mark as reference-only**: `worktrees.md` (useful when things break)

---

## 2. CLAUDE.md Effectiveness

### What's Working

Your CLAUDE.md is **one of the best-structured project instruction files I've seen**. Specific strengths:

1. **Shell Environment section** — The explicit "NEVER use Windows commands" block with the tool preference table prevents a class of errors that wastes entire turns. This is excellent.

2. **Architecture Rules with tables** — The "Belongs in core vs customer config" table is immediately actionable. An agent can check their work against it.

3. **Red flags section** — "STOP and ask user" triggers are valuable guardrails. The ">50 lines to any single file" rule prevents scope creep.

4. **Command reference** — Having exact commands for pipeline, tests, CLI avoids agents guessing.

### What Could Be Better

1. **The doc is ~230 lines long** — This is borderline. Every token in CLAUDE.md is loaded into every conversation. Some sections (worktree table, version bump details) could be moved to `.claude/docs/` since they're only needed occasionally.

2. **No mention of skills** — You have 3 custom skills (deploy, eval, docx) but CLAUDE.md doesn't reference them. An agent doesn't know `/eval run` or `/deploy` exist unless they discover the skills directory.

3. **Settings.local.json is stale** — It references `python scripts/test_persistence.py`, `python src/medical_agent.py`, and `python scripts/test_observability_hello_world.py` — files that likely don't exist in this project. These are leftovers from a different project or earlier iteration.

4. **No hooks configured** — Claude Code hooks could automate repetitive checks (e.g., "did you update BACKLOG.md?" after commits, or "are you in the right worktree?" at session start).

### Recommendations

- Add a "Custom Skills" section to CLAUDE.md listing available `/deploy`, `/eval`, `/docx` commands
- Clean up `settings.local.json` to match current project needs
- Move the version bump script details and worktree troubleshooting to `.claude/docs/` (reduce CLAUDE.md token load)

---

## 3. Git & Commit Workflow Analysis

### Commit Message Discipline: Excellent (99%+)

All commits follow conventional prefixes (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`). This is rare and shows strong discipline.

**Distribution** (last 200 commits):
- `feat:` 51% — Feature-driven development
- `fix:` 23% — Regular bug fixing
- `docs:` 13% — Consistent documentation
- `refactor:` 6% — Moderate restructuring
- `chore:` 3% — Maintenance
- `test:` <1% — **Gap**: Almost no test-specific commits

### Commit Frequency: Bursty

Peak days hit 30-47 commits (Jan 15: 47, Jan 29: 31, Jan 25: 20). This correlates with long Claude Code sessions where features are built incrementally.

**Observation**: The burst pattern suggests you're doing multi-hour sessions with Claude Code rather than shorter, focused sessions. This is effective for feature work but increases context window pressure and risk of losing work if a session crashes.

### Co-Authorship: Not Used

Zero commits have `Co-Authored-By: Claude` tags. This means:
- No traceability of which commits were AI-assisted vs manual
- Can't filter git log to see AI contribution patterns
- Missing a signal that could inform code review priorities

### Branch Strategy: Single-Threaded

Despite having 3 worktrees configured, all recent work is on `main`. Worktree branches (`worktree/slot-1`, `slot-2`, `slot-3`) are 6+ days stale. This means:
- The parallel development infrastructure is built but not being used
- You're serializing work that could be parallelized
- The worktree docs and CLAUDE.md sections represent overhead for unused capability

### Version Bumps: Infrequent

Current version is 0.3.1. The last bump was Jan 25 (to 0.3.0). Multiple features have shipped since then without a version bump. The version bump script exists but isn't part of the regular workflow.

### Recommendations

- Add Co-Authored-By tags when committing through Claude Code (update commit skill or add to CLAUDE.md conventions)
- Either activate worktrees for parallel work or simplify the setup to reduce cognitive overhead
- Bump version after feature batches (you have ~10 features since 0.3.1)
- Consider shorter, more focused sessions to reduce context pressure

---

## 4. Planning & Execution Gap

### The Pattern

Your workflow follows this cycle:
```
Meeting/Decision → Implementation starts → Plan written during/after → BACKLOG updated after completion
```

Evidence from git history:
- `plan-dashboard-screening-fixes.md` added *after* the feature was committed
- `plan-eurotax-extraction-fix.md` added *while* working on the fix
- `plan-nsa-minimum-viable-review.md` created as strategic roadmap, not pre-implementation plan

### What This Means

Plans are **post-hoc documentation of decisions already made**, not **pre-work decomposition**. This works for a single developer but creates problems:
- An agent starting a new session can't see what's being worked on until it's done
- Effort estimates are retroactive (not predictive)
- No checkpoint to catch wrong direction before code is written

### Plan Quality: High Variance

| Plan | Quality | Lines | Actionable? |
|------|---------|-------|-------------|
| `plan-service-compliance-check-4b.md` | Excellent | 146 | Yes — exact files, JSON schemas, test commands |
| `plan-labor-promotion-guards-p1-p3.md` | Excellent | ~120 | Yes — specific code changes with examples |
| `plan-explain-why-not-covered.md` | Excellent | ~100 | Yes — feature spec with concrete output examples |
| `plan-eurotax-extraction-fix.md` | Good | ~40 | Yes — surgical prompt fix |
| `plan-dashboard-screening-fixes.md` | Weak | 21 | Partially — too vague, no file references |
| `plan-nsa-minimum-viable-review.md` | Strategic | ~150 | No — roadmap, not implementation plan |

The best plans (compliance check 4b, labor promotion) are **exceptional** — they specify exact files, evidence structures, and verification steps. The weakest (dashboard fixes) is essentially a todo list.

### BACKLOG.md: Strong Structure, Stale Content

**Strengths**:
- The Jan 28 Cross-Run Reconciliation handoff is a model entry: problem, solution, files changed with line numbers, tests added, verification steps
- Priority levels (P0-P9) with feature IDs (FEAT-xx, SEC-xx) provide structure
- Security audit items (SEC-01 through SEC-05) are documented with effort estimates

**Weaknesses**:
- "Doing" section hasn't been updated since Jan 28 — 8 days of active work (labor promotion, eval dashboard, screening pipeline) have no entries
- FEAT-39 (Cross-run reconciliation) is listed in Todo but was already completed Jan 28 — never moved to Done
- REFACTOR-01 (Split main.py) is listed as Todo but was completed Jan 25 (14 routers extracted)
- No link between BACKLOG features and plan files in `plans/`
- SEC-01 through SEC-05 are listed but unassigned and unplanned despite being deployment blockers

### Recommendations

1. **Write brief plans BEFORE starting work** — Even 10 lines: goal, files, rough steps. Flesh out during implementation.
2. **Standardize plan quality** — Create a plan template with required sections (Goal, Files, Steps, Verification, Risks).
3. **Update BACKLOG.md at session boundaries** — Mark completed items, update "Doing" section, add handoff notes for anything in progress.
4. **Link BACKLOG features to plans** — Add a `Plan: plans/plan-xxx.md` field to each backlog item.
5. **Clean stale backlog items** — FEAT-39 and REFACTOR-01 are done but still in Todo.

---

## 5. Claude Code Features: What You're Using vs Not

### Using Well

| Feature | Usage | Effectiveness |
|---------|-------|---------------|
| CLAUDE.md | Comprehensive, well-structured | High |
| .claude/docs/ | 5 reference docs, actively maintained | Medium-High |
| Custom Skills (3) | deploy, eval, docx — all functional | High |
| Plan mode (plans/) | 6 plan files, quality varies | Medium |
| settings.local.json | Permission allowlists | Low (stale) |
| Git worktrees | Infrastructure built | Low (unused) |

### Not Using

| Feature | What It Does | Potential Value |
|---------|-------------|-----------------|
| **Hooks** | Auto-run commands on tool calls (pre-commit, post-edit, session-start) | High — could enforce BACKLOG updates, worktree checks |
| **Co-authored commits** | Track AI-assisted vs manual commits | Medium — audit trail |
| **Custom commands** (.claude/commands/) | Reusable prompt templates invoked with `/command` | Medium — could standardize session-start checklist |
| **TodoWrite (in sessions)** | Track task progress within conversations | Variable — depends on session complexity |
| **Background agents** | Run tasks in parallel during sessions | Medium — could run tests while implementing |

### settings.local.json: Needs Cleanup

Current allowlist contains references to files that don't exist in this project:
```json
"Bash(python scripts/test_persistence.py:*)",
"Bash(python src/medical_agent.py:*)",
"Bash(python scripts/test_observability_hello_world.py:*)"
```

These are leftovers. The allowlist should be updated to match current workflows:
```json
{
  "permissions": {
    "allow": [
      "Bash(python -m pytest:*)",
      "Bash(python -m context_builder:*)",
      "Bash(python scripts/*:*)",
      "Bash(git:*)",
      "Bash(npm:*)",
      "Bash(npx:*)",
      "Bash(pip:*)",
      "Bash(powershell:*)",
      "Bash(uvicorn:*)",
      "Bash(curl:*)"
    ]
  }
}
```

---

## 6. Testing Workflow Assessment

### Infrastructure: Mature

- 102 test files across unit, integration, contract, regression, smoke, CLI
- pytest with 50% minimum coverage
- Playwright E2E with mock/local/remote targets
- Custom markers (`@pytest.mark.slow`, `@pytest.mark.windows`)

### Gap: Test-Specific Commits

Only 1 commit out of 377 has a `test:` prefix. Tests are being written alongside features (good) but never as standalone improvements (gap). This means:
- Test coverage grows with features but gaps aren't addressed independently
- No evidence of test-driven development (TDD) or test-first approaches
- Frontend has only 5 test files for 158 components — a significant gap

### Gap: No CI/CD

No `.github/workflows/` directory exists. Tests run locally during Claude Code sessions but there's no automated gate on PRs or pushes. This means:
- Tests can be skipped (nothing enforces them)
- Regressions can reach main branch without detection
- No automated coverage tracking over time

### Recommendations

- Add GitHub Actions workflow for pytest + frontend tests on PR
- Schedule periodic "test hardening" sessions focused on coverage gaps (especially frontend)
- Consider adding pre-commit hooks to run fast tests before committing

---

## 7. Continuous Improvement Process

### Proposed Cadence: Weekly 15-Minute Retrospective

**When**: End of each week (or after each major feature batch)
**Where**: Append to `plans/retrospective-log.md`
**Format**:

```markdown
## Week of YYYY-MM-DD

### Metrics
- Commits this week: X (feat: Y, fix: Z)
- Plans created before implementation: X/Y
- BACKLOG items completed: X
- BACKLOG items stale (>2 weeks in Doing): X
- Tests added: X new test files
- Claude Code sessions: ~X

### What Worked
- (1-2 bullet points)

### What Didn't Work
- (1-2 bullet points)

### Action Items for Next Week
- [ ] (specific, measurable actions)

### CLAUDE.md/Docs Changes Needed
- (any config or documentation updates identified)
```

### Quarterly Deep Retrospective

Every 3 months, run this same comprehensive analysis:
1. Audit `.claude/docs/` freshness vs code
2. Review commit patterns and identify drift
3. Check BACKLOG staleness
4. Assess plan quality variance
5. Review Claude Code feature utilization
6. Update CLAUDE.md based on findings

### Improvement Tracking

Create `plans/improvement-backlog.md` to track meta-improvements:

```markdown
# Improvement Backlog

## Active
- [ ] Clean settings.local.json (from 2026-02-05 retro)
- [ ] Add skills section to CLAUDE.md
- [ ] Update stale BACKLOG items
- [ ] Configure pre-commit hook for tests

## Completed
- [x] Added Shell Environment section to CLAUDE.md (2026-02-02)
- [x] Added detailed commit procedure to customer-config.md (2026-01-28)
```

---

## 8. Priority Action Items

### P0 — Do This Week (High Impact, Low Effort)

1. **Clean `settings.local.json`** — Remove stale entries, add missing patterns for current workflows
2. **Update BACKLOG.md** — Move completed items (FEAT-39, REFACTOR-01) to Done, update "Doing" section with current work
3. **Add skills reference to CLAUDE.md** — List `/deploy`, `/eval`, `/docx` so agents know they exist

### P1 — Do This Month (High Impact, Medium Effort)

4. **Establish plan-before-implement rule** — Even a 10-line brief plan before starting work
5. **Create plan template** — Standardize minimum quality for plans
6. **Add GitHub Actions CI** — Automated pytest + frontend tests on PR
7. **Configure a session-start hook** — Auto-check: correct worktree? BACKLOG current? Any stale "Doing" items?

### P2 — Do This Quarter (Medium Impact, Higher Effort)

8. **Archive/merge redundant docs** — Fold `testing.md` into CLAUDE.md, update or archive `architecture.md`
9. **Frontend test coverage push** — From 5 to 20+ test files
10. **Activate worktrees or simplify** — Either start using parallel development or remove the overhead
11. **Implement weekly retrospective cadence** — 15 minutes, append to `plans/retrospective-log.md`

### P3 — Nice to Have

12. **Architecture Decision Log** — Central record of "why" decisions
13. **Co-authored commit convention** — Track AI-assisted commits
14. **BACKLOG-to-plan index** — Link every feature to its plan file

---

## Appendix: Data Sources

- Git log analysis: 377 commits, 100+ inspected in detail
- File system audit: `.claude/`, `plans/`, `docs/`, `scripts/`, `tests/`
- BACKLOG.md: Full 525-line review
- CLAUDE.md: Full 230-line review
- `.claude/settings.local.json`: Permission audit
- `.claude/skills/`: 3 skill directories inspected
- `.claude/docs/`: 5 files cross-referenced against codebase
