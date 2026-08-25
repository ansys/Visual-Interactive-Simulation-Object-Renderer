import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ansys.visor.viewer.app.trame.trame_server_manager import TrameServerManager
from ansys.visor.viewer.models.runtime.visor_scene_details import VisorSceneDetails
from ansys.visor.viewer.models.runtime.vtk.runtime_vtk_info import RuntimeVTKInfo

visor_vtk_pipeline_state = VisorSceneDetails(
        vtk_info=RuntimeVTKInfo(
            scene_graph=None,
        ),
    )

class DummyServer:
    def __init__(self, running=True, controller=True):
        self.running = running
        self.state = MagicMock()
        self.state.to_dict.return_value = {"foo": "bar"}
        self.controller = MagicMock() if controller else None
        self.start = MagicMock(return_value=AsyncMock())
        self.stop = AsyncMock()
        self.ready = AsyncMock()
        self.http_headers = MagicMock()
        self.http_headers.set_header = MagicMock()

def make_manager(server=None):
    mgr = TrameServerManager()
    mgr._server = server or DummyServer()
    mgr._async_runner = MagicMock()
    return mgr

def make_manager_with_fixed_wasm_ids():
    mock_local = MagicMock()

    # return stable IDs used by your expected `visor_state`
    mock_local.get_wasm_id.return_value = 1
    mock_local.register_vtk_object.return_value = 1
    mock_local.ref_name = "wasm_ref"

    # Patch the LocalView class imported in VtkPipeline so VtkPipeline() gets the mock
    return patch(
        "ansys.visor.viewer.vtk.vtk_pipeline.LocalView",
        return_value=mock_local
    )

def test_init_sets_properties():
    """Verify that initialization stores the configured host and port."""
    mgr = TrameServerManager(host="h", port=123)
    assert mgr._host == "h"
    assert mgr._port == 123
    assert mgr._server is not None
    assert mgr._async_runner is not None

def test_running_property_true():
    """Verify that running returns True when the server is running."""
    mgr = make_manager(DummyServer(running=True))
    assert mgr.running is True

def test_running_property_false():
    """Verify that running returns False when the server is not running."""
    mgr = make_manager(DummyServer(running=False))
    assert mgr.running is False

def test_url_property():
    """Verify that the URL property is constructed from the host and port."""
    mgr = TrameServerManager(host="abc", port=1234)
    assert mgr.url == "http://abc:1234"

def test_health_property_true():
    """Verify that health reports True when the server is healthy."""
    mgr = make_manager(DummyServer(running=True))
    assert mgr.health is True

def test_health_no_server_raises():
    """Verify that health raises when no server is available."""
    mgr = make_manager()
    mgr._server = None
    with pytest.raises(RuntimeError):
        _ = mgr.health

def test_health_no_controller_raises():
    """Verify that health raises when the server controller is unavailable."""
    mgr = make_manager(DummyServer())
    mgr._server.controller = None
    with pytest.raises(RuntimeError):
        _ = mgr.health

def test_start_calls_async_runner():
    """Verify that start delegates execution to the async runner."""
    mgr = make_manager()
    mgr._async_runner.run_coroutine_block = MagicMock()
    mgr.start(timeout=1, blocking=True)
    mgr._async_runner.run_coroutine_block.assert_called_once()

def test_stop_calls_async_runner():
    """Verify that stop delegates execution to the async runner."""
    mgr = make_manager()
    mgr._async_runner.run_coroutine_block = MagicMock()
    mgr.stop()
    mgr._async_runner.run_coroutine_block.assert_called_once()

@pytest.mark.asyncio
async def test_start_async_calls_async_runner():
    """Verify that start_async delegates execution to the async runner."""
    mgr = make_manager()
    mgr._async_runner.run_coroutine_async = AsyncMock()
    await mgr.start_async(timeout=1, blocking=True)
    mgr._async_runner.run_coroutine_async.assert_called_once()

@pytest.mark.asyncio
async def test_stop_async_calls_async_runner():
    """Verify that stop_async delegates execution to the async runner."""
    mgr = make_manager()
    mgr._async_runner.run_coroutine_async = AsyncMock()
    await mgr.stop_async()
    mgr._async_runner.run_coroutine_async.assert_called_once()

@pytest.mark.asyncio
async def test_state_property_raises():
    """Verify that the base state property raises NotImplementedError."""
    mgr = make_manager()
    with pytest.raises(NotImplementedError):
        _ = mgr.state

def test_initialize_server_called(monkeypatch):
    """Verify that server initialization uses the expected configuration."""
    called = {}

    def fake_get_server(name, log_network):
        called["name"] = name
        called["log_network"] = log_network
        return MagicMock()

    monkeypatch.setattr("ansys.visor.viewer.app.trame.trame_server_manager.get_server", fake_get_server)
    monkeypatch.setattr("ansys.visor.viewer.app.trame.trame_server_manager.get_trame_log_path", lambda x: "log_path")

    TrameServerManager(host="h", port=123, trame_log_dir="dir")

    assert called["name"] == "http://h:123"
    assert called["log_network"] == "log_path"

@pytest.mark.asyncio
async def test_start_core_invalid_timeout():
    """Verify that _start_core rejects invalid timeout values."""
    mgr = make_manager()
    with pytest.raises(Exception):
        await mgr._start_core(timeout=-1)

@pytest.mark.asyncio
async def test_start_core_server_coroutine_none():
    """Verify that _start_core raises when server startup returns no coroutine."""
    mgr = make_manager()
    mgr._server.start = MagicMock(return_value=None)
    with pytest.raises(RuntimeError):
        await mgr._start_core()

@pytest.mark.asyncio
async def test_stop_core_running():
    """Verify that _stop_core stops the server when it is running."""
    mgr = make_manager()
    mgr._server.running = True
    mgr._server.stop = AsyncMock()
    await mgr._stop_core()
    mgr._server.stop.assert_awaited_once()

@pytest.mark.asyncio
async def test_stop_core_not_running():
    """Verify that _stop_core does not stop an already stopped server."""
    mgr = make_manager()
    mgr._server.running = False
    mgr._server.stop = AsyncMock()
    await mgr._stop_core()
    mgr._server.stop.assert_not_awaited()

def test_trame_server_manager_configures_ssl_from_glow_certs_dir(tmp_path, monkeypatch):
    """TrameServerManager should configure trame/wslink SSL when certs exist."""
    # Create fake cert files
    cert = tmp_path / "server.crt"
    key = tmp_path / "server.key"
    cert.write_text("CERT")
    key.write_text("KEY")

    # Prepare a fake server with a cli.set_defaults that captures kwargs
    captured = {}

    class FakeCLI:
        def set_defaults(self, **kwargs):
            captured.update(kwargs)

    fake_server = types.SimpleNamespace(cli=FakeCLI())

    # Ensure Settings exposes the resolved ssl_certificate
    monkeypatch.setattr(
        "ansys.visor.viewer.config.settings.ssl_certificate",
        f"{str(cert)},{str(key)}",
        raising=False,
    )
    monkeypatch.setattr(
        "ansys.visor.viewer.app.trame.trame_server_manager.get_server",
        lambda name, log_network: fake_server,
    )

    # Import here to ensure monkeypatch above applies before instantiation
    from ansys.visor.viewer.app.trame.trame_server_manager import TrameServerManager

    # Instantiate manager which will call _initialize_server and thus set_defaults
    mgr = TrameServerManager(host="localhost", port=12345, trame_log_dir=None)

    # Ensure our fake server was used
    assert mgr.server is fake_server

    # Verify set_defaults was called with an ssl value containing both paths
    assert "ssl" in captured
    ssl_val = captured["ssl"]
    assert str(cert) in ssl_val
    assert str(key) in ssl_val