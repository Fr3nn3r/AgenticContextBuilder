#!/usr/bin/env python3
"""
Pytest fixtures and configuration for ContextManager tests.
Provides common test utilities and shared fixtures.
"""

import os
import tempfile
import pytest
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_text_file(tmp_path):
    """Create a sample text file for testing."""
    test_file = tmp_path / "sample.txt"
    test_file.write_text("This is a sample text file for testing.\nLine 2\nLine 3")
    return test_file


@pytest.fixture
def sample_binary_file(tmp_path):
    """Create a sample binary file for testing."""
    test_file = tmp_path / "sample.bin"
    # Create binary content with various byte values
    binary_content = bytes(range(256))
    test_file.write_bytes(binary_content)
    return test_file


@pytest.fixture
def sample_json_file(tmp_path):
    """Create a sample JSON file for testing."""
    import json
    test_file = tmp_path / "sample.json"
    data = {
        "name": "test",
        "version": "1.0",
        "items": [1, 2, 3]
    }
    test_file.write_text(json.dumps(data, indent=2))
    return test_file


@pytest.fixture
def sample_directory_structure(tmp_path):
    """Create a sample directory structure for testing."""
    # Create nested directory structure
    base_dir = tmp_path / "sample_dataset"
    base_dir.mkdir()

    # Create subdirectories
    docs_dir = base_dir / "documents"
    images_dir = base_dir / "images"
    data_dir = base_dir / "data"

    docs_dir.mkdir()
    images_dir.mkdir()
    data_dir.mkdir()

    # Create sample files
    (docs_dir / "readme.txt").write_text("This is a readme file")
    (docs_dir / "report.pdf").write_text("Fake PDF content")
    (images_dir / "photo.jpg").write_text("Fake JPEG content")
    (images_dir / "chart.png").write_text("Fake PNG content")
    (data_dir / "data.csv").write_text("col1,col2\n1,2\n3,4")
    (data_dir / "config.json").write_text('{"setting": "value"}')

    return base_dir


@pytest.fixture
def unicode_files(tmp_path):
    """Create files with unicode names and content for testing."""
    files = {}

    # Create files with different unicode characters
    test_cases = [
        ("файл.txt", "Russian filename"),
        ("文档.pdf", "Chinese filename"),
        ("documento.español", "Spanish filename"),
        ("tëst_fïlé.txt", "Accented filename"),
    ]

    for filename, content in test_cases:
        test_file = tmp_path / filename
        test_file.write_text(content, encoding='utf-8')
        files[filename] = test_file

    return files


@pytest.fixture
def large_file(tmp_path):
    """Create a large file for performance testing."""
    test_file = tmp_path / "large_file.txt"
    # Create a 1MB file
    content = "A" * (1024 * 1024)
    test_file.write_text(content)
    return test_file


@pytest.fixture
def empty_file(tmp_path):
    """Create an empty file for edge case testing."""
    test_file = tmp_path / "empty.txt"
    test_file.write_text("")
    return test_file


@pytest.fixture
def special_char_files(tmp_path):
    """Create files with special characters in names."""
    files = {}

    # Files with various special characters
    special_names = [
        "file with spaces.txt",
        "file!@#$%^&*().txt",
        "file(with)parentheses.txt",
        "file[with]brackets.txt",
        "file{with}braces.txt",
        "file-with-dashes.txt",
        "file_with_underscores.txt",
        "file.with.dots.txt",
    ]

    for filename in special_names:
        test_file = tmp_path / filename
        test_file.write_text(f"Content of {filename}")
        files[filename] = test_file

    return files


# Platform-specific fixtures
@pytest.fixture
def windows_only():
    """Skip test if not running on Windows."""
    if os.name != 'nt':
        pytest.skip("Windows-only test")


@pytest.fixture
def unix_only():
    """Skip test if not running on Unix-like system."""
    if os.name == 'nt':
        pytest.skip("Unix-only test")