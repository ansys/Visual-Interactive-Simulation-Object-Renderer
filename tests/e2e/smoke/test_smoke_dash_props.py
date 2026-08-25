# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

"""
Smoke tests: verify Visordash renders with different property configurations.

Each parametrized case launches Visor + Dash with a different set of Visordash
props (darkMode, aspectRatio, pixelDensity) and asserts that the WebGL canvas
is alive and asserts values from the DOM that indicate the prop took effect (e.g. background color for
"""

import pytest
from playwright.sync_api import Page

from tests.helpers.utils.canvas import (
    assert_canvas_alive,
    goto_and_wait,
    settle,
    wait_for_canvas,
    wait_for_webgl,
)
from tests.helpers.utils.ui_selectors import (
    get_container_aspect_ratio,
    get_ui_panel_scale,
    get_visor_viewer_background,
)

# ---------------------------------------------------------------------------
# Dash properties variant matrix
# ---------------------------------------------------------------------------

DASH_VARIANTS = [
    pytest.param(
        {"darkMode": False},
        {"check": "background", "expected": "247, 247, 247"},
        id="light-mode",
    ),
    pytest.param(
        {"aspectRatio": 1.0},
        {"check": "aspect_ratio", "expected": "1 / 1"},
        id="aspect-ratio-1.0",
    ),
    pytest.param(
        {"pixelDensity": 750},
        {"check": "pixel_density", "expected_density": 750},
        id="pixel-density-750",
    ),
]


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "launch_dash_server, expected", DASH_VARIANTS, indirect=["launch_dash_server"]
)
@pytest.mark.smoke
def test_dash_prop_variant_canvas_alive(page: Page, launch_dash_server, expected, request):
    """Smoke: Visordash renders with non-default prop configuration."""
    dash_url = launch_dash_server

    goto_and_wait(page, dash_url, wait_until="domcontentloaded")
    wait_for_canvas(page)
    wait_for_webgl(page)
    settle(page)
    assert_canvas_alive(page, label=f"dash-variant-{request.node.callspec.id}")

    # Prop-specific DOM assertions
    check = expected["check"]
    if check == "background":
        bg = get_visor_viewer_background(page)
        assert bg == expected["expected"], (
            f"Expected viewer background '{expected['expected']}', got '{bg}'"
        )
    elif check == "aspect_ratio":
        ratio = get_container_aspect_ratio(page)
        assert ratio == expected["expected"], (
            f"Expected aspect-ratio '{expected['expected']}', got '{ratio}'"
        )
    elif check == "pixel_density":
        scale = get_ui_panel_scale(page)
        assert scale is not None, "Could not read UI panel transform scale"
        # scale = containerWidth / pixelDensity; viewport is 1280px (set in goto_and_wait)
        # Note: top-left panel applies an afterScale factor of 0.85 (see UiScaffold.tsx)
        expected_scale = (1280 / expected["expected_density"]) * 0.85
        assert abs(scale - expected_scale) < 0.1, (
            f"Expected scale ~{expected_scale:.3f}, got {scale:.3f}"
        )
