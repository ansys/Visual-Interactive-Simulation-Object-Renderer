import logging
from pathlib import Path

from ansys.visor.viewer.core.visor_logging import (
    VisorDefaultLogger,
    VisorLogger,
    configure_trame_logging,
    set_up_named_logger,
)


def test_get_file_path_returns_correct_path(tmp_path):
    """Verify that get_file_path returns the expected log file path."""
    filename = "test.log"
    logger = VisorLogger("test_logger", filename, log_dir=tmp_path)
    expected_path = tmp_path / filename
    assert logger.get_file_path() == expected_path

def test_create_dir_creates_directory(tmp_path):
    """Verify that the log directory is created when it does not exist."""
    log_dir = tmp_path / "logs"
    VisorLogger("test_logger", "file.log", log_dir=log_dir)
    assert log_dir.exists() and log_dir.is_dir()

def test_logger_adds_file_handler(tmp_path):
    """Verify that a file handler is added for the configured log file."""
    logger = VisorLogger("test_logger", "log.txt", log_dir=tmp_path)
    file_paths = [h.baseFilename for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert str(tmp_path / "log.txt") in file_paths

def test_default_logger_uses_expected_filename(tmp_path):
    """Verify that VisorDefaultLogger uses the default log filename."""
    logger = VisorDefaultLogger("my_logger")
    assert logger.filename == "visor.log"

def test_formatter_applied(tmp_path):
    """Verify that the expected formatter is applied to the file handler."""
    logger = VisorLogger("formatter_logger", "log.txt", log_dir=tmp_path)
    file_handler = next(h for h in logger.handlers if isinstance(h, logging.FileHandler))
    assert isinstance(file_handler.formatter, logging.Formatter)
    assert file_handler.formatter._fmt == VisorLogger.LOGGING_FORMAT

def test_propagate_is_false(tmp_path):
    """Verify that log propagation is disabled by default."""
    logger = VisorLogger("test_logger", "logfile.log", log_dir=tmp_path)
    assert logger.propagate is False

def test_log_writes_to_file(tmp_path):
    """Verify that log messages are written to the configured file."""
    test_message = "Testing Visor logging!"
    filename = "my.log"
    logger = VisorLogger("file_logger", filename, log_dir=tmp_path)
    logger.info(test_message)

    log_file = tmp_path / filename
    with open(log_file, "r", encoding="utf-8") as f:
        contents = f.read()
        assert test_message in contents

def test_set_up_named_logger_creates_logger(tmp_path):
    """Verify that set_up_named_logger creates a configured named logger."""
    log_name = "my_named_logger"
    log_file = "named.log"
    logger = set_up_named_logger(log_name, log_file, tmp_path)

    # Check logger properties
    assert logger.name == log_name
    assert logger.level == logging.DEBUG

    # Ensure handler is attached with correct file path
    file_handler = next((h for h in logger.handlers if isinstance(h, logging.FileHandler)), None)
    assert file_handler is not None
    assert Path(file_handler.baseFilename) == tmp_path / log_file
    assert isinstance(file_handler.formatter, logging.Formatter)
    assert file_handler.formatter._fmt == VisorLogger.LOGGING_FORMAT

def test_configure_trame_logging_sets_up_lifecycle_logger(tmp_path):
    """Verify that configure_trame_logging configures the Trame lifecycle logger and related loggers."""
    logger = configure_trame_logging(str(tmp_path))

    # Check that the returned logger has correct name
    assert isinstance(logger, VisorLogger)
    assert logger.name == "trame_lifecycle"
    assert logger.filename == "visor_trame_app.log"
    assert logger.log_dir == str(tmp_path)
    assert logger.propagate is True

    # Check additional loggers are configured
    for name in ["trame", "trame_server", "trame.app"]:
        sub_logger = logging.getLogger(name)
        assert sub_logger.level == logging.DEBUG
        assert any(isinstance(h, logging.FileHandler) for h in sub_logger.handlers)

        handler_files = [Path(h.baseFilename).name for h in sub_logger.handlers if isinstance(h, logging.FileHandler)]
        assert "visor_trame_app.log" in handler_files

def test_logging_writes_to_file(tmp_path):
    """Verify that a named logger writes messages to its output file."""
    filename = "out.log"
    log_message = "Testing logging to named logger"

    logger = set_up_named_logger("temp_logger", filename, tmp_path)
    logger.info(log_message)

    log_file = tmp_path / filename
    assert log_file.exists()

    with open(log_file, encoding="utf-8") as f:
        contents = f.read()
        assert log_message in contents
