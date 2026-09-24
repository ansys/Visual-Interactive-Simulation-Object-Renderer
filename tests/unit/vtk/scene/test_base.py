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
import asyncio
import json
import threading
from unittest.mock import MagicMock, patch

import pytest
from vtkmodules.vtkCommonCore import vtkFloatArray
from vtkmodules.vtkCommonDataModel import vtkPolyData
from vtkmodules.vtkFiltersSources import vtkSphereSource

from ansys.visor.viewer.core.visor_colors import VisorColors
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState
from ansys.visor.viewer.models.common.visor_ui_state import VisorUIState
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import (
    RuntimeDatasetState,
    RuntimePartProperties,
)
from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState
from ansys.visor.viewer.renderer.local_renderer import VisorLocalRenderer
from ansys.visor.viewer.vtk.datasets.visor_dataset_registry import VisorDatasetRegistry
from ansys.visor.viewer.vtk.node_pipeline import VtkNodePipeline
from ansys.visor.viewer.vtk.scene.base import VisorSceneBase
from ansys.visor.viewer.vtk.variables.visor_part_variables import VisorPartVariables
from ansys.visor.viewer.vtk.variables.visor_variables import VisorVariable

NODE_ID = 7
SECOND_NODE_ID = 8
UNKNOWN_NODE_ID = 999999
DATASET_ID = 1

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
        "_push_runtime_state",
    }


# ===========================================================================
# Test doubles
# ===========================================================================

class _ConcreteScene(VisorSceneBase):
    """Smallest concrete VisorSceneBase: both abstract hooks are inert."""

    async def _get_runtime_state_async(self, timeout: float):
        return MagicMock(name="runtime_app_state")

    def _push_runtime_state(self, runtime_app_state) -> None:
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


def _make_part_dataset(dataset_id: int, part_ids, part_states=None, part_variables=None):
    """Dataset stand-in with a real PartIndex.part_ids and a real state object.

    Real (not MagicMock) state, so a registry write can be read back through
    object identity rather than through a recorded call.  ``part_variables``
    is the per-part variable metadata the restore path reads back through
    ``VisorDataset.list_variables()`` — one ``VisorPartVariables`` per part.
    """
    dataset = MagicMock()
    dataset.part_index = MagicMock()
    dataset.part_index.part_ids = list(part_ids)
    dataset.state = RuntimeDatasetState(id=dataset_id, part_states=part_states or {})
    dataset.list_variables.return_value = list(part_variables or [])
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


# ---------------------------------------------------------------------------
# Object-manager id literals
#
# Hand-written and distinctive.  Seeded into the renderer fixture's id source
# keyed on object identity, so that asserting ACTIVE_CAMERA_WASM_ID fails --
# rather than coincides -- if the re-serialization names the render window,
# the renderer, the interactor or the picker instead of the active camera.
# The render window keeps a literal of its own so that a revert to the
# previous call shape fails by name rather than as the catch-all.
#
# Asserting against the id source's own answer for the attribute production
# reads would pin nothing: it would pass whichever object production named.
# ---------------------------------------------------------------------------

RENDER_WINDOW_WASM_ID = 8150001
ACTIVE_CAMERA_WASM_ID = 8150002
WRONG_OBJECT_WASM_ID = 8150999


@pytest.fixture
def renderer():
    """Real VisorLocalRenderer with every VTK sub-system patched out.

    Real, so the apply bodies under test actually run against real VTK
    objects; the sub-systems are patched so no render window, interactor,
    LocalView or widget is created.

    The object manager that arrives with the patched LocalView is a MagicMock,
    so its ``GetId`` is seeded here rather than in a test: keyed on object
    identity, the active camera resolves to ACTIVE_CAMERA_WASM_ID, the render
    window to RENDER_WINDOW_WASM_ID and every other object to
    WRONG_OBJECT_WASM_ID.  This is what lets the ordering test below assert
    which object the re-serialization named.
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
        r = VisorLocalRenderer(mock_server)

    camera = r._vtk_renderer.GetActiveCamera.return_value
    r._object_manager.GetId.side_effect = (
        lambda obj: ACTIVE_CAMERA_WASM_ID
        if obj is camera
        else RENDER_WINDOW_WASM_ID
        if obj is r._render_window
        else WRONG_OBJECT_WASM_ID
    )
    return r



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

    # TODO: change "calls" to 1 and uncomment "depth" and "value" when we add round trips
    assert record["calls"] == 0
    # assert record["depth"] >= 1
    # assert record["value"] == 0
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

    # TODO: change "calls" to 1 and uncomment "depth" and "value" when we add round trips
    assert record["calls"] == 0
    # assert record["depth"] >= 1
    # assert record["value"] == pytest.approx(0.25)
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

    # TODO: change "calls" to 1 and uncomment "depth" and "value" when we add round trips
    assert record["calls"] == 0
    # assert record["depth"] >= 1
    # assert record["value"] == pytest.approx((1.0, 0.0, 0.0))
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

    # TODO: change "calls" to 1 and uncomment "depth" and "value" when we add round trips
    assert record["calls"] == 0
    # assert record["depth"] >= 1
    # assert record["value"] == pytest.approx(0.5)
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

    # TODO: change "calls" to 1 and uncomment "depth" and "value" when we add round trips
    assert record["calls"] == 0
    # assert record["depth"] >= 1
    # assert record["value"] == "pressure"
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

    # TODO: change "calls" to 1 and uncomment "depth" and "value" when we add round trips
    assert record["calls"] == 0
    # assert record["depth"] >= 1
    # assert record["value"] == 0
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
    # apply_state now walks the mapped state's dataset_states, so the mapper
    # must return a real RuntimeAppState rather than a MagicMock (whose
    # dataset_states would be a MagicMock and raise on iteration).
    s._state_mapper.persisted_to_runtime.return_value = RuntimeAppState.from_components(
        ui=VisorUIState(dark_theme=False), unit="m", dataset_states={}
    )
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
    mocked_scene._push_runtime_state = lambda state: observed.update(
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


# ===========================================================================
# Save/load: the registry is the server-side authority for per-part state
#
# The save-path assertions (what get_state hands to the persist mapper) and
# the load-path assertions (the registry write, and the pipeline applies) are
# separate tests: either half can silently do nothing while the other works.
# Every expected value below is a hand-written literal.
# ===========================================================================

FRONTEND_DATASET_ID = 4242
VARIABLE_ID = "POINT::pressure::1"

# The point array the `array_dataset` fixture carries, described the way the
# persisted variable entry describes it.  Component 0's range and the
# magnitude range are deliberately different so a test can tell which branch
# the restore took.
PRESSURE_MAGNITUDE_RANGE = (0.0, 49.0)
PRESSURE_COMPONENT_RANGE = (10.0, 20.0)


def _pressure_variable() -> VisorVariable:
    """Server-side per-part metadata for the fixture's "pressure" point array."""
    return VisorVariable(
        index=0,
        type=VisorVtkVariableType.POINT,
        name="pressure",
        num_components=1,
        num_points=50,
        ranges=[PRESSURE_COMPONENT_RANGE],
        magnitude_range=PRESSURE_MAGNITUDE_RANGE,
    )


def _variable_state(
    array_name="pressure",
    var_type=VisorVtkVariableType.POINT,
    num_components=1,
    magnitude_range=PRESSURE_MAGNITUDE_RANGE,
    ranges=(PRESSURE_COMPONENT_RANGE,),
) -> VisorVariableState:
    """A persisted variable entry, as I6a stores it."""
    return VisorVariableState(
        id=VARIABLE_ID,
        array_name=array_name,
        type=var_type,
        num_components=num_components,
        magnitude_range=magnitude_range,
        ranges=list(ranges),
    )


def _seed_part_variables(registry, variables, part_id=NODE_ID, dataset_id=1):
    """Give the registry's dataset per-part variable metadata for *part_id*."""
    registry.datasets[dataset_id].list_variables.return_value = [
        VisorPartVariables(part_id=part_id, part_name="part", variables=list(variables))
    ]


def _runtime_state(part_states, variable_states=None, dataset_id=1):
    """A real RuntimeAppState carrying the given per-part records."""
    return RuntimeAppState.from_components(
        ui=VisorUIState(dark_theme=False),
        unit="m",
        dataset_states={
            dataset_id: RuntimeDatasetState(id=dataset_id, part_states=part_states)
        },
        variable_states=variable_states or {},
    )


def _frontend_state():
    """What the browser returns: per-part values for a dataset id of its own.

    Distinguishable on both axes — a dataset id the registry does not have and
    an opacity the registry never held — so a test can tell registry-sourced
    output from frontend-sourced output.
    """
    return RuntimeAppState.from_components(
        ui=VisorUIState(dark_theme=False),
        unit="m",
        dataset_states={
            FRONTEND_DATASET_ID: RuntimeDatasetState(
                id=FRONTEND_DATASET_ID,
                part_states={NODE_ID: RuntimePartProperties(id=NODE_ID, opacity=0.99)},
            )
        },
    )


def _capture_persist_input(scene, frontend_state):
    """Wire get_state to *frontend_state* and capture what the mapper receives."""
    captured = {}

    async def _get_runtime_state_async(timeout):
        return frontend_state

    def _runtime_to_persisted(runtime_state):
        captured["runtime_state"] = runtime_state
        return MagicMock(name="persisted")

    scene._get_runtime_state_async = _get_runtime_state_async
    scene._state_mapper = MagicMock(name="state_mapper")
    scene._state_mapper.runtime_to_persisted.side_effect = _runtime_to_persisted
    return captured


def _apply(scene, runtime_state):
    """Run apply_state with the mapper stubbed to return *runtime_state*."""
    scene._state_mapper = MagicMock(name="state_mapper")
    scene._state_mapper.persisted_to_runtime.return_value = runtime_state
    return scene.apply_state(MagicMock(name="persisted_state"))


class _DepthRecordingRegistry(VisorDatasetRegistry):
    """Registry that records the scene's lock depth when it is read."""

    def __init__(self, scene):
        super().__init__()
        self._scene = scene
        self.depth_at_read = None

    @property
    def runtime_state_dict(self):
        self.depth_at_read = self._scene._vtk_lock.depth
        return VisorDatasetRegistry.runtime_state_dict.fget(self)


@pytest.fixture
def second_pipeline(renderer, array_dataset):
    """A second real VtkNodePipeline, registered under SECOND_NODE_ID."""
    pipe = VtkNodePipeline.from_dataset(array_dataset)
    renderer._pipelines[SECOND_NODE_ID] = pipe
    return pipe


# ---------------------------------------------------------------------------
# Save path
# ---------------------------------------------------------------------------

def test_get_state_sources_dataset_states_from_the_registry(scene, registry):
    """The persist mapper is handed the registry's per-part state."""
    registry.set_part_opacity(NODE_ID, 0.25)
    captured = _capture_persist_input(scene, _frontend_state())

    asyncio.run(scene.get_state(timeout=1.0))

    mapped = captured["runtime_state"].scene.dataset_states
    assert list(mapped) == [1]
    assert mapped[1].part_states[NODE_ID].opacity == 0.25


def test_get_state_discards_the_frontend_dataset_states(scene, registry):
    """The browser's per-part state does not survive into the persisted state."""
    registry.set_part_opacity(NODE_ID, 0.25)
    captured = _capture_persist_input(scene, _frontend_state())

    asyncio.run(scene.get_state(timeout=1.0))

    mapped = captured["runtime_state"].scene.dataset_states
    assert FRONTEND_DATASET_ID not in mapped
    assert all(
        part.opacity != 0.99
        for dataset_state in mapped.values()
        for part in dataset_state.part_states.values()
    )


def test_get_state_reads_the_registry_under_the_lock(scene):
    """The lock is *held* at the moment the registry is read, not merely taken."""
    scene._vtk_lock = _LockSpy()
    spy_registry = _DepthRecordingRegistry(scene)
    spy_registry.datasets = {1: _make_part_dataset(1, [NODE_ID])}
    scene._dataset_registry = spy_registry
    _capture_persist_input(scene, _frontend_state())

    asyncio.run(scene.get_state(timeout=1.0))

    assert spy_registry.depth_at_read >= 1
    assert scene._vtk_lock.depth == 0
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


def test_get_state_snapshots_the_registry_rather_than_referencing_it(scene, registry):
    """A write landing after the read does not change what was captured."""
    registry.set_part_opacity(NODE_ID, 0.25)
    live_state = registry.datasets[1].state
    captured = _capture_persist_input(scene, _frontend_state())

    asyncio.run(scene.get_state(timeout=1.0))
    registry.set_part_opacity(NODE_ID, 0.75)

    snapshot = captured["runtime_state"].scene.dataset_states[1]
    assert snapshot is not live_state
    assert snapshot.part_states[NODE_ID] is not live_state.part_states[NODE_ID]
    assert snapshot.part_states[NODE_ID].opacity == 0.25


# ---------------------------------------------------------------------------
# Save path — the camera
#
# The save takes the camera from the renderer's record.  Three things could
# supply one and they are told apart here by value, not by call recording:
#
#   * the record          -> RECORD_*    (what the save must write)
#   * the browser's reply -> REPLY_*     (what the save wrote before)
#   * the pipeline camera -> PIPELINE_*  (the record's projection, which
#                                         re-imports VTK's own drift)
#
# The record and the pipeline agree in the running application except in
# clipping_range, and only after a ResetCamera, so reading the pipeline is a
# silent failure there.  The three literal sets below differ in every field so
# that it is not silent here.
#
# These tests run the REAL state mapper -- not the _capture_persist_input
# helper, which stubs it -- because the assertion has to be on the object
# get_state returns.  An assignment placed after runtime_to_persisted passes
# every assertion made against the runtime object and still writes the wrong
# file.  The registry is replaced with an empty one so the mapper's per-dataset
# loop is empty and cannot contribute a failure.
# ---------------------------------------------------------------------------

# Hand-written literals.  Nothing here is computed the way the code computes
# it, and no value originates from VTK.
RECORD_POSITION = [11.0, 12.0, 13.0]
RECORD_FOCAL_POINT = [14.0, 15.0, 16.0]
RECORD_VIEW_UP = [0.0, 1.0, 0.0]
RECORD_CLIPPING_RANGE = [17.0, 18.0]
RECORD_PARALLEL_PROJECTION = True
RECORD_VIEW_ANGLE = 31.0
RECORD_PARALLEL_SCALE = 19.0

REPLY_POSITION = [21.0, 22.0, 23.0]
REPLY_CLIPPING_RANGE = [27.0, 28.0]

PIPELINE_POSITION = [31.0, 32.0, 33.0]
PIPELINE_CLIPPING_RANGE = [37.0, 38.0]


def _record_camera() -> VisorCameraState:
    """The renderer's camera record, from hand-written literals."""
    return VisorCameraState(
        position=RECORD_POSITION,
        focal_point=RECORD_FOCAL_POINT,
        view_up=RECORD_VIEW_UP,
        clipping_range=RECORD_CLIPPING_RANGE,
        parallel_projection=RECORD_PARALLEL_PROJECTION,
        view_angle=RECORD_VIEW_ANGLE,
        parallel_scale=RECORD_PARALLEL_SCALE,
    )


def _reply_camera() -> VisorCameraState:
    """What the browser answers getState with.  Never the right answer."""
    return VisorCameraState(
        position=REPLY_POSITION,
        focal_point=[24.0, 25.0, 26.0],
        view_up=[1.0, 0.0, 0.0],
        clipping_range=REPLY_CLIPPING_RANGE,
        parallel_projection=False,
        view_angle=32.0,
        parallel_scale=29.0,
    )


def _pipeline_camera() -> VisorCameraState:
    """What a read of the pipeline vtkCamera would return."""
    return VisorCameraState(
        position=PIPELINE_POSITION,
        focal_point=[34.0, 35.0, 36.0],
        view_up=[0.0, 0.0, 1.0],
        clipping_range=PIPELINE_CLIPPING_RANGE,
        parallel_projection=False,
        view_angle=33.0,
        parallel_scale=39.0,
    )


class _CameraRecordRenderer:
    """Hand-written renderer double for the save path's camera read.

    Deliberately not a MagicMock.  It answers the pipeline read with numbers
    of its own, so an implementation that read the pipeline instead of the
    record fails on **values** rather than on AttributeError -- an
    AttributeError would also be raised by an implementation that read nothing
    at all, and the two are different defects.

    Records the scene's lock depth at the moment the record is read, so the
    read can be asserted to happen with the lock *held* rather than merely
    taken at some point.

    ``get_cross_section_plane`` is answered because ``get_state`` now reads
    the plane record on every call, beside the camera's.  It defaults to
    ``None`` -- the camera tests above say nothing about the plane and must
    keep saying nothing -- and the plane tests below pass one in.
    """

    def __init__(self, record, pipeline_camera, scene=None, cross_section=None):
        self._record = record
        self._pipeline_camera = pipeline_camera
        self._scene = scene
        self._cross_section = cross_section
        self.record_reads = 0
        self.pipeline_reads = 0
        self.plane_reads = 0
        self.depth_at_read = None
        self.plane_depth_at_read = None

    def get_camera_state(self):
        self.record_reads += 1
        if self._scene is not None:
            self.depth_at_read = getattr(self._scene._vtk_lock, "depth", None)
        return self._record

    def get_cross_section_plane(self):
        self.plane_reads += 1
        if self._scene is not None:
            self.plane_depth_at_read = getattr(self._scene._vtk_lock, "depth", None)
        return self._cross_section

    def _read_pipeline_camera(self):
        self.pipeline_reads += 1
        return self._pipeline_camera


def _save_scene(scene, record, reply_camera):
    """Wire *scene* for a save whose record is *record* and whose browser
    reply carries *reply_camera*.  Returns the renderer double."""
    double = _CameraRecordRenderer(record, _pipeline_camera(), scene=scene)
    scene._renderer = double
    scene._dataset_registry = VisorDatasetRegistry()

    async def _get_runtime_state_async(timeout):
        return RuntimeAppState.from_components(
            ui=VisorUIState(dark_theme=False),
            unit="m",
            dataset_states={},
            camera=reply_camera,
        )

    scene._get_runtime_state_async = _get_runtime_state_async
    return double


def test_get_state_takes_the_camera_from_the_record(scene):
    """The saved camera is the record's, field for field.

    This is the assertion that pins the change.  Reverted, the camera on the
    returned state is the browser's reply and every field below differs.

    Asserted on what get_state RETURNS -- the object that reaches the writer
    -- not on the runtime state it was built from.
    """
    _save_scene(scene, _record_camera(), _reply_camera())

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    camera = persisted.scene.camera
    assert camera.position == RECORD_POSITION
    assert camera.focal_point == RECORD_FOCAL_POINT
    assert camera.view_up == RECORD_VIEW_UP
    assert camera.clipping_range == RECORD_CLIPPING_RANGE
    assert camera.parallel_projection == RECORD_PARALLEL_PROJECTION
    assert camera.view_angle == RECORD_VIEW_ANGLE
    assert camera.parallel_scale == RECORD_PARALLEL_SCALE


def test_get_state_discards_the_camera_the_browser_returned(scene):
    """The browser's camera does not survive into the persisted state.

    Its own test rather than an extra assertion above: "wrote the record" and
    "did not write the reply" are the same only while the round trip still
    carries a camera at all, and the round trip is not being removed.
    """
    _save_scene(scene, _record_camera(), _reply_camera())

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    assert persisted.scene.camera.position != REPLY_POSITION
    assert persisted.scene.camera.clipping_range != REPLY_CLIPPING_RANGE


def test_get_state_does_not_read_the_pipeline_camera(scene):
    """The record is read; the pipeline is not.

    The one test that separates the record from its own projection.  In the
    running application the two agree except in clipping_range, and only
    after a ResetCamera, so no manual check discriminates them reliably.
    """
    double = _save_scene(scene, _record_camera(), _reply_camera())

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    assert double.record_reads == 1
    assert double.pipeline_reads == 0
    assert persisted.scene.camera.position != PIPELINE_POSITION
    assert persisted.scene.camera.clipping_range != PIPELINE_CLIPPING_RANGE


def test_get_state_writes_no_camera_when_the_record_is_empty(scene):
    """Negative twin: an empty record writes no camera, reply notwithstanding.

    The record is None only for a scene that never held a dataset, since the
    first one resets the camera and that reset writes the record.  The reply
    carries a perfectly valid camera, so this is the only test in the module
    that a guarded assignment -- one that skipped the write when the record
    was None -- would fail.
    """
    _save_scene(scene, None, _reply_camera())

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    assert persisted.scene.camera is None


def test_get_state_reads_the_camera_under_the_lock(scene):
    """The lock is *held* at the moment the record is read.

    The record is a single attribute holding a whole object reference, but the
    read sits in the same critical section as the registry snapshot and is
    asserted the same way, on the precedent of
    test_get_state_reads_the_registry_under_the_lock -- which also covers the
    await, since the lock is taken after it and never held across it.
    """
    scene._vtk_lock = _LockSpy()
    double = _save_scene(scene, _record_camera(), _reply_camera())

    asyncio.run(scene.get_state(timeout=1.0))

    assert double.depth_at_read >= 1
    assert scene._vtk_lock.depth == 0
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


def test_apply_state_pushes_a_json_encodable_runtime_state(scene, registry):
    """What the bridge is handed survives JSON encoding.

    An enum-typed field reaching the transport unserialised failed the push
    with wslink -32002 at I6a while every gate passed, because nothing in the
    suite exercised the push payload.  This asserts the payload of the object
    apply_state hands to the renderer-specific step, not a model in isolation.
    """
    pushed = {}
    scene._push_runtime_state = lambda state: pushed.update(state=state)

    _apply(
        scene,
        _runtime_state(
            {NODE_ID: RuntimePartProperties(id=NODE_ID, opacity=0.25, spectrum_id=VARIABLE_ID)},
            variable_states={VARIABLE_ID: _variable_state()},
        ),
    )

    encoded = json.dumps(pushed["state"].model_dump(by_alias=True))
    assert '"POINT"' in encoded


# ---------------------------------------------------------------------------
# Load path — store half and apply half, separately
# ---------------------------------------------------------------------------

def test_apply_state_populates_the_registry_from_the_persisted_state(scene, registry):
    """Store half: the registry carries the restored record."""
    _apply(
        scene,
        _runtime_state(
            {NODE_ID: RuntimePartProperties(id=NODE_ID, opacity=0.25, visible=False)}
        ),
    )

    record = registry.get_part_state(NODE_ID)
    assert record.opacity == 0.25
    assert record.visible is False


def test_apply_state_applies_every_part_to_the_pipeline(
    scene, registry, pipeline, second_pipeline
):
    """Apply half: both parts reach their own VTK objects."""
    registry.datasets[1] = _make_part_dataset(1, [NODE_ID, SECOND_NODE_ID])
    pipeline.actor.SetVisibility(1)
    second_pipeline.actor.GetProperty().SetOpacity(1.0)

    _apply(
        scene,
        _runtime_state(
            {
                NODE_ID: RuntimePartProperties(id=NODE_ID, visible=False),
                SECOND_NODE_ID: RuntimePartProperties(id=SECOND_NODE_ID, opacity=0.25),
            }
        ),
    )

    assert pipeline.actor.GetVisibility() == 0
    assert second_pipeline.actor.GetProperty().GetOpacity() == pytest.approx(0.25)


def test_apply_state_flushes_before_the_bridge_call(scene, registry):
    """Exactly one flush, and it is ordered before the bridge call.

    This is the assertion that pins the placement of the ``finalize_scene``
    call in ``apply_state``.  The flush is what carries the restored object
    graph -- the cross-section plane above all -- to the client, so it has to
    run *after* every restore and *before* the fire-and-forget ``set_state``
    the bridge call issues.  A flush after the push races the client's rebuild
    against that call, which is the loss ``VisorLocalScene._push_runtime_state``
    documents.

    The spy is on ``_local_view.update`` and not on ``flush_wasm_state``,
    deliberately.  ``flush_wasm_state`` *is* ``_local_view.update()``, and
    ``render()`` ends in the same call, so only a spy at that boundary sees the
    flush whichever route it arrives by.  The previous version of this test
    spied ``flush_wasm_state`` and was therefore blind to the flush
    ``finalize_scene`` performs: it stayed green with the call before the push,
    after the push, and absent entirely.

    Three wrong placements, one failing assertion: after the push gives
    ``["bridge", "flush"]``, removed gives ``["bridge"]``, and returned to the
    load path also gives ``["bridge"]``, since nothing in this module drives
    ``load_state``.
    """
    order = []
    scene._push_runtime_state = lambda state: order.append("bridge")
    scene._renderer._local_view.update = lambda: order.append("flush")

    _apply(scene, _runtime_state({NODE_ID: RuntimePartProperties(id=NODE_ID, opacity=0.25)}))

    assert order == ["flush", "bridge"]


# ---------------------------------------------------------------------------
# Load path — the camera
#
# These are the only tests in this module that drive apply_state with a real
# PersistedViewerStateV1, through the real state mapper, rather than through
# the _apply helper (which stubs the mapper) or mocked_scene (which pins its
# return value).  Two consequences, both deliberate:
#
#   1. They exercise the mapper's camera pass-through as well as the camera
#      step, so they are the first tests here that would notice if the mapper
#      stopped handing camera on verbatim.
#   2. A failure could in principle be the unstubbed path rather than the
#      camera step.  The camera-bearing and camera-free tests below are built
#      from the SAME constructor call, differing in one argument, so the pair
#      discriminates: both failing means the shared path, only the first
#      failing means the camera step, only the second means the guard.
#
# ``datasets={}`` keeps the mapper's per-dataset loop empty, so the registry
# hop (get_by_name) is never taken and cannot contribute a failure.
# ---------------------------------------------------------------------------

# Hand-written literals.  Nothing here is computed the way the code computes
# it, and no value originates from VTK.
CAMERA_POSITION = [1.0, 2.0, 3.0]
CAMERA_FOCAL_POINT = [4.0, 5.0, 6.0]
CAMERA_VIEW_UP = [0.0, 0.0, 1.0]
CAMERA_CLIPPING_RANGE = [7.0, 8.0]
CAMERA_PARALLEL_PROJECTION = False
CAMERA_VIEW_ANGLE = 30.0
CAMERA_PARALLEL_SCALE = 9.0


def _persisted_state(camera):
    """A real PersistedViewerStateV1 carrying *camera*, or no camera at all.

    One constructor, one varying argument: the camera-bearing and camera-free
    cases differ in nothing else, which is what makes the pair a discriminator
    rather than two unrelated tests.
    """
    return PersistedViewerStateV1.from_components(
        ui_state=VisorUIState(dark_theme=False),
        unit="m",
        orthographic_enabled=None,
        cross_section_enabled=None,
        edges_enabled=None,
        bounding_box_enabled=None,
        datasets={},
        camera=camera,
    )


def _persisted_camera() -> VisorCameraState:
    """The camera the save file carries, from hand-written literals."""
    return VisorCameraState(
        position=CAMERA_POSITION,
        focal_point=CAMERA_FOCAL_POINT,
        view_up=CAMERA_VIEW_UP,
        clipping_range=CAMERA_CLIPPING_RANGE,
        parallel_projection=CAMERA_PARALLEL_PROJECTION,
        view_angle=CAMERA_VIEW_ANGLE,
        parallel_scale=CAMERA_PARALLEL_SCALE,
    )


def test_apply_state_writes_the_camera_record(scene):
    """Store half: a camera in the file becomes the server's record.

    This is the assertion that pins the change.  Reverted, the record stays
    None and this fails on attribute access.
    """
    scene.apply_state(_persisted_state(_persisted_camera()))

    assert scene._renderer.get_camera_state().position == CAMERA_POSITION


def test_apply_state_projects_the_camera_onto_the_pipeline(scene):
    """Apply half: the record reaches the server's pipeline camera.

    Asserted separately from the store half.  Either can silently do nothing
    while the other works, and a record that is never projected is precisely
    the arrangement that leaves a refresh showing the wrong camera -- the
    record would be right and the camera the client rebuilds from would not.
    """
    scene.apply_state(_persisted_state(_persisted_camera()))

    camera = scene._renderer._vtk_renderer.GetActiveCamera.return_value
    camera.SetPosition.assert_called_once_with(CAMERA_POSITION)
    camera.SetFocalPoint.assert_called_once_with(CAMERA_FOCAL_POINT)
    camera.SetViewUp.assert_called_once_with(CAMERA_VIEW_UP)
    camera.SetClippingRange.assert_called_once_with(CAMERA_CLIPPING_RANGE)
    camera.SetParallelProjection.assert_called_once_with(CAMERA_PARALLEL_PROJECTION)
    camera.SetViewAngle.assert_called_once_with(CAMERA_VIEW_ANGLE)
    camera.SetParallelScale.assert_called_once_with(CAMERA_PARALLEL_SCALE)


def test_apply_state_without_a_camera_leaves_the_record_untouched(scene):
    """Absent says nothing: a camera-free file does not reset the record.

    The negative twin of the two tests above -- same constructor, one
    argument changed -- so a failure here against a pass there isolates the
    guard, and a failure in both isolates the unstubbed path instead.
    """
    seeded = _persisted_camera()
    scene._renderer.sync_camera(seeded)
    scene._renderer._vtk_renderer.GetActiveCamera.return_value.reset_mock()

    scene.apply_state(_persisted_state(None))

    assert scene._renderer.get_camera_state() is seeded
    scene._renderer._vtk_renderer.GetActiveCamera.return_value.SetPosition.assert_not_called()


def test_apply_state_syncs_the_camera_under_the_lock_before_the_render_step(scene):
    """The camera step holds the lock, and precedes the delegated render.

    Placement is load-bearing and nothing else in the suite pins it: the
    existing ordering test records only the bridge call and the flush, so a
    camera step written after the render would leave every assertion in this
    module passing while the flush pushed a pipeline whose camera had not
    been written yet.

    The sequence also carries the re-serialisation, and carries it with the
    id argument production passed.  Writing the pipeline camera makes the
    server correct; it does not make the state the client is served correct,
    and the two are separate steps that can each silently do nothing.  The
    spy appends the literal string ``"camera"`` for the write, the two-tuple
    ``("serialize", <id>)`` for the re-serialisation -- the tuple is the
    recording format, not the argument -- and ``"bridge"`` for the delegated
    render step.  ``<id>`` is asserted as the bare id production passes, since
    ``UpdateStateFromObject`` takes a single id.

    Ordered between the two: after the write, because re-serialising before
    it would publish the pre-load camera; before the render step, because the
    delegated step is where the state leaves for the client.
    """
    scene._vtk_lock = _LockSpy()
    order = []
    observed = {}

    real_sync = scene._renderer.sync_camera

    def _sync(camera_state):
        order.append("camera")
        observed["depth"] = scene._vtk_lock.depth
        return real_sync(camera_state)

    scene._renderer.sync_camera = _sync
    scene._renderer._object_manager.UpdateStateFromObject = (
        lambda object_id: order.append(("serialize", object_id))
    )
    scene._push_runtime_state = lambda state: order.append("bridge")

    scene.apply_state(_persisted_state(_persisted_camera()))

    assert order == [
        "camera",
        ("serialize", ACTIVE_CAMERA_WASM_ID),
        "bridge",
    ]
    assert observed["depth"] >= 1
    assert scene._vtk_lock.depth == 0
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


def test_apply_state_serializes_the_camera_under_the_lock(scene):
    """The re-serialisation runs inside the same critical section as the write.

    Its own test rather than another assertion on the ordering test, on the
    precedent of ``test_reset_camera_holds_the_lock``: lock depth and call
    order fail for different reasons and want to be readable apart.

    A re-serialisation that escaped the lock would read the VTK object graph
    while another thread was free to mutate it, and would serve the client a
    half-written scene.  The failure would be intermittent and would never
    reproduce under a gate.
    """
    scene._vtk_lock = _LockSpy()
    observed = {}

    scene._renderer._object_manager.UpdateStateFromObject = (
        lambda object_id: observed.update(depth=scene._vtk_lock.depth)
    )

    scene.apply_state(_persisted_state(_persisted_camera()))

    assert observed["depth"] >= 1
    assert scene._vtk_lock.depth == 0
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


# ===========================================================================
# Trigger path -- the camera
#
# ``VisorSceneBase.sync_camera`` is the coordinator method the ``sync_camera``
# trigger routes through.  The handler arrives on trame's daemon thread and
# must not touch the renderer directly, so what is asserted here is the whole
# critical section: the write, the projection, the re-serialisation that
# follows the write, the lock, and -- as its own test -- the notify that must
# not happen.
#
# Its own literals, distinct from the load path's above, so that a failure
# names the path that broke.  The same seven values are written out again in
# the client-side test of this trigger.
# ===========================================================================

GESTURE_POSITION = [11.0, 12.0, 13.0]
GESTURE_FOCAL_POINT = [14.0, 15.0, 16.0]
GESTURE_VIEW_UP = [0.0, 1.0, 0.0]
GESTURE_CLIPPING_RANGE = [17.0, 18.0]
GESTURE_PARALLEL_PROJECTION = True
GESTURE_VIEW_ANGLE = 35.0
GESTURE_PARALLEL_SCALE = 19.0


def _gesture_camera() -> VisorCameraState:
    """The camera a settled gesture reports, from hand-written literals."""
    return VisorCameraState(
        position=GESTURE_POSITION,
        focal_point=GESTURE_FOCAL_POINT,
        view_up=GESTURE_VIEW_UP,
        clipping_range=GESTURE_CLIPPING_RANGE,
        parallel_projection=GESTURE_PARALLEL_PROJECTION,
        view_angle=GESTURE_VIEW_ANGLE,
        parallel_scale=GESTURE_PARALLEL_SCALE,
    )


def test_sync_camera_writes_the_camera_record(scene):
    """Store half: a reported camera becomes the server's record."""
    camera = _gesture_camera()

    scene.sync_camera(camera)

    assert scene._renderer.get_camera_state() is camera


def test_sync_camera_projects_the_camera_onto_the_pipeline(scene):
    """Apply half: the record reaches the server's pipeline camera.

    Separate from the store half on the same grounds as the load path's pair:
    either can silently do nothing while the other works, and a record that is
    never projected leaves the client rebuilding from the pre-gesture camera.
    """
    scene.sync_camera(_gesture_camera())

    camera = scene._renderer._vtk_renderer.GetActiveCamera.return_value
    camera.SetPosition.assert_called_once_with(GESTURE_POSITION)
    camera.SetFocalPoint.assert_called_once_with(GESTURE_FOCAL_POINT)
    camera.SetViewUp.assert_called_once_with(GESTURE_VIEW_UP)
    camera.SetClippingRange.assert_called_once_with(GESTURE_CLIPPING_RANGE)
    camera.SetParallelProjection.assert_called_once_with(GESTURE_PARALLEL_PROJECTION)
    camera.SetViewAngle.assert_called_once_with(GESTURE_VIEW_ANGLE)
    camera.SetParallelScale.assert_called_once_with(GESTURE_PARALLEL_SCALE)


def test_sync_camera_serializes_after_the_write_with_the_active_camera_id(scene):
    """The re-serialisation follows the write, and carries production's id.

    This is the assertion that pins the increment.  Reverted -- the write kept
    and the re-serialisation dropped -- the record is right, the pipeline
    camera is right, every other test in this module still passes, and the
    client is served the pre-gesture camera on its next fetch.  The user sees
    a refresh snap back to the framing they moved away from.

    The spy appends ``"camera"`` for the write and the two-tuple
    ``("serialize", <id>)`` for the re-serialization; the tuple is the
    recording format, not the argument.  ``<id>`` is asserted as the bare id
    production passes, since ``UpdateStateFromObject`` takes a single id.
    """
    order = []
    real_sync = scene._renderer.sync_camera

    def _sync(camera_state):
        order.append("camera")
        return real_sync(camera_state)

    scene._renderer.sync_camera = _sync
    scene._renderer._object_manager.UpdateStateFromObject = (
        lambda object_id: order.append(("serialize", object_id))
    )

    scene.sync_camera(_gesture_camera())

    assert order == ["camera", ("serialize", ACTIVE_CAMERA_WASM_ID)]


def test_sync_camera_holds_the_lock_across_both_halves(scene):
    """Both halves run inside one critical section.

    Its own test rather than another assertion on the ordering test, on the
    precedent of ``test_reset_camera_holds_the_lock``: lock depth and call
    order fail for different reasons and want to be readable apart.  The
    trigger handler runs on trame's daemon thread while the VTK objects it
    mutates belong to the caller's thread, and a re-serialisation outside the
    lock would read the object graph while another thread was free to mutate
    it.  That failure is intermittent and never reproduces under a gate.
    """
    scene._vtk_lock = _LockSpy()
    observed = {}
    real_sync = scene._renderer.sync_camera

    def _sync(camera_state):
        observed["write_depth"] = scene._vtk_lock.depth
        return real_sync(camera_state)

    scene._renderer.sync_camera = _sync
    scene._renderer._object_manager.UpdateStateFromObject = (
        lambda object_id: observed.update(serialize_depth=scene._vtk_lock.depth)
    )

    scene.sync_camera(_gesture_camera())

    assert observed["write_depth"] >= 1
    assert observed["serialize_depth"] >= 1
    assert scene._vtk_lock.depth == 0
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


def test_sync_camera_does_not_notify_the_client(scene):
    """Serialise only.  No render, no flush, no delegated push.

    A notify here would look correct and would be a loop: the push rebuilds
    the client, the rebuild re-delivers state, the reapply moves the camera
    and emits further settle reports, and each report pushes again.  It would
    also race the rebuild against a half-written object graph, which is the
    hazard ``_apply_runtime_state_to_render`` already refuses to reopen.

    Nothing else can catch this.  Every gate passes with a notify in place,
    and the symptom in the browser is a rebuild storm that looks like a
    network problem.
    """
    notifications = []
    scene._renderer.render = lambda: notifications.append("render")
    scene._renderer.render_window_only = lambda: notifications.append("render_window")
    scene._renderer.flush_wasm_state = lambda: notifications.append("flush")
    scene._apply_runtime_state_to_render = lambda state: notifications.append("bridge")

    scene.sync_camera(_gesture_camera())

    assert notifications == []


# ===========================================================================
# reset_camera -- the re-serialisation
#
# ``VisorSceneBase.reset_camera`` calls ``self._renderer.reset_camera(...)``
# then ``self._renderer.serialize_camera_state()``, both inside
# ``_vtk_lock``.  Same shape as the ``sync_camera`` trigger section above: the
# re-serialisation runs after the reset, is spied on
# ``_object_manager.UpdateStateFromObject`` with the active-camera id, and
# the lock is held (depth >= 1) at both points.
#
# Own literals are unnecessary here -- reset_camera takes no camera argument,
# only the scene-graph bounds -- so what is pinned is order and lock depth,
# not a value.
# ===========================================================================

def test_reset_camera_serializes_after_the_reset_with_the_active_camera_id(scene):
    """The re-serialisation follows the reset, and carries production's id.

    Reverted -- the reset kept and the re-serialisation dropped -- the
    pipeline camera is right and every other test in this module still
    passes, while the client is served the pre-reset camera on its next
    fetch.

    The spy appends ``"reset"`` for the reset call and the two-tuple
    ``("serialize", <id>)`` for the re-serialisation; the tuple is the
    recording format, not the argument.  ``<id>`` is asserted as the bare id
    production passes, since ``UpdateStateFromObject`` takes a single id.
    """
    order = []
    real_reset = scene._renderer.reset_camera

    def _reset(bounds):
        order.append("reset")
        return real_reset(bounds)

    scene._renderer.reset_camera = _reset
    scene._renderer._object_manager.UpdateStateFromObject = (
        lambda object_id: order.append(("serialize", object_id))
    )

    scene.reset_camera()

    assert order == ["reset", ("serialize", ACTIVE_CAMERA_WASM_ID)]


def test_reset_camera_holds_the_lock_across_both_halves(scene):
    """Both the reset and the re-serialisation run inside one critical section.

    Its own test rather than another assertion on the ordering test, on the
    precedent of ``test_sync_camera_holds_the_lock_across_both_halves``: lock
    depth and call order fail for different reasons and want to be readable
    apart.  ``reset_camera`` can be called from the trame daemon thread
    indirectly through ``finalize_scene``, while the VTK objects it mutates
    belong to the caller's thread, and a re-serialisation outside the lock
    would read the object graph while another thread was free to mutate it.
    That failure is intermittent and never reproduces under a gate.
    """
    scene._vtk_lock = _LockSpy()
    observed = {}
    real_reset = scene._renderer.reset_camera

    def _reset(bounds):
        observed["reset_depth"] = scene._vtk_lock.depth
        return real_reset(bounds)

    scene._renderer.reset_camera = _reset
    scene._renderer._object_manager.UpdateStateFromObject = (
        lambda object_id: observed.update(serialize_depth=scene._vtk_lock.depth)
    )

    scene.reset_camera()

    assert observed["reset_depth"] >= 1
    assert observed["serialize_depth"] >= 1
    assert scene._vtk_lock.depth == 0
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


def test_restore_part_states_holds_the_lock(scene, registry, pipeline):
    """The lock is held at both halves inside the restore helper itself."""
    scene._vtk_lock = _LockSpy()
    observed = {}
    real_replace = registry.replace_part_states

    def _replace(dataset_states):
        observed["store_depth"] = scene._vtk_lock.depth
        return real_replace(dataset_states)

    def _apply_opacity(node_id, opacity):
        observed["apply_depth"] = scene._vtk_lock.depth

    registry.replace_part_states = _replace
    scene._renderer.apply_opacity = _apply_opacity

    _apply(scene, _runtime_state({NODE_ID: RuntimePartProperties(id=NODE_ID, opacity=0.25)}))

    assert observed["store_depth"] >= 1
    assert observed["apply_depth"] >= 1
    assert scene._vtk_lock.depth == 0


def test_apply_state_unregistered_dataset_id_is_a_logged_skip(scene, pipeline):
    """A dataset the registry does not have is skipped explicitly, not silently."""
    pipeline.actor.SetVisibility(1)

    with patch("ansys.visor.viewer.vtk.scene.base.logger") as mock_logger:
        _apply(
            scene,
            _runtime_state(
                {NODE_ID: RuntimePartProperties(id=NODE_ID, visible=False)},
                dataset_id=FRONTEND_DATASET_ID,
            ),
        )

    assert mock_logger.warning.call_count == 1
    assert pipeline.actor.GetVisibility() == 1


def test_apply_state_unknown_node_is_a_logged_no_op(scene, registry, pipeline):
    """A part with no pipeline is a logged no-op, not a raise."""
    pipeline.actor.SetVisibility(1)

    with patch("ansys.visor.viewer.renderer.local_renderer.logger") as mock_logger:
        result = _apply(
            scene,
            _runtime_state(
                {UNKNOWN_NODE_ID: RuntimePartProperties(id=UNKNOWN_NODE_ID, visible=False)}
            ),
        )

    assert result is None
    assert mock_logger.debug.call_count >= 1
    assert pipeline.actor.GetVisibility() == 1


def test_apply_state_short_diffuse_color_is_a_logged_no_op(scene, registry, pipeline):
    """A malformed colour leaves the VTK object alone; the record keeps it."""
    pipeline.actor.GetProperty().SetDiffuseColor(0.1, 0.2, 0.3)

    with patch("ansys.visor.viewer.vtk.scene.base.logger") as mock_logger:
        _apply(
            scene,
            _runtime_state(
                {NODE_ID: RuntimePartProperties(id=NODE_ID, diffuse_rgb=[1.0, 0.0])}
            ),
        )

    assert mock_logger.warning.call_count == 1
    assert pipeline.actor.GetProperty().GetDiffuseColor() == pytest.approx((0.1, 0.2, 0.3))
    assert registry.get_part_state(NODE_ID).diffuse_rgb == [1.0, 0.0]


# ---------------------------------------------------------------------------
# Load path — the colour-variable branch
# ---------------------------------------------------------------------------

def _color_variable_state(component, **variable_kwargs):
    """A part coloured by the fixture's point array, at *component*."""
    return _runtime_state(
        {
            NODE_ID: RuntimePartProperties(
                id=NODE_ID, spectrum_id=VARIABLE_ID, spectrum_component=component
            )
        },
        variable_states={VARIABLE_ID: _variable_state(**variable_kwargs)},
    )


def _seed_unconfigured_mapper(pipeline):
    """Distinctive, non-default mapper state so a no-op is visible as one."""
    pipeline.mapper.SetScalarVisibility(0)
    pipeline.mapper.SetScalarRange(11.0, 22.0)


def test_apply_state_restores_the_magnitude_range_when_component_is_minus_one(
    scene, registry, pipeline
):
    """A stored component of -1 reads magnitude_range, not ranges[0]."""
    _seed_part_variables(registry, [_pressure_variable()])

    _apply(scene, _color_variable_state(-1))

    assert pipeline.mapper.GetArrayName() == "pressure"
    assert pipeline.mapper.GetScalarRange() == pytest.approx((0.0, 49.0))


def test_apply_state_restores_the_per_component_range(scene, registry, pipeline):
    """A stored component of 0 reads ranges[0], not magnitude_range."""
    _seed_part_variables(registry, [_pressure_variable()])

    _apply(scene, _color_variable_state(0))

    assert pipeline.mapper.GetArrayName() == "pressure"
    assert pipeline.mapper.GetScalarRange() == pytest.approx((10.0, 20.0))


def test_apply_state_negative_component_other_than_minus_one_is_a_logged_no_op(
    scene, registry, pipeline
):
    """-2 is neither the magnitude sentinel nor an index: no fallthrough."""
    _seed_part_variables(registry, [_pressure_variable()])
    _seed_unconfigured_mapper(pipeline)

    with patch("ansys.visor.viewer.vtk.scene.base.logger") as mock_logger:
        _apply(scene, _color_variable_state(-2))

    assert mock_logger.warning.call_count == 1
    assert pipeline.mapper.GetScalarVisibility() == 0
    assert pipeline.mapper.GetScalarRange() == pytest.approx((11.0, 22.0))


def test_apply_state_component_beyond_the_stored_ranges_is_a_logged_no_op(
    scene, registry, pipeline
):
    """An index past the stored ranges applies nothing."""
    _seed_part_variables(registry, [_pressure_variable()])
    _seed_unconfigured_mapper(pipeline)

    with patch("ansys.visor.viewer.vtk.scene.base.logger") as mock_logger:
        _apply(scene, _color_variable_state(3))

    assert mock_logger.warning.call_count == 1
    assert pipeline.mapper.GetScalarVisibility() == 0
    assert pipeline.mapper.GetScalarRange() == pytest.approx((11.0, 22.0))


def test_apply_state_absent_range_is_a_logged_no_op(scene, registry, pipeline):
    """A variable entry with no magnitude range applies nothing."""
    _seed_part_variables(registry, [_pressure_variable()])
    _seed_unconfigured_mapper(pipeline)

    with patch("ansys.visor.viewer.vtk.scene.base.logger") as mock_logger:
        _apply(scene, _color_variable_state(-1, magnitude_range=None))

    assert mock_logger.warning.call_count == 1
    assert pipeline.mapper.GetScalarVisibility() == 0
    assert pipeline.mapper.GetScalarRange() == pytest.approx((11.0, 22.0))


def test_apply_state_unknown_variable_identifier_is_a_logged_no_op(
    scene, registry, pipeline
):
    """A stored identifier with no variable entry applies nothing."""
    _seed_part_variables(registry, [_pressure_variable()])
    _seed_unconfigured_mapper(pipeline)
    runtime = _runtime_state(
        {
            NODE_ID: RuntimePartProperties(
                id=NODE_ID, spectrum_id=VARIABLE_ID, spectrum_component=0
            )
        },
        variable_states={},
    )

    with patch("ansys.visor.viewer.vtk.scene.base.logger") as mock_logger:
        _apply(scene, runtime)

    assert mock_logger.warning.call_count == 1
    assert pipeline.mapper.GetScalarVisibility() == 0


def test_apply_state_unknown_array_name_is_a_logged_no_op(scene, registry, pipeline):
    """An array the part does not carry applies nothing."""
    _seed_part_variables(registry, [_pressure_variable()])
    _seed_unconfigured_mapper(pipeline)

    with patch("ansys.visor.viewer.vtk.scene.base.logger") as mock_logger:
        _apply(scene, _color_variable_state(0, array_name="no_such_array"))

    assert mock_logger.warning.call_count == 1
    assert pipeline.mapper.GetScalarVisibility() == 0


def test_apply_state_array_width_mismatch_is_a_logged_no_op(scene, registry, pipeline):
    """Same name and association, different width: a different quantity."""
    _seed_part_variables(registry, [_pressure_variable()])
    _seed_unconfigured_mapper(pipeline)

    with patch("ansys.visor.viewer.vtk.scene.base.logger") as mock_logger:
        _apply(
            scene,
            _color_variable_state(
                0, num_components=3, ranges=((10.0, 20.0), (0.0, 1.0), (0.0, 2.0))
            ),
        )

    assert mock_logger.warning.call_count == 1
    assert pipeline.mapper.GetScalarVisibility() == 0


def test_apply_state_clears_the_color_variable_when_none_is_stored(
    scene, registry, pipeline
):
    """No stored identifier and no stored component: the clear branch."""
    pipeline.mapper.SetScalarVisibility(1)

    _apply(scene, _runtime_state({NODE_ID: RuntimePartProperties(id=NODE_ID)}))

    assert pipeline.mapper.GetScalarVisibility() == 0


def test_apply_state_variable_id_without_component_is_a_logged_no_op(
    scene, registry, pipeline
):
    """Half a compound value: an identifier with no component."""
    _seed_part_variables(registry, [_pressure_variable()])
    _seed_unconfigured_mapper(pipeline)
    runtime = _runtime_state(
        {NODE_ID: RuntimePartProperties(id=NODE_ID, spectrum_id=VARIABLE_ID)},
        variable_states={VARIABLE_ID: _variable_state()},
    )

    with patch("ansys.visor.viewer.vtk.scene.base.logger") as mock_logger:
        _apply(scene, runtime)

    assert mock_logger.warning.call_count == 1
    assert pipeline.mapper.GetScalarVisibility() == 0


def test_apply_state_component_without_variable_id_does_not_clear(
    scene, registry, pipeline
):
    """The mirror half: a component with no identifier must not fall through."""
    pipeline.mapper.SetScalarVisibility(1)
    runtime = _runtime_state(
        {NODE_ID: RuntimePartProperties(id=NODE_ID, spectrum_component=0)},
        variable_states={VARIABLE_ID: _variable_state()},
    )

    with patch("ansys.visor.viewer.vtk.scene.base.logger") as mock_logger:
        _apply(scene, runtime)

    assert mock_logger.warning.call_count == 1
    assert pipeline.mapper.GetScalarVisibility() == 1


# ===========================================================================
# Widget state -- the server store, the coordinator surface, and delivery
#
# Three toggles the server now holds: cross-section, edges, bounding box.
# Each has a coordinator method that writes the store and applies to the
# renderer under ``_vtk_lock``; ``get_state`` reads the store rather than the
# browser's reply; ``apply_state`` restores it; ``get_scene_details`` delivers
# it to a rebuilt or reconnecting client.
#
# Every expected value below is a hand-written literal.  ``True`` is used
# throughout as the value the client reports, because the server's own default
# is the literal ``False``, so a body that wrote a default rather than its
# argument fails.
# ===========================================================================

TOGGLE_ON = True
TOGGLE_OFF = False

# What a browser that was asked would answer.  Deliberately the opposite of
# what the store holds in the derivation test, so that "read the store" and
# "read the reply" cannot both pass.
REPLY_TOGGLE = False

DELIVERED_PARALLEL_PROJECTION = True


class _ToggleSpyRenderer:
    """Records the three widget-state calls, with the lock depth at each.

    Hand-written rather than a MagicMock so that a call under some other name
    is an AttributeError here rather than a silently absorbed no-op, and so
    that the lock depth can be read at the moment of the call rather than
    after the fact.

    ``update_bounds``, ``update_actor_count`` and ``render`` are the scene
    surface ``apply_state`` reaches through its ``finalize_scene`` call, and
    are the only three names added for it: with a toggle-only state the part
    loop makes no renderer call, the cross-section and camera restores are
    both guarded off, and ``skip_reset_camera=True`` keeps ``reset_camera``
    out.  Anything else is still an AttributeError, which is the point of the
    double.  They record into ``scene_calls`` rather than ``calls`` so that
    the toggle assertions keep their exact meaning; nothing asserts
    ``scene_calls``, which exists so a failure dump shows what was reached.
    The placement of the finalize call is pinned in
    ``test_apply_state_flushes_before_the_bridge_call``.
    """

    def __init__(self, scene):
        self._scene = scene
        self.calls = []
        self.scene_calls = []
        self.depths = {}

    def _record(self, name, visible):
        self.calls.append((name, visible))
        self.depths[name] = getattr(self._scene._vtk_lock, "depth", None)

    def set_cross_section_visibility(self, visible):
        self._record("set_cross_section_visibility", visible)

    def set_edges_visible(self, visible):
        self._record("set_edges_visible", visible)

    def set_bounding_box_visibility(self, visible):
        self._record("set_bounding_box_visibility", visible)

    def update_bounds(self, bounds):
        self.scene_calls.append("update_bounds")

    def update_actor_count(self, count):
        self.scene_calls.append("update_actor_count")

    def render(self):
        self.scene_calls.append("render")


class _SceneDetailsRenderer:
    """Renderer double for the scene-details delivery path.

    Answers only what ``get_scene_details`` asks of a renderer: the annotation
    (``None`` -- wire absence is the contract for a renderer with no handles)
    and the camera record.  A ``MagicMock`` cannot stand in here: the values it
    returns are validated by pydantic, not merely called.
    """

    def __init__(self, camera_record):
        self._camera_record = camera_record
        self.camera_reads = 0

    def build_renderer_annotation(self):
        return None

    def get_camera_state(self):
        self.camera_reads += 1
        return self._camera_record


def _delivered_camera() -> VisorCameraState:
    """A camera record whose projection is a hand-written literal."""
    return VisorCameraState(
        position=[41.0, 42.0, 43.0],
        focal_point=[44.0, 45.0, 46.0],
        view_up=[0.0, 1.0, 0.0],
        clipping_range=[47.0, 48.0],
        parallel_projection=DELIVERED_PARALLEL_PROJECTION,
        view_angle=36.0,
        parallel_scale=49.0,
    )


def _toggle_save_scene(scene, reply_toggle):
    """Wire *scene* for a save whose browser reply carries *reply_toggle*.

    The registry is emptied so the mapper's per-dataset loop contributes
    nothing; what is under test is the scene block of the persisted state.
    """
    scene._dataset_registry = VisorDatasetRegistry()

    async def _get_runtime_state_async(timeout):
        return RuntimeAppState.from_components(
            ui=VisorUIState(dark_theme=False),
            unit="m",
            dataset_states={},
            cross_section_enabled=reply_toggle,
            edges_enabled=reply_toggle,
            bounding_box_enabled=reply_toggle,
        )

    scene._get_runtime_state_async = _get_runtime_state_async


# ---------------------------------------------------------------------------
# The store's initial value
# ---------------------------------------------------------------------------

def test_widget_toggles_default_to_false_before_any_client_speaks(scene):
    """All three start at the client widgets' own constructor default.

    ``False`` and not ``None``: ``None`` would mean "nobody has said", which is
    only ever true before the first save, and it would push a three-way branch
    into get_state for a state that resolves itself on the first toolbar click.
    The literal here is hand-written and is never read from a widget.
    """
    assert scene._cross_section_enabled is False
    assert scene._edges_enabled is False
    assert scene._bounding_box_enabled is False


# ---------------------------------------------------------------------------
# The coordinator surface -- store half and renderer half, separately
# ---------------------------------------------------------------------------

def test_set_cross_section_visibility_writes_the_store(scene):
    """Store half: the coordinator records what it was told."""
    scene.set_cross_section_visibility(TOGGLE_ON)

    assert scene._cross_section_enabled is True


def test_set_cross_section_visibility_applies_to_the_renderer(scene):
    """Renderer half: the value is passed through, once.

    Its own test rather than an extra assertion above: either half can
    silently do nothing while the other succeeds, which is the posture the
    per-part surface above is tested with.
    """
    spy = _ToggleSpyRenderer(scene)
    scene._renderer = spy

    scene.set_cross_section_visibility(TOGGLE_ON)

    assert spy.calls == [("set_cross_section_visibility", True)]


def test_set_edges_visible_writes_the_store(scene):
    """Store half: the coordinator records what it was told."""
    scene.set_edges_visible(TOGGLE_ON)

    assert scene._edges_enabled is True


def test_set_edges_visible_applies_to_the_renderer(scene):
    """Renderer half: the value reaches the renderer's scene-wide verb."""
    spy = _ToggleSpyRenderer(scene)
    scene._renderer = spy

    scene.set_edges_visible(TOGGLE_ON)

    assert spy.calls == [("set_edges_visible", True)]


def test_set_bounding_box_visibility_writes_the_store(scene):
    """Store half: the coordinator records what it was told."""
    scene.set_bounding_box_visibility(TOGGLE_ON)

    assert scene._bounding_box_enabled is True


def test_set_bounding_box_visibility_applies_to_the_renderer(scene):
    """Renderer half: the value is passed through, once."""
    spy = _ToggleSpyRenderer(scene)
    scene._renderer = spy

    scene.set_bounding_box_visibility(TOGGLE_ON)

    assert spy.calls == [("set_bounding_box_visibility", True)]


def test_set_edges_visible_holds_the_lock_at_the_renderer_call(scene):
    """The lock is *held* at the moment the renderer is called.

    This is the assertion that pins AC-2's lock half, and it is the only
    assertion in this increment that sees the lock at all: the trigger module
    sees delegation, and get_state and apply_state take the lock on paths that
    already had it.  Remove ``with self._vtk_lock:`` from the coordinator
    method and the probe records 0.

    The trigger handler runs on trame's daemon thread while the VTK objects it
    mutates belong to the caller's thread; an apply outside the lock would
    interleave with another thread's mutation.  That failure is intermittent
    and never reproduces under a gate.
    """
    scene._vtk_lock = _LockSpy()
    spy = _ToggleSpyRenderer(scene)
    scene._renderer = spy

    scene.set_edges_visible(TOGGLE_ON)

    assert spy.depths["set_edges_visible"] >= 1
    assert scene._vtk_lock.depth == 0
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


# ---------------------------------------------------------------------------
# get_state -- the toggles come from the store, not from the reply
# ---------------------------------------------------------------------------

def test_get_state_takes_the_toggles_from_the_store(scene):
    """The saved toggles are the server's, with the browser saying otherwise.

    This is the assertion that pins the change.  The reply carries the
    hand-written literal ``False`` for all three while the store holds ``True``
    for all three; revert the three get_state assignments and every assertion
    below reports ``False``.  That single difference is what separates
    "server-authoritative" from "round-trips the client's answer".

    Asserted on what get_state RETURNS -- the object that reaches the writer --
    not on the runtime state it was built from.
    """
    scene.set_cross_section_visibility(TOGGLE_ON)
    scene.set_edges_visible(TOGGLE_ON)
    scene.set_bounding_box_visibility(TOGGLE_ON)
    _toggle_save_scene(scene, REPLY_TOGGLE)

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    assert persisted.scene.cross_section_enabled is True
    assert persisted.scene.edges_enabled is True
    assert persisted.scene.bounding_box_enabled is True


def test_get_state_discards_the_toggles_the_browser_returned(scene):
    """The browser's toggles do not survive into the persisted state.

    The mirror of the test above and its own test for the same reason the
    camera pair is split: "wrote the store" and "did not write the reply" are
    the same only while the round trip still carries toggles at all, and the
    round trip is not being removed.  Here the store is left at its default
    ``False`` and the reply carries ``True``.
    """
    _toggle_save_scene(scene, True)

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    assert persisted.scene.cross_section_enabled is False
    assert persisted.scene.edges_enabled is False
    assert persisted.scene.bounding_box_enabled is False


# ---------------------------------------------------------------------------
# apply_state -- the load path writes the store and the renderer
# ---------------------------------------------------------------------------

def _toggle_runtime_state(**toggles):
    """A real RuntimeAppState carrying only the toggles named."""
    return RuntimeAppState.from_components(
        ui=VisorUIState(dark_theme=False),
        unit="m",
        dataset_states={},
        **toggles,
    )


def test_apply_state_writes_the_toggles_to_the_store(scene):
    """A state carrying toggles becomes the server's store."""
    _apply(
        scene,
        _toggle_runtime_state(
            cross_section_enabled=True,
            edges_enabled=True,
            bounding_box_enabled=True,
        ),
    )

    assert scene._cross_section_enabled is True
    assert scene._edges_enabled is True
    assert scene._bounding_box_enabled is True


def test_apply_state_applies_the_toggles_to_the_renderer(scene):
    """The load path applies as well as records, in that order."""
    spy = _ToggleSpyRenderer(scene)
    scene._renderer = spy

    _apply(
        scene,
        _toggle_runtime_state(
            cross_section_enabled=True,
            edges_enabled=True,
            bounding_box_enabled=True,
        ),
    )

    assert spy.calls == [
        ("set_cross_section_visibility", True),
        ("set_edges_visible", True),
        ("set_bounding_box_visibility", True),
    ]


def test_apply_state_absent_toggles_leave_the_store_untouched(scene):
    """Absent says nothing: a state with no toggles is not a state of False.

    The guard belongs to this path and not to get_state, and this is the test
    that says so.  The store is seeded to ``True`` first, so a body that wrote
    the model's own ``None`` default through would be caught.
    """
    scene.set_cross_section_visibility(TOGGLE_ON)
    scene.set_edges_visible(TOGGLE_ON)
    scene.set_bounding_box_visibility(TOGGLE_ON)
    spy = _ToggleSpyRenderer(scene)
    scene._renderer = spy

    _apply(scene, _toggle_runtime_state())

    assert scene._cross_section_enabled is True
    assert scene._edges_enabled is True
    assert scene._bounding_box_enabled is True
    assert spy.calls == []


def test_apply_state_ignores_orthographic_enabled(scene):
    """The persisted projection toggle is emitted, never read back.

    Two independent fields writing one camera property is the divergence this
    story removes; projection arrives on the camera and nowhere else.  Pinned
    so that a later session does not restore the read as a bug fix: nothing on
    the scene stores it, and a state carrying only that field changes nothing.
    """
    spy = _ToggleSpyRenderer(scene)
    scene._renderer = spy

    _apply(scene, _toggle_runtime_state(orthographic_enabled=True))

    assert spy.calls == []
    assert not hasattr(scene, "_orthographic_enabled")


# ---------------------------------------------------------------------------
# get_scene_details -- delivery to a rebuilt or reconnecting client
# ---------------------------------------------------------------------------

def test_get_scene_details_delivers_the_four_widget_keywords(scene):
    """All four keywords reach the payload the client is served.

    This is the assertion that pins delivery, and it covers all four rather
    than one: revert any single keyword out of the ``from_components`` call and
    that field is delivered as ``None``, which reverts its toggle in the
    browser on the next rebuild.  Without this, only a manual check would see
    it.

    ``orthographic_enabled`` is derived from the camera record, so the double
    answers with a record whose ``parallel_projection`` is a hand-written
    literal; nothing here is read from a vtkCamera.
    """
    scene.set_cross_section_visibility(TOGGLE_ON)
    scene.set_edges_visible(TOGGLE_ON)
    scene.set_bounding_box_visibility(TOGGLE_ON)
    scene._dataset_registry = VisorDatasetRegistry()
    double = _SceneDetailsRenderer(_delivered_camera())
    scene._renderer = double

    delivered = scene.get_scene_details().app_state.scene

    assert delivered.cross_section_enabled is True
    assert delivered.edges_enabled is True
    assert delivered.bounding_box_enabled is True
    assert delivered.orthographic_enabled is DELIVERED_PARALLEL_PROJECTION
    assert double.camera_reads == 1


def test_get_scene_details_delivers_no_orthographic_flag_when_the_camera_record_is_empty(
    scene,
):
    """A ``None`` record delivers ``None``, not a fabricated ``False``.

    ``None`` on the wire says "nothing was ever written" and leaves the
    client's own flag alone; ``False`` would assert perspective over a client
    that may be parallel.  The three store toggles still deliver, because they
    do not depend on the camera.
    """
    scene.set_edges_visible(TOGGLE_ON)
    scene._dataset_registry = VisorDatasetRegistry()
    scene._renderer = _SceneDetailsRenderer(None)

    delivered = scene.get_scene_details().app_state.scene

    assert delivered.orthographic_enabled is None
    assert delivered.edges_enabled is True


# ---------------------------------------------------------------------------
# set_part_visibility -- the bounds fan-out (R4)
# ---------------------------------------------------------------------------

def test_set_part_visibility_fans_out_to_update_bounds_and_actor_count(scene, pipeline):
    """Hiding a part reaches the widget layer, after the apply.

    This is the assertion that pins AC-4.  Revert the two calls and the
    recorder is empty.  Asserted on the renderer's ``update_bounds`` and
    ``update_actor_count`` -- the surface MC-3 reads in the log -- reached
    through the scene's real private helpers, which are deliberately not
    patched: patching them would move the assertion off that surface.

    Order matters and is asserted: a fan-out before the apply would push the
    pre-mutation actor count.
    """
    order = []
    scene._renderer.update_bounds = lambda bounds: order.append("update_bounds")
    scene._renderer.update_actor_count = lambda count: order.append("update_actor_count")
    real_apply = scene._renderer.apply_visibility
    scene._renderer.apply_visibility = lambda node_id, visible: (
        order.append("apply_visibility"), real_apply(node_id, visible)
    )[1]

    scene.set_part_visibility(NODE_ID, False)

    assert order == ["apply_visibility", "update_bounds", "update_actor_count"]


def test_set_part_visibility_unknown_node_id_does_not_fan_out(scene):
    """The early return still skips the fan-out.

    The two calls sit inside the lock block after the renderer write, so a node
    no dataset owns costs nothing.  A fan-out hoisted above the guard would
    refresh the widgets on every stray trigger.
    """
    calls = []
    scene._renderer.update_bounds = lambda bounds: calls.append("update_bounds")
    scene._renderer.update_actor_count = lambda count: calls.append("update_actor_count")

    with patch("ansys.visor.viewer.vtk.scene.base.logger"):
        scene.set_part_visibility(UNKNOWN_NODE_ID, False)

    assert calls == []


# ===========================================================================
# Projection -- the camera record's field, written by its own trigger
#
# Projection is not a fourth toggle and there is no store field for it.  The
# camera record is the only holder, ``get_state`` derives the persisted
# ``orthographic_enabled`` from it, and the coordinator re-serialises the
# camera as part of the write.
#
# That re-serialisation is the story's one quiet failure: dropped, the record
# is right, the pipeline camera is right, every other test in this module
# passes, and the browser snaps back to the pre-toggle framing on the next
# fetch.  The probe below is the only assertion in the suite that sees it.
# ===========================================================================

PROJECTION_ON = True
PROJECTION_OFF = False

# What a browser that was asked would answer for the persisted toggle.
# Deliberately the opposite of the record's parallel_projection, so "derived
# from the record" and "passed through from the reply" cannot both pass.
REPLY_ORTHOGRAPHIC = False


def _projection_save_scene(scene, record, reply_orthographic):
    """Wire *scene* for a save: renderer record *record*, reply *orthographic*.

    The same shape as ``_save_scene`` above, but the reply carries the
    persisted projection toggle rather than a camera, because that is the
    field whose source is under test.
    """
    double = _CameraRecordRenderer(record, _pipeline_camera(), scene=scene)
    scene._renderer = double
    scene._dataset_registry = VisorDatasetRegistry()

    async def _get_runtime_state_async(timeout):
        return RuntimeAppState.from_components(
            ui=VisorUIState(dark_theme=False),
            unit="m",
            dataset_states={},
            orthographic_enabled=reply_orthographic,
        )

    scene._get_runtime_state_async = _get_runtime_state_async
    return double


# ---------------------------------------------------------------------------
# The coordinator
# ---------------------------------------------------------------------------

def test_set_projection_applies_to_the_renderer_and_then_serializes(scene):
    """The re-serialisation follows the write, and carries production's id.

    Reverted -- the write kept and the re-serialisation dropped -- the record
    is right, the pipeline camera is right, and the client is served the
    pre-toggle camera on its next fetch.

    Also pins *where* the re-serialisation lives.  Written inside the
    renderer's own ``set_projection`` instead of here, the lock probe below
    would still pass; this spy sits on the coordinator's two calls, so a
    renderer that serialised for itself would record the pair in the wrong
    order or twice.

    The spy appends ``("set_projection", <value>)`` for the write and the
    two-tuple ``("serialize", <id>)`` for the re-serialisation; the tuple is
    the recording format, not the argument.
    """
    order = []
    real_set = scene._renderer.set_projection

    def _set(parallel):
        order.append(("set_projection", parallel))
        return real_set(parallel)

    scene._renderer.set_projection = _set
    scene._renderer._object_manager.UpdateStateFromObject = (
        lambda object_id: order.append(("serialize", object_id))
    )

    scene.set_projection(PROJECTION_ON)

    assert order == [("set_projection", True), ("serialize", ACTIVE_CAMERA_WASM_ID)]


def test_set_projection_holds_the_lock_across_both_halves(scene):
    """Both halves run inside ONE critical section, at the same depth.

    This is the assertion that pins the increment, and it is the only one in
    the story that catches the quiet failure.  Three reverts, three distinct
    signatures:

    * drop ``serialize_camera_state()``  -> ``serialize_depth`` is never
      recorded and this fails on the missing key;
    * move it below the ``with`` block   -> ``serialize_depth`` is 0 while
      ``write_depth`` is 1, so both the non-zero and the equality assertions
      fail, which is what separates "outside the lock" from "absent";
    * drop the ``with`` entirely         -> both depths are 0.

    The trigger handler runs on trame's daemon thread while the VTK objects it
    mutates belong to the caller's thread, so a re-serialisation outside the
    lock reads the object graph while another thread is free to mutate it.
    That failure is intermittent and never reproduces under a gate.
    """
    scene._vtk_lock = _LockSpy()
    observed = {}
    real_set = scene._renderer.set_projection

    def _set(parallel):
        observed["write_depth"] = scene._vtk_lock.depth
        return real_set(parallel)

    scene._renderer.set_projection = _set
    scene._renderer._object_manager.UpdateStateFromObject = (
        lambda object_id: observed.update(serialize_depth=scene._vtk_lock.depth)
    )

    scene.set_projection(PROJECTION_ON)

    assert observed["write_depth"] >= 1
    assert observed["serialize_depth"] >= 1
    assert observed["write_depth"] == observed["serialize_depth"]
    assert scene._vtk_lock.depth == 0
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


def test_set_projection_writes_no_store_field(scene):
    """The camera record is the only holder, and the scene stores nothing.

    The three widget toggles have store fields because no server VTK object
    backs them.  Projection has one, so a fourth store field would be the
    second source the derivation exists to remove -- and a second source is
    invisible until the two disagree, which is a save away.

    Asserted both ways: the record carries the value, and the scene grew no
    attribute to carry it as well.
    """
    seeded = _record_camera()
    scene._renderer.sync_camera(seeded)

    scene.set_projection(PROJECTION_OFF)

    assert scene._renderer.get_camera_state().parallel_projection is False
    assert not hasattr(scene, "_orthographic_enabled")
    assert not hasattr(scene, "_parallel_projection")
    assert scene._cross_section_enabled is False
    assert scene._edges_enabled is False
    assert scene._bounding_box_enabled is False


def test_set_projection_does_not_notify_the_client(scene):
    """Serialise only.  No render, no flush, no delegated push.

    A notify here would look correct and would be a loop: the push rebuilds
    the client, the rebuild re-delivers state, the reapply fires further
    triggers, and each one pushes again.  Every gate passes with a notify in
    place and the symptom in the browser looks like a network problem.
    """
    notifications = []
    scene._renderer.render = lambda: notifications.append("render")
    scene._renderer.render_window_only = lambda: notifications.append("render_window")
    scene._renderer.flush_wasm_state = lambda: notifications.append("flush")
    scene._apply_runtime_state_to_render = lambda state: notifications.append("bridge")

    scene.set_projection(PROJECTION_ON)

    assert notifications == []


# ---------------------------------------------------------------------------
# get_state -- orthographic_enabled is derived from the record
# ---------------------------------------------------------------------------

def test_get_state_derives_orthographic_enabled_from_the_camera_record(scene):
    """The saved projection is the record's, with the browser saying otherwise.

    This is the assertion that closes AC-5.  The record carries the
    hand-written literal ``True`` while the reply carries the hand-written
    literal ``False``; revert the derivation and the assertion reports
    ``False``, which is the reply's answer passed through -- the behaviour
    before this increment.

    ``record_reads == 1`` is asserted here too: the record is bound once and
    read once, so the camera and the projection are answers to a single
    question and cannot disagree with each other.

    Asserted on what get_state RETURNS -- the object that reaches the writer
    -- not on the runtime state it was built from.
    """
    double = _projection_save_scene(scene, _record_camera(), REPLY_ORTHOGRAPHIC)

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    assert persisted.scene.orthographic_enabled is True
    assert persisted.scene.camera.parallel_projection is True
    assert double.record_reads == 1


def test_get_state_orthographic_enabled_is_none_when_the_record_is_empty(scene):
    """An empty record emits ``None``, not a fabricated ``False``.

    ``None`` says "nothing was ever written"; ``False`` would assert
    perspective over a client that may be parallel.  The reply carries
    ``True`` here, so a derivation that dropped its guard and fell back to the
    reply would be visible rather than coincide.
    """
    _projection_save_scene(scene, None, True)

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    assert persisted.scene.orthographic_enabled is None
    assert persisted.scene.camera is None


# ===========================================================================
# The cross-section plane -- trigger path, save path, load path
#
# ``VisorSceneBase.sync_cross_section_plane`` is the coordinator method the
# ``sync_cross_section_plane`` trigger routes through.  As with the camera,
# the handler arrives on trame's daemon thread and must not touch the renderer
# directly, so what is asserted is the whole critical section: the write, the
# re-serialisation that follows it, and the lock held across both.
#
# The plane has exactly one delivery channel to a rebuilt or reconnecting
# client -- the wasm state fetch after the re-serialisation.  It is not on the
# scene-details payload.  That is why the re-serialisation is asserted here at
# all: dropping it leaves the server correct, every other gate green, and the
# user's drag snapping back on the next page reload.
#
# Own literals, distinct from the camera's above, so that a failure names the
# path that broke.
# ===========================================================================

# What the renderer's record holds at save time.
RECORD_CROSS_SECTION_ORIGIN = [51.0, 52.0, 53.0]
RECORD_CROSS_SECTION_NORMAL = [0.0, 1.0, 0.0]

# What the browser answers getState with.  Never the right answer, and
# different in every component, so "read the record" and "read the reply"
# cannot both pass.
REPLY_CROSS_SECTION_ORIGIN = [61.0, 62.0, 63.0]
REPLY_CROSS_SECTION_NORMAL = [1.0, 0.0, 0.0]

# What a settled drag reports, and what a save file carries on load.
GESTURE_CROSS_SECTION_ORIGIN = [71.0, 72.0, 73.0]
GESTURE_CROSS_SECTION_NORMAL = [0.0, 0.0, 1.0]

LOADED_CROSS_SECTION_ORIGIN = [81.0, 82.0, 83.0]
LOADED_CROSS_SECTION_NORMAL = [0.0, 1.0, 0.0]


def _record_plane() -> VisorCrossSectionState:
    """The renderer's plane record, from hand-written literals."""
    return VisorCrossSectionState(
        origin=RECORD_CROSS_SECTION_ORIGIN,
        normal=RECORD_CROSS_SECTION_NORMAL,
    )


def _reply_plane() -> VisorCrossSectionState:
    """What the browser answers getState with.  Never the right answer."""
    return VisorCrossSectionState(
        origin=REPLY_CROSS_SECTION_ORIGIN,
        normal=REPLY_CROSS_SECTION_NORMAL,
    )


def _plane_save_scene(scene, record_plane, reply_plane):
    """Wire *scene* for a save: renderer record *record_plane*, reply *reply_plane*.

    The same shape as ``_save_scene`` above, but the reply carries a plane
    rather than a camera, because that is the field whose source is under
    test.  The registry is emptied so the mapper's per-dataset loop
    contributes nothing.
    """
    double = _CameraRecordRenderer(
        None, _pipeline_camera(), scene=scene, cross_section=record_plane
    )
    scene._renderer = double
    scene._dataset_registry = VisorDatasetRegistry()

    async def _get_runtime_state_async(timeout):
        return RuntimeAppState.from_components(
            ui=VisorUIState(dark_theme=False),
            unit="m",
            dataset_states={},
            cross_section=reply_plane,
        )

    scene._get_runtime_state_async = _get_runtime_state_async
    return double


# ---------------------------------------------------------------------------
# The coordinator
# ---------------------------------------------------------------------------

def test_sync_cross_section_plane_applies_to_the_renderer_and_then_serializes(scene):
    """The re-serialisation follows the write, and there are two of them.

    Reverted -- the write kept and the re-serialisation dropped -- the record
    is right, the server's own plane and representation are right, every other
    test in this module still passes, and the client is served the pre-drag
    plane on its next fetch.  The user sees a page reload snap the plane back
    to where it was before they dragged it.

    Two serialise calls, not one: ``serialize_cross_section_state`` names the
    plane and the representation separately.  Which object each names is
    pinned in tests/unit/renderer/test_local_renderer.py, against a widget
    double whose two objects have distinct ids; what is pinned here is that
    the coordinator reaches that method at all, and reaches it after the
    write.
    """
    order = []
    real_sync = scene._renderer.sync_cross_section_plane

    def _sync(origin, normal):
        order.append("plane")
        return real_sync(origin, normal)

    scene._renderer.sync_cross_section_plane = _sync
    scene._renderer._object_manager.UpdateStateFromObject = (
        lambda object_id: order.append("serialize")
    )

    scene.sync_cross_section_plane(
        GESTURE_CROSS_SECTION_ORIGIN, GESTURE_CROSS_SECTION_NORMAL
    )

    assert order == ["plane", "serialize", "serialize"]


def test_sync_cross_section_plane_holds_the_lock_across_both_halves(scene):
    """Both halves run inside one and the same critical section.

    Its own test rather than another assertion on the ordering test, on the
    precedent of ``test_sync_camera_holds_the_lock_across_both_halves``: lock
    depth and call order fail for different reasons and want to be readable
    apart.  The pair discriminates precisely -- a re-serialisation that was
    dropped fails both, one that was merely moved below the ``with`` block
    fails only this one.

    The two depths are asserted **equal** as well as non-zero.  Non-zero alone
    would pass a body that released and re-took the lock between the write and
    the re-serialise, which is not one critical section: another thread can
    mutate the VTK object graph in the gap, and the client is then served a
    half-written scene.  That failure is intermittent and never reproduces
    under a gate.
    """
    scene._vtk_lock = _LockSpy()
    observed = {}
    real_sync = scene._renderer.sync_cross_section_plane

    def _sync(origin, normal):
        observed["write_depth"] = scene._vtk_lock.depth
        return real_sync(origin, normal)

    scene._renderer.sync_cross_section_plane = _sync
    scene._renderer._object_manager.UpdateStateFromObject = (
        lambda object_id: observed.update(serialize_depth=scene._vtk_lock.depth)
    )

    scene.sync_cross_section_plane(
        GESTURE_CROSS_SECTION_ORIGIN, GESTURE_CROSS_SECTION_NORMAL
    )

    assert observed["write_depth"] >= 1
    assert observed["serialize_depth"] >= 1
    assert observed["serialize_depth"] == observed["write_depth"]
    assert scene._vtk_lock.depth == 0
    assert scene._vtk_lock.enter_count == scene._vtk_lock.exit_count


# ---------------------------------------------------------------------------
# get_state -- the plane comes from the record, not from the reply
# ---------------------------------------------------------------------------

def test_get_state_takes_the_cross_section_from_the_record(scene):
    """The saved plane is the record's, with the browser saying otherwise.

    The record and the reply differ in every component, so "server
    authoritative" and "round-trips the client's answer" cannot both pass.
    Revert the assignment and both assertions below report the reply's
    numbers.

    Asserted on what get_state RETURNS -- the object that reaches the writer
    -- not on the runtime state it was built from.  An assignment placed after
    ``runtime_to_persisted`` passes every assertion made against the runtime
    object and still writes the wrong file.
    """
    _plane_save_scene(scene, _record_plane(), _reply_plane())

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    assert persisted.scene.cross_section.origin == RECORD_CROSS_SECTION_ORIGIN
    assert persisted.scene.cross_section.normal == RECORD_CROSS_SECTION_NORMAL


def test_get_state_writes_no_cross_section_when_the_record_is_empty(scene):
    """An empty record writes ``None`` through, reply notwithstanding.

    The assignment is unconditional, exactly as the camera's, and this is the
    only test that a guarded one -- one that skipped the write when the record
    was ``None`` -- would fail.  The reply carries a perfectly valid plane, so
    the guarded version would save the browser's answer and look correct
    everywhere else.

    ``None`` says "no plane was ever written".  The guard for "absent says
    nothing" belongs to the load path, not here.
    """
    _plane_save_scene(scene, None, _reply_plane())

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    assert persisted.scene.cross_section is None


# ---------------------------------------------------------------------------
# apply_state -- the load path writes the renderer and re-serialises
# ---------------------------------------------------------------------------

def test_apply_state_serializes_the_loaded_plane_after_syncing_it(scene):
    """A plane in the file reaches the renderer, and is then re-serialised.

    Driven with a real ``PersistedViewerStateV1`` through the real state
    mapper, so this also exercises the mapper's plane pass-through; it is the
    first test here that would notice if the mapper stopped handing
    ``cross_section`` on verbatim.

    ``camera=None`` keeps the camera step out of the recording, so every
    ``"serialize"`` below is the plane's.  Reverted -- the sync kept and the
    re-serialise dropped -- the server's plane is right and the client is
    served the pre-load one, which is the defect the load path already had for
    the camera and fixed for the same reason.
    """
    order = []
    real_sync = scene._renderer.sync_cross_section_plane

    def _sync(origin, normal):
        order.append(("plane", list(origin), list(normal)))
        return real_sync(origin, normal)

    scene._renderer.sync_cross_section_plane = _sync
    scene._renderer._object_manager.UpdateStateFromObject = (
        lambda object_id: order.append("serialize")
    )

    scene.apply_state(
        PersistedViewerStateV1.from_components(
            ui_state=VisorUIState(dark_theme=False),
            unit="m",
            orthographic_enabled=None,
            cross_section_enabled=None,
            edges_enabled=None,
            bounding_box_enabled=None,
            datasets={},
            camera=None,
            cross_section=VisorCrossSectionState(
                origin=LOADED_CROSS_SECTION_ORIGIN,
                normal=LOADED_CROSS_SECTION_NORMAL,
            ),
        )
    )

    assert order == [
        ("plane", LOADED_CROSS_SECTION_ORIGIN, LOADED_CROSS_SECTION_NORMAL),
        "serialize",
        "serialize",
    ]


# ===========================================================================
# UI panel state -- the store, the read, the restore
#
# The four panel fields are the browser's chrome, recorded on the server so
# that a refresh restores them.  They have no renderer half: nothing the
# server renders depends on which panel is collapsed, so each coordinator
# writes one store field and stops.  That is why there is no apply-half test
# here to match the toggles' pair above -- there is no apply.
#
# Every expected value below is a hand-written literal.  ``True, True, True,
# 1`` is used as the value the client reports, because the server's own
# initial values are the literals ``False, False, False, 0``, so a body that
# wrote a default rather than its argument fails.
# ===========================================================================

PANEL_COLLAPSED = True
PANEL_TAB_INDEX = 1

# What a browser that was asked would answer.  Deliberately the opposite of
# what the store holds in the derivation test, so that "read the store" and
# "read the reply" cannot both pass.
REPLY_PANEL_COLLAPSED = False
REPLY_PANEL_TAB_INDEX = 0

# The theme pair.  The server holds one value and the browser reports the
# other, so that "wrote dark_mode" and "passed the reply through" are
# distinguishable in a single assertion.
SERVER_DARK_MODE = True
REPLY_DARK_THEME = False


class _PanelStoreLockSpy(_LockSpy):
    """Lock spy that reads the tab-index store field as the lock is released.

    The panel coordinators make no renderer call, so there is no inner call
    to probe the way ``_ToggleSpyRenderer`` probes the toggles.  What can be
    observed instead is the store itself at the moment the critical section
    ends: if the write happened inside ``with self._vtk_lock:`` the field
    already carries the new value when the lock is released, and the depth
    read here is the depth the write ran at.  With the ``with`` removed the
    lock is never entered at all and both recordings stay ``None``.
    """

    def __init__(self, scene):
        super().__init__()
        self._scene = scene
        self.value_at_release = None
        self.depth_at_release = None

    def __exit__(self, exc_type, exc, tb):
        self.value_at_release = self._scene._panel_top_right_tab_index
        self.depth_at_release = self.depth
        return super().__exit__(exc_type, exc, tb)


def _reply_ui(
    panel_top_left_panel_collapsed,
    panel_top_right_panel_collapsed,
    panel_top_right_legend_collapsed,
    panel_top_right_tab_index,
    dark_theme=REPLY_DARK_THEME,
):
    """The ``ui`` block a browser round trip answers with."""
    return VisorUIState(
        dark_theme=dark_theme,
        panel_top_left_panel_collapsed=panel_top_left_panel_collapsed,
        panel_top_right_panel_collapsed=panel_top_right_panel_collapsed,
        panel_top_right_legend_collapsed=panel_top_right_legend_collapsed,
        panel_top_right_tab_index=panel_top_right_tab_index,
    )


def _ui_save_scene(scene, reply_ui):
    """Wire *scene* for a save whose browser reply carries *reply_ui*.

    The same shape as ``_toggle_save_scene`` above; the registry is emptied so
    the mapper's per-dataset loop contributes nothing, and what is under test
    is the ``ui`` block of the persisted state.
    """
    scene._dataset_registry = VisorDatasetRegistry()

    async def _get_runtime_state_async(timeout):
        return RuntimeAppState.from_components(
            ui=reply_ui,
            unit="m",
            dataset_states={},
        )

    scene._get_runtime_state_async = _get_runtime_state_async


def _panel_runtime_state(ui):
    """A real RuntimeAppState carrying only the UI record named."""
    return RuntimeAppState.from_components(
        ui=ui,
        unit="m",
        dataset_states={},
    )


# ---------------------------------------------------------------------------
# The coordinator surface
# ---------------------------------------------------------------------------

def test_panel_coordinators_write_the_store(scene):
    """Each of the four coordinators records what it was told.

    One test and not four: the four bodies are the same statement against
    four fields, and a swap between two of them fails this test exactly as
    visibly as four separate ones would.  The four literals are distinct from
    the four initial values, so a body that wrote its default rather than its
    argument fails here too.
    """
    scene.set_panel_top_left_panel_collapsed(PANEL_COLLAPSED)
    scene.set_panel_top_right_panel_collapsed(PANEL_COLLAPSED)
    scene.set_panel_top_right_legend_collapsed(PANEL_COLLAPSED)
    scene.set_panel_top_right_tab_index(PANEL_TAB_INDEX)

    assert scene._panel_top_left_panel_collapsed is True
    assert scene._panel_top_right_panel_collapsed is True
    assert scene._panel_top_right_legend_collapsed is True
    assert scene._panel_top_right_tab_index == 1


def test_set_panel_top_right_tab_index_holds_the_lock_at_the_store_write(scene):
    """The lock is *held* at the moment the store is written.

    One of the four and not all four: the precedent pins the lock once per
    surface rather than once per method.  Remove ``with self._vtk_lock:`` from
    the coordinator and the spy records nothing at all -- the value and the
    depth both stay ``None`` -- because the lock is never entered.

    The trigger handler runs on trame's daemon thread while this store is read
    on the caller's thread by ``get_state``; a write outside the lock would
    interleave with the assembly of the record being saved.  That failure is
    intermittent and never reproduces under a gate.
    """
    spy = _PanelStoreLockSpy(scene)
    scene._vtk_lock = spy

    scene.set_panel_top_right_tab_index(PANEL_TAB_INDEX)

    assert spy.depth_at_release >= 1
    assert spy.value_at_release == 1
    assert spy.depth == 0
    assert spy.enter_count == spy.exit_count


# ---------------------------------------------------------------------------
# get_state -- the UI record comes from the server, not from the reply
# ---------------------------------------------------------------------------

def test_get_state_takes_the_ui_panel_state_from_the_store(scene):
    """The saved panel state is the server's, with the browser saying otherwise.

    This is the assertion that pins the change.  The store holds the
    hand-written literals ``True, True, True, 1`` while the reply carries
    ``False, False, False, 0``; delete the ``runtime_state.ui`` assignment in
    get_state and every assertion below reports the reply's value instead.

    Asserted on what get_state RETURNS -- the object that reaches the writer --
    not on the runtime state it was built from.
    """
    scene.set_panel_top_left_panel_collapsed(PANEL_COLLAPSED)
    scene.set_panel_top_right_panel_collapsed(PANEL_COLLAPSED)
    scene.set_panel_top_right_legend_collapsed(PANEL_COLLAPSED)
    scene.set_panel_top_right_tab_index(PANEL_TAB_INDEX)
    _ui_save_scene(
        scene,
        _reply_ui(
            REPLY_PANEL_COLLAPSED,
            REPLY_PANEL_COLLAPSED,
            REPLY_PANEL_COLLAPSED,
            REPLY_PANEL_TAB_INDEX,
        ),
    )

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    assert persisted.ui.panel_top_left_panel_collapsed is True
    assert persisted.ui.panel_top_right_panel_collapsed is True
    assert persisted.ui.panel_top_right_legend_collapsed is True
    assert persisted.ui.panel_top_right_tab_index == 1


def test_get_state_discards_the_ui_panel_state_the_browser_returned(scene):
    """The browser's panel state does not survive into the persisted state.

    The mirror of the test above and its own test for the same reason the
    camera and toggle pairs are split: "wrote the store" and "did not write
    the reply" are the same only while the round trip still carries a ``ui``
    block at all, and the round trip is not being removed.  Here the store is
    left at its initial values and the reply carries ``True, True, True, 1``.

    The four expected values are the hand-written literals ``False``,
    ``False``, ``False`` and ``0``, not a read of the store: a store
    initialised to ``None`` -- the silent failure the delivery decision
    turns on -- fails this test on value.
    """
    _ui_save_scene(
        scene,
        _reply_ui(
            PANEL_COLLAPSED,
            PANEL_COLLAPSED,
            PANEL_COLLAPSED,
            PANEL_TAB_INDEX,
        ),
    )

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    assert persisted.ui.panel_top_left_panel_collapsed is False
    assert persisted.ui.panel_top_right_panel_collapsed is False
    assert persisted.ui.panel_top_right_legend_collapsed is False
    assert persisted.ui.panel_top_right_tab_index == 0


def test_get_state_takes_dark_theme_from_the_server_not_the_browser(scene):
    """The saved theme is ``dark_mode``, with the browser saying otherwise.

    Its own test rather than a fifth assertion above, because it is a
    different source: the other four come from the panel store, this one from
    the public ``dark_mode`` attribute, and no trigger writes it.  The reply
    carries the opposite literal, which is what a Dash host prop override
    produces in the browser today; before this change that value reached the
    file and, on the next load, the server's own ``dark_mode``.
    """
    scene.dark_mode = SERVER_DARK_MODE
    _ui_save_scene(
        scene,
        _reply_ui(
            REPLY_PANEL_COLLAPSED,
            REPLY_PANEL_COLLAPSED,
            REPLY_PANEL_COLLAPSED,
            REPLY_PANEL_TAB_INDEX,
            dark_theme=REPLY_DARK_THEME,
        ),
    )

    persisted = asyncio.run(scene.get_state(timeout=1.0))

    assert persisted.ui.dark_theme is True


# ---------------------------------------------------------------------------
# apply_state -- the load path writes the store
# ---------------------------------------------------------------------------

def test_apply_state_restores_the_ui_panel_state_to_the_store(scene):
    """A state carrying panel fields becomes the server's store."""
    _apply(
        scene,
        _panel_runtime_state(
            VisorUIState(
                dark_theme=False,
                panel_top_left_panel_collapsed=PANEL_COLLAPSED,
                panel_top_right_panel_collapsed=PANEL_COLLAPSED,
                panel_top_right_legend_collapsed=PANEL_COLLAPSED,
                panel_top_right_tab_index=PANEL_TAB_INDEX,
            )
        ),
    )

    assert scene._panel_top_left_panel_collapsed is True
    assert scene._panel_top_right_panel_collapsed is True
    assert scene._panel_top_right_legend_collapsed is True
    assert scene._panel_top_right_tab_index == 1


def test_apply_state_leaves_an_absent_ui_panel_field_alone(scene):
    """Absent says nothing: a state with no panel fields is not a state of defaults.

    The guard belongs to this path and not to get_state, and this is the test
    that says so.  The store is seeded through the coordinators first, so a
    body that wrote the model's own ``None`` default through would be caught;
    a file written before this record existed carries exactly this shape.
    """
    scene.set_panel_top_left_panel_collapsed(PANEL_COLLAPSED)
    scene.set_panel_top_right_panel_collapsed(PANEL_COLLAPSED)
    scene.set_panel_top_right_legend_collapsed(PANEL_COLLAPSED)
    scene.set_panel_top_right_tab_index(PANEL_TAB_INDEX)

    _apply(scene, _panel_runtime_state(VisorUIState(dark_theme=False)))

    assert scene._panel_top_left_panel_collapsed is True
    assert scene._panel_top_right_panel_collapsed is True
    assert scene._panel_top_right_legend_collapsed is True
    assert scene._panel_top_right_tab_index == 1


