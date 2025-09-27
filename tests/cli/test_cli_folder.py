"""CLI tests for folder processing and discovery."""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from context_builder.cli import (
    get_supported_files,
    process_folder,
    main,
)


class TestGetSupportedFiles:
    """Test file discovery functionality."""

    def test_get_supported_files_basic(self, tmp_path):
        """Test basic file discovery."""
        # Create various files
        (tmp_path / "image.jpg").touch()
        (tmp_path / "document.pdf").touch()
        (tmp_path / "text.txt").touch()  # Not supported
        (tmp_path / "photo.png").touch()

        files = get_supported_files(tmp_path)

        # Check correct files found
        names = [f.name for f in files]
        assert "image.jpg" in names
        assert "document.pdf" in names
        assert "photo.png" in names
        assert "text.txt" not in names

        # Check files are sorted
        assert names == sorted(names)

    def test_get_supported_files_case_insensitive(self, tmp_path):
        """Test case-insensitive extension matching."""
        files_to_create = [
            "IMAGE.JPG",
            "photo.Jpeg",
            "SCAN.TIF",
            "Document.PDF",
            "picture.PNG",
            "graphic.GiF",
            "bitmap.BMP"
        ]

        for filename in files_to_create:
            (tmp_path / filename).touch()

        files = get_supported_files(tmp_path)
        names = [f.name for f in files]

        # All should be found regardless of case
        assert len(names) == len(files_to_create)
        for original in files_to_create:
            assert original in names

    def test_get_supported_files_recursive(self, tmp_path):
        """Test recursive file discovery."""
        # Create nested structure
        (tmp_path / "root.jpg").touch()
        subdir1 = tmp_path / "subdir1"
        subdir1.mkdir()
        (subdir1 / "nested1.pdf").touch()

        subdir2 = tmp_path / "subdir2"
        subdir2.mkdir()
        (subdir2 / "nested2.png").touch()

        deep = tmp_path / "sub" / "deep" / "dir"
        deep.mkdir(parents=True)
        (deep / "deep.gif").touch()

        # Non-recursive
        non_recursive = get_supported_files(tmp_path, recursive=False)
        assert len(non_recursive) == 1
        assert non_recursive[0].name == "root.jpg"

        # Recursive
        recursive = get_supported_files(tmp_path, recursive=True)
        names = [f.name for f in recursive]
        assert len(names) == 4
        assert "root.jpg" in names
        assert "nested1.pdf" in names
        assert "nested2.png" in names
        assert "deep.gif" in names

    def test_get_supported_files_empty_folder(self, tmp_path):
        """Test discovery in empty folder."""
        files = get_supported_files(tmp_path)
        assert files == []

    def test_get_supported_files_no_supported_files(self, tmp_path):
        """Test discovery when no supported files exist."""
        (tmp_path / "text.txt").touch()
        (tmp_path / "data.csv").touch()
        (tmp_path / "script.py").touch()

        files = get_supported_files(tmp_path)
        assert files == []

    def test_get_supported_files_includes_tif(self, tmp_path):
        """Test .tif files are discovered."""
        (tmp_path / "scan1.tif").touch()
        (tmp_path / "scan2.TIF").touch()
        (tmp_path / "scan3.tiff").touch()
        (tmp_path / "scan4.TIFF").touch()

        files = get_supported_files(tmp_path)
        names = [f.name for f in files]

        assert len(names) == 4
        assert "scan1.tif" in names
        assert "scan2.TIF" in names
        assert "scan3.tiff" in names
        assert "scan4.TIFF" in names


class TestProcessFolder:
    """Test folder processing functionality."""

    @pytest.fixture
    def mock_acquisition(self):
        """Mock acquisition for folder tests."""
        mock = Mock()
        mock.process = Mock(return_value={
            "file_name": "test.jpg",
            "pages": [{"text": "content"}]
        })
        return mock

    @pytest.fixture
    def mock_factory(self, mock_acquisition):
        """Mock factory."""
        with patch('context_builder.cli.AcquisitionFactory') as factory:
            factory.create = Mock(return_value=mock_acquisition)
            yield factory

    def test_process_folder_basic(self, tmp_path, mock_factory, mock_acquisition):
        """Test basic folder processing."""
        # Create test files
        (tmp_path / "file1.jpg").touch()
        (tmp_path / "file2.pdf").touch()
        (tmp_path / "file3.png").touch()

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        success_count = process_folder(tmp_path, output_dir, "openai")

        # Check all files processed
        assert success_count == 3
        assert mock_acquisition.process.call_count == 3

        # Check output files created
        assert (output_dir / "file1-context.json").exists()
        assert (output_dir / "file2-context.json").exists()
        assert (output_dir / "file3-context.json").exists()

    def test_process_folder_with_session_id(self, tmp_path, mock_factory, mock_acquisition):
        """Test folder processing with session ID."""
        (tmp_path / "test.jpg").touch()
        session_id = "test123"

        process_folder(tmp_path, tmp_path, "openai", session_id=session_id)

        # Check session ID in output
        output_file = tmp_path / "test-context.json"
        with open(output_file) as f:
            data = json.load(f)
        assert data["session_id"] == session_id

    def test_process_folder_recursive(self, tmp_path, mock_factory, mock_acquisition):
        """Test recursive folder processing."""
        (tmp_path / "root.jpg").touch()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.pdf").touch()

        success_count = process_folder(tmp_path, tmp_path, "openai", recursive=True)

        assert success_count == 2
        assert mock_acquisition.process.call_count == 2

    def test_process_folder_with_config(self, tmp_path, mock_factory, mock_acquisition):
        """Test folder processing with configuration."""
        (tmp_path / "test.jpg").touch()

        config = {
            "model": "gpt-4o",
            "max_tokens": 1000,
            "temperature": 0.2
        }

        process_folder(tmp_path, tmp_path, "openai", config=config)

        # Check config applied
        assert mock_acquisition.model == "gpt-4o"
        assert mock_acquisition.max_tokens == 1000
        assert mock_acquisition.temperature == 0.2

    def test_process_folder_empty(self, tmp_path, mock_factory, caplog):
        """Test processing empty folder."""
        with caplog.at_level(logging.WARNING):
            success_count = process_folder(tmp_path, tmp_path, "openai")

        assert success_count == 0
        assert "No supported files found" in caplog.text

    def test_process_folder_with_errors(self, tmp_path, mock_factory):
        """Test folder processing with some failures."""
        (tmp_path / "file1.jpg").touch()
        (tmp_path / "file2.pdf").touch()
        (tmp_path / "file3.png").touch()

        # Mock acquisition to fail on second file
        mock_acq = Mock()
        mock_acq.process = Mock(side_effect=[
            {"result": "ok"},
            Exception("Failed"),
            {"result": "ok"}
        ])
        mock_factory.create.return_value = mock_acq

        success_count = process_folder(tmp_path, tmp_path, "openai")

        assert success_count == 2  # Two succeeded
        assert mock_acq.process.call_count == 3  # All attempted

    def test_process_folder_keyboard_interrupt(self, tmp_path, mock_factory):
        """Test handling KeyboardInterrupt during folder processing."""
        (tmp_path / "file1.jpg").touch()
        (tmp_path / "file2.pdf").touch()

        mock_acq = Mock()
        mock_acq.process = Mock(side_effect=[
            {"result": "ok"},
            KeyboardInterrupt()
        ])
        mock_factory.create.return_value = mock_acq

        with pytest.raises(KeyboardInterrupt):
            process_folder(tmp_path, tmp_path, "openai")

        # Only first file should be processed
        assert mock_acq.process.call_count == 2

    def test_process_folder_logging(self, tmp_path, mock_factory, mock_acquisition, caplog):
        """Test folder processing logs appropriate messages."""
        (tmp_path / "file1.jpg").touch()
        (tmp_path / "file2.pdf").touch()

        with caplog.at_level(logging.INFO):
            process_folder(tmp_path, tmp_path, "openai", session_id="abc")

        assert "Found 2 files to process" in caplog.text
        assert "[Session abc] [1/2] Processing:" in caplog.text
        assert "[Session abc] [2/2] Processing:" in caplog.text
        assert "Processed 2 files successfully, 0 failed" in caplog.text

    def test_process_folder_reuses_acquisition(self, tmp_path, mock_factory):
        """Test folder processing reuses acquisition instance."""
        (tmp_path / "file1.jpg").touch()
        (tmp_path / "file2.pdf").touch()

        process_folder(tmp_path, tmp_path, "openai")

        # Factory should only be called once
        mock_factory.create.assert_called_once_with("openai")


class TestMainFolderProcessing:
    """Test main CLI function for folder processing."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment setup."""
        with patch('context_builder.cli.load_dotenv'):
            with patch('context_builder.cli.setup_signal_handlers'):
                yield

    @pytest.fixture
    def mock_acquisition(self):
        """Mock acquisition."""
        mock = Mock()
        mock.process = Mock(return_value={"file_name": "test", "data": "result"})
        with patch('context_builder.cli.AcquisitionFactory.create', return_value=mock):
            yield mock

    def test_main_folder_success(self, tmp_path, mock_env, mock_acquisition, monkeypatch, capsys):
        """Test successful folder processing through main."""
        folder = tmp_path / "input"
        folder.mkdir()
        (folder / "file1.jpg").touch()
        (folder / "file2.pdf").touch()

        output_dir = tmp_path / "output"

        test_args = ['cli.py', str(folder), '-o', str(output_dir)]
        monkeypatch.setattr(sys, 'argv', test_args)

        # Should complete without error
        main()

        captured = capsys.readouterr()
        assert "[OK] Processed 2 files" in captured.out
        assert f"Contexts saved to: {output_dir}" in captured.out

    def test_main_folder_recursive(self, tmp_path, mock_env, mock_acquisition, monkeypatch):
        """Test recursive folder processing through main."""
        folder = tmp_path / "input"
        folder.mkdir()
        (folder / "root.jpg").touch()
        subdir = folder / "sub"
        subdir.mkdir()
        (subdir / "nested.pdf").touch()

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        test_args = ['cli.py', str(folder), '-o', str(output_dir), '--recursive']
        monkeypatch.setattr(sys, 'argv', test_args)

        # Should complete without error
        main()
        assert mock_acquisition.process.call_count == 2

    def test_main_folder_no_files(self, tmp_path, mock_env, monkeypatch, capsys):
        """Test folder with no supported files."""
        folder = tmp_path / "empty"
        folder.mkdir()
        (folder / "text.txt").touch()

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        test_args = ['cli.py', str(folder), '-o', str(output_dir)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "[X] No supported files found" in captured.out

    def test_main_folder_quiet_mode(self, tmp_path, mock_env, mock_acquisition, monkeypatch, capsys):
        """Test quiet mode for folder processing."""
        folder = tmp_path / "input"
        folder.mkdir()
        (folder / "test.jpg").touch()

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        test_args = ['cli.py', str(folder), '-o', str(output_dir), '--quiet']
        monkeypatch.setattr(sys, 'argv', test_args)

        # Should complete without error
        main()

        captured = capsys.readouterr()
        assert captured.out == ""  # No output in quiet mode