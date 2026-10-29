"""Public SAF transactions, browser uploads and Visor state persistence."""

import importlib.util
import inspect
import json
import os
import subprocess
import sys
import time
from collections.abc import Generator, Iterator
from contextlib import ExitStack, contextmanager
from importlib.metadata import distribution, distributions, version
from pathlib import Path
from uuid import uuid4

import pytest
import requests
from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from ansys.visor.viewer.vtk.io.file_to_dataset import file_to_dataset
from tests.helpers.utils.canvas import wait_for_canvas_alive
from tests.helpers.utils.ports import reserved_port
from tests.helpers.utils.process import kill_proc_tree
from tests.helpers.utils.visor_api_tool import list_datasets, save_state

ROOT = Path(__file__).resolve().parents[3]
HOST = "127.0.0.1"


def wait_for_server(url: str, process: subprocess.Popen, log_path: Path) -> None:
    """Poll `url` until it returns HTTP 200.

    Args:
        url: Readiness endpoint of the server.
        process: Server process, checked for early exit while waiting.
        log_path: Server log, referenced in error messages.

    Raises:
        RuntimeError: If the process exits or the server is not ready within 90 seconds.
    """
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited with {process.returncode}. See {log_path}")
        try:
            response = requests.get(url, timeout=2)
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(0.2)
            continue
        if response.status_code == 200:
            return
        time.sleep(0.2)
    raise RuntimeError(f"Server did not become ready at {url}. See {log_path}")


@contextmanager
def server_process(
    command: list[str], env: dict[str, str], log_path: Path,
) -> Generator[subprocess.Popen, None, None]:
    """Run a server subprocess logging to `log_path` and kill its process tree on exit."""
    # Launch the server with output going to a log file, in its own process group or session so its whole tree can be killed later.
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
        # Give the running process to the caller. On exit, kill its tree if still alive and wait for it to stop.
        try:
            yield process
        finally:
            if process.poll() is None:
                kill_proc_tree(process.pid)
            process.wait(timeout=15)


@pytest.fixture(scope="module")
def saf_stack() -> Iterator[tuple[str, str, int, Path]]:
    """Start the Visor management API and the SAF GLOW API and UI once per module.

    Yields:
        The UI URL, the GLOW API URL, the Visor management port and the artifact directory.
    """
    # Preflight: the fixture package must be installed, otherwise fail with setup instructions.
    if importlib.util.find_spec("visor_saf_smoke") is None:
        pytest.fail("Install tests/fixtures/saf_visor_solution[test] and the current Visor wheel first.")

    # Per-run folder for logs, the SQLite database, provenance and the package snapshot.
    artifact_dir = ROOT / "tests" / "artifacts" / "saf-smoke" / uuid4().hex
    artifact_dir.mkdir(parents=True)
    # Build an isolated child environment: drop inherited GLOW_, OTEL_ and SAF_VISOR_ settings, then force a local SQLite desktop deployment.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GLOW_", "OTEL_", "SAF_VISOR_"))
    }
    env.update(
        PYTHONUNBUFFERED="1",
        GLOW_DEPLOYMENT="Desktop",
        GLOW_DATABASE_TYPE="sqlite",
        GLOW_DATABASE_LOCATION=str(artifact_dir / "glow.db"),
        GLOW_PROJECT_FILES_DIRECTORY=str(artifact_dir / "files"),
        GLOW_UI_PROJECT_FILES_DIRECTORY=str(artifact_dir / "files"),
        OTEL_SDK_DISABLED="true",
        NO_PROXY="127.0.0.1,localhost",
        no_proxy="127.0.0.1,localhost",
    )
    # Record which Python, Visor and SAF versions and install sources this run used, for traceability.
    (artifact_dir / "provenance.json").write_text(
        json.dumps(
            {
                "python": sys.executable,
                "visor": version("ansys-visor-viewer"),
                "saf_sdk": version("ansys-saf-sdk"),
                "visor_module": inspect.getfile(file_to_dataset),
                "visor_install": json.loads(
                    distribution("ansys-visor-viewer").read_text("direct_url.json") or "{}"
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # Snapshot every installed package so the run's dependencies can be reproduced later.
    installed = sorted(f"{package.metadata['Name']}=={package.version}" for package in distributions())
    (artifact_dir / "requirements.txt").write_text("\n".join(installed) + "\n", encoding="utf-8")
    # Start the services under one ExitStack so every server is stopped when the fixture ends, even on failure.
    # Three free localhost ports are reserved up front (Visor, API, UI).
    with ExitStack() as stack:
        ports = []
        for _ in range(3):
            _, port, guard = stack.enter_context(reserved_port(HOST))
            ports.append((port, guard))
        visor_port, api_port, ui_port = [item[0] for item in ports]
        # Wire the API and UI to the Visor and API ports chosen above, through environment variables.
        visor_url = f"http://{HOST}:{visor_port}"
        api_url = f"http://{HOST}:{api_port}"
        env["SAF_VISOR_API_URL"] = visor_url
        env["GLOW_API_URL"] = api_url
        # Command line for each service, in startup order: Visor, SAF API, SAF UI.
        commands = [
            [
                sys.executable, "-m", "ansys.visor.viewer.cli.visor_cli",
                "--api-host", HOST, "--api-port", str(visor_port), "server", "start",
            ],
            [sys.executable, "-m", "visor_saf_smoke.main", "api", "--host", HOST, "--port", str(api_port)],
            [
                sys.executable, "-m", "visor_saf_smoke.main", "ui",
                "--host", HOST, "--port", str(ui_port), "--api-server-url", api_url,
            ],
        ]
        # Start each service in turn and wait for its health endpoint before starting the next.
        # Each port guard is released just before its service launches, which limits port races.
        for (port, guard), name, command in zip(ports, ("visor", "api", "ui"), commands, strict=True):
            guard.close()
            log_path = artifact_dir / f"{name}.log"
            process = stack.enter_context(server_process(command, env, log_path))
            path = "/health" if name == "visor" else "/docs" if name == "api" else "/"
            wait_for_server(f"http://{HOST}:{port}{path}", process, log_path)

        # Hand the endpoints to the tests. The servers keep running until the tests finish and the ExitStack unwinds.
        yield f"http://{HOST}:{ui_port}", api_url, visor_port, artifact_dir


@pytest.fixture
def saf_project(
    request: pytest.FixtureRequest, saf_stack: tuple[str, str, int, Path],
) -> Iterator[tuple[str, int, Path]]:
    """Create a fresh SAF project for one case and reset Visor afterwards.

    Yields:
        The project URL, the Visor management port and the per-case artifact directory.
    """
    ui_url, api_url, visor_port, artifact_dir = saf_stack
    # One folder per parametrized case, then a new empty SAF project created through the GLOW API.
    case_dir = artifact_dir / request.node.callspec.id
    case_dir.mkdir()
    response = requests.post(
        f"{api_url}/projects", json={"display_name": "SAF Visor smoke", "description": ""}, timeout=30,
    )
    response.raise_for_status()
    yield f"{ui_url}/{response.json()['name']}", visor_port, case_dir
    # Best-effort reset so the next case initializes a new empty visualizer.
    try:
        reset = requests.post(f"http://{HOST}:{visor_port}/stop", timeout=30)
        result = {"status": reset.status_code, "body": reset.text}
    except requests.RequestException as exc:
        result = {"error": str(exc)}
    (case_dir / "visor-stop.json").write_text(json.dumps(result), encoding="utf-8")


@pytest.mark.smoke
@pytest.mark.saf
@pytest.mark.parametrize("filename", ["plate.vtp", "mesh.vtu"], ids=["vtp", "vtu"])
def test_saf_visor_vtk_filetype_loads(
    page: Page, saf_project: tuple[str, int, Path], filename: str,
) -> None:
    """Upload a VTK file through the SAF UI and verify Visor loads and saves matching geometry."""

    project_url, api_port, artifact_dir = saf_project
    input_path = ROOT / "tests" / "files" / filename

    assert input_path.is_file(), f"Required smoke asset is missing: {input_path}"

    # Collect uncaught browser errors and use a fixed viewport so UI checks are repeatable.
    browser_errors: list[str] = []
    page.on("pageerror", lambda error: browser_errors.append(error.stack or str(error)))
    page.set_viewport_size({"width": 1280, "height": 900})

    # UI flow: open the project, initialize Visor, and wait until it reports ready.
    try:
        page.goto(project_url, wait_until="domcontentloaded")
        page.get_by_role("button", name="Initialize Visor").click()
        expect(page.locator("#launch-status")).to_have_text("ready", timeout=90_000)

        # Check that Visor starts empty, then upload the file and confirm it arrived in both the UI and the Visor backend.
        assert list_datasets(HOST, api_port) == {}, "Visor must start without preloaded geometry"

        wait_for_canvas_alive(page, "before upload", timeout_ms=60_000)
        page.locator("input[type=file]").set_input_files(str(input_path))
        expect(page.locator("#upload-status")).to_have_text(f"loaded: {filename}", timeout=60_000)
        datasets = list_datasets(HOST, api_port)
        
        assert len(datasets) == 1, f"Expected only the current upload, got {datasets}"
        assert filename in json.dumps(datasets), f"Loaded dataset does not identify {filename}: {datasets}"

        # Round-trip check: save Visor state, then compare the saved geometry (points, cells, bounds) with the original file.
        state_dir = artifact_dir / "state"
        save_state(HOST, api_port, str(state_dir))
        snapshots = list(state_dir.rglob("*.vtkhdf"))
        assert len(snapshots) == 1, f"Expected one fresh snapshot, found {snapshots}"
        expected = file_to_dataset(str(input_path))
        saved = file_to_dataset(str(snapshots[0]))
        assert saved.GetNumberOfPoints() == expected.GetNumberOfPoints() > 0
        assert saved.GetNumberOfCells() == expected.GetNumberOfCells() > 0
        assert saved.GetBounds() == pytest.approx(expected.GetBounds())
        wait_for_canvas_alive(page, "after upload")
        assert not browser_errors, f"Uncaught browser errors: {browser_errors}"

    # Always record browser errors and a screenshot for diagnosis, even when the test failed.
    finally:
        (artifact_dir / "browser-errors.json").write_text(json.dumps(browser_errors), encoding="utf-8")
        if not page.is_closed():
            try:
                page.screenshot(path=str(artifact_dir / "page.png"), full_page=True, timeout=5_000)
            except PlaywrightTimeoutError as exc:
                (artifact_dir / "screenshot-error.txt").write_text(str(exc), encoding="utf-8")
