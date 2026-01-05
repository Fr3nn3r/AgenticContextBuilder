# Schema-Driven Claims Processing System

Runtime execution components for the schema-driven claims processing architecture.

## Architecture Overview

This module implements the CTO's architectural directive: **The application is merely a "player" for the "cartridge" (the Policy JSON).**

If Policy Rules change (e.g., watercraft limit changes from 8m to 10m), the application code requires **ZERO recompilation or deployment**.

## The 4 Core Components

### 1. Dynamic Form Generator (UI)
**Responsibility**: Render a user interface solely based on the `insurance_policy_form_schema.json` file.

**SOLID Principle**: Open/Closed Principle (OCP)
- Open for new form fields (via JSON updates)
- Closed for modification (source code doesn't change when fields change)

**Files**:
- `widget_factory.py` - Abstract Factory Pattern for creating UI widgets
- `streamlit_app.py` - Main application that renders forms dynamically

**Type Mappings**:

**Basic Widgets:**
- `type == "enum"` → Dropdown (with "Select..." placeholder)
- `type == "boolean"` → Toggle switch
- `type == "integer"` → Number input (step=1)
- `type == "number"` → Number input (step=0.01)
- `type == "string"` → Text input
- `repeatable == true` → List manager with Add/Remove buttons

**Semantic Widgets** (auto-detected from field names):
- Currency fields (e.g., "claim_amount", "premium") → Number input with currency symbol
- Date fields (e.g., "incident_date", "birth_date") → Date picker with custom format ("29-Nov-2025")
- Duration fields (e.g., "policy_period", "coverage_days") → Number input with unit label
- Percentage fields (e.g., "liability_percentage") → Slider (0-100%)
- Length fields (e.g., "watercraft_length") → Number input with "(meters)" label
- Long text fields (e.g., "description", "notes") → Text area
- Country fields → Dropdown with common countries
- Phone fields → Text input with placeholder "+1 (555) 123-4567"
- Email fields → Text input with placeholder "user@example.com"
- Short code fields → Text input with max length 10

**Context-Aware Help Text** (auto-injected from Symbol Table):
- **Priority 1**: Policy definitions (e.g., "Named Insured: A person or organization...")
- **Priority 2**: Limit/variable info (e.g., "Bodily Injury: 2,000,000 CAD")
- **Priority 3**: Schema description (fallback if no symbol table match)

### 2. Claim Data Model (Data Layer)
**Responsibility**: "Inflation" - Transform flat key-value pairs from UI into nested JSON structure for the logic engine.

**SOLID Principle**: Interface Segregation Principle (ISP)
- The engine requires a specific shape of data
- Don't force the engine to parse the entire internal database object
- Project only what the specific policy asks for

**Files**:
- `claim_mapper.py` - ClaimMapper interface + SchemaBasedClaimMapper implementation
- `validators.py` - Schema-based validation

**Inflation Example**:
```python
# Flat data from UI (Streamlit session state)
{
  "claim.header.claim_type": "liability",
  "claim.incident.attributes.watercraft_length": 10,
  "claim.parties.claimants[0].role": "insured"
}

# ↓ ClaimMapper.inflate() ↓

# Nested data for logic engine
{
  "claim": {
    "header": {
      "claim_type": "liability"
    },
    "incident": {
      "attributes": {
        "watercraft_length": 10
      }
    },
    "parties": {
      "claimants": [
        {"role": "insured"}
      ]
    }
  }
}
```

### 3. Logic Adaptor (Business Logic)
**Responsibility**: Orchestrate the execution of policy rules.

**SOLID Principle**: Dependency Inversion Principle (DIP)
- High-level modules (UI/Workflow) don't depend on low-level modules (json-logic library)
- Both depend on the IEvaluator abstraction

**Files**:
- `evaluator.py` - IEvaluator interface + NeuroSymbolicEvaluator implementation

**Benefit**: If we switch from json-logic to a C++ engine or cloud API, the rest of the application remains untouched.

**Statelessness**: The evaluator accepts (Rules + Data) and returns (Decision). It does not store previous claim states.

### 4. Result Interpreter (Presentation)
**Responsibility**: Translate raw engine output into human-readable decisions.

**SOLID Principle**: Single Responsibility Principle (SRP)
- The Engine decides what happened
- The Interpreter decides how to show it

**Files**:
- `result_interpreter.py` - Rich result formatting

**Output Structure**:
```json
{
  "summary": {
    "status": "APPROVED",
    "primary_message": "Claim is eligible for coverage",
    "color_code": "green"
  },
  "financials": {
    "applicable_limit": {
      "amount": 2000000,
      "currency": "CAD",
      "category": "Bodily Injury"
    },
    "applicable_deductible": {
      "amount": 25000,
      "currency": "CAD"
    }
  },
  "reasoning_trace": {
    "triggers": [
      {"rule_name": "...", "status": "PASS", "description": "..."}
    ],
    "red_flags": [
      {"rule_name": "...", "status": "TRIGGERED", "description": "..."}
    ]
  },
  "metadata": {
    "engine_version": "1.0.0",
    "execution_time_ms": 45
  }
}
```

## Developer Workflow

### Step 1: Fetch Policy Configuration
```python
from policy_compiler.runtime import load_schema, load_logic
import json
from pathlib import Path

schema = load_schema("output/output_schemas/insurance policy_form_schema.json")
logic = load_logic("output/processing/20251129-114118-insurance p/insurance policy_logic.json")

# Load symbol table (optional, for context-aware help text)
symbol_table_path = Path("output/processing/20251129-114118-insurance p/insurance policy_symbol_table.json")
if symbol_table_path.exists():
    with open(symbol_table_path, "r", encoding="utf-8") as f:
        symbol_table = json.load(f)
else:
    symbol_table = None
```

### Step 2: Render Dynamic Form
```python
from policy_compiler.runtime.widget_factory import render_section, WidgetFactory

# Flat state dictionary (managed by Streamlit)
flat_claim_data = {}

# Extract currency from policy
currency = WidgetFactory.extract_currency_from_policy(schema, logic)

# Render all sections from schema
for section_name, section_data in schema["sections"].items():
    render_section(
        section_name,
        section_data,
        flat_claim_data,
        currency=currency,
        symbol_table=symbol_table  # Context-aware help text
    )
```

### Step 3: Validate and Inflate
```python
from policy_compiler.runtime import SchemaBasedClaimMapper

mapper = SchemaBasedClaimMapper()

# Validate
errors = mapper.validate(flat_claim_data, schema)
if errors:
    for error in errors:
        print(f"Validation error: {error}")
else:
    # Inflate
    nested_claim_data = mapper.inflate(flat_claim_data, schema)
```

### Step 4: Execute Rules
```python
from policy_compiler.runtime import NeuroSymbolicEvaluator

evaluator = NeuroSymbolicEvaluator()
raw_result = evaluator.evaluate(logic, nested_claim_data)
```

### Step 5: Interpret Result
```python
from policy_compiler.runtime import ResultInterpreter

interpreter = ResultInterpreter()
rich_result = interpreter.interpret(raw_result, logic)

# Display to user
print(f"Status: {rich_result['summary']['status']}")
print(f"Message: {rich_result['summary']['primary_message']}")
```

## Success Criteria

**CTO's Requirement**: If given a new JSON file for a "Pet Insurance Policy" with completely different fields (like "Breed" and "Age"), the application should render the correct form and execute the correct rules **WITHOUT A SINGLE LINE OF CODE CHANGING**.

**Verified**: See `tests/runtime/test_integration.py::TestSuccessCriteria::test_no_hardcoded_fields`

This test creates a mock "Pet Insurance" schema and proves the system works with zero code changes.

## Running the Application

### Start Streamlit App
```bash
streamlit run src/context_builder/runtime/streamlit_app.py
```

Or using uv environment:
```bash
.venv/Scripts/python.exe -m streamlit run src/context_builder/runtime/streamlit_app.py
```

### Load Policy Configuration
1. Open the app in your browser (typically http://localhost:8501)
2. In the sidebar, enter paths to:
   - Schema file: `output/output_schemas/insurance policy_form_schema.json`
   - Logic file: `output/processing/20251129-114118-insurance p/insurance policy_logic.json`
3. Click "Load Policy Configuration"

### Fill and Submit Claim
1. Fill out the dynamically rendered form
2. Click "Validate Data" to check for errors
3. Click "Submit & Evaluate" to execute rules
4. View rich result with color-coded status

## Testing

### Run Unit Tests
```bash
.venv/Scripts/python.exe -m pytest tests/runtime/test_claim_mapper.py -v
```

### Run Integration Tests
```bash
.venv/Scripts/python.exe -m pytest tests/runtime/test_integration.py -v
```

### Test Coverage
- ClaimMapper: 86% coverage
- Validators: 87% coverage
- Evaluator: 55% coverage (core logic tested via integration tests)
- ResultInterpreter: 66% coverage (core logic tested via integration tests)

## File Structure

```
src/context_builder/runtime/
├── __init__.py                  # Module exports
├── schema_loader.py             # Utility for loading JSON files
├── validators.py                # Schema-based validation
├── claim_mapper.py              # Component 2: Inflation pattern
├── evaluator.py                 # Component 3: Rule execution
├── result_interpreter.py        # Component 4: Rich result formatting
├── widget_factory.py            # Component 1: Widget creation
├── streamlit_app.py             # Component 1: Main UI
└── README.md                    # This file

tests/runtime/
├── __init__.py
├── test_claim_mapper.py         # 14 unit tests for inflation
└── test_integration.py          # 8 integration tests (end-to-end)
```

## Design Patterns Used

### Abstract Factory Pattern
`WidgetFactory.create_widget()` creates UI components based on field type without hardcoding specific widgets.

### Dependency Inversion
`IEvaluator` interface allows swapping rule engines (json-logic, C++, cloud API) without changing consumer code.

### Strategy Pattern
`ClaimMapper` interface allows different inflation strategies (currently `SchemaBasedClaimMapper`).

### Template Method
`ResultInterpreter` follows a template for interpreting results: determine status → extract financials → build reasoning trace.

## Key Architectural Decisions

### Why Flat State for UI?
**Decision**: Streamlit manages flat key-value pairs, not nested objects.

**Rationale**: Streamlit's session state is painful to manage for nested structures. Flat keys like `claim.parties.claimants[0].role` are simpler.

**Solution**: ClaimMapper's "inflation" pattern transforms flat → nested for the engine.

### Why Stateless Evaluator?
**Decision**: The evaluator doesn't store previous claim states.

**Rationale**: Enables horizontal scaling, easier testing, and clearer reasoning about behavior.

**Trade-off**: If we need claim history, we'll implement it in a separate Claims Repository layer.

### Why JSON Logic?
**Decision**: Use industry-standard json-logic library for rule execution.

**Rationale**:
- Well-tested, mature library
- Human-readable JSON format
- Easy to serialize and version control
- Supports complex conditional logic

**Alternative Considered**: Custom rule engine (rejected due to maintenance burden).

### Why Symbol Table Integration (Context Injection)?
**Decision**: Fuse policy definitions from symbol table into widget help text.

**Rationale**:
- Original schema alone produces "dumb" UI (generic labels, no policy context)
- Symbol table contains the "brain" of policy definitions and limits
- Users need to understand insurance terminology while filling forms
- Help text provides just-in-time learning

**Implementation**:
3-tier priority system for help text generation:
1. **Priority 1**: Policy definitions from symbol table (e.g., "Named Insured: A person or organization...")
2. **Priority 2**: Limit/variable info from symbol table (e.g., "Bodily Injury: 2,000,000 CAD")
3. **Priority 3**: Generic description from schema (fallback)

**Impact**:
- Insurance Policy (22 fields): ~40% coverage with policy context
- Auto Policy (81 fields): ~6% coverage (symbol table has fewer terms)
- Coverage varies by policy richness and symbol table quality

**Future**: Consider LLM-based definition generation for fields without symbol table matches.

## Future Enhancements

### Phase 2 (Short-term)
- [X] Semantic widget inference (currency, date, duration, percentage, etc.)
- [X] Symbol table integration for context-aware help text
- [X] Smart currency detection from policy rules
- [ ] Add conditional display logic to schema (show/hide fields based on other values)
- [ ] Implement enum registry (aggregate common enums across policies)
- [ ] Add required field detection from logic analysis
- [ ] Create React/Vue version of Dynamic Form Generator

### Phase 3 (Medium-term)
- [ ] Schema versioning and migration
- [ ] Human review workflow (allow adjusters to flag incorrect fields)
- [ ] Multi-language support
- [ ] Accessibility improvements (WCAG 2.1 AA compliance)

### Phase 4 (Long-term)
- [ ] Cloud deployment (Azure, AWS)
- [ ] Real-time collaboration (multiple adjusters on same claim)
- [ ] Audit trail (track all changes to claim data)
- [ ] Integration with claims management systems

## Troubleshooting

### Import Errors
**Problem**: `ModuleNotFoundError: No module named 'context_builder'`

**Solution**: Use the uv environment:
```bash
.venv/Scripts/python.exe -m pytest ...
```

### Streamlit Not Found
**Problem**: `streamlit: command not found`

**Solution**: Install streamlit or use uv environment:
```bash
uv add streamlit json-logic
.venv/Scripts/python.exe -m streamlit run ...
```

### Validation Failures
**Problem**: Validation errors when submitting claim

**Solution**: Check field types in schema. Common issues:
- Integer field receiving string value
- Enum field receiving value not in options list
- Required field left empty

### Empty Results
**Problem**: No limits or conditions returned

**Solution**: Check that claim data matches expected structure. Use "Raw Data (Debug)" expander in Streamlit to inspect inflated data.

## License

Internal use only. See project LICENSE file.

## Contact

For questions or issues, contact the development team or file a GitHub issue.
