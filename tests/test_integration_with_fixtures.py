#!/usr/bin/env python3
"""
Test integration of new fixtures with existing metadata extraction functionality.
Demonstrates using the test data fixtures with the actual extraction code.
"""

import os
import sys
import json
from pathlib import Path
import pytest

# Add the scripts directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from extract_datasets_metadata import process_dataset_folder


class TestFixturesIntegration:
    """Test integration of new fixtures with extraction functionality."""

    def test_fixture_based_extraction_workflow(self, small_dataset, tmp_path):
        """Test that fixtures integrate properly with extraction workflow - demonstrates fixture usage."""
        # This test focuses on demonstrating fixture integration rather than testing basic functionality
        dataset_path = small_dataset['path']
        manifest = small_dataset['manifest']

        # Verify fixture created expected structure
        assert manifest['total_files'] == 6
        assert (dataset_path / "documents").exists()
        assert (dataset_path / "images").exists()
        assert (dataset_path / "data").exists()

        # Quick extraction test to verify fixture compatibility
        output_path = tmp_path / "fixture_output"
        extraction_id = "fixture-demo-001"

        files_processed = process_dataset_folder(
            dataset_path, output_path, extraction_id
        )

        # Verify fixture works with extraction (basic validation only)
        assert files_processed == 6
        expected_output_dir = output_path / extraction_id / "dataset-small_dataset"
        assert expected_output_dir.exists()

        # Focus on fixture-specific verification: deterministic content
        metadata_files = list(expected_output_dir.rglob("*_metadata.json"))
        assert len(metadata_files) == 6

        # Verify that fixture-generated files have consistent properties
        for created_file in manifest['files']:
            if 'sha256_hash' in created_file:
                # Fixture files should have deterministic hashes
                assert len(created_file['sha256_hash']) == 64

    def test_fixture_special_cases_integration(self, unicode_dataset, edge_cases_dataset, tmp_path):
        """Test fixture integration with unicode and edge case datasets - demonstrates fixture robustness."""
        # This test focuses on fixture system's ability to handle edge cases

        # Test unicode dataset fixture
        unicode_manifest = unicode_dataset['manifest']
        edge_manifest = edge_cases_dataset['manifest']

        # Verify fixtures created files despite platform limitations
        assert unicode_manifest['total_files'] > 0
        assert edge_manifest['total_files'] > 0

        # Quick validation that fixtures work with extraction
        test_cases = [
            (unicode_dataset['path'], "unicode_dataset", "fixture-unicode-001"),
            (edge_cases_dataset['path'], "edge_cases", "fixture-edge-cases-001")
        ]

        for dataset_path, dataset_name, extraction_id in test_cases:
            output_path = tmp_path / f"output_{dataset_name}"

            files_processed = process_dataset_folder(
                dataset_path, output_path, extraction_id
            )

            # Should process at least some files (platform-dependent)
            assert files_processed > 0

            # Verify basic output structure
            expected_output_dir = output_path / extraction_id / f"dataset-{dataset_name}"
            assert expected_output_dir.exists()

            # Check summary exists
            summary_file = expected_output_dir / f"{dataset_name}_summary.json"
            assert summary_file.exists()

    def test_deterministic_hash_verification(self, known_hash_files, tmp_path):
        """Test that deterministic files produce expected hashes."""
        # Process each known hash file and verify the hash matches
        for i, (filename, file_info) in enumerate(known_hash_files.items()):
            file_path = file_info['path']
            expected_hash = file_info['expected_hash']

            # Create a unique dataset for each file
            dataset_path = tmp_path / f"hash_test_dataset_{i}"
            dataset_path.mkdir(exist_ok=True)

            # Copy the test file to the dataset
            test_file_path = dataset_path / filename
            test_file_path.write_bytes(file_path.read_bytes())

            # Process the dataset
            output_path = tmp_path / f"hash_output_{i}"
            extraction_id = f"hash-test-{filename}"

            files_processed = process_dataset_folder(
                dataset_path, output_path, extraction_id
            )

            assert files_processed == 1

            # Find the metadata file
            output_dir = output_path / extraction_id / f"dataset-hash_test_dataset_{i}"
            metadata_files = list(output_dir.glob("*_metadata.json"))
            assert len(metadata_files) == 1

            # Verify the hash matches
            with open(metadata_files[0], 'r') as f:
                metadata = json.load(f)

            extracted_hash = metadata['file_metadata']['hashes']['sha256']
            assert extracted_hash == expected_hash

    def test_fixture_performance_and_scale_demonstration(self, performance_dataset, tmp_path):
        """Demonstrate fixture system's ability to create large datasets efficiently."""
        dataset_path = performance_dataset['path']
        manifest = performance_dataset['manifest']

        # Focus on fixture capabilities rather than extraction testing
        assert manifest['total_files'] == 100
        assert manifest['generator_seed'] == 42  # Deterministic generation

        # Verify fixture created proper file structure
        created_files = list(dataset_path.rglob("*.txt"))
        assert len(created_files) == 100

        # Check that files are organized in folders (fixture feature)
        folders = [d for d in dataset_path.iterdir() if d.is_dir()]
        assert len(folders) == 1  # Should have organized files in 1 folder for 100 files

        # Quick validation that fixture integrates with extraction (minimal test)
        output_path = tmp_path / "performance_output"
        extraction_id = "fixture-performance-demo"

        files_processed = process_dataset_folder(
            dataset_path, output_path, extraction_id
        )

        # Verify fixture works at scale
        assert files_processed == 100

        # Verify the fixture's deterministic properties
        sample_files = created_files[:5]  # Test first 5 files
        for sample_file in sample_files:
            # All fixture-generated files should have consistent naming pattern
            assert sample_file.name.startswith("file_")
            assert sample_file.suffix == ".txt"

    def test_complete_fixture_system_capabilities(self, test_datasets, tmp_path):
        """Demonstrate the complete fixture system's capabilities and features."""
        datasets = test_datasets['datasets']
        manifest = test_datasets['manifest']
        base_path = test_datasets['base_path']

        # Verify fixture system created all expected dataset types
        expected_datasets = ['small_dataset', 'unicode_dataset', 'edge_cases', 'size_variants']
        assert len(datasets) == 4
        for dataset_name in expected_datasets:
            assert dataset_name in datasets
            assert datasets[dataset_name].exists()

        # Verify manifest tracking
        assert manifest['total_files'] > 0
        assert manifest['generator_seed'] == 42  # Deterministic
        assert 'created_at' in manifest
        assert len(manifest['files']) == manifest['total_files']

        # Test fixture system's deterministic properties
        for file_info in manifest['files']:
            if 'sha256_hash' in file_info:
                # All fixture files should have deterministic hashes
                assert len(file_info['sha256_hash']) == 64
                assert file_info['seed_used'] == 42

        # Verify different dataset characteristics
        # Small dataset should have structured folders
        small_dataset_path = datasets['small_dataset']
        assert (small_dataset_path / "documents").exists()
        assert (small_dataset_path / "images").exists()
        assert (small_dataset_path / "data").exists()

        # Size variants should have files of different sizes
        size_variants_path = datasets['size_variants']
        size_files = list(size_variants_path.glob("*.txt"))
        if len(size_files) >= 2:
            # Files should have different sizes
            sizes = [f.stat().st_size for f in size_files]
            assert len(set(sizes)) > 1  # Should have variety of sizes

        # Quick integration validation (one dataset only to avoid duplication)
        output_path = tmp_path / "fixture_system_demo"
        extraction_id = "fixture-system-demo"

        files_processed = process_dataset_folder(
            small_dataset_path, output_path, extraction_id
        )

        # Just verify fixture system works with extraction
        assert files_processed > 0
        output_dir = output_path / extraction_id / "dataset-small_dataset"
        assert output_dir.exists()

        print(f"Fixture system successfully created {manifest['total_files']} files across {len(datasets)} datasets")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])