# Prompt Management Playbook

## The Problem We Solved
- Traditional prompt pipelines scatter model names, temperature caps, token budgets, and prompt wording across multiple modules, making upgrades brittle and audits painful.
- Context injections (customer data, pagination, locales) typically live in procedural code, so discovering how a prompt is assembled requires stepping through runtime.
- Version control for prompts is often an afterthought; stakeholders can’t easily review wording or configuration changes alongside code.

Our Markdown-first strategy consolidates every dependency a prompt requires—model choice, inference limits, schema references, and contextual text—into a single `.md` file that ships with the rest of the codebase. The Python loader handles parsing, rendering, and validation, so engineers interact with a structured API instead of ad-hoc strings.

## Template Anatomy
Each template keeps configuration and text together while staying readable:

```
---
name: Document Analysis
model: gpt-4o
temperature: 0.2
max_tokens: 4096
schema_ref: DocumentAnalysis
description: Extracts structured information from vision-capable documents.
---
system:
You are an expert document analysis assistant. Your task is to extract structured information from documents and images with high accuracy.

user:
{% if page_number and total_pages %}Page {{ page_number }} of {{ total_pages }}

{% endif %}Analyze this document and extract structured information for {{ customer_segment | default("our portfolio") }}.
```
- **YAML frontmatter** carries every inference parameter we want under source control. It is parsed into `config` so we can enforce model pinning and max token policies centrally.
- **Jinja blocks** expose controlled injection points; variables are optional and self-documenting (`page_number`, `customer_segment`, etc.).
- **Role markers (`system:`/`user:`)** turn the Markdown body into discrete chat messages, enabling multi-turn prompts without scattershot concatenation.

## Loader Pipeline (src/context_builder/utils/prompt_loader.py)
1. Resolve `PROMPTS_DIR` relative to the loader, so imports stay local and testable.
2. Parse the Markdown file with `python-frontmatter`, splitting metadata from content.
3. Render the body via `jinja2.Template.render`, applying whatever keyword arguments the caller provides.
4. Convert role sections into OpenAI-style `{"role": "...", "content": "..."}` payloads with `_parse_messages`, validating that at least one role exists.
5. Return a dictionary shaped as `{"config": metadata_dict, "messages": rendered_messages}`.

The loader is stable: new prompt capabilities usually mean editing Markdown, not Python.

## Execution Example: Configuration + Injection
```python
from openai import OpenAI
from src.context_builder.utils.prompt_loader import load_prompt

client = OpenAI()

prompt = load_prompt(
    "document_analysis",
    page_number=2,
    total_pages=12,
    customer_segment="premium auto policies",
    document_excerpt=document_text[:5000]
)

config = prompt["config"]
messages = prompt["messages"]

response = client.responses.create(
    model=config["model"],
    messages=messages,
    temperature=config.get("temperature", 0.0),
    max_output_tokens=config.get("max_tokens", 2048),
)
```
- **Model & inference parameters** come directly from the YAML frontmatter, eliminating hard-coded defaults across the codebase.
- **Context injection** happens through named kwargs (`page_number`, `customer_segment`, `document_excerpt`), rendered wherever the template needs them.
- **Auditability** improves because logs can include `config` alongside the request, clarifying exactly which model and limits were used for each call.

## Execution Example: Environment-Specific Overrides
```python
def run_document_analysis(document_text: str, env: str):
    prompt = load_prompt(
        "document_analysis",
        document_excerpt=document_text,
        reviewer=env.upper()
    )

    config = prompt["config"]
    if env == "staging":
        config = {**config, "model": "gpt-4o-mini", "max_tokens": 1024}

    return inference_client.generate(
        model=config["model"],
        messages=prompt["messages"],
        temperature=config["temperature"],
        max_tokens=config["max_tokens"]
    )
```
- A single Markdown file serves multiple environments; overrides occur in a narrow, controlled section of code.
- Teams can audit when and why a different model was used without sifting through string builders.

## Why This Design Works
- **Single Source of Truth**: Prompts, models, and inference policies live together, so diffs capture end-to-end behavior changes.
- **Developer Ergonomics**: `load_prompt` behaves like a typed configuration loader—no need to remember which helper decided the temperature or maximum tokens.
- **Extensibility**: Adding more roles (e.g., `assistant:` examples) or metadata fields (e.g., `safety_guidelines`, `cost_center`) is a document edit, not a code refactor.
- **Predictable Error Handling**: The loader raises early if a template is missing or malformed, turning template misconfigurations into actionable exceptions instead of broken API requests.
- **Operational Visibility**: Because configuration is a first-class return value, observability tooling can store the exact prompt parameters alongside outputs for postmortems.

Treat every new prompt as a Markdown asset: define inference dependencies in YAML, describe behavior in `system:` blocks, and expose the minimal set of Jinja variables callers can supply. This keeps experimentation fast, rollbacks clean, and production behavior explicit. By centralizing text and configuration, we eliminate drift between prompt wording, model selection, and runtime limits—making prompt engineering sustainable for the entire team.
