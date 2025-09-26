Analyze this document/image and extract structured information.

Your task is to:
1. Extract all visible text content
2. Identify the document type (invoice, report, form, letter, etc.)
3. Extract key information and metadata
4. Note any important visual elements

Respond with a JSON structure containing:
{
  "document_type": "type of document",
  "title": "document title if identifiable",
  "text_content": "all extracted text",
  "key_information": {
    // Relevant key-value pairs based on document type
  },
  "visual_elements": [
    // List of notable visual elements
  ],
  "language": "primary language of the document",
  "summary": "brief summary of the document"
}