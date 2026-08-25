# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.


import pytest
from playwright.sync_api import Page

from tests.helpers import visual
from tests.helpers.comparison.image_diff import compare_images
from tests.helpers.utils.canvas import assert_canvas_alive, settle


@pytest.mark.smoke
def test_st03_basic_render_rotation(page: Page, visor_server, baseline_dir, pixel_threshold, request):

    """
    Smoke: Validate the end-to-end render and rotation interaction  (rotate)

    The test asserts that:
      - The viewer loads and the WebGL canvas is alive throughout.
      - Two screenshots are taken and validated: initial load and after rotation.
    """

    target_url = visor_server.url  # "usually http://localhost:8081/index.html"

    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(target_url, wait_until="networkidle")

    console_errors = []
    def _on_console(msg):
        # Collect only error-level messages for smoke health checks
        if msg.type == "error":
            console_errors.append(msg.text)
    page.on("console", _on_console)

    page.goto(target_url, wait_until="networkidle")

    canvas = page.locator("canvas.vtk-wasm-1")
    canvas.wait_for(state="visible", timeout=15_000)

    # Find start point, canvas center
    box = canvas.bounding_box()
    assert box is not None, "Canvas bounding box not available"
    cx = box["x"] + box["width"] / 2
    cy = box["y"] + box["height"] / 2

    assert_canvas_alive(page, label="initial")

    result_initial = visual.verify_canvas_against_baseline(
        canvas_locator=canvas,
        baseline_dir=baseline_dir,
        pixel_threshold=2.55,
        request=request,
        compare_images=compare_images,
        test_id="st03_canvas_initial",
        test_suite="smoke",
    )

    # -------------------------------------------------------------------------
    # 1) Rotate: left-click + drag diagonally
    # -------------------------------------------------------------------------
    page.mouse.move(cx, cy)
    page.mouse.down(button="left")
    page.mouse.move(cx + 180, cy - 120)
    page.mouse.up(button="left")
    settle(page)
    assert_canvas_alive(page, label="after-rotate")

    result_rotation = visual.verify_canvas_against_baseline(
        canvas_locator=canvas,
        baseline_dir=baseline_dir,
        pixel_threshold=2.55,
        request=request,
        compare_images=compare_images,
        test_id="st03_canvas_rotation",
        test_suite="smoke",
    )

    suite_result = visual.make_test_result(result_initial, result_rotation)

    # Assert once on the aggregate:
    assert suite_result.passed, "Some checks failed\t\n" + suite_result.summary()
    print(suite_result.summary())
