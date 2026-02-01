---
name: Non-Covered Explanation
model: gpt-4o-mini
temperature: 0.0
max_tokens: 1500
description: Rewrites technical coverage denial reasoning into concise English adjuster-ready explanations.
---
system:
You are writing coverage denial explanations for an insurance adjuster.
Write in English. Be concise (1-2 sentences per group). Do not invent
policy clause numbers. When a part is not in the covered list, cite the
actual covered parts for that category.

user:
## Policy coverage
{% for category, parts in covered_components.items() %}
- **{{ category }}**: {{ parts | join(', ') }}
{% endfor %}

{% if excluded_components %}
## Policy exclusions
{% for category, parts in excluded_components.items() %}
- **{{ category }}**: {{ parts | join(', ') }}
{% endfor %}
{% endif %}

## Non-covered items to explain

{% for group in groups %}
### Group {{ loop.index }}: {{ group.exclusion_reason }}{% if group.category %} ({{ group.category }}){% endif %}

Items ({{ group.total_amount }} {{ currency }}):
{% for item in group["items"] %}
- {{ item }}
{% endfor %}
Technical reasoning: {{ group.technical_reasoning }}

{% endfor %}

Respond in JSON:
[
  {"group": 1, "explanation": "..."},
  ...
]
