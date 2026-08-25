"""Custom defined exception for Visor viewer application."""


class InvalidFileError(Exception):
    """Raised when an invalid file is provided"""
    def __init__(self,value):
        self.value = value
    def __str__(self):
        return repr(f"Invalid file: {self.value}")

class InvalidServerTimeoutError(Exception):
    """Raised when an invalid timeout value is provided"""
    def __init__(self,value):
        self.value = value
    def __str__(self):
        return repr(f"Invalid timeout value: {self.value}")

class InvalidUrlError(Exception):
    """Raised when an invalid url is provided"""
    def __init__(self,value):
        self.value = value
    def __str__(self):
        return repr(f"Invalid url: {self.value}")

class InvalidPathError(Exception):
    """Raised when an invalid path is provided"""
    def __init__(self,value):
        self.value = value
    def __str__(self):
        return repr(f"Invalid path: {self.value}")

class InvalidFileFormatError(Exception):
    """Raised when an invalid file format is provided"""
    def __init__(self,value):
        self.value = value
    def __str__(self):
        return repr(f"Invalid file format: {self.value}")

class ServerNotStartedError(Exception):
    """Raised when the server is not started"""
    def __init__(self,value):
        self.value = value
    def __str__(self):
        return repr(f"Server not started: {self.value}")

class VisorAddDatasetError(Exception):
    """Raised when adding/loading a dataset into a Visor scene fails."""

    def __init__(self, message: str, *, input_path: str | None = None, metadata_path: str | None = None):
        super().__init__(message)
        self.input_path = input_path
        self.metadata_path = metadata_path

    def __str__(self):
        base = super().__str__()
        details = []
        if self.input_path:
            details.append(f"input_path={self.input_path}")
        if self.metadata_path:
            details.append(f"metadata_path={self.metadata_path}")
        return base if not details else f"{base} ({', '.join(details)})"
