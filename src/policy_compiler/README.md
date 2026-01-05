# Policy Compiler

**Schema generation and claims processing runtime for insurance policies**

---

## Overview

The `policy_compiler` package transforms extracted policy documents (from `context_builder`) into executable claim processing applications.

### Purpose

`policy_compiler` sits downstream of `context_builder` in the processing pipeline:

```
context_builder                 policy_compiler
┌─────────────────────┐         ┌─────────────────────┐
│ PDF → Markdown      │  JSON   │ Schema Generator    │
│ Extract symbols     │ ──────> │ Claims UI           │
│ Extract logic       │  files  │ Rule Evaluator      │
└─────────────────────┘         └─────────────────────┘
```

**Input:** JSON files produced by `context_builder`:
- `*_logic.json` - Policy rules in JSON Logic format
- `*_symbol_table.json` - Policy definitions and limits
- `*_normalized_logic.json` - Refined rule format

**Output:**
- `*_form_schema.json` - Dynamic UI schemas
- Streamlit web application for claim processing
- Rich evaluation results with reasoning traces

---

## Architecture

The package follows **schema-driven architecture** with two main components:

### 1. Execution Package (`execution/`)

**Static analysis and schema generation**

- `form_generator.py` - Generates UI schemas from logic files
- `type_inference.py` - Infers field types from rule usage
- `schema_enrichment.py` - Enriches schemas with UDM metadata

**Usage:**
```python
from policy_compiler.execution.form_generator import FormGenerator

generator = FormGenerator()
schema = generator.generate_schema(logic_file_path)
generator.save_schema(schema, output_path)
```

**CLI:**
```bash
python scripts/generate_form_schema.py output/processing output/output_schemas
```

### 2. Runtime Package (`runtime/`)

**Dynamic claims processing application**

Implements the **4 core components** of schema-driven architecture:

1. **Dynamic Form Generator** (UI)
   - `widget_factory.py` - Semantic widget inference
   - `streamlit_app.py` - Web application

2. **Claim Data Model** (Data Layer)
   - `claim_mapper.py` - "Inflation pattern" (flat → nested)
   - `validators.py` - Schema-based validation

3. **Logic Adaptor** (Business Logic)
   - `evaluator.py` - IEvaluator abstraction + json-logic engine

4. **Result Interpreter** (Presentation)
   - `result_interpreter.py` - Rich formatted output

**Usage:**
```python
from policy_compiler.runtime import (
    load_schema,
    load_logic,
    SchemaBasedClaimMapper,
    NeuroSymbolicEvaluator,
    ResultInterpreter
)

# Load policy configuration
schema = load_schema("output/ui-data/insurance policy_form_schema.json")
logic = load_logic("output/ui-data/insurance policy_logic.json")

# Process claim
mapper = SchemaBasedClaimMapper()
nested_data = mapper.inflate(flat_claim_data, schema)

evaluator = NeuroSymbolicEvaluator()
raw_result = evaluator.evaluate(logic, nested_data)

interpreter = ResultInterpreter()
rich_result = interpreter.interpret(raw_result, logic)
```

**CLI:**
```bash
streamlit run src/policy_compiler/runtime/streamlit_app.py
```

---

## Key Design Principles

### File-Based Interface

`policy_compiler` has **NO code dependency** on `context_builder`. Communication happens via JSON files on disk.

**Benefits:**
- Clean separation of concerns
- Independent versioning and deployment
- Can swap implementations without code changes

### Schema-Driven Architecture

**Core Philosophy:** *The application is merely a "player" for the "cartridge" (the Policy JSON).*

If policy rules change, the application requires **ZERO recompilation or deployment**.

### SOLID Principles

- **Open/Closed (OCP):** Form generator open for new fields, closed for modification
- **Interface Segregation (ISP):** Claim mapper projects only required fields
- **Dependency Inversion (DIP):** Logic adaptor depends on IEvaluator abstraction
- **Single Responsibility (SRP):** Each component has one job

---

## File Structure

```
src/policy_compiler/
├── __init__.py                  # Package exports
├── README.md                    # This file
│
├── execution/                   # Schema generation
│   ├── __init__.py
│   ├── form_generator.py
│   ├── type_inference.py
│   └── schema_enrichment.py
│
├── runtime/                     # Claims processing
│   ├── __init__.py
│   ├── streamlit_app.py         # Main UI application
│   ├── widget_factory.py        # Dynamic widget creation
│   ├── claim_mapper.py          # Data transformation
│   ├── evaluator.py             # Rule execution
│   ├── result_interpreter.py    # Result formatting
│   ├── validators.py            # Schema validation
│   ├── schema_loader.py         # JSON utilities
│   └── README.md                # Detailed runtime docs
│
└── tests/                       # Package-local tests
    ├── execution/
    └── runtime/
        ├── test_claim_mapper.py
        └── test_integration.py
```

---

## Installation

Part of the monorepo:

```bash
# Install from project root
pip install -e .

# Or with uv
uv sync
```

---

## Quick Start

### 1. Generate Schemas

```bash
python scripts/generate_form_schema.py output/processing output/output_schemas
```

### 2. Launch Claims UI

```bash
streamlit run src/policy_compiler/runtime/streamlit_app.py
```

### 3. Select Policy

In the UI sidebar:
1. Choose a policy from the dropdown (e.g., "insurance policy")
2. Click "Load Selected Policy"
3. Fill out the claim form
4. Click "Submit & Evaluate"
5. View evaluation results with reasoning traces

---

## Testing

```bash
# Run all policy_compiler tests
pytest src/policy_compiler/tests/

# Run runtime tests only
pytest src/policy_compiler/tests/runtime/

# Run with coverage
pytest src/policy_compiler/tests/ --cov=policy_compiler
```

---

## Success Criteria

**"Pet Insurance Policy" Test:**

If given a new "Pet Insurance Policy" JSON with completely different fields (pet breed, vaccination records, vet claims), this application should work **WITHOUT any code changes**.

This is the ultimate validation of the schema-driven architecture.

---

## Future Enhancements

### Phase 2 (Completed)
- [X] Semantic widget inference (currency, date, duration, etc.)
- [X] Symbol table integration for context-aware help text
- [X] Smart currency detection from policy rules

### Phase 3 (Short-term)
- [ ] Conditional display logic (show/hide fields based on values)
- [ ] Enum registry (aggregate common enums across policies)
- [ ] Required field detection from logic analysis
- [ ] React/Vue version of Dynamic Form Generator

### Phase 4 (Medium-term)
- [ ] Schema versioning and migration
- [ ] Human review workflow (adjusters can flag fields)
- [ ] Multi-language support
- [ ] WCAG 2.1 AA accessibility compliance

### Phase 5 (Long-term)
- [ ] Cloud deployment (Azure, AWS)
- [ ] Real-time collaboration (multiple adjusters per claim)
- [ ] Audit trail (track all changes)
- [ ] Integration with claims management systems

---

## Related Documentation

- [Runtime Package Details](runtime/README.md) - Deep dive into the 4 core components
- [context_builder Package](../context_builder/) - Upstream document processing
- [Project Root README](../../README.md) - Overall project documentation

---

## License

Part of the AgenticContextBuilder project.
