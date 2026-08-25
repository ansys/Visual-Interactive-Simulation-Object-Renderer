# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

import json
from pathlib import Path

import pytest
from deepdiff import DeepDiff
from playwright.sync_api import Page

from tests.helpers import visual
from tests.helpers.comparison.image_diff import compare_images
from tests.helpers.utils.canvas import settle, wait_for_canvas, wait_for_webgl


@pytest.mark.regression
def test_dash_start(page: Page, launch_dash_server, baseline_dir, request, suite_name):
    """
    Regression test for DASH startup and basic geometry loading

    """
    # add launch_dash_server fixture to ensure server + instance are running
    target_url = launch_dash_server  # usually http://localhost:8050/index.html"

    page.set_viewport_size({"width": 1280, "height": 800})

    # Navigate and wait for network idle
    page.goto(target_url, wait_until="domcontentloaded")

    # Wait for the canvas and WebGL
    canvas = wait_for_canvas(page)
    wait_for_webgl(page)
    settle(page)

    verify_comparison_1 = visual.verify_canvas_against_baseline(
        canvas_locator=canvas,
        baseline_dir=baseline_dir,
        pixel_threshold=2.55,
        request=request,
        compare_images=compare_images,
        test_suite=suite_name,
        test_id="dash_start",
        )

    # compile results (we only have one test though) and assert
    result = visual.make_test_result(verify_comparison_1)

    assert result.passed, "Visual comparison failed\t\n" + result.summary()
    print(result.summary())

@pytest.mark.xfail(reason="Under investigation, issue #983, remove when fixed", strict=False)
@pytest.mark.regression
def test_dash_snapshot(page: Page, launch_dash_server, baseline_dir, request, suite_name):
    """
    Regression test for "Get Parts Snapshot" in dash

    """
    # add launch_dash_server fixture to ensure server + instance are running
    target_url = launch_dash_server  # usually http://localhost:8050/index.html"

    page.set_viewport_size({"width": 1280, "height": 800})

    # Navigate and wait for network idle
    page.goto(target_url, wait_until="domcontentloaded")

    # Wait for the canvas and WebGL
    wait_for_canvas(page)
    wait_for_webgl(page)
    settle(page)

    # Wait for the snapshot button to appear and be visible
    snapshot_btn = page.locator("#snapshot-btn")
    snapshot_btn.wait_for(state="visible", timeout=15_000)

    # Click the button to produce the JSON output
    snapshot_btn.click()

    # Wait until the output <pre id="output"> contains non-null, non-empty text
    page.wait_for_function(
        """
        () => {
        const out = document.querySelector('#output');
        if (!out) return false;
        const txt = out.innerText || out.textContent || '';
        return txt.trim().length > 0 && txt.trim() !== 'null';
        }
        """,
        timeout=30_000,
    )

    # Small pause to ensure any final rendering is done
    page.wait_for_timeout(200)

    # Read the output text
    output_locator = page.locator("#output")
    output_text = output_locator.text_content()
    assert output_text is not None, "Output element returned None for text_content()"

    # Output saving to upload as package
    out_dir = Path("tests/artifacts", suite_name , "test_dash_snapshot")
    out_dir.mkdir(parents=True, exist_ok=True)

    # assert it's valid JSON and not "null"
    try:
        output_json = json.loads(output_text)
    except Exception as e:
        # Save raw output for debugging
        actual_path = Path(out_dir) / "dash_snapshot_actual_invalid.json"
        actual_path.write_text(output_text, encoding="utf-8")
        raise AssertionError(f"Output is not valid JSON: {e}. Raw output saved to {actual_path}") from e

    # Save the actual JSON to a file for inspection / CI artifacts
    actual_path = Path(out_dir) / "dash_snapshot_actual.json"
    actual_path.write_text(json.dumps(output_json, indent=2), encoding="utf-8")

    # Compare to a reference file in baseline_dir
    reference_path = Path(baseline_dir) / "dash_snapshot_reference.json"
    update_baseline = request.config.getoption("--update-baseline")

    if update_baseline or not reference_path.exists():
       # If no reference exists, write one and fail so CI or developer can review
        reference_path.write_text(json.dumps(output_json, indent=2), encoding="utf-8")
        pytest.skip("Baseline updated; re-run without --update-baseline to validate.")

    # Load reference and compare
    with reference_path.open("r", encoding="utf-8") as file:
        reference_json = json.load(file)

    diff = DeepDiff(reference_json,
                    output_json,
                    exclude_regex_paths=[
                        r"root\['scene'\]\['datasetStates'\]\['vtk_scene_sphere_l2_b3_r32_v3_c1_z3'\](\[.*\])*\['id'\]"
                    ],
                    ignore_order=True)
    if diff:
        # Save diff for debugging
        diff_path = Path(out_dir) / "dash_snapshot_diff.json"
        diff_path.write_text(json.dumps(diff, indent=2), encoding="utf-8")
        pytest.fail(f"JSON differs:\n{diff}")

    # assert output_json == reference_json, f"Snapshot JSON does not match reference. Actual saved to {actual_path}; reference is {reference_path}."
