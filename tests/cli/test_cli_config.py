"""CLI tests for configuration and error handling."""

import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from context_builder.cli import (
    setup_argparser,
    main,
    signal_handler,
)
from context_builder.acquisition import (
    AcquisitionError,
    ConfigurationError,
    APIError,
)


class TestCLIArguments:
    """Test CLI argument parsing."""

    def test_argparser_basic_arguments(self):
        """Test basic argument structure."""
        parser = setup_argparser()
        args = parser.parse_args(['input.jpg'])

        assert args.input_path == 'input.jpg'
        assert args.output_dir == '.'
        assert args.provider == 'tesseract'  # Updated default
        assert not args.recursive
        assert not args.verbose
        assert not args.quiet

    def test_argparser_all_arguments(self):
        """Test all CLI arguments."""
        parser = setup_argparser()
        args = parser.parse_args([
            'input.jpg',
            '-o', '/output',
            '-r',
            '-p', 'openai',
            '--model', 'gpt-4-turbo',
            '--max-tokens', '2000',
            '--temperature', '0.7',
            '--max-pages', '15',
            '--render-scale', '3.0',
            '--timeout', '180',
            '--retries', '5',
            '-v'
        ])

        assert args.input_path == 'input.jpg'
        assert args.output_dir == '/output'
        assert args.recursive is True
        assert args.provider == 'openai'
        assert args.model == 'gpt-4-turbo'
        assert args.max_tokens == 2000
        assert args.temperature == 0.7
        assert args.max_pages == 15
        assert args.render_scale == 3.0
        assert args.timeout == 180
        assert args.retries == 5
        assert args.verbose is True

    def test_argparser_short_flags(self):
        """Test short flag versions."""
        parser = setup_argparser()
        args = parser.parse_args([
            'test.pdf',
            '-o', 'out',
            '-r',
            '-p', 'openai',
            '-v'
        ])

        assert args.output_dir == 'out'
        assert args.recursive is True
        assert args.provider == 'openai'
        assert args.verbose is True

    def test_argparser_quiet_verbose_exclusive(self):
        """Test quiet and verbose are mutually exclusive behaviors."""
        parser = setup_argparser()

        # Both can be parsed (not mutually exclusive in argparse)
        args = parser.parse_args(['test.jpg', '-v'])
        assert args.verbose is True
        assert args.quiet is False

        args = parser.parse_args(['test.jpg', '-q'])
        assert args.verbose is False
        assert args.quiet is True

    def test_argparser_azure_di_provider(self):
        """Test azure-di provider option."""
        parser = setup_argparser()
        args = parser.parse_args(['test.pdf', '-p', 'azure-di'])

        assert args.provider == 'azure-di'

    def test_argparser_default_provider_tesseract(self):
        """Test default provider is tesseract."""
        parser = setup_argparser()
        args = parser.parse_args(['test.pdf'])

        assert args.provider == 'tesseract'


class TestCLIConfiguration:
    """Test CLI configuration application."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment."""
        with patch('context_builder.cli.load_dotenv'):
            with patch('context_builder.cli.setup_signal_handlers'):
                yield

    def test_config_build_from_args_all_values(self):
        """Test configuration dictionary is built correctly."""
        parser = setup_argparser()
        args = parser.parse_args([
            'test.jpg',
            '--model', 'gpt-4o',
            '--max-tokens', '1000',
            '--temperature', '0.3',
            '--max-pages', '5',
            '--render-scale', '1.5',
            '--timeout', '90',
            '--retries', '2'
        ])

        # Simulate config building from main()
        config = {}
        if args.model is not None:
            config['model'] = args.model
        if args.max_tokens is not None:
            config['max_tokens'] = args.max_tokens
        if args.temperature is not None:
            config['temperature'] = args.temperature
        if args.max_pages is not None:
            config['max_pages'] = args.max_pages
        if args.render_scale is not None:
            config['render_scale'] = args.render_scale
        if args.timeout is not None:
            config['timeout'] = args.timeout
        if args.retries is not None:
            config['retries'] = args.retries

        assert config == {
            'model': 'gpt-4o',
            'max_tokens': 1000,
            'temperature': 0.3,
            'max_pages': 5,
            'render_scale': 1.5,
            'timeout': 90,
            'retries': 2
        }

    def test_config_build_partial_values(self):
        """Test configuration with only some values set."""
        parser = setup_argparser()
        args = parser.parse_args([
            'test.jpg',
            '--model', 'gpt-4-turbo',
            '--temperature', '0.5'
        ])

        config = {}
        if args.model is not None:
            config['model'] = args.model
        if args.max_tokens is not None:
            config['max_tokens'] = args.max_tokens
        if args.temperature is not None:
            config['temperature'] = args.temperature

        assert config == {
            'model': 'gpt-4-turbo',
            'temperature': 0.5
        }
        assert 'max_tokens' not in config

    def test_logging_levels(self, mock_env, tmp_path, monkeypatch):
        """Test logging level configuration."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()

        # Test verbose
        with patch('context_builder.cli.process_file', return_value={}):
            with patch('context_builder.cli.save_single_result'):
                test_args = ['cli.py', str(test_file), '--verbose']
                monkeypatch.setattr(sys, 'argv', test_args)

                # Should complete without error
                main()

                assert logging.getLogger().level == logging.DEBUG

        # Test quiet
        with patch('context_builder.cli.process_file', return_value={}):
            with patch('context_builder.cli.save_single_result'):
                test_args = ['cli.py', str(test_file), '--quiet']
                monkeypatch.setattr(sys, 'argv', test_args)

                # Should complete without error
                main()

                assert logging.getLogger().level == logging.WARNING


class TestCLIErrorHandling:
    """Test CLI error handling."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment."""
        with patch('context_builder.cli.load_dotenv'):
            with patch('context_builder.cli.setup_signal_handlers'):
                yield

    def test_file_not_found(self, mock_env, monkeypatch, caplog, capsys):
        """Test handling of non-existent file."""
        test_args = ['cli.py', '/nonexistent/file.jpg']
        monkeypatch.setattr(sys, 'argv', test_args)

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        # Error should be logged to stderr (colorlog outputs there)
        captured = capsys.readouterr()
        assert "Path not found" in captured.err

    def test_invalid_output_dir(self, mock_env, tmp_path, monkeypatch):
        """Test handling of invalid output directory."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()

        # Create a file where directory should be
        bad_dir = tmp_path / "notadir.txt"
        bad_dir.write_text("file")

        test_args = ['cli.py', str(test_file), '-o', str(bad_dir)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1

    def test_acquisition_error(self, mock_env, tmp_path, monkeypatch, capsys):
        """Test handling of AcquisitionError."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch('context_builder.cli.process_file') as mock_process:
            mock_process.side_effect = AcquisitionError("Processing failed")

            test_args = ['cli.py', str(test_file), '-o', str(output_dir)]
            monkeypatch.setattr(sys, 'argv', test_args)

            with pytest.raises(SystemExit) as exc:
                main()

            assert exc.value.code == 1

            captured = capsys.readouterr()
            assert "[X] Failed to process: Processing failed" in captured.out

    def test_configuration_error(self, mock_env, tmp_path, monkeypatch, capsys):
        """Test handling of ConfigurationError."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch('context_builder.cli.process_file') as mock_process:
            mock_process.side_effect = ConfigurationError("API key missing")

            test_args = ['cli.py', str(test_file), '-o', str(output_dir)]
            monkeypatch.setattr(sys, 'argv', test_args)

            with pytest.raises(SystemExit) as exc:
                main()

            assert exc.value.code == 1

            captured = capsys.readouterr()
            assert "[X] Failed to process: API key missing" in captured.out

    def test_api_error(self, mock_env, tmp_path, monkeypatch, capsys):
        """Test handling of APIError."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch('context_builder.cli.process_file') as mock_process:
            mock_process.side_effect = APIError("Rate limit exceeded")

            test_args = ['cli.py', str(test_file), '-o', str(output_dir)]
            monkeypatch.setattr(sys, 'argv', test_args)

            with pytest.raises(SystemExit) as exc:
                main()

            assert exc.value.code == 1

            captured = capsys.readouterr()
            assert "[X] Failed to process: Rate limit exceeded" in captured.out

    def test_unexpected_error(self, mock_env, tmp_path, monkeypatch, capsys):
        """Test handling of unexpected errors."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch('context_builder.cli.process_file') as mock_process:
            mock_process.side_effect = RuntimeError("Unexpected error")

            test_args = ['cli.py', str(test_file), '-o', str(output_dir)]
            monkeypatch.setattr(sys, 'argv', test_args)

            with pytest.raises(SystemExit) as exc:
                main()

            assert exc.value.code == 1

            captured = capsys.readouterr()
            assert "[X] Unexpected error occurred" in captured.out

    def test_keyboard_interrupt(self, mock_env, tmp_path, monkeypatch, capsys):
        """Test handling of KeyboardInterrupt."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch('context_builder.cli.process_file') as mock_process:
            mock_process.side_effect = KeyboardInterrupt()

            test_args = ['cli.py', str(test_file), '-o', str(output_dir)]
            monkeypatch.setattr(sys, 'argv', test_args)

            with pytest.raises(SystemExit) as exc:
                main()

            assert exc.value.code == 0

            captured = capsys.readouterr()
            assert "[!] Process interrupted by user" in captured.out

    def test_signal_handler(self, capsys):
        """Test signal handler for graceful shutdown."""
        with pytest.raises(SystemExit) as exc:
            signal_handler(None, None)

        assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "[!] Process interrupted by user" in captured.out

    def test_output_dir_creation_failure(self, mock_env, tmp_path, monkeypatch, capsys):
        """Test handling of output directory creation failure."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()

        with patch('pathlib.Path.mkdir') as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Cannot create directory")

            test_args = ['cli.py', str(test_file), '-o', '/newdir']
            monkeypatch.setattr(sys, 'argv', test_args)

            with pytest.raises(SystemExit) as exc:
                main()

            assert exc.value.code == 1

    def test_invalid_input_path_type(self, mock_env, tmp_path, monkeypatch):
        """Test handling of invalid input path type."""
        # Create a special file (like socket or device)
        # For simplicity, we'll test with a path that exists but isn't file or dir

        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.is_file', return_value=False):
                with patch('pathlib.Path.is_dir', return_value=False):
                    test_args = ['cli.py', '/dev/null']
                    monkeypatch.setattr(sys, 'argv', test_args)

                    with pytest.raises(SystemExit) as exc:
                        main()

                    assert exc.value.code == 1


class TestSessionTracking:
    """Test session ID generation and tracking."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment."""
        with patch('context_builder.cli.load_dotenv'):
            with patch('context_builder.cli.setup_signal_handlers'):
                yield

    def test_session_id_generated(self, mock_env, tmp_path, monkeypatch, capsys):
        """Test session ID is generated and logged."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()

        with patch('context_builder.cli.process_file', return_value={}):
            with patch('context_builder.cli.save_single_result'):
                test_args = ['cli.py', str(test_file)]
                monkeypatch.setattr(sys, 'argv', test_args)

                # Should complete without error
                main()

                # Check session ID was logged to stderr
                captured = capsys.readouterr()
                assert "Starting session:" in captured.err

    def test_session_id_format(self, mock_env, tmp_path, monkeypatch):
        """Test session ID format."""
        import uuid
        test_file = tmp_path / "test.jpg"
        test_file.touch()

        captured_session_id = None

        def capture_session(result, filepath, output_dir, session_id=None):
            nonlocal captured_session_id
            captured_session_id = session_id
            return Path("dummy.json")

        with patch('context_builder.cli.process_file', return_value={}):
            with patch('context_builder.cli.save_single_result', side_effect=capture_session):
                test_args = ['cli.py', str(test_file)]
                monkeypatch.setattr(sys, 'argv', test_args)

                # Should complete without error
                main()

                # Session ID should be 8 characters from UUID
                assert captured_session_id is not None
                assert len(captured_session_id) == 8