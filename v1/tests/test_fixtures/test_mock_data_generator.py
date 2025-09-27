#!/usr/bin/env python3
"""
Tests for the mock data generator and test dataset fixtures.
Verifies that the test data generation is working correctly and deterministically.
"""

import os
import hashlib
from pathlib import Path
import pytest

from tests.test_fixtures.mock_data_generator import MockDataGenerator, DatasetBuilder


class TestMockDataGenerator:
    """Test the mock data generator functionality."""

    def test_deterministic_text_generation(self):
        """Test that text generation is deterministic with same seed."""
        gen1 = MockDataGenerator(seed=42)
        gen2 = MockDataGenerator(seed=42)

        content1 = gen1.generate_text_content(1000, "lorem")
        content2 = gen2.generate_text_content(1000, "lorem")

        assert content1 == content2
        assert len(content1) == 1000

    def test_deterministic_binary_generation(self):
        """Test that binary generation is deterministic with same seed."""
        gen1 = MockDataGenerator(seed=42)
        gen2 = MockDataGenerator(seed=42)

        content1 = gen1.generate_binary_content(256, "sequential")
        content2 = gen2.generate_binary_content(256, "sequential")

        assert content1 == content2
        assert len(content1) == 256

    def test_different_seeds_produce_different_content(self):
        """Test that different seeds produce different content."""
        gen1 = MockDataGenerator(seed=42)
        gen2 = MockDataGenerator(seed=99)

        content1 = gen1.generate_text_content(1000, "lorem")
        content2 = gen2.generate_text_content(1000, "lorem")

        assert content1 != content2
        assert len(content1) == len(content2) == 1000

    def test_json_content_generation(self):
        """Test JSON content generation."""
        gen = MockDataGenerator(seed=42)

        simple_json = gen.generate_json_content("simple")
        nested_json = gen.generate_json_content("nested")

        assert '"name": "test_document"' in simple_json
        assert '"metadata"' in nested_json
        assert simple_json != nested_json

    def test_csv_content_generation(self):
        """Test CSV content generation."""
        gen = MockDataGenerator(seed=42)

        csv_content = gen.generate_csv_content(10, ["id", "name", "value"])
        lines = csv_content.split('\n')

        assert len(lines) == 11  # Header + 10 rows
        assert lines[0] == "id,name,value"
        assert lines[1].startswith("1,item_000,")

    def test_file_creation_with_metadata(self, tmp_path):
        """Test file creation returns correct metadata."""
        gen = MockDataGenerator(seed=42)
        file_path = tmp_path / "test_file.txt"

        metadata = gen.create_file(file_path, "text", 500)

        assert file_path.exists()
        assert metadata['size_bytes'] == 500
        assert metadata['content_type'] == "text"
        assert metadata['sha256_hash'] is not None
        assert len(metadata['sha256_hash']) == 64  # SHA256 hex length


class TestDatasetFixtures:
    """Test the dataset fixtures work correctly."""

    def test_small_dataset_fixture(self, small_dataset):
        """Test the small_dataset fixture creates expected structure."""
        dataset_path = small_dataset['path']
        manifest = small_dataset['manifest']

        # Check directory structure exists
        assert (dataset_path / "documents").exists()
        assert (dataset_path / "images").exists()
        assert (dataset_path / "data").exists()

        # Check specific files exist
        assert (dataset_path / "documents" / "sample.pdf").exists()
        assert (dataset_path / "documents" / "report.docx").exists()
        assert (dataset_path / "images" / "chart.png").exists()
        assert (dataset_path / "images" / "photo.jpg").exists()
        assert (dataset_path / "data" / "data.csv").exists()
        assert (dataset_path / "data" / "config.json").exists()

        # Check manifest has correct number of files
        assert manifest['total_files'] == 6

    def test_unicode_dataset_fixture(self, unicode_dataset):
        """Test the unicode_dataset fixture creates international files."""
        dataset_path = unicode_dataset['path']
        manifest = unicode_dataset['manifest']

        # Check that at least some unicode files were created
        # (Some may be skipped on platforms that don't support them)
        assert manifest['total_files'] > 0

        # Check that files with unicode names exist (if supported)
        created_files = list(dataset_path.rglob("*"))
        assert len(created_files) > 0

    def test_edge_cases_dataset_fixture(self, edge_cases_dataset):
        """Test the edge_cases_dataset fixture creates problematic files."""
        dataset_path = edge_cases_dataset['path']
        manifest = edge_cases_dataset['manifest']

        # Check that files were created
        assert manifest['total_files'] > 0

        # Look for specific edge case files that should be createable
        created_files = [f.name for f in dataset_path.rglob("*") if f.is_file()]

        # Empty file should always be createable
        assert any("empty_file" in filename for filename in created_files)

    def test_test_datasets_fixture(self, test_datasets):
        """Test the complete test_datasets fixture."""
        datasets = test_datasets['datasets']
        manifest = test_datasets['manifest']

        # Check all expected datasets were created
        expected_datasets = ['small_dataset', 'unicode_dataset', 'edge_cases', 'size_variants']
        for dataset_name in expected_datasets:
            assert dataset_name in datasets
            assert datasets[dataset_name].exists()

        # Check manifest
        assert manifest['total_files'] > 0
        assert manifest['generator_seed'] == 42

    def test_known_hash_files_fixture(self, known_hash_files):
        """Test the known_hash_files fixture provides verifiable hashes."""
        # Verify that files exist and have expected hashes
        for filename, file_info in known_hash_files.items():
            file_path = file_info['path']
            expected_hash = file_info['expected_hash']

            assert file_path.exists()

            # Recalculate hash and verify it matches
            with open(file_path, 'rb') as f:
                actual_hash = hashlib.sha256(f.read()).hexdigest()

            assert actual_hash == expected_hash

    def test_deterministic_file_content_fixture(self, deterministic_file_content, tmp_path):
        """Test the deterministic file content factory."""
        file_path = tmp_path / "deterministic_test.txt"

        # Create file twice with same parameters
        metadata1 = deterministic_file_content(file_path, "text", 1000, seed=123)
        hash1 = metadata1['sha256_hash']

        # Remove and recreate
        file_path.unlink()
        metadata2 = deterministic_file_content(file_path, "text", 1000, seed=123)
        hash2 = metadata2['sha256_hash']

        # Should have identical hashes
        assert hash1 == hash2
        assert metadata1['size_bytes'] == metadata2['size_bytes'] == 1000

    def test_performance_dataset_fixture(self, performance_dataset):
        """Test the performance dataset has many files."""
        dataset_path = performance_dataset['path']
        manifest = performance_dataset['manifest']

        # Should have created 100 files (as specified in fixture)
        assert manifest['total_files'] == 100

        # Check that files are distributed across folders
        created_files = list(dataset_path.rglob("*.txt"))
        assert len(created_files) == 100

        # Check folder structure (files grouped in folders of 100)
        folders = [d for d in dataset_path.iterdir() if d.is_dir()]
        assert len(folders) == 1  # Should have 1 folder for 100 files


class TestDeterministicBehavior:
    """Test that the mock data generation is truly deterministic."""

    def test_reproducible_hashes(self, tmp_path):
        """Test that same parameters always produce same file hashes."""
        # Create two generators with same seed
        gen1 = MockDataGenerator(seed=999)
        gen2 = MockDataGenerator(seed=999)

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        # Create identical files
        metadata1 = gen1.create_file(file1, "text", 2048, text_type="lorem")
        metadata2 = gen2.create_file(file2, "text", 2048, text_type="lorem")

        # Should have identical hashes
        assert metadata1['sha256_hash'] == metadata2['sha256_hash']
        assert metadata1['size_bytes'] == metadata2['size_bytes']

    def test_different_content_types_different_hashes(self, tmp_path):
        """Test that different content types produce different hashes."""
        gen = MockDataGenerator(seed=42)

        files = {}
        content_types = ["text", "binary", "json", "csv"]

        for content_type in content_types:
            file_path = tmp_path / f"test_{content_type}"
            metadata = gen.create_file(file_path, content_type, 1024)
            files[content_type] = metadata['sha256_hash']

        # All hashes should be different
        hash_values = list(files.values())
        assert len(set(hash_values)) == len(hash_values)

    def test_size_affects_content(self, tmp_path):
        """Test that different sizes produce different content."""
        gen = MockDataGenerator(seed=42)

        sizes = [100, 500, 1000, 2000]
        hashes = []

        for size in sizes:
            file_path = tmp_path / f"test_{size}.txt"
            metadata = gen.create_file(file_path, "text", size)
            hashes.append(metadata['sha256_hash'])

        # All hashes should be different
        assert len(set(hashes)) == len(hashes)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])