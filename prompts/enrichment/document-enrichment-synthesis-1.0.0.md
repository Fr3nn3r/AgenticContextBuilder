You are synthesizing information from a multi-page document that has already been analyzed page by page. Your task is to create document-level insights from the page-level analyses.

## Page-Level Analyses
{pages_summary}

## Document Overview
- Total pages analyzed: {page_count}
- Extraction method: {extraction_method}

## Required Synthesis

Create document-level insights by:

1. **Summary**: Synthesize an overall 1-2 sentence summary of the entire document
2. **Category**: Determine the document's business category based on all pages
3. **Key Data Points**: Identify the top 10 most important data points across ALL pages

## Business Categories

Classify into ONE of these categories:
- fnol_form (First Notice of Loss forms)
- expense_report (Employee expense reports and reimbursement requests)
- invoice (Bills and payment requests from vendors)
- receipt (Proof of purchase or transaction)
- police_report (Law enforcement incident reports)
- policy_document (Insurance policies, terms, and coverage documents)
- drivers_license (Government-issued driver identification)
- passport (Travel identification document)
- id_card (General identification cards)
- email_chain (Email conversations and correspondence)
- medical_record (Healthcare and medical documentation)
- claim_form (Insurance claim submissions)
- contract (Legal agreements and contracts)
- statement (Bank, credit card, or account statements)
- tax_document (Tax forms, returns, and related documents)
- insurance_card (Insurance identification and coverage cards)
- vehicle_registration (Vehicle ownership and registration documents)
- inspection_report (Property, vehicle, or equipment inspection reports)
- estimate (Cost estimates and quotes for services)
- correspondence (General business letters and communications)
- legal_document (Legal filings, court documents, affidavits)
- financial_statement (Income statements, balance sheets, financial reports)
- application_form (Applications for services, coverage, or programs)
- authorization_form (Consent and authorization documents)
- other (Documents not fitting above categories)

## Output Format

Respond ONLY with a valid JSON object:

```json
{{
  "summary": "Overall document description synthesized from all pages",
  "content_category": "category_from_list",
  "key_data_points": [
    {{"key": "field_name", "value": "field_value", "confidence": 0.95, "page": 1}},
    {{"key": "field_name", "value": "field_value", "confidence": 0.90, "page": 2}},
    ...
  ],
  "category_confidence": 0.95,
  "total_pages_analyzed": {page_count},
  "language": "ISO 639-1 code"
}}
```

## Synthesis Rules

- Combine and deduplicate information across pages
- Prioritize data points that appear consistently across pages
- Include page numbers for traceability
- For multi-page forms, extract the complete information set
- If different pages suggest different categories, choose the most appropriate for the document as a whole
- Maintain high confidence only when information is consistent across pages
- Return ONLY the JSON object, no additional text