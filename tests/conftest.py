"""Shared test fixtures and utilities."""

import os
from pathlib import Path
import pytest
from unittest.mock import Mock, patch


@pytest.fixture(autouse=True)
def cleanup_env():
    """Clean up environment variables after each test."""
    original_env = os.environ.copy()
    yield
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for tests."""
    with patch('context_builder.impl.openai_vision_ingestion.OpenAI') as mock:
        client = Mock()
        mock.return_value = client
        yield client


@pytest.fixture
def sample_json_response():
    """Sample JSON response for API tests."""
    return {
        "document_type": "test_document",
        "language": "en",
        "summary": "Test summary",
        "key_information": {
            "field1": "value1",
            "field2": "value2"
        },
        "visual_elements": ["element1", "element2"],
        "text_content": "Sample text content"
    }


@pytest.fixture
def temp_image(tmp_path):
    """Create a temporary image file."""
    image_path = tmp_path / "test_image.jpg"
    # Create a minimal JPEG header (not a real image, but has correct magic bytes)
    jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    image_path.write_bytes(jpeg_header + b'fake image data')
    return image_path


@pytest.fixture
def temp_pdf(tmp_path):
    """Create a temporary PDF file."""
    pdf_path = tmp_path / "test_document.pdf"
    # Create a minimal PDF header
    pdf_header = b'%PDF-1.4\n'
    pdf_path.write_bytes(pdf_header + b'fake pdf content')
    return pdf_path


@pytest.fixture
def mock_api_response():
    """Create a mock API response object."""
    response = Mock()
    response.choices = [Mock(message=Mock(content='{"text": "test content"}'))]
    response.usage = Mock(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150
    )
    return response


@pytest.fixture
def supported_file_extensions():
    """List of all supported file extensions."""
    return ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.tiff', '.tif']


def create_test_files(directory: Path, extensions: list, prefix: str = "test"):
    """Helper to create test files with various extensions."""
    created_files = []
    for i, ext in enumerate(extensions):
        file_path = directory / f"{prefix}{i}{ext}"
        file_path.write_bytes(b"test content")
        created_files.append(file_path)
    return created_files


def create_nested_directory_structure(base_path: Path):
    """Create a nested directory structure for testing."""
    structure = {
        "root.jpg": b"root image",
        "subdir1": {
            "file1.pdf": b"pdf content",
            "file2.png": b"png content",
            "deeper": {
                "deep.gif": b"gif content"
            }
        },
        "subdir2": {
            "another.tif": b"tif content"
        }
    }

    def create_structure(path, struct):
        for name, content in struct.items():
            full_path = path / name
            if isinstance(content, dict):
                full_path.mkdir(parents=True, exist_ok=True)
                create_structure(full_path, content)
            else:
                full_path.write_bytes(content)

    create_structure(base_path, structure)
    return structure