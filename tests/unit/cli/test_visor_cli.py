import socket
from unittest.mock import MagicMock, patch

import pytest

import ansys.visor.viewer.cli.visor_cli as visor_cli
from ansys.visor.viewer.core.visor_enums import RenderingMode


@pytest.fixture
def mock_parse_args():
    """Provide a mocked parse_args function."""
    with patch("ansys.visor.viewer.cli.visor_cli.parse_args") as mock:
        yield mock

@pytest.fixture
def mock_server_api():
    """Provide a mocked ServerAPI class."""
    with patch("ansys.visor.viewer.cli.visor_cli.ServerAPI") as mock:
        yield mock

@pytest.fixture
def mock_instance_api():
    """Provide a mocked InstanceAPI class."""
    with patch("ansys.visor.viewer.cli.visor_cli.InstanceAPI") as mock:
        yield mock

@pytest.fixture
def mock_logs_api():
    """Provide a mocked LogsAPI class."""
    with patch("ansys.visor.viewer.cli.visor_cli.LogsAPI") as mock:
        yield mock

@pytest.fixture
def mock_requests_get():
    """Provide a mocked requests.get function."""
    with patch("ansys.visor.viewer.cli.visor_cli.requests.get") as mock:
        yield mock

def test_check_server_running_success(mock_requests_get):
    """Verify that a healthy server returns True."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_requests_get.return_value = mock_resp
    assert visor_cli.check_server_running("host", 1234) is True

def test_check_server_running_failure_status(mock_requests_get, capsys):
    """Verify that a failed health check returns False and reports an error."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "fail"
    mock_requests_get.return_value = mock_resp
    assert visor_cli.check_server_running("host", 1234) is False
    out = capsys.readouterr().out
    assert "Server health check failed" in out

def test_check_server_running_exception(mock_requests_get, capsys):
    """Verify that connection exceptions return False and print a warning."""
    mock_requests_get.side_effect = Exception("boom")
    assert visor_cli.check_server_running("host", 1234) is False
    out = capsys.readouterr().out
    assert "Could not connect to server" in out

def make_args(group, action, **kwargs):
    args = MagicMock()
    args.group = group
    args.action = action
    args.api_host = "host"
    args.api_port = 1234
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args

def test_main_server_start_health(mock_parse_args, mock_server_api):
    """Verify that server start and health actions invoke the correct API methods."""
    for action in ["start", "health"]:
        args = make_args("server", action)
        mock_parse_args.return_value = args
        api = MagicMock()
        mock_server_api.return_value = api
        with patch("ansys.visor.viewer.cli.visor_cli.check_server_running"):
            visor_cli.main()
            getattr(api, action).assert_called_once()

def test_main_server_info_list(mock_parse_args, mock_server_api):
    """Verify that server info and list actions invoke the correct API methods."""
    for action in ["info", "list"]:
        args = make_args("server", action)
        mock_parse_args.return_value = args
        api = MagicMock()
        mock_server_api.return_value = api
        with patch("ansys.visor.viewer.cli.visor_cli.check_server_running", return_value=True):
            visor_cli.main()
            getattr(api, action).assert_called_once()

def test_main_server_init(mock_parse_args, mock_server_api):
    """Verify that server initialization forwards the expected arguments."""
    args = make_args(
        "server", "init",
        host="h", port=42, rendering_mode=RenderingMode.LOCAL,
        standalone=True, dark_mode=False, start=False,
    )
    mock_parse_args.return_value = args
    api = MagicMock()
    mock_server_api.return_value = api
    with patch("ansys.visor.viewer.cli.visor_cli.check_server_running", return_value=True):
        visor_cli.main()
        api.initialize.assert_called_once_with("h", 42, RenderingMode.LOCAL, True, False, False)

def test_main_server_init_with_start(mock_parse_args, mock_server_api):
    """Verify that server initialization forwards the --start flag."""
    args = make_args(
        "server", "init",
        host="h", port=42, rendering_mode=RenderingMode.LOCAL,
        standalone=True, dark_mode=False, start=True,
    )
    mock_parse_args.return_value = args
    api = MagicMock()
    mock_server_api.return_value = api
    with patch("ansys.visor.viewer.cli.visor_cli.check_server_running", return_value=True):
        visor_cli.main()
        api.initialize.assert_called_once_with("h", 42, RenderingMode.LOCAL, True, False, True)

def test_main_instance_actions(mock_parse_args, mock_instance_api):
    """Verify that instance actions invoke the corresponding API methods."""
    actions = [
        ("start", "start", {"file_path": "f", "metadata_path": "m", "timeout": 1}),
        ("update", "update", {"file_path": "f", "metadata_path": "m"}),
        ("add", "add_dataset", {"file_path": "f", "metadata_path": "m"}),
        ("remove", "remove_dataset", {"dataset_id": 99}),
        ("list", "list_datasets", {}),
        ("stop_visualization", "stop_visualization", {}),
        ("stop", "stop", {}),
    ]

    for action, method_name, extra in actions:
        args = make_args("instance", action, **extra)
        mock_parse_args.return_value = args
        api = MagicMock()
        mock_instance_api.return_value = api
        with patch("ansys.visor.viewer.cli.visor_cli.check_server_running", return_value=True):
            visor_cli.main()
            method = getattr(api, method_name)
            method.assert_called_once()

def test_main_logs_list(mock_parse_args, mock_logs_api):
    """Verify that log listing invokes the list_logs method."""
    args = make_args("logs", "list", log_name=None, follow=False, log_dir=None, lines=10)
    mock_parse_args.return_value = args
    api = MagicMock()
    mock_logs_api.return_value = api
    with patch("ansys.visor.viewer.cli.visor_cli.check_server_running", return_value=True):
        visor_cli.main()
        api.list_logs.assert_called_once()

def test_main_logs_tail(mock_parse_args, mock_logs_api):
    """Verify that log tail invokes tail_log with the requested options."""
    args = make_args("logs", "tail", log_name="mylog", follow=True, log_dir="dir", lines=5)
    mock_parse_args.return_value = args
    api = MagicMock()
    mock_logs_api.return_value = api
    with patch("ansys.visor.viewer.cli.visor_cli.check_server_running", return_value=True):
        visor_cli.main()
        api.tail_log.assert_called_once_with("mylog", True, 5)

def test_main_logs_clear(mock_parse_args, mock_logs_api):
    """Verify that log clear invokes the clear_logs method."""
    args = make_args("logs", "clear", log_dir=None, force=False)
    mock_parse_args.return_value = args
    api = MagicMock()
    mock_logs_api.return_value = api
    with patch("ansys.visor.viewer.cli.visor_cli.check_server_reachable", return_value=False):
        visor_cli.main()
        api.clear_logs.assert_called_once_with(False)

def test_main_logs_clear_force(mock_parse_args, mock_logs_api):
    """Verify that log clear -f forwards force=True to clear_logs."""
    args = make_args("logs", "clear", log_dir=None, force=True)
    mock_parse_args.return_value = args
    api = MagicMock()
    mock_logs_api.return_value = api
    with patch("ansys.visor.viewer.cli.visor_cli.check_server_reachable", return_value=False):
        visor_cli.main()
        api.clear_logs.assert_called_once_with(True)

def test_main_logs_clear_rejected_when_server_reachable(mock_parse_args, mock_logs_api, capsys):
    """Verify that log clear exits without clearing when the server is reachable."""
    args = make_args("logs", "clear", log_dir=None, force=True)
    mock_parse_args.return_value = args
    api = MagicMock()
    mock_logs_api.return_value = api
    with patch("ansys.visor.viewer.cli.visor_cli.check_server_reachable", return_value=True) as mock_check:
        with pytest.raises(SystemExit) as exc:
            visor_cli.main()
    assert exc.value.code == 1
    mock_check.assert_called_once_with("host", 1234)
    api.clear_logs.assert_not_called()
    assert "Server is running" in capsys.readouterr().out

def test_check_server_reachable_connected():
    """Verify that an established TCP connection counts as reachable."""
    with patch("ansys.visor.viewer.cli.visor_cli.socket.create_connection") as mock_conn:
        assert visor_cli.check_server_reachable("host", 1234) is True
    mock_conn.assert_called_once_with(("host", 1234), timeout=1)

@pytest.mark.parametrize(
    "exc",
    [
        ConnectionRefusedError("refused"),
        socket.timeout("connect timeout"),
        socket.gaierror("dns failure"),
    ],
)
def test_check_server_reachable_connect_failure(exc):
    """Verify that only failing to establish a connection counts as unreachable."""
    with patch("ansys.visor.viewer.cli.visor_cli.socket.create_connection", side_effect=exc):
        assert visor_cli.check_server_reachable("host", 1234) is False

@pytest.mark.parametrize(
    "group, action, expected",
    [
        ("server", "start", False),
        ("server", "health", False),
        ("server", "info", True),
        ("server", "init", True),
        ("instance", "start", True),
        ("logs", "list", False),
        ("logs", "tail", False),
        ("logs", "clear", False),
    ],
)
def test_needs_server_running(group, action, expected):
    """Verify which commands require a running server."""
    assert visor_cli.needs_server_running(make_args(group, action)) is expected

@pytest.mark.parametrize(
    "group, action, expected",
    [
        ("logs", "clear", True),
        ("logs", "list", False),
        ("logs", "tail", False),
        ("server", "start", False),
        ("instance", "stop", False),
    ],
)
def test_needs_server_stopped(group, action, expected):
    """Verify that only log clear requires a stopped server."""
    assert visor_cli.needs_server_stopped(make_args(group, action)) is expected

def test_main_logs_does_not_require_running_server(mock_parse_args, mock_logs_api):
    """Verify that log commands do not require the server to be running."""
    args = make_args("logs", "list", log_name=None, follow=False, log_dir=None, lines=10)
    mock_parse_args.return_value = args
    api = MagicMock()
    mock_logs_api.return_value = api
    with patch("ansys.visor.viewer.cli.visor_cli.check_server_running") as mock_check:
        visor_cli.main()
        mock_check.assert_not_called()
        api.list_logs.assert_called_once()

def test_main_server_not_running_exits(mock_parse_args, capsys):
    """Verify that instance commands exit when the server is not running."""
    args = make_args("instance", "start", file_path="f", metadata_path="m", timeout=1)
    mock_parse_args.return_value = args
    with patch("ansys.visor.viewer.cli.visor_cli.check_server_running", return_value=False):
        with pytest.raises(SystemExit) as e:
            visor_cli.main()
        assert e.value.code == 1
    out = capsys.readouterr().out
    assert "Server is not running" in out
