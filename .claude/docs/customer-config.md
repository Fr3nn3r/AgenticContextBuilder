# Customer Configuration

This document describes how to work with customer-specific configuration in ContextBuilder.

## Overview

Customer-specific extractors, prompts, and field specifications are stored in **separate git repositories** rather than in the main codebase. This provides:

- **Version control** for customer configs (workspaces are gitignored)
- **Separation** of customer-specific code from the generic application
- **Easy deployment** of different config versions
- **Multi-customer support** with separate repos per customer

## Architecture

```
C:\Users\fbrun\Documents\GitHub\
├── AgenticContextBuilder/              # Main application (generic)
│   ├── src/context_builder/            # Application code
│   └── workspaces/nsa/config/          # Active workspace config (gitignored)
│       ├── extractors/                 # Loaded dynamically at runtime
│       ├── extraction_specs/
│       └── prompts/
│
└── context-builder-nsa/                # Customer config repo (versioned)
    ├── extractors/                     # Customer extractors
    ├── extraction_specs/               # Field specifications
    ├── prompts/                        # Custom prompts
    └── sync-to-workspace.ps1           # Deployment script
```

## How It Works

### Dynamic Extractor Loading

When the application starts, `src/context_builder/extraction/extractors/__init__.py`:

1. Registers the generic extractor for all document types
2. Looks for `config/extractors/__init__.py` in the active workspace
3. If found, loads and calls `register_extractors()` to register custom extractors
4. Custom extractors override the generic extractor for their document types

### Workspace Config Location

The active workspace is determined by `.contextbuilder/workspaces.json`. The config directory is:

```
{workspace_path}/config/
├── extractors/          # Python extractor modules
│   ├── __init__.py      # Must define register_extractors()
│   └── *.py             # Extractor implementations
├── extraction_specs/    # YAML field specifications
├── prompts/             # Markdown prompt templates
└── prompt_configs.json  # Prompt configuration
```

## Development Workflow

### For Customer-Specific Changes

1. **Edit** files in the workspace (`workspaces/nsa/config/...`)
2. **Test** by running extraction (changes load automatically)
3. **Copy** to customer repo using `copy-from-workspace.ps1`
4. **Commit** in customer repo (NOT in main repo - workspace is gitignored)

```powershell
# Edit in workspace, then:
cd C:\Users\fbrun\Documents\GitHub\context-builder-nsa
.\copy-from-workspace.ps1
git add -A && git commit -m "fix: improved extraction"
git push
```

## Detailed Commit Procedure for Customer Config

> **IMPORTANT**: Customer config files in `workspaces/nsa/config/` are **gitignored** in the main
> AgenticContextBuilder repo. You MUST commit them to the separate customer repo.

### Step-by-Step Procedure

#### 1. Develop and Test in Workspace

Make your changes in the workspace directory:

```
AgenticContextBuilder/workspaces/nsa/config/
├── extraction_specs/     # YAML field specs (e.g., parts_delivery_note.yaml)
├── extractors/           # Python extractors (e.g., nsa_guarantee.py)
├── prompts/              # Markdown prompts
└── doc_type_catalog.yaml # Classification cues
```

Test with the pipeline:

```bash
python -m context_builder.cli pipeline --file "data\07-Claims-Motor-NSA\65258\document.pdf" --force
```

#### 2. Copy to Customer Repository

Run the copy script from the customer repo:

```bash
powershell -ExecutionPolicy Bypass -File "C:\Users\fbrun\Documents\GitHub\context-builder-nsa\copy-from-workspace.ps1"
```

This copies:
- `extraction_specs/*.yaml` → `context-builder-nsa/extraction_specs/`
- `extractors/*.py` → `context-builder-nsa/extractors/`
- `prompts/*.md` → `context-builder-nsa/prompts/`
- `prompt_configs.json`, `assumptions.json`, `scripts/`

#### 3. Check Status in Customer Repo

```bash
git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" status
```

#### 4. Stage Relevant Files

Stage only the files related to your change (avoid committing unrelated work):

```bash
git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" add extraction_specs/my_new_spec.yaml extraction_specs/doc_type_catalog.yaml
```

Or stage all changes if everything is related:

```bash
git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" add -A
```

#### 5. Commit with Descriptive Message

```bash
git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" commit -m "$(cat <<'EOF'
feat: add parts_delivery_note document type for Lieferschein

Add classification and extraction support for German parts delivery notes.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

#### 6. Verify Commit

```bash
git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" log -1 --oneline
```

### Common Scenarios

#### Adding a New Document Type

Files to create/modify:
1. `extraction_specs/doc_type_catalog.yaml` - Add classification cues
2. `extraction_specs/{doc_type}.yaml` - Create field extraction spec
3. (Optional) `extractors/{doc_type}.py` - Custom extractor if needed
4. (Optional) `extractors/__init__.py` - Register custom extractor

#### Modifying Extraction Fields

1. Edit `extraction_specs/{doc_type}.yaml` in workspace
2. Test with pipeline
3. Copy and commit to customer repo

#### Updating Prompts

1. Edit `prompts/{prompt_name}.md` in workspace
2. Test extraction
3. Copy and commit to customer repo

### Directory Reference

| Location | Purpose | Git Status |
|----------|---------|------------|
| `AgenticContextBuilder/workspaces/nsa/config/` | Active development | **GITIGNORED** |
| `context-builder-nsa/` | Version-controlled customer config | **TRACKED** |

### Git Commands Quick Reference

```bash
# All commands use -C to specify the customer repo path
REPO="C:\Users\fbrun\Documents\GitHub\context-builder-nsa"

# Check status
git -C "$REPO" status

# Stage files
git -C "$REPO" add extraction_specs/my_file.yaml

# Commit
git -C "$REPO" commit -m "message"

# View recent commits
git -C "$REPO" log --oneline -5

# Push to remote
git -C "$REPO" push
```

### For Fresh Environment Setup

1. Clone both repos
2. Run sync script to deploy config to workspace

```powershell
cd C:\Users\fbrun\Documents\GitHub\context-builder-nsa
.\sync-to-workspace.ps1
```

## Creating a New Customer Config Repo

### 1. Create Repository Structure

```powershell
mkdir context-builder-{customer}
cd context-builder-{customer}
git init

mkdir extractors, extraction_specs, prompts
```

### 2. Create extractors/__init__.py

```python
"""Customer extractors - auto-registration module."""

def register_extractors():
    """Register custom extractors with ExtractorFactory."""
    from context_builder.extraction.base import ExtractorFactory

    # Import and register your extractors
    from .my_extractor import MyExtractor
    ExtractorFactory.register("my_doc_type", MyExtractor)
```

### 3. Create Extractor

```python
# extractors/my_extractor.py
from context_builder.extraction.base import FieldExtractor

class MyExtractor(FieldExtractor):
    def extract(self, pages, doc_meta, run_metadata):
        # Your extraction logic
        pass
```

### 4. Create Sync Scripts

Copy `sync-to-workspace.ps1` and `copy-from-workspace.ps1` from an existing customer repo and update the default workspace path.

### 5. Add Field Specs and Prompts

Copy and customize `extraction_specs/` and `prompts/` from the workspace or another customer repo.

## Customer Repositories

| Customer | Repository | Visibility |
|----------|------------|------------|
| NSA | [context-builder-nsa](https://github.com/Fr3nn3r/context-builder-nsa) | Private |

## Troubleshooting

### Extractors Not Loading

1. Check workspace is active: `GET /api/workspaces`
2. Verify `config/extractors/__init__.py` exists
3. Check logs for "Loaded workspace extractors" message
4. Ensure `register_extractors()` function is defined

### Changes Not Taking Effect

- Restart Python/server after modifying extractors (loaded at import time)
- Verify files are in the correct workspace config directory

### Import Errors in Custom Extractors

- Custom extractors can import from `context_builder.*`
- Use absolute imports, not relative imports to main codebase
- The workspace extractors directory is added to `sys.modules` as `workspace_extractors`
