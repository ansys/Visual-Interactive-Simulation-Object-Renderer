import json
import subprocess
import sys
from unittest.mock import MagicMock, mock_open, patch

import pytest
import requests

from ansys.visor.viewer.cli.apis import InstanceAPI, LogsAPI, ServerAPI
from ansys.visor.viewer.core.visor_enums import RenderingMode

## --- ServerAPI tests ---

def test_serverapi_start_invokes_uvicorn_run():
    """Verify that starting the server delegates to uvicorn.run."""
    api = ServerAPI("host", 1234)
    with patch("ansys.visor.viewer.cli.apis.uvicorn.run") as mock_run:
        api.start()
        mock_run.assert_called_once_with(
            "ansys.visor.viewer.api.server:app",
            host="host",
            port=1234,
            log_level="info",
        )

def test_serverapi_health_prints_response():
    """Verify that the health endpoint response is printed."""
    api = ServerAPI("host", 1234)
    with patch("requests.get") as mock_get, patch("builtins.print") as mock_print:
        mock_get.return_value.json.return_value = {"status": "ok"}
        api.health()
        mock_get.assert_called_once_with("http://host:1234/health")
        mock_print.assert_called_with({"status": "ok"})

def test_serverapi_info_prints_response():
    """Verify that the info endpoint response is printed."""
    api = ServerAPI("host", 1234)
    with patch("requests.get") as mock_get, patch("builtins.print") as mock_print:
        mock_get.return_value.json.return_value = {"info": "data"}
        api.info()
        mock_get.assert_called_once_with("http://host:1234/info")
        mock_print.assert_called_with({"info": "data"})

def test_serverapi_initialize_prints_response():
    """Verify that the initialize response is printed."""
    api = ServerAPI("host", 1234)
    with patch("requests.post") as mock_post, patch("builtins.print") as mock_print:
        mock_post.return_value.json.return_value = {"result": "ok"}
        api.initialize("h", 1, RenderingMode.LOCAL, True, dark_mode=False, start=False)
        mock_post.assert_called_once()
        mock_print.assert_called_with({"result": "ok"})

def test_serverapi_initialize_with_start_also_starts_instance():
    """Verify that passing start=True also posts to the /start endpoint."""
    api = ServerAPI("host", 1234)
    with patch("requests.post") as mock_post, patch("builtins.print"):
        mock_post.return_value.json.return_value = {"result": "ok"}
        api.initialize("h", 1, RenderingMode.LOCAL, True, dark_mode=False, start=True)
        assert mock_post.call_count == 2
        mock_post.assert_any_call(f"{api.base}/initialize", json={
            "host": "h", "port": 1, "rendering_mode": RenderingMode.LOCAL,
            "standalone": True, "dark_mode": False,
        })
        mock_post.assert_any_call(f"{api.base}/start", json={})

def test_serverapi_list_prints_urls():
    """Verify that available instance URLs are printed."""
    api = ServerAPI("host", 1234)
    with patch("requests.get") as mock_get, patch("builtins.print") as mock_print:
        mock_get.return_value.json.return_value = {"urls": ["url1", "url2"]}
        api.list()
        mock_print.assert_any_call("Available instances:")
        mock_print.assert_any_call("  url1")
        mock_print.assert_any_call("  url2")

def test_serverapi_list_prints_nothing_if_no_urls():
    """Verify that nothing is printed when no instances are available."""
    api = ServerAPI("host", 1234)
    with patch("requests.get") as mock_get, patch("builtins.print") as mock_print:
        mock_get.return_value.json.return_value = {"urls": []}
        api.list()
        mock_print.assert_not_called()

## --- InstanceAPI tests ---

def test_instanceapi_start_prints_response():
    """Verify that the start response is printed."""
    api = InstanceAPI("host", 1234)
    with patch("requests.post") as mock_post, patch("builtins.print") as mock_print:
        mock_post.return_value.json.return_value = {"started": True}
        api.start("file", "meta", 5)
        mock_post.assert_called_once()
        mock_print.assert_called_with({"started": True})

def test_instanceapi_update_prints_response():
    """Verify that the update response is printed."""
    api = InstanceAPI("host", 1234)
    with patch("requests.post") as mock_post, patch("builtins.print") as mock_print:
        mock_post.return_value.json.return_value = {"updated": True}
        api.update("file", "meta")
        mock_post.assert_called_once()
        mock_print.assert_called_with({"updated": True})

def test_instanceapi_add_dataset_prints_response():
    """Verify that the add_dataset response is printed."""
    api = InstanceAPI("host", 1234)
    with patch("requests.post") as mock_post, patch("builtins.print") as mock_print:
        mock_post.return_value.json.return_value = {"added": True}
        api.add_dataset("file", "meta")
        mock_post.assert_called_once()
        mock_print.assert_called_with({"added": True})

def test_instanceapi_list_datasets_prints_json():
    """Verify that datasets are printed as formatted JSON."""
    api = InstanceAPI("host", 1234)
    with patch("requests.get") as mock_get, patch("builtins.print") as mock_print:
        mock_get.return_value.json.return_value = {"datasets": {"a": 1}}
        api.list_datasets()
        mock_print.assert_called_once_with(json.dumps({"a": 1}, indent=4))

def test_instanceapi_remove_dataset_prints_response():
    """Verify that the remove_dataset response is printed."""
    api = InstanceAPI("host", 1234)
    with patch("requests.post") as mock_post, patch("builtins.print") as mock_print:
        mock_post.return_value.json.return_value = {"removed": True}
        api.remove_dataset(42)
        mock_post.assert_called_once()
        mock_print.assert_called_with({"removed": True})

def test_instanceapi_stop_visualization_prints_response():
    """Verify that the stop_visualization response is printed."""
    api = InstanceAPI("host", 1234)
    with patch("requests.post") as mock_post, patch("builtins.print") as mock_print:
        mock_post.return_value.json.return_value = {"stopped": True}
        api.stop_visualization()
        mock_post.assert_called_once()
        mock_print.assert_called_with({"stopped": True})

def test_instanceapi_stop_prints_response():
    """Verify that the stop response is printed."""
    api = InstanceAPI("host", 1234)
    with patch("requests.post") as mock_post, patch("builtins.print") as mock_print:
        mock_post.return_value.json.return_value = {"stopped": True}
        api.stop()
        mock_post.assert_called_once()
        mock_print.assert_called_with({"stopped": True})

## --- LogsAPI tests ---

def test_logsapi_list_logs_prints_files(tmp_path):
    """Verify that available log files are listed."""
    log_dir = tmp_path
    (log_dir / "foo.log").write_text("x")
    (log_dir / "bar.log").write_text("y")
    api = LogsAPI(str(log_dir))
    with patch("builtins.print") as mock_print:
        api.list_logs()
        mock_print.assert_any_call(f"Available log files in log dir {log_dir}:")
        mock_print.assert_any_call("  foo")
        mock_print.assert_any_call("  bar")

def test_logsapi_list_logs_prints_no_files(tmp_path):
    """Verify that a message is printed when no log files exist."""
    api = LogsAPI(str(tmp_path))
    with patch("builtins.print") as mock_print:
        api.list_logs()
        mock_print.assert_any_call(f"No log files found in log dir {tmp_path}.")

def test_logsapi_list_logs_prints_dir_not_found():
    """Verify that a missing log directory is reported."""
    api = LogsAPI("not_a_dir")
    with patch("builtins.print") as mock_print:
        api.list_logs()
        mock_print.assert_any_call("Log directory not found: not_a_dir")

def test_logsapi_tail_log_prints_last_lines():
    """Verify that the requested tail of the log file is printed."""
    api = LogsAPI()
    log_content = "line1\nline2\nline3\n"
    m = mock_open(read_data=log_content)
    with patch("builtins.open", m), patch("builtins.print") as mock_print, patch("os.path.join", return_value="file.log"):
        api.tail_log("file", follow=False, lines=2)
        # Should print last 2 lines
        printed = "".join([call.args[0] for call in mock_print.call_args_list])
        assert "line2" in printed and "line3" in printed

def test_logsapi_tail_log_file_not_found():
    """Verify that a missing log file is reported."""
    api = LogsAPI()
    with patch("builtins.open", side_effect=FileNotFoundError), patch("builtins.print") as mock_print, patch("os.path.join", return_value="file.log"):
        api.tail_log("file")
        mock_print.assert_any_call("Log file not found: file.log")

def test_logsapi_tail_log_follow_prints_and_waits(monkeypatch):
    """Verify that follow mode continues monitoring the log file."""
    api = LogsAPI()
    log_content = "line1\nline2\nline3\n"
    m = mock_open(read_data=log_content)
    file_obj = m()
    # Simulate file with 3 lines, then no new lines
    lines = ["", "", ""]
    def readline_side_effect():
        return lines.pop(0) if lines else ""
    file_obj.readline.side_effect = readline_side_effect
    monkeypatch.setattr("builtins.open", lambda *a, **kw: file_obj)
    monkeypatch.setattr("os.path.join", lambda *a, **kw: "file.log")

    # Patch time.sleep and break after a few loops
    call_count = {"count": 0}
    def sleep_side_effect(_):
        call_count["count"] += 1
        if call_count["count"] > 3:
            raise SystemExit()  # Stop the test

    with patch("builtins.print") as mock_print, patch("time.sleep", side_effect=sleep_side_effect):
        try:
            api.tail_log("file", follow=True, lines=2)
        except SystemExit:
            pass
        printed = "".join([call.args[0] for call in mock_print.call_args_list])
        assert "line2" in printed or "line3" in printed

def test_logsapi_clear_logs_prints_dir_not_found():
    """Verify that a missing log directory is reported when clearing."""
    api = LogsAPI("not_a_dir")
    with patch("builtins.print") as mock_print:
        api.clear_logs()
        mock_print.assert_any_call("Log directory not found: not_a_dir")

def test_logsapi_clear_logs_aborted_on_no(tmp_path):
    """Verify that clearing is aborted when the user does not confirm."""
    api = LogsAPI(str(tmp_path))
    with patch("builtins.input", return_value="n"), \
         patch("builtins.print") as mock_print, \
         patch("shutil.rmtree") as mock_rmtree:
        api.clear_logs()
        mock_print.assert_any_call("Aborted.")
        mock_rmtree.assert_not_called()

def test_logsapi_clear_logs_removes_dir_on_confirm(tmp_path):
    """Verify that the log directory is removed when the user confirms."""
    api = LogsAPI(str(tmp_path))
    with patch("builtins.input", return_value="y"), \
         patch("builtins.print") as mock_print, \
         patch("shutil.rmtree") as mock_rmtree:
        api.clear_logs()
        mock_rmtree.assert_called_once_with(str(tmp_path))
        mock_print.assert_any_call("Log directory removed: " + str(tmp_path))

def test_logsapi_clear_logs_reports_failure(tmp_path):
    """Verify that failures during removal are reported."""
    api = LogsAPI(str(tmp_path))
    with patch("builtins.input", return_value="y"), \
         patch("builtins.print") as mock_print, \
         patch("shutil.rmtree", side_effect=OSError("boom")):
        api.clear_logs()
        mock_print.assert_any_call(f"Failed to remove log directory {tmp_path}: boom")

def test_logsapi_clear_logs_force_skips_confirmation(tmp_path):
    """Verify that force=True removes the log directory without prompting."""
    api = LogsAPI(str(tmp_path))
    with patch("builtins.input") as mock_input, \
         patch("builtins.print") as mock_print, \
         patch("shutil.rmtree") as mock_rmtree:
        api.clear_logs(force=True)
        mock_input.assert_not_called()
        mock_rmtree.assert_called_once_with(str(tmp_path))
        mock_print.assert_any_call("Log directory removed: " + str(tmp_path))

def test_cli_import_does_not_open_log_files(tmp_path):
    """Verify that importing the CLI does not load app loggers or open log files.

    Runs in a fresh interpreter because other tests may already have imported
    the application modules into this process.
    """
    code = (
        "import logging, sys\n"
        "import ansys.visor.viewer.cli.visor_cli\n"
        "assert 'ansys.visor.viewer.core.visor_logging' not in sys.modules, 'visor_logging imported'\n"
        "assert 'ansys.visor.viewer.app.visor' not in sys.modules, 'app imported'\n"
        "files = [r() for r in logging._handlerList if isinstance(r(), logging.FileHandler)]\n"
        "assert not files, files\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "logs").exists()
