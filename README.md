# 🚀 ContextBuilder

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A robust document context extraction tool using AI vision APIs to extract structured information from images and PDFs. Built with modularity and extensibility in mind.

## ✨ Features

- 🎯 **Multi-format support**: Process images (JPG, JPEG, PNG, GIF, BMP, TIFF, TIF) and PDF documents
- 🔍 **Case-insensitive file discovery**: Automatically finds files regardless of extension case
- 🤖 **AI-powered extraction**: Uses OpenAI Vision API and Tesseract OCR for text extraction
- 📁 **Batch processing**: Process entire directories recursively
- 🔄 **Resilient API calls**: Built-in retry logic with exponential backoff for rate limits and timeouts
- 💾 **Memory-efficient PDF processing**: Streams pages one-by-one to minimize memory usage
- 🆔 **Session tracking**: Unique session IDs for tracking processing runs
- ⚙️ **Highly configurable**: Extensive CLI options for customizing behavior
- 🎨 **Rich CLI output**: Beautiful colored logging and progress indicators

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/AgenticContextBuilder.git
cd AgenticContextBuilder

# Install dependencies using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### Configuration

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your-api-key-here
```

## 📖 Usage Examples

### 1. Simple Python API Usage

#### Using OpenAI Vision API

```python
import os
from pathlib import Path
from context_builder.acquisition import AcquisitionFactory
from rich.console import Console

# Set your API key
os.environ["OPENAI_API_KEY"] = "your-key-here"

# Create OpenAI vision processor
openai_vision = AcquisitionFactory.create("openai")

# Process a document
file_path = Path("document.pdf")
result = openai_vision.process(file_path)

# Display results with rich formatting
console = Console()
console.print(result)
```

#### Using Tesseract OCR

```python
from pathlib import Path
from context_builder.acquisition import AcquisitionFactory
from rich.console import Console

# Create Tesseract processor
tesseract = AcquisitionFactory.create("tesseract")
tesseract.languages = ["eng"]  # Set language(s)

# Process a document
file_path = Path("document.pdf")
result = tesseract.process(file_path)

# Display results
console = Console()
console.print(result)
```

### 2. Command Line Interface

#### Basic Usage

```bash
# Process a single file
python -m context_builder.cli document.pdf

# Process a directory
python -m context_builder.cli /path/to/documents/

# Process recursively with verbose output
python -m context_builder.cli /path/to/documents/ -r -v
```

#### Advanced Configuration

```bash
# Custom model and settings
python -m context_builder.cli document.pdf \
  --model gpt-4o \
  --max-tokens 2048 \
  --temperature 0.1 \
  --max-pages 10

# Batch processing with custom output
python -m context_builder.cli /batch/folder/ \
  -r \
  --timeout 180 \
  --retries 5 \
  -o ./output/
```

## 🛠️ CLI Options

### Required Arguments
- `input_path`: Path to file or folder to process

### Optional Arguments

#### Output Options
- `-o, --output-dir DIR`: Output directory for JSON results (default: current directory)
- `-r, --recursive`: Process folders recursively

#### Provider Options
- `-p, --provider NAME`: Vision API provider to use (default: openai)

#### Model Configuration
- `--model MODEL`: Model name to use (e.g., 'gpt-4o' for OpenAI)
- `--max-tokens N`: Maximum tokens for response (default: 4096)
- `--temperature T`: Temperature for response generation (0.0-2.0, default: 0.2)

#### PDF Processing
- `--max-pages N`: Maximum pages to process from PDFs (default: 20)
- `--render-scale S`: Render scale for PDF to image conversion (default: 2.0)

#### API Resilience
- `--timeout N`: API request timeout in seconds (default: 120)
- `--retries N`: Maximum number of retries for API calls (default: 3)

#### Logging Options
- `-v, --verbose`: Enable verbose logging
- `-q, --quiet`: Minimal console output

## 📊 Output Format

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

## 🏗️ Architecture

### Core Components

- **Acquisition Layer**: Abstract base classes and factory pattern for different providers
- **Implementation Layer**: OpenAI Vision and Tesseract OCR implementations
- **CLI Interface**: Rich command-line interface with colored output
- **Utilities**: File operations, hashing, and helper functions

### Supported Providers

- **OpenAI Vision API**: Advanced AI-powered document analysis
- **Tesseract OCR**: Open-source OCR engine for text extraction

## ⚡ Performance Tips

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

## 🧪 Development

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=context_builder --cov-report=html

# Run specific test categories
python -m pytest tests/unit/ -v
python -m pytest tests/cli/ -v
```

### Project Structure

```
context_builder/
├── acquisition.py          # Base classes and factory
├── cli.py                 # Command-line interface
├── impl/
│   ├── openai_vision_acquisition.py  # OpenAI implementation
│   └── tesseract_acquisition.py     # Tesseract implementation
├── utils/
│   ├── file_utils.py      # File operations
│   └── hashing.py         # Hashing utilities
examples/
├── simple_openai_vision.py  # OpenAI example
└── simple_tesseract.py      # Tesseract example
tests/
├── unit/                  # Unit tests
├── cli/                   # CLI tests
└── assets/                # Test files
```

## 🔧 Error Handling

The tool includes robust error handling:
- **Automatic retries** for rate limits (429) and server errors (5xx)
- **Exponential backoff** to respect API limits
- **Graceful interruption** handling (Ctrl+C)
- **Clear error messages** for configuration issues
- **Session IDs** for tracking and debugging

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please ensure:
1. Code follows the SOLID principles outlined in [CLAUDE.md](CLAUDE.md)
2. All tests pass
3. New features include tests
4. Documentation is updated

## 📞 Support

For issues or questions, please open an issue on GitHub.

---

**Made with ❤️ for the AI community**