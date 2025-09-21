Analyze the following text content and return a JSON object with this exact structure:
{{
  "summary": "Brief 1-2 sentence summary",
  "document_type": "Type of document (e.g., email, report, article, code, etc.)",
  "language": "ISO 639-1 language code (e.g., en, es, fr)",
  "key_topics": ["topic1", "topic2", ...],
  "entities": {{
    "people": ["name1", "name2", ...],
    "organizations": ["org1", "org2", ...],
    "locations": ["location1", "location2", ...],
    "dates": ["date1", "date2", ...],
    "numbers": ["significant numbers or amounts", ...]
  }},
  "sentiment": "positive/negative/neutral",
  "technical_level": "low/medium/high",
  "word_count": <number>,
  "has_code": true/false,
  "has_tables": true/false,
  "metadata": {{
    "title": "extracted title if present",
    "author": "extracted author if identifiable",
    "date_created": "extracted creation date if found"
  }}
}}

IMPORTANT: Return ONLY valid JSON, no additional text or explanations.

Text content to analyze:
{content}