# Test Suite Plan for dataset_metadata_extraction.py

Based on my analysis, here's a comprehensive test plan for the dataset metadata extraction functionality:

## Test Framework Setup
- **Framework**: pytest (recommend adding to pyproject.toml)
- **Test Structure**: `/tests/` directory with modular test files
- **Coverage**: pytest-cov for coverage reporting

## 1. Unit Tests (`test_metadata_extraction_units.py`)

### Hash Function Tests (`test_get_file_hash`)
- Valid file with different algorithms (md5, sha1, sha256)
- Non-existent file handling
- Permission denied scenarios
- Large file processing
- Binary vs text file differences
- Edge case: empty file

### Metadata Extraction Tests (`test_extract_file_metadata`)
- **Basic file attributes**: name, path, extension, size
- **Timestamp handling**: creation, modification, access times
- **Permission extraction**: octal format, read/write/execute flags
- **File type detection**: regular files, directories, symlinks
- **MIME type detection**: various file extensions
- **Hash generation**: for files vs directories
- **Windows attributes**: hidden, system, archive flags (Windows-specific)
- **Error handling**: permission denied, non-existent files

### Utility Function Tests (`test_format_bytes`)
- Byte conversion accuracy (B, KB, MB, GB, TB, PB)
- Edge cases: 0 bytes, exactly 1024, very large numbers
- Floating point precision

### ID Generation Tests (`test_generate_extraction_id`)
- Date format consistency
- Random suffix uniqueness
- Input folder name handling
- Special characters in folder names

## 2. Integration Tests (`test_metadata_extraction_integration.py`)

### Dataset Processing Tests (`test_process_dataset_folder`)
- **Basic functionality**: single dataset with multiple files
- **Directory structure preservation**: nested folders
- **Subfolder filtering**: include/exclude specific subfolders
- **Output file generation**: individual metadata files + summary
- **File name handling**: special characters, unicode, long names
- **Mixed file types**: documents, images, binaries, text files

### Main Function Tests (`test_main_function`)
- **Command-line argument parsing**: all combinations
- **Dataset selection**: specific datasets vs default count
- **Subfolder filtering**: integration with CLI args
- **Error scenarios**: invalid paths, permissions, missing datasets
- **Output generation**: extraction summary creation

## 3. End-to-End Tests (`test_metadata_extraction_e2e.py`)

### Full Workflow Tests
- **Complete pipeline**: input folder → processing → output verification
- **Multiple datasets**: batch processing with different characteristics
- **Large dataset simulation**: performance and memory usage
- **Mixed content**: text, PDF, images, archives
- **Unicode handling**: international file names and content

### Output Validation Tests
- **JSON structure validation**: schema compliance
- **Metadata completeness**: all expected fields present
- **Cross-platform consistency**: Windows vs Unix paths
- **Timestamp accuracy**: file times vs metadata times

## 4. Performance Tests (`test_metadata_extraction_performance.py`)

### Scalability Tests
- **Large file handling**: multi-GB files
- **Many small files**: thousands of files
- **Deep directory structures**: nested folder performance
- **Memory usage**: monitoring during large operations
- **Concurrent access**: multiple extraction processes

## 5. Error Handling Tests (`test_metadata_extraction_errors.py`)

### File System Error Tests
- **Permission denied**: read-only files/directories
- **Network drives**: disconnected/slow connections
- **Corrupted files**: damaged file headers
- **Symbolic link handling**: broken links, circular references
- **Disk space**: insufficient space for output

### Input Validation Tests
- **Invalid arguments**: malformed CLI inputs
- **Missing dependencies**: required modules unavailable
- **Path validation**: relative vs absolute paths
- **Character encoding**: non-UTF8 file names

## 6. Test Data Setup (`test_fixtures/`)

### Sample Dataset Structure
```
test_datasets/
├── small_dataset/
│   ├── documents/
│   │   ├── sample.pdf
│   │   └── report.docx
│   ├── images/
│   │   ├── chart.png
│   │   └── photo.jpg
│   └── data/
│       ├── data.csv
│       └── config.json
├── unicode_dataset/
│   ├── файл.txt
│   ├── 文档.pdf
│   └── मस्केट.jpg
└── edge_cases/
    ├── empty_file.txt
    ├── very_long_filename_that_exceeds_normal_limits.doc
    └── special!@#$%^&*()_+chars.txt
```

### Mock Data Generation
- **Automated test file creation**: various sizes and types
- **Temporary directory management**: setup/cleanup
- **Deterministic content**: reproducible hashes for verification

## 7. Configuration and CI/CD

### Test Configuration (`pytest.ini`)
- Test discovery patterns
- Coverage thresholds (recommend 85%+)
- Parallel execution settings
- Platform-specific test markers

### Continuous Integration
- **Platform matrix**: Windows, Linux, macOS
- **Python version matrix**: 3.9, 3.10, 3.11, 3.12
- **Performance regression detection**: benchmark comparisons
- **Coverage reporting**: automated coverage updates

## 8. Test Execution Strategy

### Test Categories
- **Fast tests**: unit tests (< 1 second each)
- **Medium tests**: integration tests (< 10 seconds each)
- **Slow tests**: e2e and performance tests (marked for optional execution)

### Recommended Test Commands
```bash
# Quick unit tests
pytest tests/test_*_units.py -v

# Full test suite
pytest tests/ --cov=scripts.extract_datasets_metadata --cov-report=html

# Performance tests only
pytest tests/test_*_performance.py -m slow
```

This test plan ensures comprehensive coverage of all functionality while maintaining fast feedback loops for development.