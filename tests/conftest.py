# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

# ==================================================== [Imports] ==================================================== #

import sys
from pathlib import Path

import pytest

from ansys.visor.viewer.core.paraview_python import PARAVIEW_PYTHON_VERSION, PARAVIEW_VERSION

# =================================================== [Variables] =================================================== #


# =================================================== [Functions] =================================================== #

# Add options for pytest-image comparison common operations
def pytest_addoption(parser: pytest.Parser):
    parser.addoption("--update-baseline", action="store_true", default=False, help="Overwrite baseline image with current screenshot.")
    parser.addoption("--baseline-dir", action="store", default="tests/references", help="Directory where baseline images are stored.")
    parser.addoption("--pixel-threshold", action="store", default="2.55", help="RMS threshold for image comparison (0..255).")
    # parser.addoption("--url", action="store", default="http://localhost:8081/index.html", help="Target URL for ST-03.")
    parser.addoption("--dash-port", action="store", default="8050", help="Port where the Dash app will run.")
    # parser.addoption("--visor-port", action="store", default="8081", help="Port where the Visor will run.")
    parser.addoption("--host", action="store", default="127.0.0.1", help="Target host for servers.")


# Tests marked ``paraview`` exercise code that only runs inside pvpython, so they
# run only on the Python ParaView embeds.
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]):
    if sys.version_info[:2] == PARAVIEW_PYTHON_VERSION:
        return
    required = ".".join(map(str, PARAVIEW_PYTHON_VERSION))
    running = ".".join(map(str, sys.version_info[:2]))
    skip = pytest.mark.skip(
        reason=f"PARAVIEW mode requires Python {required}, the Python ParaView {PARAVIEW_VERSION} ships with; running {running}"
    )
    for item in items:
        if item.get_closest_marker("paraview"):
            item.add_marker(skip)


# Base fixtures -----------------------------------

@pytest.fixture(scope="module")
def baseline_dir(request) -> Path:
    return Path(request.config.getoption("--baseline-dir")).resolve()

@pytest.fixture(scope="module")
def pixel_threshold(request) -> float:
    return float(request.config.getoption("--pixel-threshold"))

@pytest.fixture
def suite_name(request):
    # get all markers applied to this test
    markers = request.node.iter_markers()
    names = [m.name for m in markers]
    # return only the first marker name
    return names[0]