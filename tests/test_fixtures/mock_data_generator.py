#!/usr/bin/env python3
"""
Mock data generation utilities for ContextManager tests.
Provides deterministic test data creation with various file types and sizes.
"""

import os
import json
import hashlib
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Union


class MockDataGenerator:
    """Generator for creating deterministic test data files."""

    def __init__(self, seed: int = 42):
        """Initialize generator with fixed seed for reproducible results."""
        self.seed = seed
        random.seed(seed)

    def generate_text_content(self, size_bytes: int, content_type: str = "generic") -> str:
        """Generate deterministic text content of specified size."""
        random.seed(self.seed + hash(content_type))

        if content_type == "lorem":
            base_text = (
                "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
                "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
                "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris. "
            )
        elif content_type == "technical":
            base_text = (
                "The quick brown fox jumps over the lazy dog. "
                "This is a technical document containing various metrics and data points. "
                "Error rates: 0.01%, Throughput: 1000 req/s, Latency: 50ms. "
            )
        elif content_type == "structured":
            base_text = (
                "Section 1: Introduction\n"
                "This document outlines the key findings from our analysis.\n\n"
                "Section 2: Methodology\n"
                "We employed various statistical methods to analyze the data.\n\n"
            )
        else:
            base_text = (
                "This is generic test content for file generation purposes. "
                "It contains repeatable patterns that can be used for verification. "
                "Data integrity is important for testing purposes. "
            )

        # Add some randomness based on seed to make different seeds produce different content
        random_suffix = f" Random seed value: {random.randint(1000, 9999)}. "
        base_text += random_suffix

        # Repeat and truncate to get exact size
        repetitions = (size_bytes // len(base_text)) + 1
        content = (base_text * repetitions)[:size_bytes]
        return content

    def generate_binary_content(self, size_bytes: int, pattern_type: str = "sequential") -> bytes:
        """Generate deterministic binary content of specified size."""
        random.seed(self.seed + hash(pattern_type))

        if pattern_type == "sequential":
            # Create pattern of sequential bytes
            pattern = bytes(range(256))
            repetitions = (size_bytes // 256) + 1
            content = (pattern * repetitions)[:size_bytes]
        elif pattern_type == "random":
            # Create pseudo-random but deterministic content
            content = bytes(random.randint(0, 255) for _ in range(size_bytes))
        elif pattern_type == "alternating":
            # Create alternating pattern
            content = bytes((i % 2) * 255 for i in range(size_bytes))
        else:
            # Default pattern
            content = bytes(i % 256 for i in range(size_bytes))

        return content

    def generate_json_content(self, complexity: str = "simple") -> str:
        """Generate deterministic JSON content with specified complexity."""
        random.seed(self.seed + hash(complexity))

        if complexity == "simple":
            data = {
                "name": "test_document",
                "version": "1.0.0",
                "timestamp": "2025-01-01T12:00:00Z",
                "status": "active"
            }
        elif complexity == "nested":
            data = {
                "metadata": {
                    "created": "2025-01-01T12:00:00Z",
                    "author": "test_user",
                    "version": {
                        "major": 1,
                        "minor": 0,
                        "patch": 0
                    }
                },
                "content": {
                    "sections": [
                        {"id": 1, "title": "Introduction", "pages": 5},
                        {"id": 2, "title": "Methods", "pages": 10},
                        {"id": 3, "title": "Results", "pages": 15}
                    ],
                    "total_pages": 30
                },
                "tags": ["test", "documentation", "sample"]
            }
        elif complexity == "array_heavy":
            data = {
                "items": [
                    {"id": i, "value": f"item_{i}", "score": random.randint(1, 100)}
                    for i in range(50)
                ],
                "summary": {
                    "total_items": 50,
                    "avg_score": 50.5
                }
            }
        else:
            data = {"test": True, "data": "sample"}

        return json.dumps(data, indent=2, sort_keys=True)

    def generate_csv_content(self, rows: int = 100, columns: List[str] = None) -> str:
        """Generate deterministic CSV content."""
        random.seed(self.seed)

        if columns is None:
            columns = ["id", "name", "value", "timestamp", "status"]

        lines = [",".join(columns)]

        for i in range(rows):
            row_data = []
            for col in columns:
                if col == "id":
                    row_data.append(str(i + 1))
                elif col == "name":
                    row_data.append(f"item_{i:03d}")
                elif col == "value":
                    row_data.append(str(random.randint(1, 1000)))
                elif col == "timestamp":
                    row_data.append(f"2025-01-{(i % 30) + 1:02d}T12:00:00Z")
                elif col == "status":
                    row_data.append(random.choice(["active", "inactive", "pending"]))
                else:
                    row_data.append(f"data_{i}")

            lines.append(",".join(row_data))

        return "\n".join(lines)

    def create_file(self, file_path: Path, content_type: str, size_bytes: Optional[int] = None, **kwargs) -> Dict:
        """Create a file with specified content type and return metadata."""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        created_at = datetime.now()

        if content_type == "text":
            size = size_bytes or 1024
            content = self.generate_text_content(size, kwargs.get('text_type', 'generic'))
            file_path.write_text(content, encoding='utf-8')

        elif content_type == "binary":
            size = size_bytes or 1024
            content = self.generate_binary_content(size, kwargs.get('pattern_type', 'sequential'))
            file_path.write_bytes(content)

        elif content_type == "json":
            content = self.generate_json_content(kwargs.get('complexity', 'simple'))
            file_path.write_text(content, encoding='utf-8')

        elif content_type == "csv":
            content = self.generate_csv_content(
                kwargs.get('rows', 100),
                kwargs.get('columns', None)
            )
            file_path.write_text(content, encoding='utf-8')

        elif content_type == "empty":
            file_path.write_text("", encoding='utf-8')

        else:
            # Default to text content
            content = self.generate_text_content(size_bytes or 1024)
            file_path.write_text(content, encoding='utf-8')

        # Calculate file hash for verification
        if file_path.exists():
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
        else:
            file_hash = None

        return {
            'path': str(file_path),
            'content_type': content_type,
            'size_bytes': file_path.stat().st_size if file_path.exists() else 0,
            'created_at': created_at.isoformat(),
            'sha256_hash': file_hash,
            'seed_used': self.seed
        }


class DatasetBuilder:
    """Builder for creating complete test dataset structures."""

    def __init__(self, base_path: Path, generator: MockDataGenerator = None):
        """Initialize builder with base path and optional generator."""
        self.base_path = Path(base_path)
        self.generator = generator or MockDataGenerator()
        self.created_files = []

    def create_small_dataset(self) -> Path:
        """Create the small_dataset structure as specified in the test plan."""
        dataset_path = self.base_path / "small_dataset"

        # Documents folder
        docs_path = dataset_path / "documents"
        self.created_files.append(
            self.generator.create_file(
                docs_path / "sample.pdf",
                "text",
                2048,
                text_type="technical"
            )
        )
        self.created_files.append(
            self.generator.create_file(
                docs_path / "report.docx",
                "text",
                4096,
                text_type="structured"
            )
        )

        # Images folder
        images_path = dataset_path / "images"
        self.created_files.append(
            self.generator.create_file(
                images_path / "chart.png",
                "binary",
                8192,
                pattern_type="random"
            )
        )
        self.created_files.append(
            self.generator.create_file(
                images_path / "photo.jpg",
                "binary",
                16384,
                pattern_type="sequential"
            )
        )

        # Data folder
        data_path = dataset_path / "data"
        self.created_files.append(
            self.generator.create_file(
                data_path / "data.csv",
                "csv",
                rows=50,
                columns=["id", "name", "value", "category"]
            )
        )
        self.created_files.append(
            self.generator.create_file(
                data_path / "config.json",
                "json",
                complexity="nested"
            )
        )

        return dataset_path

    def create_unicode_dataset(self) -> Path:
        """Create the unicode_dataset structure with international filenames."""
        dataset_path = self.base_path / "unicode_dataset"

        # Files with unicode names
        unicode_files = [
            ("файл.txt", "text", {"text_type": "lorem"}),  # Russian
            ("文档.pdf", "text", {"text_type": "technical"}),  # Chinese
            ("मस्केट.jpg", "binary", {"pattern_type": "alternating"})  # Hindi
        ]

        for filename, content_type, kwargs in unicode_files:
            try:
                self.created_files.append(
                    self.generator.create_file(
                        dataset_path / filename,
                        content_type,
                        2048,
                        **kwargs
                    )
                )
            except (UnicodeError, OSError) as e:
                # Skip files that can't be created on this platform
                print(f"Skipping {filename}: {e}")

        return dataset_path

    def create_edge_cases_dataset(self) -> Path:
        """Create the edge_cases dataset with problematic filenames."""
        dataset_path = self.base_path / "edge_cases"

        # Edge case files
        edge_cases = [
            ("empty_file.txt", "empty", {}),
            ("very_long_filename_that_exceeds_normal_limits_and_continues_to_be_very_long_indeed.doc",
             "text", {"text_type": "lorem"}),
            ("special!@#$%^&*()_+chars.txt", "text", {"text_type": "technical"})
        ]

        for filename, content_type, kwargs in edge_cases:
            try:
                self.created_files.append(
                    self.generator.create_file(
                        dataset_path / filename,
                        content_type,
                        1024,
                        **kwargs
                    )
                )
            except (OSError, UnicodeError) as e:
                # Skip files that can't be created on this platform
                print(f"Skipping {filename}: {e}")

        return dataset_path

    def create_performance_dataset(self, num_files: int = 1000) -> Path:
        """Create a dataset with many files for performance testing."""
        dataset_path = self.base_path / "performance_dataset"

        for i in range(num_files):
            folder = f"folder_{i // 100:03d}"  # Group files in folders of 100
            filename = f"file_{i:06d}.txt"

            self.created_files.append(
                self.generator.create_file(
                    dataset_path / folder / filename,
                    "text",
                    random.randint(100, 10000),
                    text_type="generic"
                )
            )

        return dataset_path

    def create_size_variant_dataset(self) -> Path:
        """Create dataset with files of various sizes."""
        dataset_path = self.base_path / "size_variants"

        sizes = [
            ("tiny.txt", 10),          # 10 bytes
            ("small.txt", 1024),       # 1 KB
            ("medium.txt", 100*1024),  # 100 KB
            ("large.txt", 1024*1024),  # 1 MB
        ]

        for filename, size in sizes:
            self.created_files.append(
                self.generator.create_file(
                    dataset_path / filename,
                    "text",
                    size,
                    text_type="lorem"
                )
            )

        return dataset_path

    def get_creation_manifest(self) -> Dict:
        """Get manifest of all created files with their metadata."""
        return {
            'base_path': str(self.base_path),
            'total_files': len(self.created_files),
            'created_at': datetime.now().isoformat(),
            'generator_seed': self.generator.seed,
            'files': self.created_files
        }

    def cleanup(self):
        """Clean up all created test files."""
        import shutil
        if self.base_path.exists():
            shutil.rmtree(self.base_path)


def create_complete_test_datasets(base_path: Path, seed: int = 42) -> Dict:
    """Create all test datasets and return creation manifest."""
    generator = MockDataGenerator(seed=seed)
    builder = DatasetBuilder(base_path, generator)

    # Create all dataset types
    datasets = {
        'small_dataset': builder.create_small_dataset(),
        'unicode_dataset': builder.create_unicode_dataset(),
        'edge_cases': builder.create_edge_cases_dataset(),
        'size_variants': builder.create_size_variant_dataset()
    }

    manifest = builder.get_creation_manifest()
    manifest['datasets'] = {name: str(path) for name, path in datasets.items()}

    return manifest


if __name__ == '__main__':
    # Example usage
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "test_datasets"
        manifest = create_complete_test_datasets(test_path)

        print("Created test datasets:")
        print(f"Total files: {manifest['total_files']}")
        for dataset_name, dataset_path in manifest['datasets'].items():
            print(f"  {dataset_name}: {dataset_path}")