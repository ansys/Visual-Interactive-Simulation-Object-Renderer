# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

"""
Smoke test: verify Visordash renders correctly in dark mode.

This test lives in its own module so that the module-scoped visor_server fixture
is created with dark_mode=True (the Visor backend must be initialized with dark mode
enabled for the frontend theme to apply correctly).
"""

from pathlib import Path

import pytest
from playwright.sync_api import Page

from tests.helpers.utils.canvas import (
    assert_canvas_alive,
    goto_and_wait,
    settle,
    wait_for_canvas,
    wait_for_webgl,
)
from tests.helpers.utils.ui_selectors import get_visor_viewer_background

# ---------------------------------------------------------------------------
# Parametrize visor_asset_spec to enable dark_mode on the Visor server
# ---------------------------------------------------------------------------

DARK_MODE_ASSET_SPEC = {
    "asset_path": str(Path("examples/assets/vtk_scene_sphere_l2_b3_r32_v3_c1_z3.vtm")),
    "metadata_path": str(Path("examples/assets/vtk_scene_sphere_l2_b3_r32_v3_c1_z3.json")),
    "dark_mode": True,
}


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("visor_asset_spec", [DARK_MODE_ASSET_SPEC], indirect=True)
@pytest.mark.parametrize("launch_dash_server", [{"darkMode": True}], indirect=True)
@pytest.mark.smoke
def test_dash_dark_mode_canvas_alive(page: Page, launch_dash_server, request):
    """Smoke: Visordash renders with dark mode enabled on the Visor server."""
    dash_url = launch_dash_server

    goto_and_wait(page, dash_url, wait_until="domcontentloaded")
    wait_for_canvas(page)
    wait_for_webgl(page)
    settle(page)
    assert_canvas_alive(page, label="dash-variant-dark-mode")

    # Assert dark mode background color
    bg = get_visor_viewer_background(page)
    assert bg == "54, 60, 67", (
        f"Expected dark mode viewer background '54, 60, 67', got '{bg}'"
    )
