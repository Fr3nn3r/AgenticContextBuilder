# Context Builder

A robust document context extraction tool using AI vision APIs to extract structured information from images and PDFs.

## Features

- **Multi-format support**: Process images (JPG, JPEG, PNG, GIF, BMP, TIFF, TIF) and PDF documents
- **Case-insensitive file discovery**: Automatically finds files regardless of extension case
- **AI-powered extraction**: Uses OpenAI Vision API to extract text and structured information
- **Batch processing**: Process entire directories recursively
- **Resilient API calls**: Built-in retry logic with exponential backoff for rate limits and timeouts
- **Memory-efficient PDF processing**: Streams pages one-by-one to minimize memory usage
- **Session tracking**: Unique session IDs for tracking processing runs
- **Highly configurable**: Extensive CLI options for customizing behavior

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/AgenticContextBuilder.git
cd AgenticContextBuilder

# Install dependencies using pip
pip install -e .

# Or using uv
uv pip install -e .
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your-api-key-here
```

## Usage

### Basic Usage

Process a single file:
```bash
python -m context_builder.cli image.jpg
```

Process a directory:
```bash
python -m context_builder.cli /path/to/documents/
```

### CLI Options

```bash
python -m context_builder.cli [input_path] [options]
```

#### Required Arguments
- `input_path`: Path to file or folder to process

#### Optional Arguments

**Output Options:**
- `-o, --output-dir DIR`: Output directory for JSON results (default: current directory)

**Processing Options:**
- `-r, --recursive`: Process folders recursively
- `-p, --provider NAME`: Vision API provider to use (default: openai)

**Model Configuration:**
- `--model MODEL`: Model name to use (e.g., 'gpt-4o' for OpenAI)
- `--max-tokens N`: Maximum tokens for response (default: 4096)
- `--temperature T`: Temperature for response generation (0.0-2.0, default: 0.2)

**PDF Processing:**
- `--max-pages N`: Maximum pages to process from PDFs (default: 20)
- `--render-scale S`: Render scale for PDF to image conversion (default: 2.0)

**API Resilience:**
- `--timeout N`: API request timeout in seconds (default: 120)
- `--retries N`: Maximum number of retries for API calls (default: 3)

**Logging Options:**
- `-v, --verbose`: Enable verbose logging
- `-q, --quiet`: Minimal console output

### Examples

Process a single image with custom settings:
```bash
python -m context_builder.cli document.jpg \
  --model gpt-4o \
  --max-tokens 2048 \
  --temperature 0.1
```

Process a folder recursively with increased timeout:
```bash
python -m context_builder.cli /path/to/documents/ \
  -r \
  --timeout 180 \
  --retries 5 \
  -o ./output/
```

Process PDFs with custom page limits and quality:
```bash
python -m context_builder.cli report.pdf \
  --max-pages 10 \
  --render-scale 1.5
```

Quiet mode for automation:
```bash
python -m context_builder.cli /batch/folder/ -q
```

## Output Format

The tool generates JSON files with extracted context. Each output file contains:

```json
{
  "file_name": "document.pdf",
  "file_path": "/absolute/path/to/document.pdf",
  "file_extension": ".pdf",
  "file_size_bytes": 1024000,
  "mime_type": "application/pdf",
  "md5": "abc123...",
  "session_id": "a1b2c3d4",
  "total_pages": 3,
  "pages": [
    {
      "page_number": 1,
      "document_type": "invoice",
      "language": "en",
      "summary": "Invoice from Company XYZ",
      "key_information": {
        "invoice_number": "INV-001",
        "date": "2024-01-15",
        "total": "$1,234.56"
      },
      "visual_elements": ["company logo", "signature"],
      "text_content": "Full extracted text..."
    }
  ],
  "_usage": {
    "prompt_tokens": 1000,
    "completion_tokens": 500,
    "total_tokens": 1500
  }
}
```

## Performance Tips

### PDF Processing
- Use `--max-pages` to limit processing for large PDFs
- Adjust `--render-scale` to balance quality vs. processing time
  - Lower values (1.0-1.5) for faster processing
  - Higher values (2.0-3.0) for better text extraction quality

### API Rate Limits
- The tool automatically retries on rate limits with exponential backoff
- Use `--retries` to increase retry attempts for busy periods
- Consider `--timeout` for slow network connections

### Memory Optimization
- PDFs are processed page-by-page to minimize memory usage
- Large batches are processed file-by-file without accumulation

## Error Handling

The tool includes robust error handling:
- **Automatic retries** for rate limits (429) and server errors (5xx)
- **Exponential backoff** to respect API limits
- **Graceful interruption** handling (Ctrl+C)
- **Clear error messages** for configuration issues
- **Session IDs** for tracking and debugging

## Development

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=context_builder --cov-report=html
```

### Project Structure

```
context_builder/
├── acquisition.py          # Base classes and factory
├── cli.py                 # Command-line interface
├── impl/
│   └── openai_vision_acquisition.py  # OpenAI implementation
tests/
├── test_context_builder.py  # Unit and integration tests
```

## License

[Your License Here]

## Contributing

Contributions are welcome! Please ensure:
1. Code follows the SOLID principles outlined in CLAUDE.md
2. All tests pass
3. New features include tests
4. Documentation is updated

## Support

For issues or questions, please open an issue on GitHub.