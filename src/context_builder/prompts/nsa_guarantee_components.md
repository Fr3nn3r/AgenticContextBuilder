---
name: NSA Guarantee Component Extraction
model: gpt-4o
temperature: 0.1
max_tokens: 4096
description: Extracts component coverage lists from pages 2-3 of NSA Guarantee warranty policies.
---
system:
You are extracting component coverage lists from an NSA Guarantee vehicle warranty policy.

The document contains two columns:
- LEFT: "Covered components and parts" / "Abgedeckte Komponenten und Teile"
- RIGHT: "Not insured components and parts" / "Nicht versicherte Komponenten und Teile"

## Task
Extract ALL component items organized by category. Keep items in their ORIGINAL LANGUAGE.

## Categories to Extract
- engine: Motor/Engine components
- turbo_supercharger: Turbo/Kompressor components
- four_wd: 4x4/Allrad components
- electric: Electric/Elektro components (for EVs)
- mechanical_transmission: Manual transmission / Mechanisches Schaltgetriebe
- automatic_transmission: Automatic transmission / Automatikgetriebe
- limited_slip_differential: Differential / Sperrdifferenzial
- fuel_system: Fuel system / Kraftstoffanlage
- axle_drive: Drive shafts / Kraftübertragungswellen
- steering: Steering / Lenkung
- brakes: Brakes / Bremsen
- suspension: Suspension / Aufhängung
- electrical_system: Electrical system / Elektrische Anlage
- air_conditioning: Air conditioning / Klimaanlage
- cooling_system: Cooling system / Kühlsystem
- chassis: Chassis / Fahrwerk
- electronics: Electronics / Elektronik
- comfort_options: Comfort options / Komfortausstattung
- exhaust: Exhaust / Abgasanlage

## Coverage Scale
Also extract the parts/labor coverage scale (usually at the end of the components section):
- Format: km threshold to coverage percentage
- Example: "ab 50'000 Km zu 80%" means threshold 50000, coverage 80%

## Output Format
Return a JSON object:

```json
{
  "covered": {
    "engine": ["Pistons", "Cylinder liners", "Crankshaft"],
    "mechanical_transmission": ["Pinion", "Gearshift forks"],
    "brakes": ["Servobrake", "Master cylinder"]
  },
  "excluded": {
    "engine": ["Distribution system including timing belt"],
    "brakes": ["ABS sensors"],
    "suspension": ["Ball pins", "Silentbloc"]
  },
  "coverage_scale": [
    {"km_threshold": 50000, "coverage_percent": 80},
    {"km_threshold": 80000, "coverage_percent": 60},
    {"km_threshold": 110000, "coverage_percent": 40}
  ]
}
```

## Important Rules
1. Extract COMPLETE lists - do not summarize or truncate
2. Keep component names in their original language (German or English)
3. Only include categories that have components listed
4. If a category has no components, omit it from the output
5. For coverage_scale, extract all threshold/percentage pairs

user:
Document type: nsa_guarantee (pages 2-3)

Document snippets (component lists):

{{ context }}

Extract all covered and excluded components by category, plus the coverage scale, as JSON.
