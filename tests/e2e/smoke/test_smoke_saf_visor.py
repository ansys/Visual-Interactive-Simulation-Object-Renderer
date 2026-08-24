# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

"""
Smoke tests: verify saf-visor-poc loads and visualizes supported VTK file types.

Each parametrized case uploads a file of a given type (.vtp, .vtu) through the
"VTK Files" page and asserts that the upload succeeds and the Visor viewer
container is populated.

These tests are skipped automatically when the SAF CLI is not available.
"""

import os
import re
import subprocess
import tempfile
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

import pytest
import requests
from playwright.sync_api import Page, expect

from ansys.visor.viewer.vtk.io.file_to_dataset import file_to_dataset
from tests.helpers.utils.ports import reserve_free_port
from tests.helpers.utils.process import kill_proc_tree
from tests.helpers.utils.visor_api_tool import discover_from_log, list_datasets, save_state


def _saf_cli_available() -> bool:
    """Check if the SAF CLI is installed by running 'saf --version'."""
    try:
        result = subprocess.run(
            ["saf", "--version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


if not _saf_cli_available():
    pytest.skip("SAF CLI not available (saf --version failed)", allow_module_level=True)

# Console error substrings that originate from TDV WASM initialisation and are benign
_BENIGN_CONSOLE_PATTERNS = (
    "appendChild",
    "addSelectionChangeListener",
    "style",
    "rows",
    "FpsCounter",
)

# The VISOR launch alert fires once launch_visor()'s long-running transaction
# completes, but the shared "visor" instance handle used by update_visor() can
# take a little longer to become visible.
# These substrings identify that specific transient error
# so the upload can be retried instead of treated as a real failure.
_TRANSIENT_INSTANCE_ERROR_MARKERS = (
    "has not been initialized",
    "out of sequence",
)


@dataclass
class SafServerInfo:
    """SAF server connection info yielded by the saf_server fixture."""

    project_url: str
    log_path: str


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def saf_server(request):
    """
    Launch saf-visor-poc via `saf run` and yield its connection info.

    project_url includes the SAF project ID path (e.g. /projects/<id>), which is
    required for Dash project-context injection to work. log_path is the SAF
    stdout log, used to discover the Visor management API host/port (see
    tests/helpers/utils/visor_api_tool.py).

    Requires either --saf-project-dir CLI option or SAF_VISOR_POC_DIR env var
    to point at the saf-visor-poc root directory.
    """
    saf_project_dir_raw = request.config.getoption("--saf-project-dir") or os.environ.get(
        "SAF_VISOR_POC_DIR"
    )
    if not saf_project_dir_raw:
        pytest.skip(
            "SAF project dir not configured; "
            "pass --saf-project-dir or set SAF_VISOR_POC_DIR env var"
        )

    saf_project_dir = Path(saf_project_dir_raw).resolve()
    if not saf_project_dir.is_dir():
        pytest.skip(f"SAF project dir not found: {saf_project_dir}")

    host = request.config.getoption("--host")

    _, ui_port, ui_guard = reserve_free_port(host=host)
    _, api_port, api_guard = reserve_free_port(host=host)
    # Release guard sockets so the SAF server can bind to those ports
    ui_guard.close()
    api_guard.close()

    base_url = f"http://{host}:{ui_port}"

    popen_kwargs: dict = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["preexec_fn"] = os.setsid

    # Write to a temp file — avoids pipe-buffer deadlock (SAF emits many
    # WARNING lines on startup) and lets us extract the project URL from the log.
    log_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".log", prefix="saf_server_", delete=False
    )
    log_path = log_file.name

    proc = subprocess.Popen(
        [
            "saf", "run", str(saf_project_dir),
            "--solution-ui-port", str(ui_port),
            "--solution-api-port", str(api_port),
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        **popen_kwargs,
    )

    # Poll until the UI HTTP server responds (else clause fires only on timeout)
    deadline = time.time() + 90
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            resp = requests.get(base_url, timeout=2)
            if resp.status_code == 200:
                break
        except Exception as exc:
            last_err = exc
        time.sleep(2)
    else:
        log_file.flush()
        log_file.close()
        kill_proc_tree(proc.pid)
        raise RuntimeError(
            f"SAF UI not reachable at {base_url} within 90s. "
            f"Last error: {last_err!r}"
        )

    # SAF logs "INFO - Solution UI: http://host:port/projects/<id>" after startup.
    # Navigate directly to the project URL so the Dash project context is set.
    # The Flask app can start accepting connections (HTTP 200 above) slightly
    # before this log line is written, so poll the log for a few seconds.
    project_url = None
    log_deadline = time.time() + 15
    while time.time() < log_deadline:
        log_file.flush()
        with open(log_path) as f:
            log_content = f.read()
        match = re.search(r"INFO - Solution UI: (http://\S+)", log_content)
        if match:
            project_url = match.group(1)
            break
        time.sleep(1)

    if project_url is None:
        log_file.close()
        kill_proc_tree(proc.pid)
        raise RuntimeError(
            f"Could not find 'Solution UI' project URL in SAF log within 15s. "
            f"Log path: {log_path}"
        )

    yield SafServerInfo(project_url=project_url, log_path=log_path)

    kill_proc_tree(proc.pid)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log_file.close()
    try:
        Path(log_path).unlink(missing_ok=True)
    except PermissionError:
        pass  # Windows may keep the file locked briefly after process exit


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# Each entry is (file_path,) the test ID reflects the file extension.
_VTK_CASES = [
    pytest.param(Path("tests/files/plate.vtp"), id="vtp"),
    pytest.param(Path("tests/files/mesh.vtu"), id="vtu"),
]


@pytest.mark.smoke
@pytest.mark.saf
@pytest.mark.parametrize("vtk_file_path", _VTK_CASES)
def test_saf_visor_vtk_filetype_loads(
    page: Page,
    saf_server: SafServerInfo,
    vtk_file_path: Path,
) -> None:
    """
    Smoke: Verify saf-visor-poc loads and visualizes VTP and VTU files.

    Navigates to the VTK Files page, uploads a file, and asserts:
      - The upload status reports success with the filename.
      - The Visor viewer container is populated after upload.
    """
    vtk_file = vtk_file_path.resolve()

    if not vtk_file.is_file():
        pytest.skip(f"Test file not found: {vtk_file}")

    page.set_viewport_size({"width": 1280, "height": 800})

    console_errors: list[str] = []

    def _on_console(msg) -> None:
        is_benign = any(pattern in msg.text for pattern in _BENIGN_CONSOLE_PATTERNS)
        if msg.type == "error" and not is_benign:
            console_errors.append(msg.text)

    page.on("console", _on_console)

    page.goto(saf_server.project_url, wait_until="domcontentloaded")

    # The About page auto-launches the Visor service on first load.
    # We need to wait for the launch result alert before navigating away so that
    # update_visor() does not fail with "shared product instance not initialized".
    page.locator("#visor_launch_message .alert").wait_for(state="visible", timeout=120_000)

    # The launch alert fires once launch_visor()'s transaction completes, but the
    # shared "visor" instance handle can take a little longer to become visible.
    # The "Visor API host/port" log line itself can also lag slightly behind the alert
    instance_ready_deadline = time.time() + 60
    while True:
        try:
            api_host, api_port = discover_from_log(saf_server.log_path)
            list_datasets(api_host, api_port)
            break
        except (requests.ConnectionError, RuntimeError):
            if time.time() >= instance_ready_deadline:
                pytest.fail("Visor shared instance did not become ready within 60s")
            time.sleep(2)

    # Click "VTK Files" in the sidebar navigation
    vtk_nav = page.locator("text=VTK Files")
    vtk_nav.wait_for(state="visible", timeout=15_000)
    vtk_nav.click()

    # Confirm the upload button is visible before attempting upload
    upload_btn = page.locator("#btn_vtk_upload")
    upload_btn.wait_for(state="visible", timeout=10_000)

    status_locator = page.locator("#vtk_upload_status")

    # Retry on the transient "instance not initialized" race (see marker comment
    # above) as a safety net, since re-selecting the file re-triggers the upload
    # callback cleanly.
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        page.locator("input[type='file']").set_input_files(str(vtk_file))
        expect(status_locator).to_contain_text(vtk_file.name, timeout=30_000)
        status_text = status_locator.inner_text()

        is_transient = any(marker in status_text for marker in _TRANSIENT_INSTANCE_ERROR_MARKERS)
        if not is_transient or attempt == max_attempts:
            break
        page.wait_for_timeout(2_000 * attempt)

    assert "✅" in status_text, (
        f"Upload did not succeed for {vtk_file.name}. Status: {status_text!r}"
    )

    # # # Currently disabled: SAF-visor poc always show at least one child even on a failed upload
    # # Assert the Visor viewer container was populated with child elements
    # viewer = page.locator("#visor_vtk_viewer_container")
    # viewer.wait_for(state="visible", timeout=10_000)
    # child_count = viewer.evaluate("el => el.children.length")
    # assert child_count > 0, "Visor viewer container is empty after upload"

    # Report console errors as warnings but allow test to pass
    if console_errors:
        warnings.warn(
            f"Unexpected JS console errors detected: {console_errors}",
            UserWarning,
            stacklevel=2,
        )

    # Save the visualizer's state and assert the resulting VTKHDF snapshot actually contains geometry.

    state_dir = Path(
        "tests/artifacts", "saf-smoke", "results", "test_saf_visor_vtk_filetype_loads", vtk_file_path.stem
    ).resolve()
    state_dir.mkdir(parents=True, exist_ok=True)

    # Retry save_state briefly since backend registration can lag after upload.
    save_state_deadline = time.time() + 30
    while True:
        try:
            save_state(api_host, api_port, str(state_dir))
            break
        except requests.HTTPError as exc:
            body = exc.response.text if exc.response is not None else "<no body>"
            if time.time() >= save_state_deadline:
                pytest.fail(
                    f"save_state failed with {exc}.\nServer response body:\n{body}"
                )
            time.sleep(2)

    vtkhdf_files = list(state_dir.rglob("*.vtkhdf"))
    assert vtkhdf_files, f"No .vtkhdf snapshot files found under {state_dir}"

    dataset = file_to_dataset(str(vtkhdf_files[0]))
    assert dataset.GetNumberOfPoints() > 0, (
        f"Saved VTKHDF snapshot {vtkhdf_files[0].name} contains no points"
    )
    assert dataset.GetNumberOfCells() > 0, (
        f"Saved VTKHDF snapshot {vtkhdf_files[0].name} contains no cells"
    )
