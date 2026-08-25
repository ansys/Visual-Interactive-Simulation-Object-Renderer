import sys
from unittest.mock import patch

import pytest

from ansys.visor.viewer.cli.parse_args import parse_args
from ansys.visor.viewer.cli.visor_cli import check_init_args
from ansys.visor.viewer.core.visor_enums import RenderingMode


def run_parse_args(argv):
    with patch.object(sys, "argv", argv):
        return parse_args()

def test_server_start_args():
    """Verify that server start arguments are parsed correctly."""
    args = run_parse_args(["visor-cli", "server", "start"])
    assert args.group == "server"
    assert args.action == "start"
    assert args.api_host == "localhost"
    assert args.api_port == 53211

def test_server_health_args():
    """Verify that server health arguments are parsed correctly."""
    args = run_parse_args(["visor-cli", "server", "health"])
    assert args.group == "server"
    assert args.action == "health"

def test_server_info_args():
    """Verify that server info arguments are parsed correctly."""
    args = run_parse_args(["visor-cli", "server", "info"])
    assert args.group == "server"
    assert args.action == "info"

def test_server_init_args_defaults():
    """Verify that server init uses the expected default argument values."""
    args = run_parse_args(["visor-cli", "server", "init"])
    assert args.group == "server"
    assert args.action == "init"
    assert args.host == "localhost"
    assert args.standalone is None
    assert args.port == 0
    assert args.dark_mode is None

def test_server_init_args_custom():
    """Verify that custom server init arguments are parsed correctly."""
    args = run_parse_args([
        "visor-cli", "server", "init",
        "--host", "myhost", "--port", "12345", "--standalone", "False"
    ])
    assert args.host == "myhost"
    assert args.port == 12345
    assert args.standalone is False

def test_server_list_args():
    """Verify that server list arguments are parsed correctly."""
    args = run_parse_args(["visor-cli", "server", "list"])
    assert args.group == "server"
    assert args.action == "list"

def test_instance_start_args_defaults():
    """Verify that instance start uses the expected default argument values."""
    args = run_parse_args(["visor-cli", "instance", "start"])
    assert args.group == "instance"
    assert args.action == "start"
    assert args.file_path is None
    assert args.metadata_path is None
    assert args.timeout == 0

def test_instance_start_args_custom():
    """Verify that custom instance start arguments are parsed correctly."""
    args = run_parse_args([
        "visor-cli", "instance", "start", "file.vtk",
        "--metadata-path", "meta.json", "--timeout", "5"
    ])
    assert args.file_path == "file.vtk"
    assert args.metadata_path == "meta.json"
    assert args.timeout == 5

def test_instance_update_args():
    """Verify that instance update arguments are parsed correctly."""
    args = run_parse_args([
        "visor-cli", "instance", "update", "file2.vtk",
        "--metadata-path", "meta2.json"
    ])
    assert args.action == "update"
    assert args.file_path == "file2.vtk"
    assert args.metadata_path == "meta2.json"

def test_instance_add_dataset_args():
    """Verify that add-dataset arguments are parsed correctly."""
    args = run_parse_args([
        "visor-cli", "instance", "add", "file3.vtk",
        "--metadata-path", "meta3.json"
    ])
    assert args.action == "add"
    assert args.file_path == "file3.vtk"
    assert args.metadata_path == "meta3.json"

def test_instance_list_datasets_args():
    """Verify that list-datasets arguments are parsed correctly."""
    args = run_parse_args(["visor-cli", "instance", "list"])
    assert args.action == "list"

def test_instance_remove_dataset_args():
    """Verify that remove-dataset arguments are parsed correctly."""
    args = run_parse_args(["visor-cli", "instance", "remove", "42"])
    assert args.action == "remove"
    assert args.dataset_id == 42

def test_instance_stop_visualization_args():
    """Verify that stop_visualization arguments are parsed correctly."""
    args = run_parse_args(["visor-cli", "instance", "stop_visualization"])
    assert args.action == "stop_visualization"

def test_instance_stop_args():
    """Verify that instance stop arguments are parsed correctly."""
    args = run_parse_args(["visor-cli", "instance", "stop"])
    assert args.action == "stop"

def test_logs_list_args_defaults():
    """Verify that logs arguments use the expected default values."""
    args = run_parse_args(["visor-cli", "logs"])
    assert args.group == "logs"
    assert args.log_name is None
    assert args.follow is False
    assert args.log_dir is None
    assert args.lines == 10

def test_logs_show_args_custom():
    """Verify that custom log display arguments are parsed correctly."""
    args = run_parse_args([
        "visor-cli", "logs", "mylog", "-f", "--log-dir", "/tmp", "-n", "5"
    ])
    assert args.log_name == "mylog"
    assert args.follow is True
    assert args.log_dir == "/tmp"
    assert args.lines == 5

def test_missing_group_raises():
    """Verify that omitting the command group raises SystemExit."""
    with patch.object(sys, "argv", ["visor-cli"]):
        with pytest.raises(SystemExit):
            parse_args()

def test_missing_action_raises():
    """Verify that omitting the command action raises SystemExit."""
    with patch.object(sys, "argv", ["visor-cli", "server"]):
        with pytest.raises(SystemExit):
            parse_args()

def test_no_flags_does_not_call_requests(monkeypatch):
    """Verify that no instance lookup occurs when no init flags are provided."""
    def fail_if_called(*args, **kwargs):
        raise AssertionError("requests.get should not be called when no flags are provided")

    # Patch the requests.get used in the module to fail if invoked
    monkeypatch.setattr(
        "ansys.visor.viewer.cli.visor_cli.requests.get", fail_if_called
    )

    # Neither standalone nor dark_mode set -> should return cleanly and not call requests.get
    check_init_args("api-host", 0, "host", 9000, RenderingMode.LOCAL, None, None)

def test_flags_and_request_raises_warning(monkeypatch, capsys):
    """Verify that request failures emit a warning without exiting."""
    def raise_exc(*args, **kwargs):
        raise Exception("boom")

    monkeypatch.setattr(
        "ansys.visor.viewer.cli.visor_cli.requests.get", raise_exc
    )

    # Should not raise SystemExit; should print a warning
    check_init_args("api-host", 0, "host", 9000, RenderingMode.LOCAL, True, None)

    captured = capsys.readouterr()
    assert "Warning: could not check existing instances: boom" in captured.out

def test_existing_instance_triggers_exit(monkeypatch, capsys):
    """Verify that initialization exits when the target instance already exists."""
    class FakeResp:
        def json(self):
            return {"urls": ["http://target-host:1234"]}

    def fake_get(url, timeout=5):
        return FakeResp()

    monkeypatch.setattr(
        "ansys.visor.viewer.cli.visor_cli.requests.get", fake_get
    )

    with pytest.raises(SystemExit) as excinfo:
        check_init_args("api-host", 0, "target-host", 1234, RenderingMode.LOCAL, True, None)

    # sys.exit(1) should produce SystemExit with code 1
    assert excinfo.value.code == 1

    captured = capsys.readouterr()
    assert "Error: Instance already initialized on http://target-host:1234." in captured.out

def test_flags_but_no_existing_instance(monkeypatch):
    """Verify that initialization proceeds when no matching instance exists."""
    class FakeResp:
        def json(self):
            return {"urls": ["http://other:1111"]}

    def fake_get(url, timeout=5):
        return FakeResp()

    monkeypatch.setattr(
        "ansys.visor.viewer.cli.visor_cli.requests.get", fake_get
    )

    # Should not raise
    check_init_args("api-host", 0, "target-host", 1234, RenderingMode.LOCAL, True, False)
