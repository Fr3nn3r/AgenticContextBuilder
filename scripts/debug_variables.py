"""Debug script to check variable extraction."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context_builder.execution.form_generator import FormGenerator
import json

# Create generator
gen = FormGenerator()

# Load logic file
logic_file = Path("output/processing/20251129-113816-GoReady Cho/GoReady Choice Plan MN 4_logic.json")
with open(logic_file) as f:
    logic_data = json.load(f)

# Extract variables
vars = gen._extract_all_variables(logic_data)

print(f"Extracted {len(vars)} variables")
print("\nFirst 20 variables:")
for v in sorted(vars)[:20]:
    print(f"  - {v}")

# Check sections
sections = gen._organize_by_section(vars)
print(f"\nSections:")
for section, data in sections.items():
    field_count = len(data["fields"])
    print(f"  {section}: {field_count} fields")
