"""CLI tests for single file processing."""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest

from context_builder.cli import (
    process_file,
    save_single_result,
    main,
    setup_argparser,
)
from context_builder.acquisition import AcquisitionError


class TestCLISingleFileProcessing:
    """Test single file processing through CLI."""

    @pytest.fixture
    def mock_acquisition(self):
        """Mock acquisition instance."""
        mock = Mock()
        mock.process = Mock(return_value={
            "file_name": "test.jpg",
            "pages": [{"text": "content"}],
            "_usage": {"total_tokens": 100}
        })
        return mock

    @pytest.fixture
    def mock_factory(self, mock_acquisition):
        """Mock factory that returns our acquisition."""
        with patch('context_builder.cli.AcquisitionFactory') as factory:
            factory.create = Mock(return_value=mock_acquisition)
            yield factory

    def test_process_file_basic(self, tmp_path, mock_factory, mock_acquisition):
        """Test basic single file processing."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"image data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = process_file(test_file, output_dir, "openai")

        # Verify factory was called
        mock_factory.create.assert_called_once_with("openai")

        # Verify process was called
        mock_acquisition.process.assert_called_once_with(test_file)

        # Verify result
        assert result["file_name"] == "test.jpg"
        assert result["pages"][0]["text"] == "content"

    def test_process_file_with_config(self, tmp_path, mock_factory, mock_acquisition):
        """Test processing with configuration."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        config = {
            "model": "gpt-4-turbo",
            "max_tokens": 2048,
            "temperature": 0.5,
            "timeout": 60,
            "retries": 5,
            "max_pages": 10,
            "render_scale": 2.5
        }

        process_file(test_file, tmp_path, "openai", config=config)

        # Verify config was applied
        assert mock_acquisition.model == "gpt-4-turbo"
        assert mock_acquisition.max_tokens == 2048
        assert mock_acquisition.temperature == 0.5
        assert mock_acquisition.timeout == 60
        assert mock_acquisition.retries == 5
        assert mock_acquisition.max_pages == 10
        assert mock_acquisition.render_scale == 2.5

    def test_process_file_with_partial_config(self, tmp_path, mock_factory, mock_acquisition):
        """Test processing with partial configuration."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        # Some values are None
        config = {
            "model": "gpt-4o",
            "max_tokens": None,
            "temperature": 0.3,
            "timeout": None
        }

        # Add attributes that might not exist
        mock_acquisition.unknown_attr = None

        process_file(test_file, tmp_path, "openai", config=config)

        # Only non-None values should be set
        assert mock_acquisition.model == "gpt-4o"
        assert mock_acquisition.temperature == 0.3

        # These shouldn't be set to None
        if hasattr(mock_acquisition, 'max_tokens'):
            assert mock_acquisition.max_tokens != None
        if hasattr(mock_acquisition, 'timeout'):
            assert mock_acquisition.timeout != None

    def test_process_file_reuse_acquisition(self, tmp_path, mock_factory):
        """Test processing with provided acquisition instance."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        existing_acquisition = Mock()
        existing_acquisition.process = Mock(return_value={"result": "data"})

        process_file(test_file, tmp_path, "openai", acquisition=existing_acquisition)

        # Factory should not be called when acquisition is provided
        mock_factory.create.assert_not_called()

        # Existing acquisition should be used
        existing_acquisition.process.assert_called_once_with(test_file)

    def test_process_file_logs_info(self, tmp_path, mock_factory, mock_acquisition, caplog):
        """Test processing logs appropriate messages."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        with caplog.at_level(logging.INFO):
            process_file(test_file, tmp_path, "openai")

        assert f"Processing file: {test_file}" in caplog.text
        assert "Using openai vision API for processing" in caplog.text

    def test_process_file_logs_config_debug(self, tmp_path, mock_factory, mock_acquisition, caplog):
        """Test config application logs debug messages."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        config = {"model": "gpt-4o"}

        with caplog.at_level(logging.DEBUG):
            process_file(test_file, tmp_path, "openai", config=config)

        assert "Set model=gpt-4o on acquisition instance" in caplog.text


class TestCLISaveSingleResult:
    """Test saving single file results."""

    def test_save_single_result_basic(self, tmp_path):
        """Test basic result saving."""
        result = {
            "file_name": "test.jpg",
            "pages": [{"text": "content"}]
        }

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        original_file = Path("test.jpg")

        output_path = save_single_result(result, original_file, output_dir)

        # Check output file created
        assert output_path.exists()
        assert output_path.name == "test-context.json"

        # Check content
        with open(output_path) as f:
            saved = json.load(f)
        assert saved["file_name"] == "test.jpg"
        assert saved["pages"][0]["text"] == "content"

    def test_save_single_result_with_session(self, tmp_path):
        """Test saving with session ID."""
        result = {"data": "test"}
        output_dir = tmp_path
        original_file = Path("doc.pdf")
        session_id = "abc123"

        output_path = save_single_result(result, original_file, output_dir, session_id)

        with open(output_path) as f:
            saved = json.load(f)

        assert saved["session_id"] == "abc123"
        assert saved["data"] == "test"

    def test_save_single_result_unicode(self, tmp_path):
        """Test saving results with Unicode content."""
        result = {
            "text": "中文内容",
            "emoji": "🎉",
            "special": "café"
        }

        output_path = save_single_result(result, Path("test.jpg"), tmp_path)

        with open(output_path, encoding='utf-8') as f:
            saved = json.load(f)

        assert saved["text"] == "中文内容"
        assert saved["emoji"] == "🎉"
        assert saved["special"] == "café"

    def test_save_single_result_logs_info(self, tmp_path, caplog):
        """Test saving logs info message."""
        result = {"data": "test"}
        session_id = "xyz789"

        with caplog.at_level(logging.INFO):
            save_single_result(result, Path("test.jpg"), tmp_path, session_id)

        assert f"[Session {session_id}] Saving results to:" in caplog.text

    def test_save_single_result_overwrites_existing(self, tmp_path):
        """Test saving overwrites existing file."""
        output_file = tmp_path / "test-context.json"
        output_file.write_text('{"old": "data"}')

        result = {"new": "data"}
        output_path = save_single_result(result, Path("test.jpg"), tmp_path)

        with open(output_path) as f:
            saved = json.load(f)

        assert saved["new"] == "data"
        assert "old" not in saved


class TestCLIMainSingleFile:
    """Test main CLI function for single file processing."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment setup."""
        with patch('context_builder.cli.load_dotenv'):
            with patch('context_builder.cli.setup_signal_handlers'):
                yield

    @pytest.fixture
    def mock_acquisition(self):
        """Mock acquisition for main tests."""
        mock = Mock()
        mock.process = Mock(return_value={
            "file_name": "test.jpg",
            "pages": [{"text": "content"}]
        })
        with patch('context_builder.cli.AcquisitionFactory.create', return_value=mock):
            yield mock

    def test_main_single_file_success(self, tmp_path, mock_env, mock_acquisition, capsys, monkeypatch):
        """Test successful single file processing through main."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock command line args - use output dir to avoid creating files in cwd
        test_args = ['cli.py', str(test_file), '-o', str(output_dir)]
        monkeypatch.setattr(sys, 'argv', test_args)

        # Run main
        # Should complete without error
        main()

        # Check output
        captured = capsys.readouterr()
        assert "[OK] Context extracted to:" in captured.out

        # Check JSON file created in output dir
        output_file = output_dir / "test-context.json"
        assert output_file.exists()

    def test_main_single_file_with_output_dir(self, tmp_path, mock_env, mock_acquisition, monkeypatch):
        """Test single file with custom output directory."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")
        output_dir = tmp_path / "output"

        test_args = ['cli.py', str(test_file), '-o', str(output_dir)]
        monkeypatch.setattr(sys, 'argv', test_args)

        # Should complete without error
        main()

        # Check output file in correct directory
        output_file = output_dir / "test-context.json"
        assert output_file.exists()

    def test_main_single_file_verbose(self, tmp_path, mock_env, mock_acquisition, monkeypatch, caplog):
        """Test verbose logging mode."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        test_args = ['cli.py', str(test_file), '-o', str(output_dir), '--verbose']
        monkeypatch.setattr(sys, 'argv', test_args)

        # Save original level
        original_level = logging.getLogger().level

        try:
            # Should complete without error
            main()

            # Verify debug messages were captured (indicates DEBUG level was active)
            with caplog.at_level(logging.DEBUG):
                pass

            # Check for debug-level activity in the logs
            assert any(record.levelno == logging.DEBUG for record in caplog.records) or logging.getLogger().level == logging.DEBUG
        finally:
            # Restore original level
            logging.getLogger().setLevel(original_level)

    def test_main_single_file_quiet(self, tmp_path, mock_env, mock_acquisition, monkeypatch, capsys):
        """Test quiet mode."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        test_args = ['cli.py', str(test_file), '-o', str(output_dir), '--quiet']
        monkeypatch.setattr(sys, 'argv', test_args)

        # Should complete without error
        main()

        # No output in quiet mode
        captured = capsys.readouterr()
        assert captured.out == ""

        # Files are in tmp_path, cleanup automatic

    def test_main_single_file_all_config_flags(self, tmp_path, mock_env, mock_acquisition, monkeypatch):
        """Test all configuration flags."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        test_args = [
            'cli.py', str(test_file),
            '-o', str(output_dir),
            '--model', 'gpt-4-turbo',
            '--max-tokens', '2048',
            '--temperature', '0.5',
            '--max-pages', '10',
            '--render-scale', '2.5',
            '--timeout', '60',
            '--retries', '5'
        ]
        monkeypatch.setattr(sys, 'argv', test_args)

        # Should complete without error
        main()

        # Verify config was applied
        assert mock_acquisition.model == 'gpt-4-turbo'
        assert mock_acquisition.max_tokens == 2048
        assert mock_acquisition.temperature == 0.5
        assert mock_acquisition.max_pages == 10
        assert mock_acquisition.render_scale == 2.5
        assert mock_acquisition.timeout == 60
        assert mock_acquisition.retries == 5

        # Files are in tmp_path, cleanup automatic

    def test_main_single_file_acquisition_error(self, tmp_path, mock_env, monkeypatch, capsys):
        """Test handling of acquisition errors."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch('context_builder.cli.process_file') as mock_process:
            mock_process.side_effect = AcquisitionError("API failed")

            test_args = ['cli.py', str(test_file), '-o', str(output_dir)]
            monkeypatch.setattr(sys, 'argv', test_args)

            with pytest.raises(SystemExit) as exc:
                main()

            assert exc.value.code == 1

            captured = capsys.readouterr()
            assert "[X] Failed to process: API failed" in captured.out