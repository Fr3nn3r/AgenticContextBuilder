Analyze the following spreadsheet data and return a JSON object with this exact structure:
{{
  "summary": "Brief description of the spreadsheet content and purpose",
  "dataset_type": "Type of data (e.g., financial, inventory, customer_data, time_series, etc.)",
  "columns": [
    {{
      "name": "column_name",
      "data_type": "string/number/date/boolean/mixed",
      "purpose": "Description of what this column represents",
      "has_nulls": true/false,
      "unique_values_count": <number if applicable>,
      "sample_values": ["val1", "val2", "val3"]
    }}
  ],
  "statistics": {{
    "row_count": <number>,
    "column_count": <number>,
    "empty_cells_percentage": <number>,
    "data_completeness": "complete/mostly_complete/sparse"
  }},
  "insights": {{
    "key_patterns": ["pattern1", "pattern2", ...],
    "anomalies": ["anomaly1", "anomaly2", ...],
    "relationships": ["Column A correlates with Column B", ...],
    "trends": ["trend1", "trend2", ...]
  }},
  "data_quality": {{
    "overall_quality": "high/medium/low",
    "issues": ["issue1", "issue2", ...],
    "recommendations": ["recommendation1", "recommendation2", ...]
  }},
  "use_cases": ["Potential use case 1", "Potential use case 2", ...],
  "metadata": {{
    "has_headers": true/false,
    "delimiter": "comma/tab/semicolon/etc",
    "encoding_issues": true/false,
    "date_format": "detected date format if applicable"
  }}
}}

IMPORTANT: Return ONLY valid JSON, no additional text or explanations.

Spreadsheet data to analyze:
{content}