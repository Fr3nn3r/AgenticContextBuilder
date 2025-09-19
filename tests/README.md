# Tests for ContextManager

This directory contains comprehensive tests for the ContextManager file ingestion system.

## Test Structure

The test suite is organized into logical categories:

### Core Tests (`test_core/`)
- `test_utils.py`: Core utility functions (hashing, file operations, ID generation)
- `test_metadata_processor.py`: MetadataProcessor functionality
- `test_file_ingestor.py`: FileIngestor class and main orchestration logic

### Processor Tests (`test_processors/`)
- `test_processor_registry.py`: Processor discovery and registry management
- `test_enrichment_processor.py`: EnrichmentProcessor functionality
- `test_metadata_processor.py`: MetadataProcessor specific tests

### Integration Tests (`test_integration/`)
- `test_file_ingestor.py`: End-to-end file ingestion workflows
- `test_cli.py`: Command-line interface integration tests

### Test Fixtures (`test_fixtures/`)
- `test_mock_data_generator.py`: Mock data generation system tests

### Legacy Tests (maintained for compatibility)
- `test_metadata_extraction_units.py`: Original unit tests for legacy functions
- `test_metadata_extraction_integration.py`: Original integration tests
- `test_integration_with_fixtures.py`: Fixture system demonstration tests

### Configuration
- `conftest.py`: Shared pytest fixtures and test utilities
- `pytest.ini`: Test configuration and settings
- `__init__.py`: Test package initialization

## Running Tests

### Prerequisites

Install test dependencies:
```bash
uv sync
```

### Running Core Tests

Run all core functionality tests:
```bash
uv run python -m pytest tests/test_core/ -v
```

Run specific core test modules:
```bash
uv run python -m pytest tests/test_core/test_utils.py -v
uv run python -m pytest tests/test_core/test_metadata_processor.py -v
```

### Running Processor Tests

Run all processor tests:
```bash
uv run python -m pytest tests/test_processors/ -v
```

Run specific processor tests:
```bash
uv run python -m pytest tests/test_processors/test_processor_registry.py -v
uv run python -m pytest tests/test_processors/test_enrichment_processor.py -v
```

### Running Integration Tests

Run all integration tests:
```bash
uv run python -m pytest tests/test_integration/ -v
```

Run CLI integration tests:
```bash
uv run python -m pytest tests/test_integration/test_cli.py -v
```

### Running Legacy Tests

Run legacy unit tests:
```bash
uv run python -m pytest tests/test_metadata_extraction_units.py -v
```

Run legacy integration tests:
```bash
uv run python -m pytest tests/test_metadata_extraction_integration.py -v
```

### Running All Tests

Run complete test suite:
```bash
uv run python -m pytest tests/ -v
```

### Coverage Reports

Generate coverage report for the file ingestion system:
```bash
uv run python -m pytest tests/ --cov=file_ingest --cov-report=term-missing --cov-report=html
```

Generate coverage for specific modules:
```bash
# Core functionality coverage
uv run python -m pytest tests/test_core/ --cov=file_ingest --cov-report=html

# Processor coverage
uv run python -m pytest tests/test_processors/ --cov=file_ingest.processors --cov-report=html

# Integration coverage
uv run python -m pytest tests/test_integration/ --cov=file_ingest --cov-report=html
```

View HTML coverage report:
```bash
# Open htmlcov/index.html in your browser
```

### Current Test Categories

#### Core Tests (`test_core/`)

1. **Utility Function Tests** (`test_utils.py`)
   - Hash function tests (MD5, SHA1, SHA256)
   - File operation utilities
   - ID generation and formatting functions
   - Byte formatting and conversion
   - Error handling for edge cases

2. **MetadataProcessor Tests** (`test_metadata_processor.py`)
   - File metadata extraction
   - Hash generation integration
   - MIME type detection
   - Permission and timestamp handling
   - Configuration validation

#### Processor Tests (`test_processors/`)

1. **Processor Registry Tests** (`test_processor_registry.py`)
   - Automatic processor discovery
   - Registry management and instantiation
   - Pipeline construction and execution
   - Error handling for missing processors

2. **EnrichmentProcessor Tests** (`test_enrichment_processor.py`)
   - Content analysis functionality
   - File categorization logic
   - Configuration handling
   - Integration with existing metadata

#### Integration Tests (`test_integration/`)

1. **FileIngestor Integration** (`test_file_ingestor.py`)
   - End-to-end file processing workflows
   - Dataset folder processing
   - Output structure validation
   - Error handling and recovery

2. **CLI Integration** (`test_cli.py`)
   - Command-line argument parsing
   - Batch processing operations
   - Configuration file handling
   - User interface validation

#### Legacy Tests (maintained for compatibility)

1. **Legacy Unit Tests** (`test_metadata_extraction_units.py`)
   - Hash function tests for legacy functions
   - Metadata extraction tests for original implementation
   - Utility function tests (byte formatting, ID generation)
   - Comprehensive edge case coverage

2. **Legacy Integration Tests** (`test_metadata_extraction_integration.py`)
   - Dataset processing tests with original workflow
   - Command-line interface tests for legacy scripts
   - Comprehensive special character and file type handling
   - Output structure validation for original format

3. **Fixture Integration Tests** (`test_integration_with_fixtures.py`)
   - Fixture system demonstration and validation
   - Deterministic hash verification with known values
   - Performance and scale testing with large datasets
   - Unicode and edge case fixture robustness testing

**Note**: Legacy tests are maintained to ensure backward compatibility during the transition to the new file ingestion system. They test the same core functionality but using the original implementation.

## Test Configuration

The test suite is configured via `pytest.ini` with:
- Coverage threshold of 85%
- HTML and terminal coverage reports
- Platform-specific test markers
- Warning filters

## Fixtures

### Core Fixtures (available in `conftest.py`)

#### Basic File Fixtures
- `temp_dir`: Temporary directory for test files
- `sample_text_file`: Sample text file with known content
- `sample_binary_file`: Sample binary file for testing
- `sample_json_file`: Sample JSON file with structured data
- `sample_directory_structure`: Nested directory structure for hierarchy tests
- `unicode_files`: Files with international character names
- `large_file`: Large file for performance and memory testing
- `empty_file`: Empty file for edge case testing
- `special_char_files`: Files with special characters and edge case names

#### System Fixtures
- `mock_cli_args`: Factory for creating CLI argument objects
- `cleanup_test_data`: Utility for registering test files for cleanup

#### File Ingest Fixtures
- `basic_ingestor`: Basic FileIngestor instance for testing
- `configured_ingestor`: FileIngestor with custom configuration
- `sample_dataset`: Simple dataset structure for ingestion testing

### Advanced Mock Data Fixtures (from `test_fixtures/`)
- `mock_data_generator`: MockDataGenerator instance with fixed seed for reproducible content
- `test_datasets`: Complete test dataset structure with all dataset types
- `small_dataset`: Small dataset with documents, images, and data folders
- `unicode_dataset`: Dataset with international filenames
- `edge_cases_dataset`: Dataset with problematic filenames and edge cases
- `performance_dataset`: Dataset with many files for performance testing
- `known_hash_files`: Files with known, reproducible hashes for verification
- `deterministic_file_content`: Factory for creating files with deterministic content
- `cleanup_test_data`: Utility for registering paths for cleanup

### Mock Data Generation Features
- **Deterministic content**: Same seed always produces identical content
- **Various file types**: Text, binary, JSON, CSV with different patterns
- **Reproducible hashes**: File hashes are consistent across test runs
- **Platform compatibility**: Handles unicode and special character limitations
- **Automated structure creation**: Complete dataset hierarchies with one fixture
- **Size variants**: Files of different sizes for testing edge cases

### Usage Examples

```python
# Using the small_dataset fixture
def test_with_small_dataset(small_dataset):
    dataset_path = small_dataset['path']
    manifest = small_dataset['manifest']
    # dataset_path contains: documents/, images/, data/ folders with test files

# Using the mock_data_generator directly
def test_custom_content(mock_data_generator, tmp_path):
    # Create custom deterministic content
    metadata = mock_data_generator.create_file(
        tmp_path / "test.txt",
        "text",
        1024,
        text_type="lorem"
    )
    # metadata contains size, hash, creation info

# Using deterministic_file_content factory
def test_reproducible_files(deterministic_file_content, tmp_path):
    # Create file with known hash
    metadata = deterministic_file_content(
        tmp_path / "reproducible.txt",
        content_type="text",
        size=500,
        seed=123
    )
    # Same parameters always produce same file hash
```

## Platform-Specific Tests

Some tests are platform-specific:
- Windows-only tests (marked with `@pytest.mark.skipif`)
- Unix-only tests (marked with `@pytest.mark.skipif`)

These tests will be automatically skipped on unsupported platforms.