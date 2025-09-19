# Tests for ContextManager

This directory contains comprehensive tests for the ContextManager project.

## Test Structure

- `test_metadata_extraction_units.py`: Unit tests for individual functions in `extract_datasets_metadata.py`
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

## Test Configuration

The test suite is configured via `pytest.ini` with:
- Coverage threshold of 85%
- HTML and terminal coverage reports
- Platform-specific test markers
- Warning filters

## Fixtures

Common test fixtures are available in `conftest.py`:
- `temp_dir`: Temporary directory for test files
- `sample_text_file`: Sample text file
- `sample_binary_file`: Sample binary file
- `sample_json_file`: Sample JSON file
- `sample_directory_structure`: Nested directory structure
- `unicode_files`: Files with unicode names
- `large_file`: Large file for performance testing
- `empty_file`: Empty file for edge cases
- `special_char_files`: Files with special characters

## Platform-Specific Tests

Some tests are platform-specific:
- Windows-only tests (marked with `@pytest.mark.skipif`)
- Unix-only tests (marked with `@pytest.mark.skipif`)

These tests will be automatically skipped on unsupported platforms.