from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import ansys.visor.viewer.api.server as server_mod


@pytest.fixture
def mock_settings():
    """Provide mock application settings."""
    settings = MagicMock()
    settings.default_host = "localhost"
    settings.default_port = 8081
    settings.default_standalone = True
    settings.trame_log_dir = "logdir"
    settings.app_name = "TestApp"
    settings.binding_host = None
    # Ensure SSL-related attributes are explicit for tests
    settings.ssl_certificate = None
    settings.url_scheme = "http"
    return settings


@pytest.fixture
def api(mock_settings):
    """Provide a VisorAPI instance with mocked dependencies."""
    with patch.object(server_mod, "settings", mock_settings), \
         patch.object(server_mod, "VisorCache") as mock_cache, \
         patch.object(server_mod, "VisorLogger"), \
         patch.object(server_mod, "Visor"):
        mock_cache.get_instance.return_value = (MagicMock(), None)
        mock_cache.list_instances.return_value = ["http://localhost:8081"]
        return server_mod.VisorAPI()


def test_get_url(api):
    """Verify that a URL is constructed from the host and port."""
    url = api._get_url("host", 1234)
    assert url == "http://host:1234"


def test_server_get_url_reports_public_host_not_binding_host(monkeypatch, api):
    """_get_url should report the public host passed to initialize, not the binding/listen host."""
    # When binding_host is set, Trame will listen on it, but advertised URLs must use the public host
    monkeypatch.setenv("GLOW_PRODUCT_BINDING_HOST", "example.com")
    api.settings.binding_host = "example.com"
    url = api._get_url("127.0.0.1", 8080)
    assert url == "http://127.0.0.1:8080"

    # When binding_host is not set, behaviour is unchanged
    monkeypatch.delenv("GLOW_PRODUCT_BINDING_HOST", raising=False)
    api.settings.binding_host = None
    url2 = api._get_url("127.0.0.1", 8080)
    assert url2 == "http://127.0.0.1:8080"


def test_initialize_visualizer(api):
    """Verify that an existing visualizer instance is returned from the cache."""
    with patch.object(server_mod, "VisorCache") as mock_cache:
        mock_instance = MagicMock()
        mock_cache.get_instance.return_value = (mock_instance, None)
        result, warnings = api._connect_or_initialize_visualizer("host", 1234, True, False)
        assert result is mock_instance
        assert warnings is None
        mock_cache.get_instance.assert_called_once()


@pytest.mark.asyncio
async def test_info_with_visualizer(api):
    """Verify that visualizer information is returned when available."""
    api.visualizer = MagicMock()
    api.visualizer.info.return_value = {
        "app_name": "TestApp",
        "host": "h",
        "port": 1,
        "standalone": True,
        "datasets": [],
        "metadata": None
    }
    result = await api.info()
    assert result.app_name == "TestApp"


@pytest.mark.asyncio
async def test_info_without_visualizer(api, mock_settings):
    """Verify that default information is returned when no visualizer exists."""
    api.visualizer = None
    # Ensure all required fields are present
    result = await api.info()
    assert result.app_name == mock_settings.app_name
    assert result.host == mock_settings.default_host
    assert result.port == mock_settings.default_port
    assert result.standalone == mock_settings.default_standalone
    assert isinstance(result.datasets, list)


@pytest.mark.asyncio
async def test_list_instances(api):
    """Verify that available instance URLs are returned."""
    result = await api.list_instances()
    assert "urls" in result
    assert isinstance(result["urls"], list)


@pytest.mark.asyncio
async def test_handle_exceptions_decorator_catches_known_errors(api):
    """Verify that known errors are converted to HTTP 422 responses."""

    @server_mod.handle_exceptions
    async def dummy(self):
        raise server_mod.errors.InvalidUrlError("bad")

    with pytest.raises(server_mod.HTTPException) as exc:
        await dummy(api)

    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_handle_exceptions_decorator_catches_runtime_error(api):
    """Verify that runtime errors are converted to HTTP 500 responses."""

    @server_mod.handle_exceptions
    async def dummy(self):
        raise RuntimeError("fail")

    with pytest.raises(server_mod.HTTPException) as exc:
        await dummy(api)

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_handle_exceptions_decorator_catches_unhandled(api):
    """Verify that unhandled exceptions are converted to HTTP 500 responses."""

    @server_mod.handle_exceptions
    async def dummy(self):
        raise Exception("fail")

    with pytest.raises(server_mod.HTTPException) as exc:
        await dummy(api)

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_initialize_server(api):
    """Verify that a server instance can be initialized successfully."""
    props = MagicMock()
    props.host = "h"
    props.port = 1
    props.standalone = True
    props.dark_mode = False

    with patch.object(api, "_connect_or_initialize_visualizer", return_value=(MagicMock(), None)):
        result = await api.connect_or_initialize_server(props)
        assert "Set active instance" in result["message"]
        assert result["message"] == "Set active instance to http://h:1"


@pytest.mark.asyncio
async def test_initialize_server_port_zero_uses_find_unused_port(api):
    """When port is 0, the server must call find_unused_port and use its result."""
    props = MagicMock()
    props.host = "h"
    props.port = 0
    props.standalone = True
    props.dark_mode = False

    with patch.object(api, "_connect_or_initialize_visualizer",
                      return_value=(MagicMock(), None)) as mock_conn, \
         patch.object(server_mod, "find_unused_port", return_value=55555) as mock_find:
        result = await api.connect_or_initialize_server(props)

    # find_unused_port must have been asked for a port on the request host
    mock_find.assert_called_once_with(host="h")
    # The picked port must be forwarded to the visualizer factory
    call_args = mock_conn.call_args
    assert call_args.args[0] == "h"
    assert call_args.args[1] == 55555
    # And reflected in the response message
    assert result["message"] == "Set active instance to http://h:55555"


@pytest.mark.asyncio
async def test_initialize_server_port_zero_probes_binding_host_when_set(api):
    """When settings.binding_host is set, that must be used as the probe host."""
    api.settings.binding_host = "0.0.0.0"

    props = MagicMock()
    props.host = "h"
    props.port = 0
    props.standalone = True
    props.dark_mode = False

    with patch.object(api, "_connect_or_initialize_visualizer",
                      return_value=(MagicMock(), None)), \
         patch.object(server_mod, "find_unused_port", return_value=44444) as mock_find:
        await api.connect_or_initialize_server(props)

    mock_find.assert_called_once_with(host="0.0.0.0")


@pytest.mark.asyncio
async def test_initialize_server_port_zero_no_free_port_raises_503(api):
    """When find_unused_port returns None, the endpoint must raise HTTP 503."""
    props = MagicMock()
    props.host = "h"
    props.port = 0
    props.standalone = True
    props.dark_mode = False

    with patch.object(server_mod, "find_unused_port", return_value=None):
        with pytest.raises(server_mod.HTTPException) as exc:
            await api.connect_or_initialize_server(props)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_initialize_server_forwards_warnings(api):
    """Warnings returned by _connect_or_initialize_visualizer must reach the response."""
    props = MagicMock()
    props.host = "h"
    props.port = 1
    props.standalone = True
    props.dark_mode = False

    warnings = ["ignored standalone flag"]
    with patch.object(api, "_connect_or_initialize_visualizer",
                      return_value=(MagicMock(), warnings)):
        result = await api.connect_or_initialize_server(props)

    assert result["warnings"] == warnings


@pytest.mark.asyncio
async def test_start_instance_success(api):
    """Verify that a visualization can be started successfully."""
    api.visualizer = MagicMock()
    api.visualizer._start_async = AsyncMock(return_value=("dataset_id", "task"))

    props = MagicMock()
    props.file_path = "file"
    props.metadata = {"name": "m"}
    props.timeout = 0

    result = await api.start_instance(props)
    assert "success" in result


@pytest.mark.asyncio
async def test_start_instance_no_visualizer(api):
    """Verify that starting a visualization requires an active visualizer."""
    api.visualizer = None
    props = MagicMock()

    with pytest.raises(server_mod.HTTPException) as exc:
        await api.start_instance(props)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_update_success(api):
    """Verify that an active visualization can be updated."""
    api.visualizer = MagicMock()
    api.visualizer.update = MagicMock(return_value=None)

    props = MagicMock()
    props.file_path = "file"
    props.metadata = {"name": "m"}

    result = await api.update(props)
    assert "success" in result


@pytest.mark.asyncio
async def test_update_no_visualizer(api):
    """Verify that updating requires an active visualizer."""
    api.visualizer = None
    props = MagicMock()

    with pytest.raises(server_mod.HTTPException) as exc:
        await api.update(props)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_stop_visualization_success(api):
    """Verify that an active visualization can be stopped."""
    api.visualizer = MagicMock()
    api.visualizer.url = "url"
    api.visualizer._stop_async = AsyncMock(return_value=None)

    result = await api.stop_visualization()
    assert "success" in result


@pytest.mark.asyncio
async def test_stop_instance_success(api):
    """Verify that an active instance can be stopped and cleared."""
    api.visualizer = MagicMock()
    api.visualizer.url = "url"
    api.visualizer._stop_async = AsyncMock(return_value=None)

    with patch.object(server_mod, "VisorCache"):
        result = await api.stop_instance()
        assert "success" in result
        assert api.visualizer is None


@pytest.mark.asyncio
async def test_add_dataset_success(api):
    """Verify that a dataset can be added successfully."""
    api.visualizer = MagicMock()
    api.visualizer.add_dataset = MagicMock(return_value=None)

    props = MagicMock()
    props.file_path = "file"
    props.metadata = {"name": "m"}

    result = await api.add_dataset(props)
    assert "success" in result


@pytest.mark.asyncio
async def test_add_dataset_no_visualizer(api):
    """Verify that adding a dataset requires an active visualizer."""
    api.visualizer = None
    props = MagicMock()

    with pytest.raises(server_mod.HTTPException) as exc:
        await api.add_dataset(props)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_remove_dataset_success(api):
    """Verify that a dataset can be removed successfully."""
    api.visualizer = MagicMock()
    api.visualizer.url = "url"
    api.visualizer.remove_dataset = MagicMock(return_value=None)

    props = MagicMock()
    props.dataset_id = 123

    result = await api.remove_dataset(props)
    assert "success" in result


@pytest.mark.asyncio
async def test_remove_dataset_no_visualizer(api):
    """Verify that removing a dataset requires an active visualizer."""
    api.visualizer = None
    props = MagicMock()

    with pytest.raises(server_mod.HTTPException) as exc:
        await api.remove_dataset(props)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_list_datasets_success(api):
    """Verify that datasets are returned from the visualizer."""
    api.visualizer = MagicMock()
    api.visualizer.list_datasets = MagicMock(return_value={"a": 1})

    result = await api.list_datasets()
    assert "datasets" in result


@pytest.mark.asyncio
async def test_list_datasets_no_visualizer(api):
    """Verify that listing datasets requires an active visualizer."""
    api.visualizer = None

    with pytest.raises(server_mod.HTTPException) as exc:
        await api.list_datasets()

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_health_live(api):
    """Verify that the health endpoint reports an OK status."""
    result = await api.health_live()
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_handle_exceptions_add_dataset_error(api):
    """Verify that dataset addition errors return a sentinel response."""

    @server_mod.handle_exceptions
    async def dummy(self):
        raise server_mod.errors.VisorAddDatasetError("fail")

    result = await dummy(api)

    assert result["success"] is False
    assert result["dataset_id"] == -1
    assert "Failed to add dataset" in result["error"]


@pytest.mark.asyncio
async def test_handle_exceptions_invalid_file(api):
    """Verify that InvalidFileError is converted to an HTTP 422 response."""

    @server_mod.handle_exceptions
    async def dummy(self):
        raise server_mod.errors.InvalidFileError("bad")

    with pytest.raises(server_mod.HTTPException) as exc:
        await dummy(api)

    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_handle_exceptions_invalid_file_format(api):
    """Verify that InvalidFileFormatError is converted to an HTTP 422 response."""

    @server_mod.handle_exceptions
    async def dummy(self):
        raise server_mod.errors.InvalidFileFormatError("bad")

    with pytest.raises(server_mod.HTTPException) as exc:
        await dummy(api)

    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_handle_exceptions_server_not_started(api):
    """Verify that ServerNotStartedError is converted to an HTTP 400 response."""

    @server_mod.handle_exceptions
    async def dummy(self):
        raise server_mod.errors.ServerNotStartedError("bad")

    with pytest.raises(server_mod.HTTPException) as exc:
        await dummy(api)

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_handle_exceptions_type_error(api):
    """Verify that TypeError is converted to an HTTP 500 response."""

    @server_mod.handle_exceptions
    async def dummy(self):
        raise TypeError("bad")

    with pytest.raises(server_mod.HTTPException) as exc:
        await dummy(api)

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_list_variables_no_visualizer(api):
    """Verify that listing variables requires an active visualizer."""

    api.visualizer = None

    with pytest.raises(server_mod.HTTPException) as exc:
        await api.list_variables(1)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_update_variables_no_visualizer(api):
    """Verify that updating variables requires an active visualizer."""

    api.visualizer = None

    props = MagicMock()
    props.variables = []

    with pytest.raises(server_mod.HTTPException) as exc:
        await api.update_variables(1, props)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_save_state_no_visualizer(api):
    """Verify that saving state requires an active visualizer."""

    api.visualizer = None

    props = MagicMock()
    props.state_dir = "dir"

    with pytest.raises(server_mod.HTTPException) as exc:
        await api.save_state(props)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_load_state_no_visualizer(api):
    """Verify that loading state requires an active visualizer."""

    api.visualizer = None

    props = MagicMock()
    props.state_dir = "dir"

    with pytest.raises(server_mod.HTTPException) as exc:
        await api.load_state(props)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_list_variables_success(api):
    """Verify that variable results are serialized using to_dict."""

    part = MagicMock()
    part.to_dict.return_value = {"id": 1}

    api.visualizer = MagicMock()
    api.visualizer.list_variables.return_value = [part]

    result = await api.list_variables(1)

    assert result == {"parts": [{"id": 1}]}


@pytest.mark.asyncio
async def test_update_variables_success(api):
    """Verify that variables are serialized before being forwarded."""

    var = MagicMock()
    var.model_dump.return_value = {"x": 1}

    props = MagicMock()
    props.variables = [var]

    api.visualizer = MagicMock()
    api.visualizer.update_variables.return_value = {"ok": True}

    result = await api.update_variables(5, props)

    assert result == {"variables": {"ok": True}}
    api.visualizer.update_variables.assert_called_once_with(5, [{"x": 1}])


@pytest.mark.asyncio
async def test_save_state_success(api):
    """Verify that state can be saved successfully."""

    api.visualizer = MagicMock()
    api.visualizer.url = "url"
    api.visualizer.save_state = AsyncMock()

    props = MagicMock()
    props.state_dir = "dir"

    result = await api.save_state(props)

    assert "Saved state to dir" in result["success"]
    api.visualizer.save_state.assert_called_once_with("dir")


@pytest.mark.asyncio
async def test_load_state_success(api):
    """Verify that state can be loaded successfully."""

    api.visualizer = MagicMock()
    api.visualizer.url = "url"
    api.visualizer.load_state = MagicMock()

    props = MagicMock()
    props.state_dir = "dir"

    result = await api.load_state(props)

    assert "Loaded state from dir" in result["success"]
    api.visualizer.load_state.assert_called_once_with("dir")
