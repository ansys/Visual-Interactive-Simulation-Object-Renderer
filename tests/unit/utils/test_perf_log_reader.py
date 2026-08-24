import json
from pathlib import Path

import pytest

from ansys.visor.viewer.utils.perf_log_reader import PerfLogReader

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def write_log(path: Path, content: str):
    """Overwrite the log file with the provided content."""
    path.write_text(content, encoding="utf-8")


def append_log(path: Path, content: str):
    """Append additional content to the existing log file."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)


# -----------------------------------------------------------------------------
# Log fixtures
# -----------------------------------------------------------------------------

FULL_UPDATE_VARIABLES_LOG = """[PERF] update_variables n_vars=2 | from_dict=0.01s update_variables_for_dataset=0.02s total=0.03s
[PERF] VisorDataset.update_variables | validate=0.005s vtk_set_loop=0.006s reload=0.007s
[PERF] update_variables_for_dataset | dataset_registry.update=0.01s update_descendant_parts=0.02s render=0.03s
[PERF] render | RenderWindow.Render=0.02s LocalView.update=0.03s
[PERF] _update_variable 'pressure' n_tuples=100 n_components=3 | set_loop+modified=0.02s
[PERF] _update_variable 'temperature' n_tuples=200 n_components=1 | set_loop+modified=0.01s
[PERF] client updateAsync | total=50 wasm=30 resize=5 states=2 (10 MB) blobs=3 (20 MB total, largest=8 MB in 12ms)
[PERF] client onServerUpdateAsync | handler=15
"""
"""Representative update_variables log covering server, client, and variable parsing."""

MINIMAL_UPDATE_LOG = "[PERF] update_variables n_vars=1 | total=0.05s\n"
"""Minimal valid update_variables log with only a total phase."""

ADD_DATASET_LOG = "[PERF] add_dataset | resolve_io=0.01s add_to_scene=0.02s finalize_scene=0.03s total=0.04s\n"
"""Minimal add_dataset namespace log including total phase."""

MISSING_TOTAL_LOG = "[PERF] VisorDataset.update_variables | validate=0.01s\n"
"""Log lacking required total key, used to trigger validation failure."""

NOISE_LOG = """some random log line
[INFO] something else
[PERF] unknown_label | foo=1
"""
"""Log containing no valid PERF entries for the target namespace."""


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def test_mark_no_log_file(tmp_path):
    """mark() should set position to zero when log file does not exist."""
    log_path = tmp_path / "visor.log"

    reader = PerfLogReader(log_path=log_path, report_dir=tmp_path)
    reader.mark()

    assert reader._mark_pos == 0


def test_save_report_minimal(tmp_path):
    """save_report() should succeed with minimal valid log and produce correct fields."""
    log_path = tmp_path / "visor.log"

    write_log(log_path, "")
    reader = PerfLogReader(log_path=log_path, report_dir=tmp_path)

    reader.mark()
    append_log(log_path, MINIMAL_UPDATE_LOG)

    json_path = reader.save_report(dataset_label="test.vtp")
    data = json.loads(json_path.read_text())

    assert data["namespace"] == "update_variables"
    assert data["dataset_label"] == "test.vtp"
    assert data["total_s"] == pytest.approx(0.05)
    assert data["num_variables"] == 1
    assert data["meets_target"] is True


def test_save_report_full_parsing(tmp_path):
    """save_report() should correctly parse full log including phases, variables, and client data."""
    log_path = tmp_path / "visor.log"

    write_log(log_path, "")
    reader = PerfLogReader(
        log_path=log_path,
        report_dir=tmp_path,
        target_s=0.02,
    )

    reader.mark()
    append_log(log_path, FULL_UPDATE_VARIABLES_LOG)

    json_path = reader.save_report()
    data = json.loads(json_path.read_text())

    assert "from_dict_total_s" in data["phases"]
    assert "registry_update_s" in data["phases"]
    assert "render_scene_s" in data["phases"]

    assert len(data["variables"]) == 2
    assert data["variables"][0]["name"] == "pressure"
    assert data["variables"][1]["name"] == "temperature"

    expected_elements = 100 * 3 + 200 * 1
    assert data["total_elements"] == expected_elements

    client = data["client"]
    assert client["total_ms"] == 50.0
    assert client["wasm_ms"] == 30.0
    assert client["state_total_mb"] == 10.0
    assert client["blob_total_mb"] == 20.0
    assert client["blob_max_mb"] == 8.0
    assert client["blob_max_dur_ms"] == 12.0
    assert client["handler_ms"] == 15.0

    assert data["meets_target"] is False


def test_add_dataset_namespace(tmp_path):
    """save_report() should respect add_dataset namespace and extract total correctly."""
    log_path = tmp_path / "visor.log"

    write_log(log_path, "")
    reader = PerfLogReader(
        log_path=log_path,
        report_dir=tmp_path,
        namespace="add_dataset",
    )

    reader.mark()
    append_log(log_path, ADD_DATASET_LOG)

    json_path = reader.save_report()
    data = json.loads(json_path.read_text())

    assert data["namespace"] == "add_dataset"
    assert data["total_s"] == pytest.approx(0.04)


def test_save_report_missing_total_raises(tmp_path):
    """save_report() should raise RuntimeError if required total key is absent."""
    log_path = tmp_path / "visor.log"

    write_log(log_path, "")
    reader = PerfLogReader(log_path=log_path, report_dir=tmp_path)

    reader.mark()
    append_log(log_path, MISSING_TOTAL_LOG)

    with pytest.raises(RuntimeError):
        reader.save_report()


def test_mark_excludes_old_lines(tmp_path):
    """mark() should exclude log lines written before it was called."""
    log_path = tmp_path / "visor.log"

    write_log(log_path, "[PERF] update_variables n_vars=1 | total=0.1s\n")

    reader = PerfLogReader(log_path=log_path, report_dir=tmp_path)
    reader.mark()

    append_log(log_path, "[PERF] update_variables n_vars=1 | total=0.05s\n")

    json_path = reader.save_report()
    data = json.loads(json_path.read_text())

    assert data["total_s"] == pytest.approx(0.05)


def test_noise_lines_ignored(tmp_path):
    """save_report() should fail when no valid PERF lines are found after mark()."""
    log_path = tmp_path / "visor.log"

    write_log(log_path, "")
    reader = PerfLogReader(log_path=log_path, report_dir=tmp_path)

    reader.mark()
    append_log(log_path, NOISE_LOG)

    with pytest.raises(RuntimeError):
        reader.save_report()
