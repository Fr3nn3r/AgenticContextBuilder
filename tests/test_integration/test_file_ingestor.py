#!/usr/bin/env python3
"""
Integration tests for the file ingestion system.
Tests end-to-end functionality with real files and directory structures.
"""

import json
from pathlib import Path
import pytest

from intake.ingest import FileIngestor


class TestFileIngestor:
    """Integration test suite for the FileIngestor class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.ingestor = FileIngestor()

    def test_ingest_single_file(self, tmp_path):
        """Test ingesting a single file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, world!")

        result = self.ingestor.ingest_file(test_file)

        # Should have metadata from MetadataProcessor
        assert 'file_metadata' in result
        assert result['file_metadata']['file_name'] == "test.txt"
        assert result['file_metadata']['file_size_bytes'] == len("Hello, world!")

    def test_ingest_dataset_folder_basic(self, tmp_path):
        """Test ingesting a basic dataset folder."""
        # Create test dataset structure
        dataset_path = tmp_path / "test_dataset"
        dataset_path.mkdir()

        # Create test files
        (dataset_path / "file1.txt").write_text("Content 1")
        (dataset_path / "file2.txt").write_text("Content 2")

        # Create subfolder with file
        subfolder = dataset_path / "subfolder"
        subfolder.mkdir()
        (subfolder / "file3.txt").write_text("Content 3")

        output_path = tmp_path / "output"
        ingestion_id = "test-2025-01-01-1430-1234567890-test_dataset"

        result = self.ingestor.ingest_dataset_folder(
            dataset_path, output_path, ingestion_id
        )

        # Check result structure
        assert 'dataset_info' in result
        assert 'processed_files' in result
        assert result['dataset_info']['total_files_processed'] == 3

        # Check output files were created
        output_dataset_path = output_path / ingestion_id / "dataset-test_dataset"
        assert output_dataset_path.exists()

        # Check individual intake files
        intake_files = list(output_dataset_path.rglob("*_intake.json"))
        assert len(intake_files) == 3

        # Check summary file
        summary_file = output_dataset_path / "test_dataset_summary.json"
        assert summary_file.exists()

        # Verify summary content
        with open(summary_file, 'r') as f:
            summary_data = json.load(f)
        assert summary_data['dataset_info']['total_files_processed'] == 3

    def test_ingest_dataset_folder_with_subfolders_filter(self, tmp_path):
        """Test ingesting dataset with subfolder filtering."""
        # Create test dataset structure
        dataset_path = tmp_path / "test_dataset"
        dataset_path.mkdir()

        # Create files in different subfolders
        train_folder = dataset_path / "train"
        train_folder.mkdir()
        (train_folder / "train1.txt").write_text("Train data 1")

        test_folder = dataset_path / "test"
        test_folder.mkdir()
        (test_folder / "test1.txt").write_text("Test data 1")

        val_folder = dataset_path / "validation"
        val_folder.mkdir()
        (val_folder / "val1.txt").write_text("Validation data 1")

        output_path = tmp_path / "output"
        ingestion_id = "test-2025-01-01-1430-1234567890-test_dataset"

        # Only process train and test folders
        result = self.ingestor.ingest_dataset_folder(
            dataset_path, output_path, ingestion_id, subfolders_filter=["train", "test"]
        )

        # Should only process 2 files (validation folder excluded)
        assert result['dataset_info']['total_files_processed'] == 2

        # Check that only specified subfolders were processed
        output_dataset_path = output_path / ingestion_id / "dataset-test_dataset"
        train_intake = output_dataset_path / "train" / "train1_intake.json"
        test_intake = output_dataset_path / "test" / "test1_intake.json"
        val_intake = output_dataset_path / "validation" / "val1_intake.json"

        assert train_intake.exists()
        assert test_intake.exists()
        assert not val_intake.exists()

    def test_ingest_multiple_datasets(self, tmp_path):
        """Test ingesting multiple datasets."""
        # Create input directory with multiple datasets
        input_path = tmp_path / "datasets"
        input_path.mkdir()

        # Create first dataset
        dataset1 = input_path / "dataset1"
        dataset1.mkdir()
        (dataset1 / "file1.txt").write_text("Dataset 1 content")

        # Create second dataset
        dataset2 = input_path / "dataset2"
        dataset2.mkdir()
        (dataset2 / "file2.txt").write_text("Dataset 2 content")

        # Create third dataset
        dataset3 = input_path / "dataset3"
        dataset3.mkdir()
        (dataset3 / "file3.txt").write_text("Dataset 3 content")

        output_path = tmp_path / "output"

        # Process only 2 datasets
        result = self.ingestor.ingest_multiple_datasets(
            input_path, output_path, num_datasets=2
        )

        # Check overall result
        assert 'ingestion_summary' in result
        assert result['ingestion_summary']['datasets_processed'] == 2
        assert result['ingestion_summary']['total_files_processed'] == 2

        # Check that ingestion ID was used consistently
        ingestion_id = result['ingestion_summary']['ingestion_id']
        assert ingestion_id.startswith("intake-")

        # Check output structure
        output_ingestion_path = output_path / ingestion_id
        assert output_ingestion_path.exists()

        # Check that only 2 dataset folders were created
        dataset_folders = [d for d in output_ingestion_path.iterdir() if d.is_dir() and d.name.startswith("dataset-")]
        assert len(dataset_folders) == 2

        # Check overall summary file
        summary_file = output_ingestion_path / "ingestion_summary.json"
        assert summary_file.exists()

    def test_ingest_specific_datasets(self, tmp_path):
        """Test ingesting specific named datasets."""
        # Create input directory with multiple datasets
        input_path = tmp_path / "datasets"
        input_path.mkdir()

        # Create datasets
        for i in range(1, 4):
            dataset = input_path / f"dataset{i}"
            dataset.mkdir()
            (dataset / f"file{i}.txt").write_text(f"Dataset {i} content")

        output_path = tmp_path / "output"

        # Process only specific datasets
        result = self.ingestor.ingest_multiple_datasets(
            input_path, output_path, specific_datasets=["dataset1", "dataset3"]
        )

        # Check that only specified datasets were processed
        assert result['ingestion_summary']['datasets_processed'] == 2
        assert "dataset1" in result['ingestion_summary']['processed_datasets']
        assert "dataset3" in result['ingestion_summary']['processed_datasets']
        assert "dataset2" not in result['ingestion_summary']['processed_datasets']

    def test_ingest_with_custom_config(self, tmp_path):
        """Test ingesting with custom configuration."""
        # Create ingestor with custom config
        config = {
            'processors': [
                {
                    'name': 'MetadataProcessor',
                    'config': {'include_hashes': False}
                }
            ]
        }
        ingestor = FileIngestor(config)

        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, world!")

        result = ingestor.ingest_file(test_file)

        # Should have output from MetadataProcessor
        assert 'file_metadata' in result

        # Hashes should be disabled
        assert 'hashes' not in result['file_metadata']

    def test_error_handling_nonexistent_dataset(self, tmp_path):
        """Test error handling for non-existent datasets."""
        input_path = tmp_path / "datasets"
        input_path.mkdir()

        # Create one real dataset
        real_dataset = input_path / "real_dataset"
        real_dataset.mkdir()
        (real_dataset / "file.txt").write_text("content")

        output_path = tmp_path / "output"

        # Try to process non-existent dataset
        with pytest.raises(ValueError, match="No valid datasets found"):
            self.ingestor.ingest_multiple_datasets(
                input_path, output_path, specific_datasets=["nonexistent"]
            )

    def test_error_handling_empty_input_directory(self, tmp_path):
        """Test error handling for empty input directory."""
        input_path = tmp_path / "empty_datasets"
        input_path.mkdir()

        output_path = tmp_path / "output"

        # Try to process empty directory
        with pytest.raises(ValueError, match="No dataset folders found"):
            self.ingestor.ingest_multiple_datasets(input_path, output_path)

    def test_intake_file_structure(self, tmp_path):
        """Test that intake files have correct structure."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, world!")

        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        test_file = dataset_path / "test.txt"
        test_file.write_text("Hello, world!")

        output_path = tmp_path / "output"
        ingestion_id = "test-2025-01-01-1430-1234567890-dataset"

        self.ingestor.ingest_dataset_folder(dataset_path, output_path, ingestion_id)

        # Find and check intake file
        intake_file = output_path / ingestion_id / "dataset-dataset" / "test_intake.json"
        assert intake_file.exists()

        with open(intake_file, 'r') as f:
            intake_data = json.load(f)

        # Check required top-level keys
        assert 'processing_info' in intake_data
        assert 'file_metadata' in intake_data
        # file_content may or may not exist depending on if ContentProcessor is configured

        # Check processing info structure
        processing_info = intake_data['processing_info']
        required_keys = [
            'ingestion_time', 'ingestion_id', 'source_dataset',
            'dataset_folder_name', 'output_path'
        ]
        for key in required_keys:
            assert key in processing_info

        # Check that ingestion_id matches
        assert processing_info['ingestion_id'] == ingestion_id

    def test_directory_structure_preservation(self, tmp_path):
        """Test that directory structure is preserved in output."""
        # Create nested directory structure
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()

        nested_dir = dataset_path / "level1" / "level2"
        nested_dir.mkdir(parents=True)
        (nested_dir / "nested_file.txt").write_text("Nested content")

        output_path = tmp_path / "output"
        ingestion_id = "test-2025-01-01-1430-1234567890-dataset"

        self.ingestor.ingest_dataset_folder(dataset_path, output_path, ingestion_id)

        # Check that nested structure is preserved
        expected_intake_path = (
            output_path / ingestion_id / "dataset-dataset" /
            "level1" / "level2" / "nested_file_intake.json"
        )
        assert expected_intake_path.exists()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])