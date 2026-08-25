"""Logging configuration for Visor"""

import logging
from logging import Logger
from pathlib import Path

from ansys.visor.viewer.config import settings


class VisorLogger(Logger):
    """
    Custom logger for the Visor app.

    This logger writes logs to a file, allows setting the log level,
    and ensures the log directory exists.

    Args:
        name (str): The name of the logger, typically the module or class name.
        filename (str): The name of the log file.
        log_dir (Optional[str]): Directory to save logs.
                                 Default is the default_log_dir from config settings.
        level (int): Logging level. Default is logging.DEBUG.
    """

    # Logging format to comply with Ansys ADR:
    # https://github.com/ansys-internal/architecture-decision-records/blob/main/content/
    # docs/adrs/0016-observability-strategy.md
    LOGGING_FORMAT = (
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d %(funcName)s()] - %(message)s"
    )
    ENCODING = "utf-8"

    def __init__(self,
                 name: str,
                 filename: str,
                 log_dir: str | None = None,
                 level: int = logging.DEBUG,
                 basic_config: bool = True,
                 propagate: bool = False):
        """Initialize the logger."""
        # Initialize the parent class
        super().__init__(name, level)

        # Log level
        self.level = level

        # Set up the log directory and file path
        self.filename = filename
        self.log_dir = log_dir
        if log_dir is None:
            self.log_dir = settings.default_log_dir
        self.file_path = self.get_file_path()

        # Ensure the log directory exists
        self.create_dir()

        if basic_config:
            # Set up basic config unless set to False
            self.__basic_config()

        # Create file handler and set logging level
        file_handler = logging.FileHandler(
            self.file_path,
            encoding=self.ENCODING
        )
        file_handler.setLevel(level)

        # Add formatter for file handler
        formatter = logging.Formatter(self.LOGGING_FORMAT)
        file_handler.setFormatter(formatter)

        self.addHandler(file_handler)

        # Prevent propagation to the root logger
        self.propagate = propagate

    def __basic_config(self):
        """
        Configure the root logger via basicConfig
        (this will affect any logger that doesn't have a handler)
        """
        logging.basicConfig(
            level=self.level,
            format=self.LOGGING_FORMAT,
            handlers=[
                logging.FileHandler(
                    self.file_path,
                    encoding=self.ENCODING
                )
            ],
        )

    def create_dir(self) -> None:
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)

    def get_file_path(self) -> Path:
        return Path(self.log_dir).joinpath(self.filename)


class VisorDefaultLogger(VisorLogger):
    """
    Custom logger for Visor app with a default log file.

    This logger writes to a fixed log file named "visor.log", ensuring
    consistency across multiple modules within the project.
    It inherits from the VisorLogger class, which allows for centralized
    configuration and logging.

    This default logger is intended for logging all of the project-related
    messages to the same log file across different modules while maintaining
    a consistent logging format and level.

    Args:
        name (str): The name of the logger, typically the module or class name.
    """
    def __init__(self, name):
        # Initialize the parent class
        super().__init__(name, "visor.log")


def set_up_named_logger(log_name, log_filename, log_dir, level=logging.DEBUG):
    """Configure the logger for the named logger."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger(log_name)
    root_logger.setLevel(level)

    # Create file handler and set logging level
    file_handler = logging.FileHandler(Path(log_dir).joinpath(log_filename))
    file_handler.setLevel(level)

    # Add formatter for file handler
    formatter = logging.Formatter(VisorLogger.LOGGING_FORMAT)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    return root_logger


def configure_trame_logging(trame_log_dir: str) -> VisorLogger:
    """Configure the loggers for the trame application"""
    trame_log_filename = "visor_trame_app.log"

    # Set up custom logger for writing lifecycle events
    lifecycle_logger = VisorLogger(
        "trame_lifecycle",
        trame_log_filename,
        trame_log_dir,
        level=logging.DEBUG,
        basic_config=False,
        propagate=True # Keep the logging in the default log file
    )

    # trame's internal python loggers
    # set up file handlers to write to visor_trame_app.log
    set_up_named_logger("trame", trame_log_filename, trame_log_dir)
    set_up_named_logger("trame_server", trame_log_filename, trame_log_dir)
    set_up_named_logger("trame.app", trame_log_filename, trame_log_dir)

    return lifecycle_logger

def get_trame_logger(trame_log_dir: str | None) -> VisorLogger | None:
    """ For trame Python logging, output to app log file """
    if trame_log_dir:
        return configure_trame_logging(trame_log_dir)
    return None

def get_trame_log_path(trame_log_dir: str | None) -> Path | bool:
    """For Server option to enable network logging, set output file path"""
    if trame_log_dir:
        return Path(trame_log_dir).joinpath("visor_trame_network.log")
    return False

