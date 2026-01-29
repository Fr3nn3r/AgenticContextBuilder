"""Analyze assessment calls for a specific claim from llm_calls.jsonl."""
import json
import sys

claim_id = sys.argv[1] if len(sys.argv) > 1 else "65196"
log_file = "workspaces/nsa/logs/llm_calls.jsonl"

print(f"\nAssessment calls for claim {claim_id}:")
print("-" * 80)

with open(log_file, 'r', encoding='utf-8') as f:
    count = 0
    for line in f:
        if claim_id not in line or '"assessment"' not in line:
            continue

        d = json.loads(line)
        if d.get('call_purpose') != 'assessment' or d.get('claim_id') != claim_id:
            continue

        count += 1
        user_content = d.get('messages', [{}])[-1].get('content', '')
        has_check_inputs = '_check_inputs' in user_content
        tokens = d.get('prompt_tokens', 0)
        ts = d.get('created_at', '')[:19]

        print(f"{count}. {ts} | {tokens:,} tokens | _check_inputs: {has_check_inputs}")

print("-" * 80)
print(f"Total: {count} assessment calls")
