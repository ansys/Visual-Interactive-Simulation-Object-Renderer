from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.app.trame.local_app import LocalApp


class MockController:
    def __init__(self):
        self.handlers = {}
        self.add_call_count = 0
    def add(self, event):
        self.add_call_count += 1
        def decorator(fn):
            self.handlers[event] = fn
            return fn
        return decorator

@pytest.fixture
def mock_server():
    """Provide a mock Trame server."""
    server = MagicMock()
    server.controller = MockController()
    server.http_headers.set_header = MagicMock()
    server.name = "TestServer"
    server._www = None
    return server


@pytest.fixture
def mock_logger():
    """Provide a mock logger."""
    logger = MagicMock()
    logger.debug = MagicMock()
    return logger


@pytest.fixture
def mock_get_scene_details_json():
    """Provide a mock scene details callback."""
    return MagicMock(return_value={"scene": "details"})


@pytest.fixture
def mock_handle_save_state_response():
    """Provide a mock save-state callback."""
    return MagicMock(return_value={"ok": True})


@patch("ansys.visor.viewer.app.trame.local_app.settings")
def test_init_sets_attributes(
    mock_settings,
    mock_server,
    mock_get_scene_details_json,
    mock_handle_save_state_response,
    mock_logger,
):
    """Verify that initialization stores the provided attributes."""
    mock_settings.get_client_bundle.return_value = "/mock/path"
    app = LocalApp(
        server=mock_server,
        get_scene_details_json=mock_get_scene_details_json,
        handle_save_state_response=mock_handle_save_state_response,
        standalone=True,
        trame_logger=mock_logger,
    )
    assert app.server == mock_server
    assert app._get_scene_details_json == mock_get_scene_details_json
    assert app._LocalApp__trame_logger == mock_logger


def test_register_lifecycle_hooks_adds_handlers(
    mock_server, mock_get_scene_details_json, mock_handle_save_state_response
):
    """Verify that lifecycle event handlers are registered."""
    LocalApp(
        server=mock_server,
        get_scene_details_json=mock_get_scene_details_json,
        handle_save_state_response=mock_handle_save_state_response,
        standalone=True,
    )
    assert mock_server.controller.add_call_count >= 5


def test_set_headers_sets_http_headers(
    mock_server, mock_get_scene_details_json, mock_handle_save_state_response
):
    """Verify that the required HTTP headers are configured."""
    LocalApp(
        server=mock_server,
        get_scene_details_json=mock_get_scene_details_json,
        handle_save_state_response=mock_handle_save_state_response,
        standalone=True,
    )
    mock_server.http_headers.set_header.assert_any_call(
        "Access-Control-Allow-Origin", "*"
    )
    mock_server.http_headers.set_header.assert_any_call(
        "Cache-Control", "max-age=0"
    )


@patch("ansys.visor.viewer.app.trame.local_app.settings")
def test_set_www_path_sets_www(
    mock_settings,
    mock_server,
    mock_get_scene_details_json,
    mock_handle_save_state_response,
):
    """Verify that the client bundle path is assigned to the server."""
    mock_settings.get_client_bundle.return_value = "/mock/path"
    LocalApp(
        server=mock_server,
        get_scene_details_json=mock_get_scene_details_json,
        handle_save_state_response=mock_handle_save_state_response,
        standalone=True,
    )
    assert mock_server._www == "/mock/path"


def test_get_visor_scene_details_json_returns_scene_details(
    mock_server, mock_get_scene_details_json, mock_handle_save_state_response
):
    """Verify that scene details are returned from the callback."""
    app = LocalApp(
        server=mock_server,
        get_scene_details_json=mock_get_scene_details_json,
        handle_save_state_response=mock_handle_save_state_response,
        standalone=True,
    )
    result = app.get_visor_scene_details_json()
    assert result == {"scene": "details"}


@patch("ansys.visor.viewer.app.trame.local_app.settings")
def test_trame_logger_is_set_when_provided(
    mock_settings,
    mock_server,
    mock_get_scene_details_json,
    mock_handle_save_state_response,
    mock_logger,
):
    """Verify that the provided logger is stored."""
    mock_settings.get_client_bundle.return_value = "/mock/path"
    app = LocalApp(
        server=mock_server,
        get_scene_details_json=mock_get_scene_details_json,
        handle_save_state_response=mock_handle_save_state_response,
        standalone=True,
        trame_logger=mock_logger,
    )
    assert app._LocalApp__trame_logger == mock_logger


@patch("ansys.visor.viewer.app.trame.local_app.settings")
def test_trame_logger_is_none_when_not_provided(
    mock_settings,
    mock_server,
    mock_get_scene_details_json,
    mock_handle_save_state_response,
):
    """Verify that the logger is None when not provided."""
    mock_settings.get_client_bundle.return_value = "/mock/path"
    app = LocalApp(
        server=mock_server,
        get_scene_details_json=mock_get_scene_details_json,
        handle_save_state_response=mock_handle_save_state_response,
        standalone=True,
    )
    assert app._LocalApp__trame_logger is None


@patch("ansys.visor.viewer.app.trame.local_app.settings")
def test_lifecycle_logging_calls_debug(
    mock_settings,
    mock_server,
    mock_get_scene_details_json,
    mock_handle_save_state_response,
    mock_logger,
):
    """Verify that lifecycle events generate debug log messages."""
    mock_settings.get_client_bundle.return_value = "/mock/path"
    LocalApp(
        server=mock_server,
        get_scene_details_json=mock_get_scene_details_json,
        handle_save_state_response=mock_handle_save_state_response,
        standalone=True,
        trame_logger=mock_logger,
    )

    # Trigger each lifecycle event
    mock_server.controller.handlers["on_server_start"](None)
    mock_server.controller.handlers["on_server_ready"]()
    mock_server.controller.handlers["on_client_connected"]()
    mock_server.controller.handlers["on_client_exited"]()
    mock_server.controller.handlers["on_server_exited"]()

    # Check logger.debug was called with expected messages
    mock_logger.debug.assert_any_call("Starting server")
    mock_logger.debug.assert_any_call("Server is ready.")
    mock_logger.debug.assert_any_call("Client connected.")
    mock_logger.debug.assert_any_call("Client exited.")
    mock_logger.debug.assert_any_call("Server is exiting.")
