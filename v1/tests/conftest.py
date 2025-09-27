#!/usr/bin/env python3
"""
Pytest fixtures and configuration for ContextManager tests.
Provides common test utilities and shared fixtures.
"""

import os
import tempfile
import argparse
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


@pytest.fixture
def complex_dataset_structure(tmp_path):
    """Create a complex dataset structure for integration testing."""
    base_dir = tmp_path / "complex_dataset"
    base_dir.mkdir()

    # Create multiple datasets
    datasets = ["dataset_alpha", "dataset_beta", "dataset_gamma"]

    for dataset_name in datasets:
        dataset_dir = base_dir / dataset_name
        dataset_dir.mkdir()

        # Create subfolders
        (dataset_dir / "documents").mkdir()
        (dataset_dir / "images").mkdir()
        (dataset_dir / "data").mkdir()
        (dataset_dir / "misc").mkdir()

        # Create files in each subfolder
        (dataset_dir / "documents" / "readme.txt").write_text(f"README for {dataset_name}")
        (dataset_dir / "documents" / "manual.pdf").write_text(f"Manual for {dataset_name}")

        (dataset_dir / "images" / "logo.png").write_text(f"Logo for {dataset_name}")
        (dataset_dir / "images" / "screenshot.jpg").write_text(f"Screenshot for {dataset_name}")

        (dataset_dir / "data" / "config.json").write_text(f'{{"dataset": "{dataset_name}"}}')
        (dataset_dir / "data" / "values.csv").write_text(f"name,value\n{dataset_name},100")

        (dataset_dir / "misc" / "notes.txt").write_text(f"Notes for {dataset_name}")

        # Create some files at root level
        (dataset_dir / "summary.txt").write_text(f"Summary of {dataset_name}")

    return base_dir


@pytest.fixture
def multilevel_dataset(tmp_path):
    """Create a dataset with deep nested structure for testing."""
    dataset_dir = tmp_path / "multilevel_dataset"
    dataset_dir.mkdir()

    # Create deep nested structure
    current_dir = dataset_dir
    levels = ["level1", "level2", "level3", "level4", "level5"]

    for i, level in enumerate(levels):
        current_dir = current_dir / level
        current_dir.mkdir()

        # Create a file at each level
        (current_dir / f"file_at_{level}.txt").write_text(f"Content at {level}")

        # Create some additional structure at specific levels
        if i == 1:  # level2
            (current_dir / "branch_a").mkdir()
            (current_dir / "branch_b").mkdir()
            (current_dir / "branch_a" / "branch_file_a.txt").write_text("Branch A content")
            (current_dir / "branch_b" / "branch_file_b.txt").write_text("Branch B content")

    return dataset_dir


@pytest.fixture
def problematic_dataset(tmp_path):
    """Create a dataset with potentially problematic files for testing edge cases."""
    dataset_dir = tmp_path / "problematic_dataset"
    dataset_dir.mkdir()

    # Create files with edge case names and content
    edge_cases = {
        "empty_file.txt": "",
        "file_with_newlines\nin_name.txt": "Content with problematic filename",
        "very_long_filename_" + "x" * 200 + ".txt": "Long filename content",
        ".hidden_file": "Hidden file content",
        "file.with.many.dots.txt": "Many dots in filename",
        "file-with-unicode-🚀.txt": "Unicode emoji in filename",
    }

    for filename, content in edge_cases.items():
        try:
            file_path = dataset_dir / filename
            file_path.write_text(content, encoding='utf-8')
        except (OSError, UnicodeError):
            # Skip files that can't be created on this platform
            continue

    # Create a very large file
    try:
        large_file = dataset_dir / "large_file.txt"
        large_content = "A" * (1024 * 1024)  # 1MB
        large_file.write_text(large_content)
    except OSError:
        pass

    return dataset_dir


@pytest.fixture
def mock_cli_args():
    """Factory fixture for creating mock CLI arguments."""
    def _create_args(input_path, output_path, **kwargs):
        """Create mock argparse.Namespace with specified arguments."""
        args = argparse.Namespace()
        args.input_folder = str(input_path)
        args.output_folder = str(output_path)
        args.num_datasets = kwargs.get('num_datasets', 3)
        args.datasets = kwargs.get('datasets', None)
        args.subfolders = kwargs.get('subfolders', None)
        return args

    return _create_args


# Import mock data generation utilities
from tests.test_fixtures.mock_data_generator import MockDataGenerator, DatasetBuilder, create_complete_test_datasets


@pytest.fixture
def mock_data_generator():
    """Provide a mock data generator with fixed seed for reproducible tests."""
    return MockDataGenerator(seed=42)


@pytest.fixture
def test_datasets(tmp_path, mock_data_generator):
    """Create complete test dataset structure as specified in test plan."""
    datasets_path = tmp_path / "test_datasets"
    builder = DatasetBuilder(datasets_path, mock_data_generator)

    # Create all specified datasets
    created_datasets = {
        'small_dataset': builder.create_small_dataset(),
        'unicode_dataset': builder.create_unicode_dataset(),
        'edge_cases': builder.create_edge_cases_dataset(),
        'size_variants': builder.create_size_variant_dataset()
    }

    manifest = builder.get_creation_manifest()
    manifest['datasets'] = {name: str(path) for name, path in created_datasets.items()}

    return {
        'base_path': datasets_path,
        'datasets': created_datasets,
        'manifest': manifest,
        'builder': builder
    }


@pytest.fixture
def small_dataset(tmp_path, mock_data_generator):
    """Create the small_dataset structure for focused testing."""
    datasets_path = tmp_path / "test_datasets"
    builder = DatasetBuilder(datasets_path, mock_data_generator)
    dataset_path = builder.create_small_dataset()

    return {
        'path': dataset_path,
        'builder': builder,
        'manifest': builder.get_creation_manifest()
    }


@pytest.fixture
def unicode_dataset(tmp_path, mock_data_generator):
    """Create the unicode_dataset structure for international filename testing."""
    datasets_path = tmp_path / "test_datasets"
    builder = DatasetBuilder(datasets_path, mock_data_generator)
    dataset_path = builder.create_unicode_dataset()

    return {
        'path': dataset_path,
        'builder': builder,
        'manifest': builder.get_creation_manifest()
    }


@pytest.fixture
def edge_cases_dataset(tmp_path, mock_data_generator):
    """Create the edge_cases dataset for problematic filename testing."""
    datasets_path = tmp_path / "test_datasets"
    builder = DatasetBuilder(datasets_path, mock_data_generator)
    dataset_path = builder.create_edge_cases_dataset()

    return {
        'path': dataset_path,
        'builder': builder,
        'manifest': builder.get_creation_manifest()
    }


@pytest.fixture
def performance_dataset(tmp_path, mock_data_generator):
    """Create a dataset with many files for performance testing."""
    datasets_path = tmp_path / "test_datasets"
    builder = DatasetBuilder(datasets_path, mock_data_generator)
    dataset_path = builder.create_performance_dataset(num_files=100)  # Reduced for test speed

    return {
        'path': dataset_path,
        'builder': builder,
        'manifest': builder.get_creation_manifest()
    }


@pytest.fixture
def deterministic_file_content():
    """Provide factory for creating files with deterministic content for hash verification."""
    def _create_file(file_path, content_type="text", size=1024, seed=42):
        generator = MockDataGenerator(seed=seed)
        return generator.create_file(file_path, content_type, size)

    return _create_file


@pytest.fixture
def known_hash_files(tmp_path):
    """Create files with known, reproducible hashes for verification testing."""
    generator = MockDataGenerator(seed=123)  # Fixed seed for known hashes
    files = {}

    # Create files with specific, known content
    test_cases = [
        ("text_small.txt", "text", 100),
        ("text_medium.txt", "text", 1024),
        ("binary_small.bin", "binary", 256),
        ("json_simple.json", "json", None),
        ("csv_data.csv", "csv", None),
        ("empty.txt", "empty", None)
    ]

    for filename, content_type, size in test_cases:
        file_path = tmp_path / filename
        metadata = generator.create_file(file_path, content_type, size)
        files[filename] = {
            'path': file_path,
            'expected_hash': metadata['sha256_hash'],
            'expected_size': metadata['size_bytes'],
            'content_type': content_type
        }

    return files


@pytest.fixture(scope="session")
def reference_hashes():
    """Provide reference hashes for deterministic content verification."""
    # These hashes are calculated from the deterministic content with seed=42
    # This allows tests to verify that content generation is truly deterministic
    return {
        'text_100_bytes_seed42': '1234567890abcdef',  # Placeholder - calculate actual
        'binary_256_bytes_seed42': 'fedcba0987654321',  # Placeholder - calculate actual
        'json_simple_seed42': 'abcdef1234567890',  # Placeholder - calculate actual
    }


@pytest.fixture
def cleanup_test_data():
    """Provide cleanup utility for test data."""
    cleanup_paths = []

    def register_for_cleanup(path):
        cleanup_paths.append(Path(path))

    yield register_for_cleanup

    # Cleanup after test
    import shutil
    for path in cleanup_paths:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()