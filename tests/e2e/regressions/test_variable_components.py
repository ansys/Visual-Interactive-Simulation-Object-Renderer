# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.
# E2E tests for variable component selection in the viewer UI, focused on 9-component tensor variables.

import time
from pathlib import Path

import pytest
from PIL import Image
from playwright.sync_api import Page

from ansys.visor.viewer import Metadata
from tests.helpers import visual
from tests.helpers.comparison.image_diff import compare_images, ensure_same_size_and_mode, rms_diff
from tests.helpers.utils.canvas import settle, wait_for_canvas_alive
from tests.helpers.utils.mesh_creator import MeshCreator

# ===========================================================================
# Test Data Setup: Create mesh with scalar (1-comp), vector (3-comp), and
# tensor (9-comp) variables using MeshCreator.
# ===========================================================================

TENSOR_NAME = "Stress"
VECTOR_NAME = "Velocity"
SCALAR_NAME = "Temperature"
SCALE_FACTOR = 10.0

# Build mesh with all three variable types
data_obj = MeshCreator(scale=1.0, xoffset=0.0)
data_obj.add_random_variable(SCALAR_NAME, 1, scale_factor=SCALE_FACTOR)
data_obj.add_random_variable(VECTOR_NAME, 3, scale_factor=SCALE_FACTOR)
data_obj.add_random_variable(TENSOR_NAME, 9, scale_factor=SCALE_FACTOR)

TENSOR_ASSETS = {
    "asset_path": data_obj.polydata,
    "metadata_path": Metadata(name="tensor_test_sphere", unit="m"),
}

# Expected component labels for the 9-component tensor
TENSOR_COMPONENT_LABELS = ["XX", "XY", "XZ", "YX", "YY", "YZ", "ZX", "ZY", "ZZ"]


# ===========================================================================
# Selecting a tensor component colors the part (screenshot diff)
# ===========================================================================

@pytest.mark.parametrize("visor_asset_spec", [TENSOR_ASSETS], indirect=True)
@pytest.mark.regression
class TestTensorComponentColoring:
    """
    Verify that selecting a tensor component updates the rendered
    view, confirmed by screenshot baseline comparison.
    """

    def test_initial_render_baseline(self, page: Page, visor_server, baseline_dir, request):
        """Take a baseline screenshot of the tensor mesh initial render."""
        target_url = visor_server.url
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(target_url, wait_until="networkidle")
        canvas = wait_for_canvas_alive(page, "tensor-initial")
        settle(page, 300)  # preserve prior render-settle timing before baseline capture

        result = visual.verify_canvas_against_baseline(
            canvas_locator=canvas,
            baseline_dir=baseline_dir,
            pixel_threshold=2.55,
            request=request,
            compare_images=compare_images,
            test_id="e2e02_tensor_initial_render",
            test_suite="regression",
        )

        suite_result = visual.make_test_result(result)
        assert suite_result.passed, "Initial render baseline failed\n" + suite_result.summary()

    def test_component_selection_changes_rendering(self, page: Page, visor_server):
        """Selecting different tensor components produces visually distinct canvas renders."""
        target_url = visor_server.url
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(target_url, wait_until="networkidle")
        canvas = wait_for_canvas_alive(page, "tensor-coloring")

        # Select the part to activate the variable selection UI
        part_row = page.locator("div.visor-tree-view td:nth-child(2)").filter(has_text="tensor_test_sphere")
        part_row.wait_for(state="visible", timeout=10_000)
        part_row.click()

        # Select the Stress variable
        variable_select = page.locator("select").filter(has=page.locator("option[data-name='Stress']"))
        variable_select.wait_for(state="visible", timeout=10_000)
        variable_select.select_option(value="POINT::Stress::9")

        # Wait for the component dropdown to become visible
        component_select = page.locator("label").filter(has_text="Component").locator("select")
        component_select.wait_for(state="visible", timeout=10_000)

        # Capture a canvas screenshot per component for the representative subset
        components_to_test = ["XX", "YY", "ZZ", "Magnitude"]
        screenshots_root = Path("tests/artifacts/regression/screenshots")
        screenshots_root.mkdir(parents=True, exist_ok=True)

        stamp = time.strftime("%Y%m%d-%H%M%S")
        shot_paths: list[Path] = []
        for comp in components_to_test:
            component_select.select_option(label=comp)
            settle(page, 500)  # Allow renderer time to update
            shot_path = screenshots_root / f"e2e04_coloring_{comp}_{stamp}.png"
            canvas.screenshot(path=str(shot_path))
            shot_paths.append(shot_path)

        # Assert each consecutive pair of screenshots differs (RMS > threshold),
        # confirming that selecting a different component changes the rendering.
        min_rms = 1.0
        for i in range(len(shot_paths) - 1):
            img_a = Image.open(shot_paths[i])
            img_b = Image.open(shot_paths[i + 1])
            img_a, img_b = ensure_same_size_and_mode(img_a, img_b)
            rms, _ = rms_diff(img_a, img_b)
            assert rms > min_rms, (
                f"Switching from '{components_to_test[i]}' to '{components_to_test[i + 1]}' "
                f"did not change the render (RMS={rms:.3f}, expected > {min_rms}). "
                f"Screenshots: {shot_paths[i]}, {shot_paths[i + 1]}"
            )


# ===========================================================================
# Variable dropdown shows all 9 tensor components
# ===========================================================================

@pytest.mark.parametrize("visor_asset_spec", [TENSOR_ASSETS], indirect=True)
@pytest.mark.regression
class TestTensorVariableDropdown:
    """
    Verify that the variable/spectrum dropdown in the UI contains
    all 9 tensor components plus Magnitude (10 total) when a dataset with
    a 9-component variable is loaded.
    """

    def test_tensor_variable_listed_via_python_api(self, visor_server):
        """The Python API list_variables returns a 9-component variable."""
        visor = visor_server
        datasets = visor.list_datasets()
        dataset_id = list(datasets.keys())[0]

        variables = visor.list_variables(dataset_id)
        # list_variables now returns one VisorPartVariables per part; flatten to get individual variables
        all_vars = [v for part in variables for v in getattr(part, "variables", [])]
        tensor_vars = [v for v in all_vars if getattr(v, "num_components", None) == 9]
        assert len(tensor_vars) >= 1, (
            f"No 9-component variable found. Variables: "
            f"{[(v.name, v.num_components) for v in variables]}"
        )

    def test_canvas_loads_with_tensor_data(self, page: Page, visor_server):
        """The viewer canvas loads and is alive with tensor data."""
        target_url = visor_server.url
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(target_url, wait_until="networkidle")
        canvas = wait_for_canvas_alive(page, "tensor-load")
        assert canvas is not None

    def test_tensor_component_dropdown_options(self, page: Page, visor_server, baseline_dir, request):
        """Component select shows all 9 tensor components + Magnitude when Stress is selected."""
        target_url = visor_server.url
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(target_url, wait_until="networkidle")
        wait_for_canvas_alive(page, "tensor-dropdown")

        # Select the part to activate the variable selection UI
        part_row = page.locator("div.visor-tree-view td:nth-child(2)").filter(has_text="tensor_test_sphere")
        part_row.wait_for(state="visible", timeout=10_000)
        part_row.click()

        # Select the Stress (9-component tensor) variable from the variable dropdown.
        # Value format is "{type}::{name}::{numComponents}" — stable across sessions.
        variable_select = page.locator("select").filter(has=page.locator("option[data-name='Stress']"))
        variable_select.wait_for(state="visible", timeout=10_000)
        variable_select.select_option(value="POINT::Stress::9")

        # Wait for the component dropdown to become visible
        component_select = page.locator("label").filter(has_text="Component").locator("select")
        component_select.wait_for(state="visible", timeout=10_000)

        # Assert all 10 options are present: Magnitude + 9 tensor components
        expected_options = ["Magnitude"] + TENSOR_COMPONENT_LABELS
        option_texts = component_select.evaluate(
            "el => Array.from(el.options).map(o => o.text)"
        )
        assert option_texts == expected_options, (
            f"Component dropdown options mismatch.\n"
            f"  Expected: {expected_options}\n"
            f"  Got:      {option_texts}"
        )

        # Screenshot the closed component select element for visual regression
        result = visual.verify_canvas_against_baseline(
            canvas_locator=component_select,
            baseline_dir=baseline_dir,
            pixel_threshold=11,
            request=request,
            compare_images=compare_images,
            test_id="e2e01_tensor_component_dropdown",
            test_suite="regression",
        )
        suite_result = visual.make_test_result(result)
        assert suite_result.passed, (
            "Component dropdown screenshot baseline failed\n" + suite_result.summary()
        )


# ===========================================================================
# Regression — Selecting scalar/vector components still works
# ===========================================================================

@pytest.mark.parametrize("visor_asset_spec", [TENSOR_ASSETS], indirect=True)
@pytest.mark.regression
class TestScalarVectorRegression:
    """
    Confirm that selecting scalar and vector variables still works
    correctly alongside 9-component tensor variables in the same dataset.
    """

    def test_all_variable_types_listed(self, visor_server):
        """All variable types (scalar, vector, tensor) are listed via Python API."""
        visor = visor_server
        datasets = visor.list_datasets()
        dataset_id = list(datasets.keys())[0]

        variables = visor.list_variables(dataset_id)
        all_vars = [v for part in variables for v in getattr(part, "variables", [])]
        component_counts = {getattr(v, "num_components", None) for v in all_vars}

        # Expect scalar (1), vector (3), and tensor (9)
        assert 1 in component_counts, "Scalar (1-comp) variable not found"
        assert 3 in component_counts, "Vector (3-comp) variable not found"
        assert 9 in component_counts, "Tensor (9-comp) variable not found"

    def test_scalar_variable_properties(self, visor_server):
        """Scalar variable has expected properties."""
        visor = visor_server
        datasets = visor.list_datasets()
        dataset_id = list(datasets.keys())[0]

        variables = visor.list_variables(dataset_id)
        all_vars = [v for part in variables for v in getattr(part, "variables", [])]
        scalar_vars = [v for v in all_vars if getattr(v, "num_components", None) == 1]
        assert len(scalar_vars) >= 1

        scalar_var = scalar_vars[0]
        assert scalar_var.name == SCALAR_NAME
        assert len(scalar_var.ranges) == 1

    def test_vector_variable_properties(self, visor_server):
        """Vector variable has expected properties."""
        visor = visor_server
        datasets = visor.list_datasets()
        dataset_id = list(datasets.keys())[0]

        variables = visor.list_variables(dataset_id)
        all_vars = [v for part in variables for v in getattr(part, "variables", [])]
        vector_vars = [v for v in all_vars if getattr(v, "num_components", None) == 3 and getattr(v, "name", None) == VECTOR_NAME]
        assert len(vector_vars) >= 1

        vector_var = vector_vars[0]
        assert vector_var.name == VECTOR_NAME
        assert len(vector_var.ranges) == 3

    def test_tensor_variable_properties(self, visor_server):
        """Tensor variable has expected properties."""
        visor = visor_server
        datasets = visor.list_datasets()
        dataset_id = list(datasets.keys())[0]

        variables = visor.list_variables(dataset_id)
        all_vars = [v for part in variables for v in getattr(part, "variables", [])]
        tensor_vars = [v for v in all_vars if getattr(v, "num_components", None) == 9]
        assert len(tensor_vars) >= 1

        tensor_var = tensor_vars[0]
        assert tensor_var.name == TENSOR_NAME
        assert len(tensor_var.ranges) == 9

    def test_canvas_alive_with_mixed_variables(self, page: Page, visor_server):
        """Canvas loads correctly with scalar, vector, and tensor variables."""
        target_url = visor_server.url
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(target_url, wait_until="networkidle")
        canvas = wait_for_canvas_alive(page, "mixed-variables")
        assert canvas is not None
