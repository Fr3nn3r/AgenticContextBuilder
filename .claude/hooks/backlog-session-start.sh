#!/bin/bash
# Hook: SessionStart — Show "doing" items from backlog on session start
# Exit silently if no backlog file exists

BACKLOG_FILE="${CLAUDE_PROJECT_DIR}/plans/backlog.json"

if [ ! -f "$BACKLOG_FILE" ]; then
  exit 0
fi

python -c "
import json, sys

try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
except Exception:
    sys.exit(0)

items = data.get('items', [])
doing = [i for i in items if i.get('status') == 'doing']
todo = [i for i in items if i.get('status') == 'todo']

if not doing and not todo:
    sys.exit(0)

parts = []
if doing:
    parts.append('Active backlog items (doing):')
    for i in doing:
        parts.append(f\"  - [{i['id']}] {i['title']} (P{i.get('priority','5')[1:] if i.get('priority','P5').startswith('P') else i.get('priority','5')})\")
    parts.append('')

parts.append(f'{len(todo)} todo items in backlog. Run /backlog status for details.')
print('\n'.join(parts))
" "$BACKLOG_FILE"
