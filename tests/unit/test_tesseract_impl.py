"""Unit tests for TesseractAcquisition implementation."""

import logging
import platform
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest

from context_builder.acquisition import (
    ConfigurationError,
    AcquisitionError,
)


class TestTesseractAcquisitionInit:
    """Test TesseractAcquisition initialization and setup."""

    @patch('pytesseract.get_tesseract_version')
    @patch('pypdfium2.PdfDocument')
    def test_init_success_with_all_dependencies(self, mock_pdfium, mock_get_version):
        """Test successful initialization with all dependencies."""
        mock_get_version.return_value = '5.0.1'

        with patch('platform.system', return_value='Linux'):
            from context_builder.impl.tesseract_acquisition import TesseractAcquisition
            acquisition = TesseractAcquisition()

        assert acquisition.languages == ['eng']
        assert acquisition.render_scale == 2.0
        assert acquisition.max_pages == 50
        assert acquisition.enable_preprocessing is True
        assert acquisition.deskew is True
        assert acquisition.remove_noise is False
        assert acquisition.enhance_contrast is True

    @patch('pytesseract.get_tesseract_version')
    def test_init_without_opencv(self, mock_get_version, caplog):
        """Test initialization without OpenCV."""
        mock_get_version.return_value = '5.0.1'

        with patch.dict(sys.modules, {'cv2': None, 'numpy': None}):
            with patch('platform.system', return_value='Linux'):
                with caplog.at_level(logging.WARNING):
                    from context_builder.impl.tesseract_acquisition import TesseractAcquisition
                    acquisition = TesseractAcquisition()

                assert "OpenCV not available" in caplog.text
                assert acquisition.cv2 is None
                assert acquisition.np is None

    @patch('pytesseract.get_tesseract_version')
    def test_init_without_pdf_support(self, mock_get_version, caplog):
        """Test initialization without PDF support."""
        mock_get_version.return_value = '5.0.1'

        with patch.dict(sys.modules, {'pypdfium2': None}):
            with patch('platform.system', return_value='Linux'):
                with caplog.at_level(logging.WARNING):
                    from context_builder.impl.tesseract_acquisition import TesseractAcquisition
                    acquisition = TesseractAcquisition()

                assert "pypdfium2 not installed, PDF support disabled" in caplog.text
                assert acquisition.pdf_renderer is None

    def test_init_missing_pytesseract(self):
        """Test initialization fails without pytesseract."""
        with patch.dict(sys.modules, {'pytesseract': None}):
            with pytest.raises(ConfigurationError, match="Required packages not installed"):
                from context_builder.impl.tesseract_acquisition import TesseractAcquisition
                TesseractAcquisition()

    @patch('pytesseract.get_tesseract_version')
    @patch('pytesseract.TesseractNotFoundError', Exception)
    def test_init_tesseract_not_found(self, mock_get_version):
        """Test initialization fails when Tesseract binary not found."""
        mock_get_version.side_effect = Exception("Not found")

        with patch('platform.system', return_value='Linux'):
            with pytest.raises(ConfigurationError, match="Tesseract OCR not found"):
                from context_builder.impl.tesseract_acquisition import TesseractAcquisition
                TesseractAcquisition()


class TestTesseractAcquisitionWindows:
    """Test Windows-specific Tesseract setup."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock TesseractAcquisition instance."""
        from context_builder.impl.tesseract_acquisition import TesseractAcquisition
        with patch.object(TesseractAcquisition, '_setup_tesseract'):
            acquisition = TesseractAcquisition()
            acquisition.pytesseract = Mock()
            acquisition.pytesseract.pytesseract = Mock()
            return acquisition

    @patch('os.path.exists')
    @patch('os.environ.get')
    def test_find_tesseract_windows_env_var(self, mock_env_get, mock_exists, mock_acquisition):
        """Test finding Tesseract via environment variable."""
        mock_env_get.side_effect = lambda key, default=None: {
            'TESSERACT_PATH': 'C:\\Custom\\tesseract.exe',
            'USERNAME': 'testuser'
        }.get(key, default)

        mock_exists.side_effect = lambda path: path == 'C:\\Custom\\tesseract.exe'

        result = mock_acquisition._find_tesseract_windows()

        assert result is True
        assert mock_acquisition.pytesseract.pytesseract.tesseract_cmd == 'C:\\Custom\\tesseract.exe'

    @patch('os.path.exists')
    @patch('os.environ.get')
    def test_find_tesseract_windows_program_files(self, mock_env_get, mock_exists, mock_acquisition):
        """Test finding Tesseract in Program Files."""
        mock_env_get.side_effect = lambda key, default=None: {
            'TESSERACT_PATH': None,
            'USERNAME': 'testuser'
        }.get(key, default)

        mock_exists.side_effect = lambda path: path == r'C:\Program Files\Tesseract-OCR\tesseract.exe'

        result = mock_acquisition._find_tesseract_windows()

        assert result is True
        assert mock_acquisition.pytesseract.pytesseract.tesseract_cmd == r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    @patch('os.path.exists')
    @patch('os.environ.get')
    def test_find_tesseract_windows_not_found(self, mock_env_get, mock_exists, mock_acquisition):
        """Test Tesseract not found on Windows."""
        mock_env_get.return_value = None
        mock_exists.return_value = False

        result = mock_acquisition._find_tesseract_windows()

        assert result is False


class TestTesseractAcquisitionPreprocessing:
    """Test image preprocessing functionality."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock TesseractAcquisition instance."""
        from context_builder.impl.tesseract_acquisition import TesseractAcquisition
        with patch.object(TesseractAcquisition, '_setup_tesseract'):
            acquisition = TesseractAcquisition()

            # Mock PIL components
            acquisition.Image = Mock()
            acquisition.ImageEnhance = Mock()
            acquisition.ImageOps = Mock()

            return acquisition

    def test_preprocess_disabled(self, mock_acquisition):
        """Test preprocessing when disabled."""
        mock_acquisition.enable_preprocessing = False
        mock_image = Mock()

        result = mock_acquisition._preprocess_image(mock_image)

        assert result == mock_image

    def test_preprocess_grayscale_conversion(self, mock_acquisition):
        """Test grayscale conversion during preprocessing."""
        mock_image = Mock()
        mock_image.mode = 'RGB'
        mock_grayscale = Mock()
        mock_grayscale.mode = 'L'
        mock_image.convert.return_value = mock_grayscale

        # Mock contrast enhancement
        mock_enhancer = Mock()
        mock_acquisition.ImageEnhance.Contrast.return_value = mock_enhancer
        mock_enhancer.enhance.return_value = mock_grayscale

        result = mock_acquisition._preprocess_image(mock_image)

        mock_image.convert.assert_called_once_with('L')

    def test_preprocess_contrast_enhancement(self, mock_acquisition):
        """Test contrast enhancement during preprocessing."""
        mock_image = Mock()
        mock_image.mode = 'L'

        mock_enhancer = Mock()
        mock_enhanced = Mock()
        mock_enhancer.enhance.return_value = mock_enhanced
        mock_acquisition.ImageEnhance.Contrast.return_value = mock_enhancer

        result = mock_acquisition._preprocess_image(mock_image)

        mock_acquisition.ImageEnhance.Contrast.assert_called_once_with(mock_image)
        mock_enhancer.enhance.assert_called_once_with(1.5)

    def test_preprocess_with_opencv_deskew(self, mock_acquisition):
        """Test deskewing with OpenCV."""
        # Test that deskewing code path is triggered when OpenCV is available
        mock_acquisition.cv2 = Mock()
        mock_acquisition.np = Mock()
        mock_acquisition.deskew = True

        mock_image = Mock()
        mock_image.mode = 'L'

        # Create a proper numpy array mock that supports comparison
        import numpy as np
        real_array = np.ones((100, 200), dtype=np.uint8) * 255
        mock_acquisition.np.array.return_value = real_array

        # Mock np.where to work with real array
        mock_acquisition.np.where.side_effect = np.where

        # Mock column_stack to return real coords
        def column_stack_side_effect(indices):
            # Return a non-empty array of coordinates
            return np.array([[10, 20], [30, 40], [50, 60]])

        mock_acquisition.np.column_stack.side_effect = column_stack_side_effect

        # Mock minAreaRect to return significant angle
        mock_acquisition.cv2.minAreaRect.return_value = (None, None, -10.0)

        # Mock rotation matrix and warpAffine
        mock_rotation_matrix = np.array([[1, 0, 0], [0, 1, 0]])
        mock_acquisition.cv2.getRotationMatrix2D.return_value = mock_rotation_matrix
        mock_acquisition.cv2.warpAffine.return_value = real_array

        # Mock contrast enhancement
        mock_enhancer = Mock()
        mock_acquisition.ImageEnhance.Contrast.return_value = mock_enhancer
        mock_enhancer.enhance.return_value = mock_image

        # Mock PIL Image creation
        mock_result_image = Mock()
        mock_acquisition.Image.fromarray.return_value = mock_result_image

        # Mock INTER_CUBIC and BORDER_REPLICATE constants
        mock_acquisition.cv2.INTER_CUBIC = 2
        mock_acquisition.cv2.BORDER_REPLICATE = 1

        result = mock_acquisition._preprocess_image(mock_image)

        # Verify deskewing operations were called
        mock_acquisition.cv2.minAreaRect.assert_called_once()
        mock_acquisition.cv2.getRotationMatrix2D.assert_called_once()
        mock_acquisition.cv2.warpAffine.assert_called_once()

    def test_preprocess_error_handling(self, mock_acquisition, caplog):
        """Test preprocessing error handling."""
        mock_image = Mock()
        mock_image.mode = 'RGB'
        mock_image.convert.side_effect = Exception("Conversion failed")

        with caplog.at_level(logging.WARNING):
            result = mock_acquisition._preprocess_image(mock_image)

        assert result == mock_image
        assert "Image preprocessing failed" in caplog.text


class TestTesseractAcquisitionConfidence:
    """Test confidence calculation."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock TesseractAcquisition instance."""
        from context_builder.impl.tesseract_acquisition import TesseractAcquisition
        with patch.object(TesseractAcquisition, '_setup_tesseract'):
            return TesseractAcquisition()

    def test_calculate_confidence_valid_data(self, mock_acquisition):
        """Test confidence calculation with valid data."""
        data = {
            'conf': ['95', '85', '90', '-1', '80']
        }

        confidence = mock_acquisition._calculate_confidence(data)

        # Should ignore -1 and calculate weighted average
        assert 0 < confidence <= 1.0

    def test_calculate_confidence_no_valid_scores(self, mock_acquisition):
        """Test confidence calculation with no valid scores."""
        data = {
            'conf': ['-1', '-1', '-1']
        }

        confidence = mock_acquisition._calculate_confidence(data)

        assert confidence == 0.0

    def test_calculate_confidence_empty_data(self, mock_acquisition):
        """Test confidence calculation with empty data."""
        data = {}

        confidence = mock_acquisition._calculate_confidence(data)

        assert confidence == 0.0

    def test_calculate_confidence_error_handling(self, mock_acquisition):
        """Test confidence calculation error handling."""
        data = {
            'conf': ['not_a_number', 'invalid', None]
        }

        # Should handle invalid values gracefully and return 0
        confidence = mock_acquisition._calculate_confidence(data)
        assert confidence == 0.0


class TestTesseractAcquisitionTextExtraction:
    """Test text extraction from images."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock TesseractAcquisition instance."""
        from context_builder.impl.tesseract_acquisition import TesseractAcquisition
        with patch.object(TesseractAcquisition, '_setup_tesseract'):
            acquisition = TesseractAcquisition()
            acquisition.pytesseract = Mock()
            acquisition.pytesseract.Output = Mock(DICT='dict')
            acquisition.languages = ['eng', 'fra']
            return acquisition

    def test_extract_text_success(self, mock_acquisition):
        """Test successful text extraction."""
        mock_image = Mock()
        mock_processed = Mock()
        mock_acquisition._preprocess_image = Mock(return_value=mock_processed)

        # Mock Tesseract responses
        mock_data = {
            'conf': ['95', '90', '85'],
            'text': ['Hello', 'World', '!']
        }
        mock_acquisition.pytesseract.image_to_data.return_value = mock_data
        mock_acquisition.pytesseract.image_to_string.return_value = "Hello World!"

        mock_acquisition._calculate_confidence = Mock(return_value=0.9)

        result = mock_acquisition._extract_text_from_image(mock_image, page_num=1)

        assert result['page_number'] == 1
        assert result['text'] == "Hello World!"
        assert result['confidence'] == 0.9
        assert result['languages'] == ['eng', 'fra']
        assert result['preprocessed'] is True
        assert result['word_count'] == 2

    def test_extract_text_with_custom_languages(self, mock_acquisition):
        """Test text extraction with custom languages."""
        mock_acquisition.languages = ['deu', 'spa']
        mock_image = Mock()
        mock_acquisition._preprocess_image = Mock(return_value=mock_image)

        mock_acquisition.pytesseract.image_to_data.return_value = {'conf': []}
        mock_acquisition.pytesseract.image_to_string.return_value = "Test"

        result = mock_acquisition._extract_text_from_image(mock_image)

        # Verify correct language string was used
        calls = mock_acquisition.pytesseract.image_to_string.call_args_list
        assert 'deu+spa' in str(calls[0])

    def test_extract_text_error_handling(self, mock_acquisition, caplog):
        """Test text extraction error handling."""
        mock_image = Mock()
        mock_acquisition._preprocess_image = Mock(side_effect=Exception("OCR failed"))

        with caplog.at_level(logging.ERROR):
            result = mock_acquisition._extract_text_from_image(mock_image, page_num=2)

        assert result['page_number'] == 2
        assert result['text'] == ""
        assert result['confidence'] == 0.0
        assert 'error' in result
        assert "OCR failed for page 2" in caplog.text


class TestTesseractAcquisitionPDFProcessing:
    """Test PDF processing functionality."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock TesseractAcquisition instance."""
        from context_builder.impl.tesseract_acquisition import TesseractAcquisition
        with patch.object(TesseractAcquisition, '_setup_tesseract'):
            acquisition = TesseractAcquisition()
            acquisition.pdf_renderer = Mock()
            acquisition.render_scale = 2.0
            acquisition.max_pages = 50
            return acquisition

    def test_process_pdf_no_renderer(self, mock_acquisition):
        """Test PDF processing without renderer."""
        mock_acquisition.pdf_renderer = None

        with pytest.raises(ConfigurationError, match="PDF support not available"):
            mock_acquisition._process_pdf_pages(Path("test.pdf"))

    def test_process_pdf_success(self, mock_acquisition):
        """Test successful PDF processing."""
        pdf_path = Path("test.pdf")

        # Mock PDF document
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 3
        mock_acquisition.pdf_renderer.PdfDocument.return_value = mock_doc

        # Mock pages
        mock_pages = []
        for i in range(3):
            mock_page = Mock()
            mock_mat = Mock()
            mock_img = Mock()
            mock_mat.to_pil.return_value = mock_img
            mock_page.render.return_value = mock_mat
            mock_pages.append(mock_page)

        mock_doc.__getitem__.side_effect = mock_pages

        # Mock text extraction
        mock_acquisition._extract_text_from_image = Mock(side_effect=[
            {"page_number": 1, "text": "Page 1", "confidence": 0.9, "word_count": 2},
            {"page_number": 2, "text": "Page 2", "confidence": 0.85, "word_count": 2},
            {"page_number": 3, "text": "Page 3", "confidence": 0.95, "word_count": 2}
        ])

        result = mock_acquisition._process_pdf_pages(pdf_path)

        assert len(result) == 3
        assert result[0]['text'] == "Page 1"
        assert result[1]['text'] == "Page 2"
        assert result[2]['text'] == "Page 3"

        mock_doc.close.assert_called_once()

    def test_process_pdf_max_pages_limit(self, mock_acquisition, caplog):
        """Test PDF processing with max pages limit."""
        mock_acquisition.max_pages = 2
        pdf_path = Path("large.pdf")

        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 5
        mock_acquisition.pdf_renderer.PdfDocument.return_value = mock_doc

        # Mock pages
        mock_pages = []
        for i in range(2):  # Only process max_pages
            mock_page = Mock()
            mock_mat = Mock()
            mock_img = Mock()
            mock_mat.to_pil.return_value = mock_img
            mock_page.render.return_value = mock_mat
            mock_pages.append(mock_page)

        mock_doc.__getitem__.side_effect = mock_pages

        mock_acquisition._extract_text_from_image = Mock(return_value={
            "text": "text", "confidence": 0.9, "word_count": 1
        })

        with caplog.at_level(logging.WARNING):
            result = mock_acquisition._process_pdf_pages(pdf_path)

        assert len(result) == 2
        assert "PDF has 5 pages, processing only first 2" in caplog.text

    def test_process_pdf_cleanup_on_error(self, mock_acquisition):
        """Test PDF cleanup on error."""
        pdf_path = Path("test.pdf")

        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 1
        mock_acquisition.pdf_renderer.PdfDocument.return_value = mock_doc

        # Mock page that raises error
        mock_page = Mock()
        mock_page.render.side_effect = Exception("Render failed")
        mock_doc.__getitem__.return_value = mock_page

        with pytest.raises(Exception):
            mock_acquisition._process_pdf_pages(pdf_path)

        # Should still close document
        mock_doc.close.assert_called_once()


class TestTesseractAcquisitionProcessImplementation:
    """Test main processing implementation."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock TesseractAcquisition instance."""
        from context_builder.impl.tesseract_acquisition import TesseractAcquisition
        with patch.object(TesseractAcquisition, '_setup_tesseract'):
            acquisition = TesseractAcquisition()
            acquisition.Image = Mock()
            return acquisition

    @patch('context_builder.impl.tesseract_acquisition.get_file_metadata')
    def test_process_implementation_image_success(self, mock_get_metadata, mock_acquisition):
        """Test successful image file processing."""
        filepath = Path("test.jpg")

        mock_metadata = {
            "file_name": "test.jpg",
            "file_path": str(filepath),
            "file_extension": ".jpg",
            "file_size_bytes": 1024,
            "mime_type": "image/jpeg",
            "md5": "abc123"
        }
        mock_get_metadata.return_value = mock_metadata

        mock_img = Mock()
        mock_acquisition.Image.open.return_value = mock_img

        mock_page_result = {
            "page_number": 1,
            "text": "Sample text",
            "confidence": 0.92,
            "word_count": 2
        }
        mock_acquisition._extract_text_from_image = Mock(return_value=mock_page_result)

        result = mock_acquisition._process_implementation(filepath)

        assert result["file_name"] == "test.jpg"
        assert result["total_pages"] == 1
        assert result["pages"][0]["text"] == "Sample text"
        assert result["average_confidence"] == 0.92
        assert result["processor"] == "tesseract"
        assert result["tesseract_languages"] == ['eng']

    @patch('context_builder.impl.tesseract_acquisition.get_file_metadata')
    def test_process_implementation_pdf_success(self, mock_get_metadata, mock_acquisition):
        """Test successful PDF file processing."""
        filepath = Path("test.pdf")

        mock_metadata = {
            "file_name": "test.pdf",
            "file_extension": ".pdf"
        }
        mock_get_metadata.return_value = mock_metadata

        mock_pages = [
            {"page_number": 1, "text": "Page 1", "confidence": 0.9},
            {"page_number": 2, "text": "Page 2", "confidence": 0.8}
        ]
        mock_acquisition._process_pdf_pages = Mock(return_value=mock_pages)

        result = mock_acquisition._process_implementation(filepath)

        assert result["total_pages"] == 2
        assert len(result["pages"]) == 2
        assert abs(result["average_confidence"] - 0.85) < 0.001  # Use approximate equality

    @patch('context_builder.impl.tesseract_acquisition.get_file_metadata')
    def test_process_implementation_various_formats(self, mock_get_metadata, mock_acquisition):
        """Test processing various image formats."""
        formats = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif']

        mock_img = Mock()
        mock_acquisition.Image.open.return_value = mock_img
        mock_acquisition._extract_text_from_image = Mock(return_value={
            "text": "content", "confidence": 0.9
        })

        for fmt in formats:
            filepath = Path(f"test{fmt}")
            mock_get_metadata.return_value = {
                "file_extension": fmt
            }

            result = mock_acquisition._process_implementation(filepath)

            assert result["file_extension"] == fmt
            assert result["total_pages"] == 1

    @patch('context_builder.impl.tesseract_acquisition.get_file_metadata')
    def test_process_implementation_error_handling(self, mock_get_metadata, mock_acquisition, caplog):
        """Test error handling in process implementation."""
        filepath = Path("test.jpg")

        mock_get_metadata.return_value = {"file_extension": ".jpg"}
        mock_acquisition.Image.open.side_effect = Exception("Cannot open file")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(AcquisitionError, match="Failed to process file"):
                mock_acquisition._process_implementation(filepath)

        assert "Failed to process file" in caplog.text

    @patch('context_builder.impl.tesseract_acquisition.get_file_metadata')
    def test_process_implementation_logs_info(self, mock_get_metadata, mock_acquisition, caplog):
        """Test process logs appropriate info messages."""
        filepath = Path("test.jpg")

        mock_get_metadata.return_value = {"file_extension": ".jpg"}
        mock_acquisition.Image.open.return_value = Mock()
        mock_acquisition._extract_text_from_image = Mock(return_value={
            "text": "content", "confidence": 0.9
        })

        with caplog.at_level(logging.INFO):
            mock_acquisition._process_implementation(filepath)

        assert "Processing with Tesseract OCR" in caplog.text


class TestTesseractAcquisitionFactory:
    """Test factory registration."""

    def test_factory_registration(self):
        """Test TesseractAcquisition is registered with factory."""
        from context_builder.acquisition import AcquisitionFactory

        # Check that tesseract is in the registry
        assert 'tesseract' in AcquisitionFactory._registry

        # Should be able to create tesseract instance
        with patch('pytesseract.get_tesseract_version', return_value='5.0.0'):
            with patch('platform.system', return_value='Linux'):
                instance = AcquisitionFactory.create('tesseract')
                assert instance is not None