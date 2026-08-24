# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

# ==================================================== [Imports] ==================================================== #

import time
from datetime import datetime, timezone
from multiprocessing import Process
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests

from ansys.visor.viewer import Visor
from tests.helpers.utils.dash_server import run_dash_server
from tests.helpers.utils.ports import reserved_port


@pytest.fixture(scope="module")
def visor_asset_spec(request):
    """
    Carries the asset + metadata paths. If not parametrized, uses defaults.

    Specify in test via:
    @pytest.mark.parametrize(
        "visor_asset_spec",
        [{
            "asset_path": Path("path/to/asset.vtm"),
            "metadata_path": Path("path/to/metadata.json"),
        }],
        indirect=True,
    """
    default = {
        "asset_path": str(Path("examples/assets/vtk_scene_sphere_l2_b3_r32_v3_c1_z3.vtm")),
        "metadata_path": str(Path("examples/assets/vtk_scene_sphere_l2_b3_r32_v3_c1_z3.json")),
        "dark_mode": None,
    }
    return getattr(request, "param", default)


@pytest.fixture(scope="module")
def visor_server(request, visor_asset_spec):
    """
    Starts Visor server via Python API, launches visualizer with asset + metadata,
    and stops it after tests.

    Important: One instance per (session x asset_spec parameter)
    """
    # Getting URL from pytest option: -----------------------
    # It would be nice to allow the tester to use a specific url or port if they really wanted to despite possibly not being available

    # url = request.config.getoption("--url")
    # visor_port = request.config.getoption("--visor_port")
    #--------------------------------------------------------
    host = request.config.getoption("--host")

    # Asset and metadata paths are now variables
    asset_path = visor_asset_spec["asset_path"]
    metadata_path = visor_asset_spec["metadata_path"]
    dark_mode = visor_asset_spec.get("dark_mode", None)

    with reserved_port(host=host) as (host, port, guard):
        base_url = f"http://{host}:{port}"
        url = f"{base_url}/index.html"

        try:
            guard.close()
        except Exception:
            pass

        visor = Visor(url=url, dark_mode=dark_mode)
        visor.start(asset_path, metadata=metadata_path)

    # Poll the target URL until it's reachable (HTTP 200)
    deadline = time.time() + 45
    last_err = None
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                break
        except Exception as e:
            last_err = e
        time.sleep(1.5)
    else:
        raise RuntimeError(
            f"Visor visualizer not reachable at {url} within the expected time. "
            f"Last error: {last_err!r}"
        )

    # Yield the instance for tests
    yield visor

    # Stop the server after tests
    visor.stop()

# DASH fixtures -----------------------------

@pytest.fixture(scope="module")
def launch_dash_server(request, visor_server):
    """
    Starts a Dash app that embeds the Visordash component connected to the Visor instance.
    Waits for it to be reachable, yields its base URL, and tears it down afterwards.

    Depends on `visor_server` to ensure Visor is up before Dash starts.
    """
    # Parse Visor host/port from visor.url (default: http://localhost:8081/index.html)
    parsed = urlparse(visor_server.url)

    if ":" in parsed.netloc:
        visor_host, port_str = parsed.netloc.split(":", 1)
        visor_port = int(port_str)
    else:
        visor_host = parsed.hostname or "localhost"
        visor_port = parsed.port or 8081

    with reserved_port(host=visor_host) as (host, dash_port, guard):
            base_url = f"http://{host}:{dash_port}"
            dash_url = f"{base_url}/index.html"

            try:
                guard.close()
            except Exception:
                pass

            # Optional prop overrides supplied via indirect parametrize
            dash_props = getattr(request, "param", {})

            # Start Dash in a separate process for clean teardown
            proc = Process(
                target=run_dash_server,
                args=(visor_host, visor_port, dash_port),
                kwargs=dash_props,
            )
            proc.daemon = True
            proc.start()

    # Poll Dash until reachable (HTTP 200)
    deadline = time.time() + 90
    last_err = None
    while time.time() < deadline:
        try:
            resp = requests.get(dash_url, timeout=2)
            if resp.status_code == 200:
                break
        except Exception as e:
            last_err = e
        time.sleep(1.5)
    else:
        # Ensure we terminate the process if startup failed
        try:
            proc.terminate()
        except Exception:
            pass
        raise RuntimeError(
            f"Dash app not reachable at {dash_url} within the expected time. "
            f"Last error: {last_err!r}"
        )

    # Yield the Dash URL for tests
    yield dash_url

    # Stop Dash after tests
    try:
        proc.terminate()
        proc.join(timeout=10)
    finally:
        if proc.is_alive():
            # Force kill if still running
            proc.kill()


# =================================================== [Playwright] =================================================== #
# This fixture automatically starts Playwright tracing for each test, and if the test fails, it saves the trace to a file for later analysis.

@pytest.fixture(autouse=True)
def trace_on_failure(request, page):
    # start tracing for this test
    page.context.tracing.start(screenshots=True, snapshots=True, sources=True)
    yield
    # after test: if failed -> stop and save trace
    rep = request.node.rep_call  # set by pytest_runtest_makereport hook below
    if rep and rep.failed:
        outdir = Path(request.config.rootpath) / "artifacts" / "traces"
        outdir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        fname = outdir / f"{request.node.name}.{ts}.zip"
        page.context.tracing.stop(path=str(fname))
        print(f"Saved Playwright trace to: {fname}")
    else:
        # stop without saving to avoid disk use
        page.context.tracing.stop()

# This hook captures the test report for the "call" phase (the actual test execution) and attaches it to the test item, so that the trace_on_failure
# fixture can check if the test failed or not after the test runs.
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call":
        item.rep_call = rep