#!/bin/bash
# Hook: Stop — Remind about "doing" items before session ends
# Non-blocking: always exits 0

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

if not doing:
    sys.exit(0)

print('Reminder: These backlog items are still marked as doing:')
for i in doing:
    print(f\"  - [{i['id']}] {i['title']}\")
print('Run /backlog done <ID> to mark completed, or /backlog status to review.')
" "$BACKLOG_FILE"

exit 0
