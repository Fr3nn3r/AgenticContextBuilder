#!/usr/bin/env python3
"""
Demo script showing how to use the test data fixtures.
Creates sample datasets for manual inspection and testing.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from mock_data_generator import create_complete_test_datasets, MockDataGenerator


def demo_mock_data_generator():
    """Demonstrate basic MockDataGenerator usage."""
    print("=== MockDataGenerator Demo ===")

    gen = MockDataGenerator(seed=42)

    # Generate different types of content
    text_content = gen.generate_text_content(200, "lorem")
    print(f"Generated text content (200 bytes): {text_content[:50]}...")

    binary_content = gen.generate_binary_content(50, "sequential")
    print(f"Generated binary content (50 bytes): {binary_content[:20].hex()}...")

    json_content = gen.generate_json_content("simple")
    print(f"Generated JSON content: {json_content[:100]}...")

    csv_content = gen.generate_csv_content(5, ["id", "name", "value"])
    print(f"Generated CSV content (5 rows):\n{csv_content}")

    print()


def demo_test_datasets():
    """Demonstrate complete test dataset creation."""
    print("=== Test Datasets Demo ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        datasets_path = Path(tmpdir) / "demo_test_datasets"
        print(f"Creating test datasets in: {datasets_path}")

        # Create all test datasets
        manifest = create_complete_test_datasets(datasets_path, seed=42)

        print(f"Created {manifest['total_files']} files across {len(manifest['datasets'])} datasets:")

        for dataset_name, dataset_path in manifest['datasets'].items():
            dataset_dir = Path(dataset_path)
            if dataset_dir.exists():
                file_count = len(list(dataset_dir.rglob("*")))
                print(f"  {dataset_name}: {file_count} items at {dataset_path}")

                # Show some file details for small_dataset
                if dataset_name == "small_dataset":
                    print("    Contents of small_dataset:")
                    for item in sorted(dataset_dir.rglob("*")):
                        if item.is_file():
                            size = item.stat().st_size
                            print(f"      {item.relative_to(dataset_dir)}: {size} bytes")

    print()


def demo_deterministic_behavior():
    """Demonstrate that the generator produces deterministic results."""
    print("=== Deterministic Behavior Demo ===")

    # Create two generators with same seed
    gen1 = MockDataGenerator(seed=999)
    gen2 = MockDataGenerator(seed=999)

    # Generate identical content
    content1 = gen1.generate_text_content(100, "technical")
    content2 = gen2.generate_text_content(100, "technical")

    print(f"Generator 1 content: {content1[:50]}...")
    print(f"Generator 2 content: {content2[:50]}...")
    print(f"Contents are identical: {content1 == content2}")

    # Show that different seeds produce different content
    gen3 = MockDataGenerator(seed=888)
    content3 = gen3.generate_text_content(100, "technical")
    print(f"Generator 3 content: {content3[:50]}...")
    print(f"Content differs from generators 1&2: {content1 != content3}")

    print()


def demo_file_hash_verification():
    """Demonstrate file creation with hash verification."""
    print("=== File Hash Verification Demo ===")

    gen = MockDataGenerator(seed=123)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create same file twice
        file1_path = tmpdir_path / "test1.txt"
        file2_path = tmpdir_path / "test2.txt"

        metadata1 = gen.create_file(file1_path, "text", 500, text_type="lorem")

        # Reset generator with same seed
        gen = MockDataGenerator(seed=123)
        metadata2 = gen.create_file(file2_path, "text", 500, text_type="lorem")

        print(f"File 1 hash: {metadata1['sha256_hash']}")
        print(f"File 2 hash: {metadata2['sha256_hash']}")
        print(f"Hashes are identical: {metadata1['sha256_hash'] == metadata2['sha256_hash']}")
        print(f"File sizes: {metadata1['size_bytes']} vs {metadata2['size_bytes']}")

    print()


if __name__ == '__main__':
    print("Test Data Fixtures Demo")
    print("=" * 50)
    print()

    demo_mock_data_generator()
    demo_test_datasets()
    demo_deterministic_behavior()
    demo_file_hash_verification()

    print("Demo completed successfully!")
    print("\nTo use these fixtures in your tests:")
    print("1. Use @pytest.fixture decorators like 'small_dataset', 'test_datasets'")
    print("2. Use MockDataGenerator directly for custom content generation")
    print("3. All content is deterministic with fixed seeds for reproducible tests")