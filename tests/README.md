# Tests for ContextManager

This directory contains comprehensive tests for the ContextManager project.

## Test Structure

- `test_metadata_extraction_units.py`: Unit tests for individual functions in `extract_datasets_metadata.py`
- `test_metadata_extraction_integration.py`: Integration tests for component interactions and workflows
- `conftest.py`: Shared pytest fixtures and test utilities
- `__init__.py`: Test package initialization

## Running Tests

### Prerequisites

Install test dependencies:
```bash
uv sync
```

### Running Unit Tests

Run all unit tests:
```bash
uv run python -m pytest tests/test_metadata_extraction_units.py -v
```

Run specific test class:
```bash
uv run python -m pytest tests/test_metadata_extraction_units.py::TestGetFileHash -v
```

Run single test:
```bash
uv run python -m pytest tests/test_metadata_extraction_units.py::TestGetFileHash::test_valid_file_md5 -v
```

### Running Integration Tests

Run all integration tests:
```bash
uv run python -m pytest tests/test_metadata_extraction_integration.py -v
```

Run dataset processing tests:
```bash
uv run python -m pytest tests/test_metadata_extraction_integration.py::TestProcessDatasetFolder -v
```

Run main function tests:
```bash
uv run python -m pytest tests/test_metadata_extraction_integration.py::TestMainFunction -v
```

### Running All Tests

Run complete test suite:
```bash
uv run python -m pytest tests/ -v
```

### Coverage Reports

Generate coverage report:
```bash
uv run python -m pytest tests/test_metadata_extraction_units.py --cov=scripts --cov-report=term-missing --cov-report=html
```

View HTML coverage report:
```bash
# Open htmlcov/index.html in your browser
```

### Test Categories

The tests are organized into the following categories:

1. **Hash Function Tests** (`TestGetFileHash`)
   - Tests for MD5, SHA1, SHA256 hash calculations
   - Error handling for missing files and permissions
   - Edge cases like empty files and large files

2. **Metadata Extraction Tests** (`TestExtractFileMetadata`)
   - Basic file attributes (name, path, size, extension)
   - Timestamp extraction and formatting
   - Permission and file type detection
   - MIME type identification
   - Hash generation for files
   - Windows-specific attributes
   - Error handling scenarios

3. **Utility Function Tests** (`TestFormatBytes`)
   - Byte to human-readable format conversion
   - Edge cases and precision testing

4. **ID Generation Tests** (`TestGenerateExtractionId`)
   - Date format consistency
   - Random suffix uniqueness
   - Input folder name handling
   - Special character support

### Integration Tests (`test_metadata_extraction_integration.py`)

1. **Dataset Processing Tests** (`TestProcessDatasetFolder`)
   - Basic functionality with single dataset and multiple files
   - Directory structure preservation for nested folders
   - Subfolder filtering (include/exclude specific subfolders)
   - Output file generation (individual metadata files + summary)
   - **Comprehensive special character handling** (unicode, long names, edge cases)
   - **Comprehensive mixed file types and MIME detection** (25+ file types, binary patterns)

2. **Main Function Tests** (`TestMainFunction`)
   - Command-line argument parsing (all combinations)
   - Dataset selection (specific datasets vs default count)
   - Subfolder filtering integration with CLI args
   - Error scenarios (invalid paths, permissions, missing datasets)
   - Output generation (extraction summary creation)
   - Mixed successful and failed dataset processing

### Fixture Integration Tests (`test_integration_with_fixtures.py`)

1. **Fixture System Demonstration** (`TestFixturesIntegration`)
   - **Fixture-based extraction workflow** (demonstrates fixture usage with minimal extraction testing)
   - **Fixture special cases integration** (unicode and edge case fixture robustness)
   - **Deterministic hash verification** (reproducible hash testing with known values)
   - **Fixture performance and scale demonstration** (large dataset creation efficiency)
   - **Complete fixture system capabilities** (multi-dataset fixture system features)

**Key Differences:**
- **Integration tests**: Focus on comprehensive extraction functionality and edge cases
- **Fixture tests**: Focus on demonstrating fixture system capabilities and deterministic behavior
- **No duplication**: Each test has distinct purpose and validation criteria

## Test Configuration

The test suite is configured via `pytest.ini` with:
- Coverage threshold of 85%
- HTML and terminal coverage reports
- Platform-specific test markers
- Warning filters

## Fixtures

### Basic Fixtures (available in `conftest.py`)
- `temp_dir`: Temporary directory for test files
- `sample_text_file`: Sample text file
- `sample_binary_file`: Sample binary file
- `sample_json_file`: Sample JSON file
- `sample_directory_structure`: Nested directory structure
- `unicode_files`: Files with unicode names
- `large_file`: Large file for performance testing
- `empty_file`: Empty file for edge cases
- `special_char_files`: Files with special characters

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