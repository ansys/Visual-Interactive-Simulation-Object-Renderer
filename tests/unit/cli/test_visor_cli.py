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
    args = make_args("server", "init", host="h", port=42, rendering_mode=RenderingMode.LOCAL, standalone=True, dark_mode=False)
    mock_parse_args.return_value = args
    api = MagicMock()
    mock_server_api.return_value = api
    with patch("ansys.visor.viewer.cli.visor_cli.check_server_running", return_value=True):
        visor_cli.main()
        api.initialize.assert_called_once_with("h", 42, RenderingMode.LOCAL, True, False)

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
    args = make_args("logs", None, log_name=None, follow=False, log_dir=None, lines=10)
    mock_parse_args.return_value = args
    api = MagicMock()
    mock_logs_api.return_value = api
    with patch("ansys.visor.viewer.cli.visor_cli.check_server_running", return_value=True):
        visor_cli.main()
        api.list_logs.assert_called_once()

def test_main_logs_show(mock_parse_args, mock_logs_api):
    """Verify that log display invokes show_log with the requested options."""
    args = make_args("logs", None, log_name="mylog", follow=True, log_dir="dir", lines=5)
    mock_parse_args.return_value = args
    api = MagicMock()
    mock_logs_api.return_value = api
    with patch("ansys.visor.viewer.cli.visor_cli.check_server_running", return_value=True):
        visor_cli.main()
        api.show_log.assert_called_once_with("mylog", True, 5)

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
