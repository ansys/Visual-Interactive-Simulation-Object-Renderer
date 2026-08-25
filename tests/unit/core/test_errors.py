import ansys.visor.viewer.core.errors as errors


def test_invalid_file_error_str():
    """Verify that InvalidFileError formats its message and stores the value."""
    e = errors.InvalidFileError("foo.txt")
    assert str(e) == repr("Invalid file: foo.txt")
    assert e.value == "foo.txt"

def test_invalid_server_timeout_error_str():
    """Verify that InvalidServerTimeoutError formats its message and stores the value."""
    e = errors.InvalidServerTimeoutError(42)
    assert str(e) == repr("Invalid timeout value: 42")
    assert e.value == 42

def test_invalid_url_error_str():
    """Verify that InvalidUrlError formats its message and stores the value."""
    e = errors.InvalidUrlError("bad_url")
    assert str(e) == repr("Invalid url: bad_url")
    assert e.value == "bad_url"

def test_invalid_path_error_str():
    """Verify that InvalidPathError formats its message and stores the value."""
    e = errors.InvalidPathError("/bad/path")
    assert str(e) == repr("Invalid path: /bad/path")
    assert e.value == "/bad/path"

def test_invalid_file_format_error_str():
    """Verify that InvalidFileFormatError formats its message and stores the value."""
    e = errors.InvalidFileFormatError(".bad")
    assert str(e) == repr("Invalid file format: .bad")
    assert e.value == ".bad"

def test_server_not_started_error_str():
    """Verify that ServerNotStartedError formats its message and stores the value."""
    e = errors.ServerNotStartedError("not running")
    assert str(e) == repr("Server not started: not running")
    assert e.value == "not running"

def test_visor_add_dataset_error_str_no_paths():
    """Verify that VisorAddDatasetError returns the base message when no paths are provided."""
    e = errors.VisorAddDatasetError("failed")
    assert str(e) == "failed"
    assert e.input_path is None
    assert e.metadata_path is None

def test_visor_add_dataset_error_str_with_input_path():
    """Verify that VisorAddDatasetError includes the input path in the message."""
    e = errors.VisorAddDatasetError("failed", input_path="input.vtk")
    assert str(e) == "failed (input_path=input.vtk)"
    assert e.input_path == "input.vtk"
    assert e.metadata_path is None

def test_visor_add_dataset_error_str_with_metadata_path():
    """Verify that VisorAddDatasetError includes the metadata path in the message."""
    e = errors.VisorAddDatasetError("failed", metadata_path="meta.json")
    assert str(e) == "failed (metadata_path=meta.json)"
    assert e.input_path is None
    assert e.metadata_path == "meta.json"

def test_visor_add_dataset_error_str_with_both_paths():
    """Verify that VisorAddDatasetError includes both paths in the message."""
    e = errors.VisorAddDatasetError(
        "failed",
        input_path="input.vtk",
        metadata_path="meta.json",
    )
    assert str(e) == "failed (input_path=input.vtk, metadata_path=meta.json)"
    assert e.input_path == "input.vtk"
    assert e.metadata_path == "meta.json"
