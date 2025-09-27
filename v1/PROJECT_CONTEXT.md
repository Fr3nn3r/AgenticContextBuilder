# PROJECT_CONTEXT.md

## Project Overview
ContextManager is a document ingestion and processing system that extracts content and metadata from various file types (PDFs, images, spreadsheets, documents) using AI-powered analysis, OCR, and structured extraction methods.

## Architecture Overview

### Core Modules
- **context_builder/** - Main package containing all ingestion logic
  - `ingest.py` - Orchestrates file/dataset processing through pipeline
  - `cli.py` - Command-line interface for running ingestion
  - `models.py` - Pydantic data models for type safety
  - `output_writer.py` - Handles JSON output generation

- **context_builder/processors/** - Plugin-based processing pipeline
  - `base.py` - Abstract base class defining processor interface
  - `metadata.py` - Extracts filesystem metadata (size, timestamps, hashes)
  - `content.py` - AI-powered content extraction and analysis

- **context_builder/processors/content_support/** - Content processing infrastructure
  - `handlers/` - File type-specific handlers (PDF, image, text, spreadsheet, document)
  - `interfaces/` - Contracts for AI providers, extractors, image processors
  - `services/` - AI analysis service, processing tracker
  - `models.py` - Content-specific data models
  - `factory.py` - Handler creation factory pattern
  - `config.py` - Configuration management

### Key Design Patterns
- **Plugin Architecture**: Processors inherit from BaseProcessor, enabling modular pipeline
- **Factory Pattern**: Handler selection based on file type
- **Strategy Pattern**: Multiple PDF processing strategies (OCR, Vision API)
- **Dependency Injection**: AI providers and services injected into handlers

### Data Flow
1. CLI/Script → FileIngestor initialization with config
2. FileIngestor → ProcessingPipeline with registered processors
3. For each file: Pipeline executes processors sequentially
4. Each processor enriches metadata, passing to next
5. OutputWriter → Structured JSON output to filesystem

## Directory Structure
```
ContextManager/
├── context_builder/              # Main package
│   ├── processors/      # Processing plugins
│   │   ├── content_support/  # Content extraction infrastructure
│   │   │   ├── handlers/     # File-type specific handlers
│   │   │   ├── interfaces/   # Abstract contracts
│   │   │   └── services/     # Shared services
│   │   └── [processor modules]
│   └── [core modules]
├── scripts/            # Standalone utility scripts
├── tests/              # Test suite
├── config/             # Configuration files
├── prompts/            # AI prompt templates
├── data/               # Input data directory
├── tmp/                # For temporary files e.g. temporary test scripts
└── output/             # Processing output directory
```

## Key Interfaces & Contracts

### BaseProcessor (context_builder/processors/base.py)
```python
class BaseProcessor(ABC):
    def process_file(file_path: Path, existing_metadata: Dict) -> Dict
    def configure(config: Dict) -> None
    def validate() -> bool
```

### Content Handler Interface (content_support/handlers/base.py)
```python
class BaseContentHandler(ABC):
    def can_handle(file_path: Path) -> bool
    def extract_content(file_path: Path, config: Dict) -> FileContentOutput
```

### AI Provider Interface (content_support/interfaces/ai_provider.py)
```python
class AIProvider(Protocol):
    def analyze_text(text: str, prompt: str) -> str
    def analyze_image(image_path: Path, prompt: str) -> str
```

### Core Data Models (context_builder/models.py)
- `FileMetadata` - Core filesystem metadata
- `FileContentOutput` - Content extraction results
- `ProcessingInfo` - Processing metadata and statistics
- `DatasetSummary` - Dataset-level aggregation

## Tech Stack & Dependencies

### Languages & Runtime
- **Python 3.9+** - Core language
- **uv** - Fast Python package/project manager

### Core Libraries
- **pydantic** - Data validation and type safety
- **python-dotenv** - Environment variable management
- **pathlib** - Cross-platform path handling

### Content Processing
- **unstructured[pdf]** - Document parsing and extraction
- **openai** - AI/LLM integration for content analysis
- **pypdfium2** - PDF rendering and processing
- **PIL/Pillow** - Image processing
- **pandas** - Spreadsheet handling (lazy import)

### Testing
- **pytest** - Test framework
- **pytest-cov** - Coverage reporting
- **pytest-mock** - Mock/stub utilities

### External Services
- **OpenAI API** - GPT-4 Vision for content analysis (requires OPENAI_API_KEY)

## Entry Points

### Main CLI Command
```bash
python -m context_builder.cli [input_path] [output_path] [options]
```

### Programmatic Usage
```python
from context_builder.ingest import FileIngestor
ingestor = FileIngestor(config)
result = ingestor.ingest_file(file_path)
```

### Legacy Scripts
- `scripts/extract_datasets_metadata.py` - Standalone metadata extraction

## Configuration

### Config Files
- `config/default_config.json` - Full pipeline with AI processing
- `config/metadata_only_config.json` - Metadata extraction only

### Environment Variables
- `OPENAI_API_KEY` - Required for ContentProcessor
- Loaded from `.env` file via python-dotenv

## Build & Test Commands
```bash
# Install dependencies
uv sync

# Run tests
uv run python -m pytest tests/ -v

# Run specific test
uv run python -m pytest tests/test_processors/test_content.py -v

# Run with coverage
uv run python -m pytest --cov=context_builder tests/
```

## Important Notes
- Modular processor pipeline allows easy extension
- Lazy imports optimize startup time and memory
- Comprehensive error handling with fallback strategies
- Type safety enforced through Pydantic models
- AI processing optional via configuration