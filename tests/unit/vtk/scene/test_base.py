"""Tests for VisorSceneBase.

Two groups:

1.  The abstract contract: direct instantiation raises TypeError, and exactly
    the expected set of abstract methods is declared.
2.  The per-part coordinator surface and the VTK lock.  For each of the six
    coordinator methods the two halves are asserted **separately** -- the
    registry record (the store write) and the VTK object (the pipeline apply)
    -- because either half can silently do nothing while the other succeeds.
    The lock is asserted around every coordinator method and around all ten
    existing public entry points that mutate VTK or push to wasm; a lock added
    only to the trigger side would serialise nothing while looking correct.

Behavioural coverage of the remaining shared logic lives in
test_local_scene.py, exercised through the concrete VisorLocalScene subclass.
"""
import threading
from unittest.mock import MagicMock, patch

import pytest
from vtkmodules.vtkCommonCore import vtkFloatArray
from vtkmodules.vtkCommonDataModel import vtkPolyData
from vtkmodules.vtkFiltersSources import vtkSphereSource

from ansys.visor.viewer.core.visor_colors import VisorColors
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import (
    RuntimeDatasetState,
    RuntimePartProperties,
)
from ansys.visor.viewer.renderer.local_renderer import VisorLocalRenderer
from ansys.visor.viewer.vtk.datasets.visor_dataset_registry import VisorDatasetRegistry
from ansys.visor.viewer.vtk.node_pipeline import VtkNodePipeline
from ansys.visor.viewer.vtk.scene.base import VisorSceneBase

NODE_ID = 7
UNKNOWN_NODE_ID = 999999


def test_cannot_instantiate_directly():
    """VisorSceneBase is abstract and must raise TypeError on direct instantiation."""
    try:
        VisorSceneBase(None)  # type: ignore[abstract]
        raise AssertionError("Expected TypeError was not raised")
    except TypeError:
        pass


def test_abstract_methods():
    """VisorSceneBase declares exactly the two expected abstract hooks."""
    assert VisorSceneBase.__abstractmethods__ == {
        "_get_runtime_state_async",
        "_apply_runtime_state_to_render",
    }


# ===========================================================================
# Test doubles
# ===========================================================================

class _ConcreteScene(VisorSceneBase):
    """Smallest concrete VisorSceneBase: both abstract hooks are inert."""

    async def _get_runtime_state_async(self, timeout: float):
        return MagicMock(name="runtime_app_state")

    def _apply_runtime_state_to_render(self, runtime_app_state) -> None:
        return None


class _LockSpy:
    """Re-entrant lock that records its own acquisition depth.

    Wraps a real RLock so nesting still behaves, and exposes ``depth`` so a
    test can assert the lock was *held* at the moment some inner call ran,
    rather than merely acquired at some point.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self.enter_count = 0
        self.exit_count = 0
        self.depth = 0
        self.max_depth = 0

    def __enter__(self):
        self._lock.acquire()
        self.enter_count += 1
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.depth -= 1
        self.exit_count += 1
        self._lock.release()
        return False


def _make_part_dataset(dataset_id: int, part_ids, part_states=None):
    """Dataset stand-in with a real PartIndex.part_ids and a real state object.

    Real (not MagicMock) state, so a registry write can be read back through
    object identity rather than through a recorded call.
    """
    dataset = MagicMock()
    dataset.part_index = MagicMock()
    dataset.part_index.part_ids = list(part_ids)
    dataset.state = RuntimeDatasetState(id=dataset_id, part_states=part_states or {})
    return dataset


@pytest.fixture
def array_dataset() -> vtkPolyData:
    """Sphere output carrying one named point array and one named cell array."""
    src = vtkSphereSource()
    src.Update()
    dataset = src.GetOutput()

    pressure = vtkFloatArray()
    pressure.SetName("pressure")
    pressure.SetNumberOfComponents(1)
    pressure.SetNumberOfTuples(dataset.GetNumberOfPoints())
    for i in range(dataset.GetNumberOfPoints()):
        pressure.SetTuple1(i, float(i))
    dataset.GetPointData().AddArray(pressure)

    temperature = vtkFloatArray()
    temperature.SetName("temperature")
    temperature.SetNumberOfComponents(1)
    temperature.SetNumberOfTuples(dataset.GetNumberOfCells())
    for i in range(dataset.GetNumberOfCells()):
        temperature.SetTuple1(i, float(i))
    dataset.GetCellData().AddArray(temperature)

    return dataset


@pytest.fixture
def renderer():
    """Real VisorLocalRenderer with every VTK sub-system patched out.

    Real, so the apply bodies under test actually run against real VTK
    objects; the sub-systems are patched so no render window, interactor,
    LocalView or widget is created.
    """
    mock_server = MagicMock()
    mock_server.state = {}

    with (
        patch.object(VisorLocalRenderer, "_initialize_vtk_renderer", return_value=MagicMock()),
        patch.object(VisorLocalRenderer, "_initialize_render_window", return_value=MagicMock()),
        patch.object(
            VisorLocalRenderer, "_initialize_render_window_interactor", return_value=MagicMock()
        ),
        patch.object(VisorLocalRenderer, "_initialize_local_view", return_value=MagicMock()),
        patch.object(VisorLocalRenderer, "_initialize_orientation_widget", return_value=MagicMock()),
        patch.object(
            VisorLocalRenderer, "_initialize_cross_section_widget", return_value=MagicMock()
        ),
        patch.object(
            VisorLocalRenderer, "_initialize_bounding_box_widget", return_value=MagicMock()
        ),
    ):
        return VisorLocalRenderer(mock_server)


@pytest.fixture
def pipeline(renderer, array_dataset):
    """A real VtkNodePipeline registered under NODE_ID."""
    pipe = VtkNodePipeline.from_dataset(array_dataset)
    renderer._pipelines[NODE_ID] = pipe
    return pipe


@pytest.fixture
def registry():
    """Registry holding one dataset that owns NODE_ID, with no part state yet."""
    reg = VisorDatasetRegistry()
    reg.datasets = {1: _make_part_dataset(1, [NODE_ID])}
    return reg


@pytest.fixture
def scene(renderer, registry, pipeline):
    """Concrete scene wired to the real renderer, pipeline and registry."""
    s = _ConcreteScene(MagicMock(name="server"), dark_mode=False, renderer=renderer)
    s._dataset_registry = registry
    s._renderer.flush_wasm_state = MagicMock(name="flush_wasm_state")
    return s


def _spy_flush(scene, read_back):
    """Replace flush_wasm_state with a spy recording lock depth and VTK state.

    ``read_back`` is called at flush time and its value recorded, so a test
    can assert the pipeline apply had *already* happened when the flush ran.
    A flush ordered before the apply would push pre-mutation state, and the
    client's own reapply would hide that in the browser.
    """
    record = {"calls": 0, "depth": None, "value": None}

    def _flush():
        record["calls"] += 1
        record["depth"] = scene._vtk_lock.depth
        record["value"] = read_back()

    scene._renderer.flush_wasm_state = _flush
    return record


# ===========================================================================
# set_part_visibility
# ===========================================================================

def test_set_part_visibility_writes_the_registry_record(scene, registry):
    """Store half: the record carries the requested visibility."""
    scene.set_part_visibility(NODE_ID, False)

    assert registry.get_part_state(NODE_ID).visible is False


def test_set_part_visibility_applies_to_the_vtk_actor(scene, pipeline):
    """Apply half: the actor's visibility is off."""
    scene.set_part_visibility(NODE_ID, False)

    assert pipeline.actor.GetVisibility() == 0


def test_set_part_visibility_flushes_under_the_lock_after_the_apply(scene, pipeline):
    """Lock held, and the actor already mutated, when the flush runs."""
    scene._vtk_lock = _LockSpy()
    record = _spy_flush(scene, lambda: pipeline.actor.GetVisibility())

    scene.set_part_visibility(NODE_ID, False)

    assert record["calls"] == 1
    assert record["depth"] >= 1
    assert record["value"] == 0
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count
    assert scene._vtk_lock.depth == 0


# ===========================================================================
# set_part_opacity
# ===========================================================================

def test_set_part_opacity_writes_the_registry_record(scene, registry):
    """Store half: the record carries the requested opacity."""
    scene.set_part_opacity(NODE_ID, 0.25)

    assert registry.get_part_state(NODE_ID).opacity == 0.25


def test_set_part_opacity_applies_to_the_vtk_property(scene, pipeline):
    """Apply half: the actor property's opacity is the requested value."""
    scene.set_part_opacity(NODE_ID, 0.25)

    assert pipeline.actor.GetProperty().GetOpacity() == pytest.approx(0.25)


def test_set_part_opacity_flushes_under_the_lock_after_the_apply(scene, pipeline):
    """Lock held, and the property already mutated, when the flush runs."""
    scene._vtk_lock = _LockSpy()
    record = _spy_flush(scene, lambda: pipeline.actor.GetProperty().GetOpacity())

    scene.set_part_opacity(NODE_ID, 0.25)

    assert record["calls"] == 1
    assert record["depth"] >= 1
    assert record["value"] == pytest.approx(0.25)
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


# ===========================================================================
# set_part_diffuse_color
# ===========================================================================

def test_set_part_diffuse_color_writes_the_registry_record(scene, registry):
    """Store half: the record carries the requested colour."""
    scene.set_part_diffuse_color(NODE_ID, [1.0, 0.0, 0.0])

    assert registry.get_part_state(NODE_ID).diffuse_rgb == [1.0, 0.0, 0.0]


def test_set_part_diffuse_color_applies_to_the_vtk_property(scene, pipeline):
    """Apply half: the actor property's diffuse colour is the requested one."""
    scene.set_part_diffuse_color(NODE_ID, [1.0, 0.0, 0.0])

    assert pipeline.actor.GetProperty().GetDiffuseColor() == pytest.approx((1.0, 0.0, 0.0))


def test_set_part_diffuse_color_none_clears_the_registry_record(scene, registry):
    """Store half of a clear: absence is stored as absence, not as a colour."""
    registry.set_part_diffuse_color(NODE_ID, [1.0, 0.0, 0.0])

    scene.set_part_diffuse_color(NODE_ID, None)

    assert registry.get_part_state(NODE_ID).diffuse_rgb is None


def test_set_part_diffuse_color_none_applies_the_default_mesh_colour(scene, pipeline):
    """Apply half of a clear: the pipeline falls back to the default colour."""
    scene.set_part_diffuse_color(NODE_ID, [1.0, 0.0, 0.0])

    scene.set_part_diffuse_color(NODE_ID, None)

    assert pipeline.actor.GetProperty().GetDiffuseColor() == pytest.approx(
        tuple(VisorColors.DefaultMeshColor)
    )


def test_set_part_diffuse_color_flushes_under_the_lock_after_the_apply(scene, pipeline):
    """Lock held, and the colour already applied, when the flush runs."""
    scene._vtk_lock = _LockSpy()
    record = _spy_flush(scene, lambda: pipeline.actor.GetProperty().GetDiffuseColor())

    scene.set_part_diffuse_color(NODE_ID, [1.0, 0.0, 0.0])

    assert record["calls"] == 1
    assert record["depth"] >= 1
    assert record["value"] == pytest.approx((1.0, 0.0, 0.0))
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


# ===========================================================================
# set_part_selected
# ===========================================================================

def test_set_part_selected_writes_the_registry_record(scene, registry):
    """Store half: the record carries the requested selection state."""
    scene.set_part_selected(NODE_ID, True)

    assert registry.get_part_state(NODE_ID).selected is True


def test_set_part_selected_applies_the_highlight_to_the_vtk_property(scene, pipeline):
    """Apply half: the selection lighting terms are on the actor property."""
    scene.set_part_selected(NODE_ID, True)

    prop = pipeline.actor.GetProperty()
    assert prop.GetAmbient() == pytest.approx(0.5)
    assert prop.GetDiffuse() == pytest.approx(0.5)
    assert prop.GetAmbientColor() == pytest.approx((0.0, 62 / 255, 111 / 255))


def test_set_part_selected_uses_the_stored_diffuse_colour(scene, registry, pipeline):
    """The colour comes from the server's own record, not from the caller."""
    registry.set_part_diffuse_color(NODE_ID, [0.25, 0.5, 0.75])

    scene.set_part_selected(NODE_ID, True)

    assert pipeline.actor.GetProperty().GetDiffuseColor() == pytest.approx((0.25, 0.5, 0.75))


def test_set_part_selected_falls_back_to_the_default_mesh_colour(scene, pipeline):
    """With no stored colour, the default constant is used."""
    scene.set_part_selected(NODE_ID, True)

    assert pipeline.actor.GetProperty().GetDiffuseColor() == pytest.approx(
        tuple(VisorColors.DefaultMeshColor)
    )


def test_set_part_selected_flushes_under_the_lock_after_the_apply(scene, pipeline):
    """Lock held, and the highlight already applied, when the flush runs."""
    scene._vtk_lock = _LockSpy()
    record = _spy_flush(scene, lambda: pipeline.actor.GetProperty().GetAmbient())

    scene.set_part_selected(NODE_ID, True)

    assert record["calls"] == 1
    assert record["depth"] >= 1
    assert record["value"] == pytest.approx(0.5)
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


# ===========================================================================
# set_part_color_variable
# ===========================================================================

def test_set_part_color_variable_writes_the_registry_record(scene, registry):
    """Store half: variable id and component are recorded together."""
    scene.set_part_color_variable(
        NODE_ID, "POINT::pressure::1", VisorVtkVariableType.POINT, "pressure", 0, 0.0, 49.0
    )

    state = registry.get_part_state(NODE_ID)
    assert state.spectrum_id == "POINT::pressure::1"
    assert state.spectrum_component == 0


def test_set_part_color_variable_applies_to_the_vtk_mapper(scene, pipeline):
    """Apply half: the mapper selects the array and honours the given range."""
    scene.set_part_color_variable(
        NODE_ID, "POINT::pressure::1", VisorVtkVariableType.POINT, "pressure", 0, 0.0, 49.0
    )

    mapper = pipeline.mapper
    assert mapper.GetScalarVisibility() == 1
    assert mapper.GetArrayName() == "pressure"
    assert mapper.GetArrayComponent() == 0
    assert mapper.GetScalarRange() == pytest.approx((0.0, 49.0))


def test_set_part_color_variable_applies_a_cell_association(scene, pipeline):
    """Apply half, cell branch: the cell array is selected."""
    scene.set_part_color_variable(
        NODE_ID, "CELL::temperature::1", VisorVtkVariableType.CELL, "temperature", 0, 0.0, 95.0
    )

    assert pipeline.mapper.GetArrayName() == "temperature"
    assert pipeline.mapper.GetScalarVisibility() == 1


def test_set_part_color_variable_flushes_under_the_lock_after_the_apply(scene, pipeline):
    """Lock held, and the mapper already configured, when the flush runs."""
    scene._vtk_lock = _LockSpy()
    record = _spy_flush(scene, lambda: pipeline.mapper.GetArrayName())

    scene.set_part_color_variable(
        NODE_ID, "POINT::pressure::1", VisorVtkVariableType.POINT, "pressure", 0, 0.0, 49.0
    )

    assert record["calls"] == 1
    assert record["depth"] >= 1
    assert record["value"] == "pressure"
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


# ===========================================================================
# clear_part_color_variable
# ===========================================================================

def test_clear_part_color_variable_clears_the_registry_record(scene, registry):
    """Store half: both fields are cleared together."""
    registry.set_part_color_variable(NODE_ID, "POINT::pressure::1", 0)

    scene.clear_part_color_variable(NODE_ID)

    state = registry.get_part_state(NODE_ID)
    assert state.spectrum_id is None
    assert state.spectrum_component is None


def test_clear_part_color_variable_disables_scalar_visibility_on_the_mapper(scene, pipeline):
    """Apply half: scalar colouring is off on the mapper."""
    scene.set_part_color_variable(
        NODE_ID, "POINT::pressure::1", VisorVtkVariableType.POINT, "pressure", 0, 0.0, 49.0
    )

    scene.clear_part_color_variable(NODE_ID)

    assert pipeline.mapper.GetScalarVisibility() == 0


def test_clear_part_color_variable_flushes_under_the_lock_after_the_apply(scene, pipeline):
    """Lock held, and scalar visibility already off, when the flush runs."""
    scene._vtk_lock = _LockSpy()
    record = _spy_flush(scene, lambda: pipeline.mapper.GetScalarVisibility())

    scene.clear_part_color_variable(NODE_ID)

    assert record["calls"] == 1
    assert record["depth"] >= 1
    assert record["value"] == 0
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


# ===========================================================================
# Unknown node id: logged no-op at every layer
# ===========================================================================

COORDINATOR_CALLS = {
    "set_part_visibility": (UNKNOWN_NODE_ID, False),
    "set_part_opacity": (UNKNOWN_NODE_ID, 0.25),
    "set_part_diffuse_color": (UNKNOWN_NODE_ID, [1.0, 0.0, 0.0]),
    "set_part_selected": (UNKNOWN_NODE_ID, True),
    "set_part_color_variable": (
        UNKNOWN_NODE_ID,
        "POINT::pressure::1",
        VisorVtkVariableType.POINT,
        "pressure",
        0,
        0.0,
        49.0,
    ),
    "clear_part_color_variable": (UNKNOWN_NODE_ID,),
}


@pytest.mark.parametrize("name", list(COORDINATOR_CALLS))
def test_unknown_node_id_is_a_logged_no_op(scene, registry, pipeline, name):
    """No raise, no store write, no VTK mutation and no flush."""
    scene._renderer.flush_wasm_state = MagicMock(name="flush_wasm_state")
    pipeline.actor.SetVisibility(1)
    pipeline.actor.GetProperty().SetOpacity(1.0)

    with patch("ansys.visor.viewer.vtk.scene.base.logger") as mock_logger:
        assert getattr(scene, name)(*COORDINATOR_CALLS[name]) is None

    assert mock_logger.debug.call_count == 1
    assert registry.get_part_state(UNKNOWN_NODE_ID) is None
    assert pipeline.actor.GetVisibility() == 1
    assert pipeline.actor.GetProperty().GetOpacity() == pytest.approx(1.0)
    scene._renderer.flush_wasm_state.assert_not_called()


def test_seeded_part_state_is_mutated_in_place(scene, registry):
    """An existing record is mutated in place, not replaced."""
    seeded = RuntimePartProperties(id=NODE_ID)
    registry.datasets[1].state.part_states[NODE_ID] = seeded

    scene.set_part_opacity(NODE_ID, 0.25)

    assert registry.get_part_state(NODE_ID) is seeded


# ===========================================================================
# The ten existing public entry points hold the lock
# ===========================================================================

@pytest.fixture
def mocked_scene(renderer):
    """Scene whose scene graph, registry and renderer are all MagicMocks.

    Lets the ten existing entry points run to completion without real VTK, so
    the assertion is purely about the lock.
    """
    s = _ConcreteScene(MagicMock(name="server"), dark_mode=False, renderer=renderer)
    s._scene_graph = MagicMock(name="scene_graph")
    s._dataset_registry = MagicMock(name="dataset_registry")
    s._dataset_registry.count = 1
    s._renderer = MagicMock(name="renderer")
    s._state_mapper = MagicMock(name="state_mapper")
    s._vtk_lock = _LockSpy()
    return s


def _depth_probe(mocked_scene, owner, attribute):
    """Record the lock depth observed inside a delegated call."""
    observed = {}

    def _side_effect(*args, **kwargs):
        observed["depth"] = mocked_scene._vtk_lock.depth
        return MagicMock()

    getattr(owner, attribute).side_effect = _side_effect
    return observed


def test_clear_holds_the_lock(mocked_scene):
    """clear() deregisters actors with the lock held."""
    observed = _depth_probe(mocked_scene, mocked_scene._renderer, "deregister_all")

    mocked_scene.clear()

    assert observed["depth"] >= 1
    assert mocked_scene._vtk_lock.enter_count == mocked_scene._vtk_lock.exit_count


def test_add_dataset_holds_the_lock(mocked_scene):
    """add_dataset() registers nodes with the lock held."""
    subtree = mocked_scene._scene_graph.get_descendant_node.return_value
    subtree.get_descendant_part_nodes.return_value = [MagicMock(name="leaf")]
    observed = _depth_probe(mocked_scene, mocked_scene._renderer, "register_node")

    mocked_scene.add_dataset(MagicMock(name="input"), MagicMock(name="metadata"))

    assert observed["depth"] >= 1
    assert mocked_scene._vtk_lock.enter_count == mocked_scene._vtk_lock.exit_count


def test_remove_dataset_holds_the_lock(mocked_scene):
    """remove_dataset() deregisters nodes with the lock held."""
    node = mocked_scene._scene_graph.get_descendant_node.return_value
    node.get_descendant_part_nodes.return_value = [MagicMock(name="leaf")]
    observed = _depth_probe(mocked_scene, mocked_scene._renderer, "deregister_node")

    mocked_scene.remove_dataset(1)

    assert observed["depth"] >= 1
    assert mocked_scene._vtk_lock.enter_count == mocked_scene._vtk_lock.exit_count


def test_update_variables_for_dataset_holds_the_lock(mocked_scene):
    """update_variables_for_dataset() updates arrays with the lock held."""
    observed = _depth_probe(mocked_scene, mocked_scene._dataset_registry, "update_variables")

    mocked_scene.update_variables_for_dataset(1, [])

    assert observed["depth"] >= 1
    assert mocked_scene._vtk_lock.enter_count == mocked_scene._vtk_lock.exit_count


def test_apply_state_holds_the_lock(mocked_scene):
    """apply_state() runs the renderer-specific step with the lock held."""
    observed = {}
    mocked_scene._apply_runtime_state_to_render = lambda state: observed.update(
        depth=mocked_scene._vtk_lock.depth
    )

    mocked_scene.apply_state(MagicMock(name="persisted_state"))

    assert observed["depth"] >= 1
    assert mocked_scene._vtk_lock.enter_count == mocked_scene._vtk_lock.exit_count


def test_render_holds_the_lock(mocked_scene):
    """render() renders and pushes to wasm with the lock held."""
    observed = _depth_probe(mocked_scene, mocked_scene._renderer, "render")

    mocked_scene.render()

    assert observed["depth"] >= 1
    assert mocked_scene._vtk_lock.enter_count == mocked_scene._vtk_lock.exit_count


def test_update_widgets_holds_the_lock(mocked_scene):
    """update_widgets() mutates the widget VTK objects with the lock held."""
    observed = _depth_probe(mocked_scene, mocked_scene._renderer, "update_bounds")

    mocked_scene.update_widgets()

    assert observed["depth"] >= 1
    assert mocked_scene._vtk_lock.enter_count == mocked_scene._vtk_lock.exit_count


def test_populate_scene_holds_the_lock(mocked_scene):
    """populate_scene() reaches the widget update with the lock held."""
    observed = _depth_probe(mocked_scene, mocked_scene._renderer, "update_actor_count")

    mocked_scene.populate_scene()

    assert observed["depth"] >= 1
    assert mocked_scene._vtk_lock.enter_count == mocked_scene._vtk_lock.exit_count


def test_finalize_scene_holds_the_lock(mocked_scene):
    """finalize_scene() reaches the render with the lock held."""
    observed = _depth_probe(mocked_scene, mocked_scene._renderer, "render")

    mocked_scene.finalize_scene()

    assert observed["depth"] >= 1
    assert mocked_scene._vtk_lock.enter_count == mocked_scene._vtk_lock.exit_count


def test_reset_camera_holds_the_lock(mocked_scene):
    """reset_camera() mutates the VTK camera with the lock held."""
    observed = _depth_probe(mocked_scene, mocked_scene._renderer, "reset_camera")

    mocked_scene.reset_camera()

    assert observed["depth"] >= 1
    assert mocked_scene._vtk_lock.enter_count == mocked_scene._vtk_lock.exit_count


def test_nested_entry_points_reacquire_the_lock(mocked_scene):
    """finalize_scene -> populate_scene / render nests; the RLock allows it."""
    mocked_scene.finalize_scene()

    assert mocked_scene._vtk_lock.max_depth >= 2
    assert mocked_scene._vtk_lock.depth == 0
    assert mocked_scene._vtk_lock.enter_count == mocked_scene._vtk_lock.exit_count


def test_the_scene_lock_is_reentrant():
    """The scene's own lock can be acquired twice on one thread."""
    scene = _ConcreteScene(MagicMock(name="server"), renderer=MagicMock(name="renderer"))

    with scene._vtk_lock:
        with scene._vtk_lock:
            assert scene._vtk_lock is not None



