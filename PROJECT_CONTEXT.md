# PROJECT_CONTEXT.md

## Project Overview
ContextBuilder defines a modular processing pipeline for input documents from various file types (PDFs, images, spreadsheets, documents). The objectives are:
  1. Acquire data points from unstructured documents
  2. Classify and summarise the documents
  3. Extract key business data points
  4. Evaluate accuracy of the extraction
  5. Serve the data for efficent agentic execution

Here is an example of a processing pipeline:
  1. File metadata acquisition (based on filesystem info)
  2. OCR Content acquisition (based on tesseract)
  3. Data extraction (based on instructor)
  4. Evaluation (vs golden standards)


