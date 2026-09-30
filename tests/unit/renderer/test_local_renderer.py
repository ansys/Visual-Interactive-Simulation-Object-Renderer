"""
Unit tests for IRenderer / VisorLocalRenderer.

Coverage targets
----------------
1.  Node lifecycle  -- register_node / deregister_node (the non-trivial seam).
2.  Interface conformance -- NullRenderer and VisorLocalRenderer both satisfy
    IRenderer's abstract contract.
3.  Per-part visual mutations -- visibility, opacity, diffuse colour,
    selection and colour variable all resolve the pipeline and delegate to
    VtkNodePipeline (their VTK effects are asserted in
    tests/unit/vtk/test_node_pipeline.py); edge visibility and the
    colour-variable range refresh stay no-ops.
4.  Camera round-trip -- reset_camera, sync_camera / get_camera_state.
5.  Render / flush delegation.
6.  pick_geometry -- vertex, edge, face modes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.renderer.base import IRenderer
from ansys.visor.viewer.renderer.local_renderer import VisorLocalRenderer
from ansys.visor.viewer.renderer.null_renderer import NullRenderer

# ---------------------------------------------------------------------------
# Lightweight VTK-data stubs (no real VTK objects required for pick tests)
# ---------------------------------------------------------------------------

class _DummyPoints:
    def __init__(self, pts):
        self._pts = pts

    def GetPoint(self, i): # noqa: N802
        return tuple(self._pts[i])


class _DummyCell:
    def __init__(self, points):
        self._pts = _DummyPoints(points)
        self._n = len(points)

    def GetNumberOfPoints(self): # noqa: N802
        return self._n

    def GetPoints(self): # noqa: N802
        return self._pts


class _DummyDataset:
    def __init__(self, cells):
        self._cells = cells

    def GetNumberOfCells(self): # noqa: N802
        return len(self._cells)

    def GetCell(self, idx): # noqa: N802
        return self._cells[idx] if 0 <= idx < len(self._cells) else None


class _DummyMapper:
    def __init__(self, dataset):
        self._ds = dataset

    def GetInputDataObject(self, a, b): # noqa: N802
        return self._ds


class _DummyActor:
    def __init__(self, mapper):
        self._mapper = mapper

    def GetMapper(self): # noqa: N802
        return self._mapper


class _DummyActors:
    """Minimal traversable actor collection matching vtkActorCollection's API."""

    def __init__(self, actors):
        self._actors = actors
        self._idx = 0

    def InitTraversal(self): # noqa: N802
        self._idx = 0

    def GetNextActor(self): # noqa: N802
        if self._idx >= len(self._actors):
            return None
        a = self._actors[self._idx]
        self._idx += 1
        return a


# ---------------------------------------------------------------------------
# Camera double
#
# Hand-written rather than a MagicMock: reset_camera reads the active camera
# back into a VisorCameraState, and pydantic rejects Mock attributes.
#
# No literal below matches a vtkCamera construction default -- view angle 30.0
# is the trap -- so an assertion against these values can still fail if the
# double is ever pointed at a real vtkRenderer.
# ---------------------------------------------------------------------------

CAMERA_DOUBLE_POSITION = [11.0, 12.0, 13.0]
CAMERA_DOUBLE_FOCAL_POINT = [14.0, 15.0, 16.0]
CAMERA_DOUBLE_VIEW_UP = [17.0, 18.0, 19.0]
CAMERA_DOUBLE_CLIPPING_RANGE = [21.0, 22.0]
CAMERA_DOUBLE_PARALLEL_PROJECTION = 1
CAMERA_DOUBLE_VIEW_ANGLE = 23.0
CAMERA_DOUBLE_PARALLEL_SCALE = 24.0


class _CameraDouble:
    """Stand-in for vtkCamera.

    Getters return the literals above, so ``_read_pipeline_camera`` produces a
    valid VisorCameraState.  Setters append to ``calls`` so
    ``_apply_to_pipeline_camera`` can be asserted on by value *and* by order.
    """

    def __init__(self):
        self.calls = []

    # -- getters, read by _read_pipeline_camera --

    def GetPosition(self): # noqa: N802
        return tuple(CAMERA_DOUBLE_POSITION)

    def GetFocalPoint(self): # noqa: N802
        return tuple(CAMERA_DOUBLE_FOCAL_POINT)

    def GetViewUp(self): # noqa: N802
        return tuple(CAMERA_DOUBLE_VIEW_UP)

    def GetClippingRange(self): # noqa: N802
        return tuple(CAMERA_DOUBLE_CLIPPING_RANGE)

    def GetParallelProjection(self): # noqa: N802
        return CAMERA_DOUBLE_PARALLEL_PROJECTION

    def GetViewAngle(self): # noqa: N802
        return CAMERA_DOUBLE_VIEW_ANGLE

    def GetParallelScale(self): # noqa: N802
        return CAMERA_DOUBLE_PARALLEL_SCALE

    # -- setters, written by _apply_to_pipeline_camera --

    def SetPosition(self, value): # noqa: N802
        self.calls.append(("SetPosition", value))

    def SetFocalPoint(self, value): # noqa: N802
        self.calls.append(("SetFocalPoint", value))

    def SetViewUp(self, value): # noqa: N802
        self.calls.append(("SetViewUp", value))

    def SetClippingRange(self, value): # noqa: N802
        self.calls.append(("SetClippingRange", value))

    def SetParallelProjection(self, value): # noqa: N802
        self.calls.append(("SetParallelProjection", value))

    def SetViewAngle(self, value): # noqa: N802
        self.calls.append(("SetViewAngle", value))

    def SetParallelScale(self, value): # noqa: N802
        self.calls.append(("SetParallelScale", value))


# ---------------------------------------------------------------------------
# Object-manager id literals
#
# One literal per object, so asserting ACTIVE_CAMERA_WASM_ID fails -- rather
# than coincides -- if production names the render window, the renderer, the
# interactor or the picker instead.  The render window keeps its own literal
# so a revert to the previous call shape fails by name, not as the catch-all.
# ---------------------------------------------------------------------------

RENDER_WINDOW_WASM_ID = 8150001
ACTIVE_CAMERA_WASM_ID = 8150002
WRONG_OBJECT_WASM_ID = 8150999



# ---------------------------------------------------------------------------
# Fixture: VisorLocalRenderer with all VTK infrastructure mocked
# ---------------------------------------------------------------------------

@pytest.fixture
def renderer():
    """VisorLocalRenderer whose every VTK sub-system is a MagicMock.

    Each ``_initialize_*`` method is patched so that no real VTK render window,
    interactor, LocalView, or widget is created.  The resulting object has fully
    controllable mock attributes (``_vtk_renderer``, ``_cross_section_widget``,
    etc.) that each test can configure independently.
    """
    mock_server = MagicMock()
    mock_server.state = {}

    vtk_renderer = MagicMock(name="vtk_renderer")
    # _read_pipeline_camera feeds pydantic, which rejects Mock attributes.
    vtk_renderer.GetActiveCamera.return_value = _CameraDouble()
    render_window = MagicMock(name="render_window")
    interactor = MagicMock(name="interactor")
    local_view = MagicMock(name="local_view")
    orientation_widget = MagicMock(name="orientation_widget")
    cross_section_widget = MagicMock(name="cross_section_widget")
    bounding_box_widget = MagicMock(name="bounding_box_widget")

    with (
        patch.object(VisorLocalRenderer, "_initialize_vtk_renderer", return_value=vtk_renderer),
        patch.object(VisorLocalRenderer, "_initialize_render_window", return_value=render_window),
        patch.object(VisorLocalRenderer, "_initialize_render_window_interactor", return_value=interactor),
        patch.object(VisorLocalRenderer, "_initialize_local_view", return_value=local_view),
        patch.object(VisorLocalRenderer, "_initialize_orientation_widget", return_value=orientation_widget),
        patch.object(VisorLocalRenderer, "_initialize_cross_section_widget", return_value=cross_section_widget),
        patch.object(VisorLocalRenderer, "_initialize_bounding_box_widget", return_value=bounding_box_widget),
    ):
        r = VisorLocalRenderer(mock_server)

    return r


# ---------------------------------------------------------------------------
# Helper: seed one actor into the renderer's actor list for pick tests
# ---------------------------------------------------------------------------

def _seed_actor(renderer, actor_wasm_id: int, dataset):
    """Wire a dummy actor+dataset into the renderer's VTK actor traversal.

    Returns the actor so callers can make additional assertions.
    """
    actor = _DummyActor(_DummyMapper(dataset))
    renderer._vtk_renderer.GetActors.return_value = _DummyActors([actor])
    renderer._object_manager.GetId.side_effect = (
        lambda a: actor_wasm_id if a is actor else -1
    )
    return actor


# ===========================================================================
# 1.  Interface conformance
# ===========================================================================

class TestInterfaceConformance:
    def test_null_renderer_instantiates_without_type_error(self):
        """NullRenderer satisfies IRenderer's full abstract set."""
        r = NullRenderer()
        assert isinstance(r, IRenderer)

    def test_local_renderer_has_no_remaining_abstract_methods(self):
        """VisorLocalRenderer provides a concrete body for every @abstractmethod."""
        assert not VisorLocalRenderer.__abstractmethods__

    def test_null_renderer_has_no_remaining_abstract_methods(self):
        assert not NullRenderer.__abstractmethods__


# ===========================================================================
# 2.  Node lifecycle  (register_node / deregister_node)
# ===========================================================================

class TestNodeLifecycle:

    # ------------------------------------------------------------------
    # register_node
    # ------------------------------------------------------------------

    def test_register_node_calls_from_dataset_with_node_dataset(self, renderer):
        """register_node builds the pipeline from the node's dataset."""
        node = MagicMock()
        node.id = 10
        dataset = MagicMock(name="dataset")
        mock_pipe = MagicMock(name="pipeline")

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.VtkNodePipeline.from_dataset",
            return_value=mock_pipe,
        ) as mock_from_ds:
            renderer.register_node(node, dataset)

        mock_from_ds.assert_called_once_with(dataset)

    def test_register_node_stores_pipeline_keyed_by_node_id(self, renderer):
        """Pipeline is registered under node.id in the internal registry."""
        node = MagicMock()
        node.id = 99
        mock_pipe = MagicMock(name="pipeline")

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.VtkNodePipeline.from_dataset",
            return_value=mock_pipe,
        ):
            renderer.register_node(node, MagicMock())

        assert renderer._pipelines[99] is mock_pipe

    def test_register_node_attaches_cross_section_clipping_plane(self, renderer):
        """Pipeline's clipping plane is set to the cross-section widget's plane."""
        node = MagicMock()
        node.id = 7
        mock_pipe = MagicMock(name="pipeline")

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.VtkNodePipeline.from_dataset",
            return_value=mock_pipe,
        ):
            renderer.register_node(node, MagicMock())

        mock_pipe.set_clipping_plane.assert_called_once_with(
            renderer._cross_section_widget.plane
        )

    def test_register_node_disables_scalar_visibility(self, renderer):
        """Mapper scalar visibility is turned off immediately after pipeline creation."""
        node = MagicMock()
        node.id = 5
        mock_pipe = MagicMock(name="pipeline")

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.VtkNodePipeline.from_dataset",
            return_value=mock_pipe,
        ):
            renderer.register_node(node, MagicMock())

        mock_pipe.mapper.SetScalarVisibility.assert_called_once_with(False)

    def test_register_node_adds_actor_to_vtk_renderer(self, renderer):
        """Actor is added to the VTK renderer so it appears in the scene."""
        node = MagicMock()
        node.id = 3
        mock_pipe = MagicMock(name="pipeline")

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.VtkNodePipeline.from_dataset",
            return_value=mock_pipe,
        ):
            renderer.register_node(node, MagicMock())

        renderer._vtk_renderer.AddActor.assert_called_once_with(mock_pipe.actor)

    def test_register_node_is_idempotent(self, renderer):
        """Calling register_node twice for the same node does not create a duplicate."""
        node = MagicMock()
        node.id = 1
        mock_pipe = MagicMock(name="pipeline")

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.VtkNodePipeline.from_dataset",
            return_value=mock_pipe,
        ) as mock_from_ds:
            renderer.register_node(node, MagicMock())
            renderer.register_node(node, MagicMock())  # second call -- must be ignored

        # Pipeline factory called only once; registry still has exactly one entry.
        mock_from_ds.assert_called_once()
        assert len(renderer._pipelines) == 1
        # Actor attached only once.
        renderer._vtk_renderer.AddActor.assert_called_once()

    # ------------------------------------------------------------------
    # deregister_node
    # ------------------------------------------------------------------

    def test_deregister_node_removes_actor_from_vtk_renderer(self, renderer):
        """deregister_node removes the actor from the VTK renderer."""
        node_id = 20
        mock_pipe = MagicMock(name="pipeline")
        renderer._pipelines[node_id] = mock_pipe

        renderer.deregister_node(node_id)

        renderer._vtk_renderer.RemoveActor.assert_called_once_with(mock_pipe.actor)

    def test_deregister_node_removes_pipeline_from_registry(self, renderer):
        """Pipeline is gone from the registry after deregistration."""
        node_id = 21
        renderer._pipelines[node_id] = MagicMock(name="pipeline")

        renderer.deregister_node(node_id)

        assert node_id not in renderer._pipelines

    def test_deregister_node_silently_ignores_unknown_id(self, renderer):
        """deregister_node is a no-op when the node was never registered."""
        renderer.deregister_node(9999)  # must not raise
        renderer._vtk_renderer.RemoveActor.assert_not_called()

    def test_register_then_deregister_leaves_empty_registry(self, renderer):
        """Full lifecycle: register one node then deregister it; registry is empty."""
        node = MagicMock()
        node.id = 55
        mock_pipe = MagicMock(name="pipeline")

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.VtkNodePipeline.from_dataset",
            return_value=mock_pipe,
        ):
            renderer.register_node(node, MagicMock())

        renderer.deregister_node(55)

        assert renderer._pipelines == {}
        renderer._vtk_renderer.RemoveActor.assert_called_once_with(mock_pipe.actor)

    # ------------------------------------------------------------------
    # deregister_all
    # ------------------------------------------------------------------

    def test_deregister_all_empties_registry_and_detaches_all_actors(self, renderer):
        """deregister_all removes every pipeline and detaches every actor."""
        mock_pipe_1 = MagicMock(name="pipeline1")
        mock_pipe_2 = MagicMock(name="pipeline2")
        renderer._pipelines[1] = mock_pipe_1
        renderer._pipelines[2] = mock_pipe_2

        renderer.deregister_all()

        assert renderer._pipelines == {}
        renderer._vtk_renderer.RemoveActor.assert_any_call(mock_pipe_1.actor)
        renderer._vtk_renderer.RemoveActor.assert_any_call(mock_pipe_2.actor)
        assert renderer._vtk_renderer.RemoveActor.call_count == 2


# ===========================================================================
# 3.  Per-part visual mutations
# ===========================================================================

class TestPerPartMutations:
    """The permanently un-implemented method accepts its arguments.

    It stays a no-op beyond this story: the colour-variable range is not
    held per part.
    """

    def test_refresh_color_variable_range(self, renderer):
        assert (
            renderer.refresh_color_variable_range(1, "sp-1", "CELL", "temp", 0)
            is None
        )


# ===========================================================================
# 3a-bis.  Scene-wide widget state: set_edges_visible
#
#      The VTK effect lives on VtkNodePipeline and is asserted in
#      tests/unit/vtk/test_node_pipeline.py.  What is asserted here is the
#      fan-out: every registered pipeline, no node-id resolution, and no
#      guard branch for an empty registry.
# ===========================================================================

class TestGlobalEdgeVisibility:

    def test_set_edges_visible_fans_out_over_every_pipeline(self, renderer):
        """Every registered pipeline is told, with the value as given.

        Three pipelines under non-contiguous ids, so a body that iterated a
        range or resolved a node id rather than iterating the registry's
        values fails here.
        """
        pipes = {4: MagicMock(name="pipe-4"), 9: MagicMock(name="pipe-9"),
                 17: MagicMock(name="pipe-17")}
        renderer._pipelines.update(pipes)

        assert renderer.set_edges_visible(True) is None

        for pipe in pipes.values():
            pipe.set_edge_visibility.assert_called_once_with(True)

    def test_set_edges_visible_with_no_pipelines_is_a_no_op(self, renderer):
        """An empty scene is a no-op by iteration, not by guard.

        Pinned because the contract says there is no logged-no-op branch here:
        a later session adding one would be adding a branch that can only ever
        be wrong, and this test says the empty case is already handled.
        """
        renderer._pipelines.clear()

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.logger"
        ) as mock_logger:
            assert renderer.set_edges_visible(True) is None

        assert mock_logger.debug.call_count == 0
        assert mock_logger.warning.call_count == 0


# ===========================================================================
# 3b.  Delegated apply bodies: visibility, opacity, diffuse colour,
#      selection, colour variable
#
#      The VTK effects of these live on VtkNodePipeline and are asserted in
#      tests/unit/vtk/test_node_pipeline.py.  What is asserted here is that
#      the renderer resolved the pipeline and delegated with the arguments
#      it was given, and that an unknown node id is a logged no-op.
# ===========================================================================

class TestDelegatedApplyBodies:

    # ------------------------------------------------------------------
    # apply_visibility
    # ------------------------------------------------------------------

    def test_apply_visibility_delegates_to_pipeline(self, renderer):
        """The visibility flag is passed straight through."""
        pipe = MagicMock(name="pipeline")
        renderer._pipelines[4] = pipe

        renderer.apply_visibility(4, True)

        pipe.set_visibility.assert_called_once_with(True)

    def test_apply_visibility_unknown_node_id_is_logged_no_op(self, renderer):
        """An unregistered node id logs at debug, does not raise, delegates nothing."""
        pipe = MagicMock(name="pipeline")
        renderer._pipelines[4] = pipe

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.logger"
        ) as mock_logger:
            renderer.apply_visibility(9999, False)  # must not raise

        mock_logger.debug.assert_called_once()
        pipe.set_visibility.assert_not_called()

    # ------------------------------------------------------------------
    # apply_opacity
    # ------------------------------------------------------------------

    def test_apply_opacity_delegates_to_pipeline(self, renderer):
        """The opacity value is passed straight through."""
        pipe = MagicMock(name="pipeline")
        renderer._pipelines[4] = pipe

        renderer.apply_opacity(4, 0.25)

        pipe.set_opacity.assert_called_once_with(0.25)

    def test_apply_opacity_unknown_node_id_is_logged_no_op(self, renderer):
        """An unregistered node id logs at debug, does not raise, delegates nothing."""
        pipe = MagicMock(name="pipeline")
        renderer._pipelines[4] = pipe

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.logger"
        ) as mock_logger:
            renderer.apply_opacity(9999, 0.25)  # must not raise

        mock_logger.debug.assert_called_once()
        pipe.set_opacity.assert_not_called()

    # ------------------------------------------------------------------
    # apply_diffuse_color
    # ------------------------------------------------------------------

    def test_apply_diffuse_color_delegates_to_pipeline(self, renderer):
        """r, g, b are passed straight through."""
        pipe = MagicMock(name="pipeline")
        renderer._pipelines[4] = pipe

        renderer.apply_diffuse_color(4, 1.0, 0.0, 0.0)

        pipe.set_diffuse_color.assert_called_once_with(1.0, 0.0, 0.0)

    def test_apply_diffuse_color_unknown_node_id_is_logged_no_op(self, renderer):
        """An unregistered node id logs at debug, does not raise, delegates nothing."""
        pipe = MagicMock(name="pipeline")
        renderer._pipelines[4] = pipe

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.logger"
        ) as mock_logger:
            renderer.apply_diffuse_color(9999, 1.0, 0.0, 0.0)  # must not raise

        mock_logger.debug.assert_called_once()
        pipe.set_diffuse_color.assert_not_called()

    # ------------------------------------------------------------------
    # apply_selected
    # ------------------------------------------------------------------

    def test_apply_selected_delegates_to_pipeline(self, renderer):
        """Selection state and the given colour are passed straight through."""
        pipe = MagicMock(name="pipeline")
        renderer._pipelines[4] = pipe

        renderer.apply_selected(4, True, [1.0, 0.0, 0.0])

        pipe.set_selected.assert_called_once_with(True, [1.0, 0.0, 0.0])

    def test_apply_selected_unknown_node_id_is_logged_no_op(self, renderer):
        """An unregistered node id logs at debug, does not raise, delegates nothing."""
        pipe = MagicMock(name="pipeline")
        renderer._pipelines[4] = pipe

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.logger"
        ) as mock_logger:
            renderer.apply_selected(9999, True, [1.0, 0.0, 0.0])  # must not raise

        mock_logger.debug.assert_called_once()
        pipe.set_selected.assert_not_called()

    # ------------------------------------------------------------------
    # apply_color_variable
    # ------------------------------------------------------------------

    def test_apply_color_variable_delegates_with_given_arguments(self, renderer):
        """The association is forwarded unchanged; spectrum_id is not forwarded."""
        pipe = MagicMock(name="pipeline")
        renderer._pipelines[4] = pipe

        renderer.apply_color_variable(
            4, "sp-1", VisorVtkVariableType.POINT, "pressure", 1, 0.0, 7.5
        )

        pipe.set_color_variable.assert_called_once_with(
            VisorVtkVariableType.POINT, "pressure", 1, 0.0, 7.5
        )

    def test_apply_color_variable_unknown_node_id_is_logged_no_op(self, renderer):
        """An unregistered node id logs at debug, does not raise, delegates nothing."""
        pipe = MagicMock(name="pipeline")
        renderer._pipelines[4] = pipe

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.logger"
        ) as mock_logger:
            renderer.apply_color_variable(
                9999, "sp-1", VisorVtkVariableType.POINT, "pressure", 1, 0.0, 7.5
            )  # must not raise

        mock_logger.debug.assert_called_once()
        pipe.set_color_variable.assert_not_called()

    # ------------------------------------------------------------------
    # clear_color_variable
    # ------------------------------------------------------------------

    def test_clear_color_variable_delegates_to_pipeline(self, renderer):
        pipe = MagicMock(name="pipeline")
        renderer._pipelines[4] = pipe

        renderer.clear_color_variable(4)

        pipe.clear_color_variable.assert_called_once_with()

    def test_clear_color_variable_unknown_node_id_is_logged_no_op(self, renderer):
        """An unregistered node id logs at debug, does not raise, delegates nothing."""
        pipe = MagicMock(name="pipeline")
        renderer._pipelines[4] = pipe

        with patch(
            "ansys.visor.viewer.renderer.local_renderer.logger"
        ) as mock_logger:
            renderer.clear_color_variable(9999)  # must not raise

        mock_logger.debug.assert_called_once()
        pipe.clear_color_variable.assert_not_called()


# ===========================================================================
# 4.  Camera
# ===========================================================================

class TestCamera:
    def test_reset_camera_delegates_to_vtk_renderer(self, renderer):
        bounds = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
        renderer.reset_camera(bounds)
        renderer._vtk_renderer.ResetCamera.assert_called_once_with(bounds)

    def test_get_camera_state_returns_none_initially(self, renderer):
        assert renderer.get_camera_state() is None

    def test_sync_camera_stores_state_for_get(self, renderer):
        cam = MagicMock(name="camera_state")
        renderer.sync_camera(cam)
        assert renderer.get_camera_state() is cam

    def test_reset_camera_writes_the_record(self, renderer):
        """The reset is authoritative and its result becomes the record.

        Pinned by a presence transition, never by values: what ResetCamera
        computes is a VTK product, and no assertion may rest on one.
        """
        assert renderer.get_camera_state() is None

        renderer.reset_camera([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])

        assert renderer.get_camera_state() is not None

    def test_reset_camera_record_is_read_from_the_active_camera(self, renderer):
        """The record is read back from the pipeline, not invented.

        The renderer's ``_vtk_renderer`` is a MagicMock, so ResetCamera
        computes nothing; every expected value here is a hand-written literal
        carried by the camera double, not a value VTK produced.

        This is the only assertion in the suite that can distinguish "read the
        pipeline" from "wrote a constant".  A manual refresh check cannot: the
        refresh reads the pipeline camera, which ResetCamera frames correctly
        whatever went into the record.
        """
        renderer.reset_camera([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])

        record = renderer.get_camera_state()
        assert record.position == CAMERA_DOUBLE_POSITION
        assert record.focal_point == CAMERA_DOUBLE_FOCAL_POINT
        assert record.view_up == CAMERA_DOUBLE_VIEW_UP
        assert record.clipping_range == CAMERA_DOUBLE_CLIPPING_RANGE
        assert record.parallel_projection is True
        assert record.view_angle == CAMERA_DOUBLE_VIEW_ANGLE
        assert record.parallel_scale == CAMERA_DOUBLE_PARALLEL_SCALE

    def test_sync_camera_projects_onto_the_pipeline_camera(self, renderer):
        """The record is projected onto the pipeline camera, in setter order.

        Every expected value is a hand-written literal, chosen distinct from
        the camera double's getters so that a projection reading the pipeline
        instead of the argument would fail rather than coincide.
        """
        camera_state = VisorCameraState(
            position=[1.0, 2.0, 3.0],
            focal_point=[4.0, 5.0, 6.0],
            view_up=[0.0, 0.0, 1.0],
            clipping_range=[7.0, 8.0],
            parallel_projection=False,
            view_angle=31.0,
            parallel_scale=9.0,
        )

        renderer.sync_camera(camera_state)

        camera = renderer._vtk_renderer.GetActiveCamera.return_value
        assert camera.calls == [
            ("SetPosition", [1.0, 2.0, 3.0]),
            ("SetFocalPoint", [4.0, 5.0, 6.0]),
            ("SetViewUp", [0.0, 0.0, 1.0]),
            ("SetClippingRange", [7.0, 8.0]),
            ("SetParallelProjection", False),
            ("SetViewAngle", 31.0),
            ("SetParallelScale", 9.0),
        ]

    def test_sync_camera_stores_the_object_without_copying(self, renderer):
        """Object identity is contractual: no defensive copy on the way in."""
        cam = VisorCameraState(
            position=[1.0, 2.0, 3.0],
            focal_point=[4.0, 5.0, 6.0],
            view_up=[0.0, 0.0, 1.0],
            clipping_range=[7.0, 8.0],
            parallel_projection=False,
            view_angle=31.0,
            parallel_scale=9.0,
        )

        renderer.sync_camera(cam)

        assert renderer.get_camera_state() is cam

    def test_serialize_camera_state_updates_the_states_from_the_active_camera_id(
        self, renderer
    ):
        """The re-serialise names the active camera, and nothing else.

        The id source is keyed on object identity, so every object other than
        the active camera resolves to a different, equally distinctive
        literal.  Asserting ``ACTIVE_CAMERA_WASM_ID`` therefore fails if the
        implementation names ``_render_window``, ``_vtk_renderer``, the
        interactor or the picker, rather than coinciding with them.  The
        render window has a literal of its own, so the previous call shape
        fails by name.  Asserting against
        ``GetId(renderer._vtk_renderer.GetActiveCamera())`` -- the expression
        production reads -- would pass in all of those cases and pin nothing.

        The expected value is the bare id production passes:
        ``UpdateStateFromObject`` takes a single id, not a sequence.
        """
        camera = renderer._vtk_renderer.GetActiveCamera()
        renderer._object_manager.GetId.side_effect = (
            lambda obj: ACTIVE_CAMERA_WASM_ID
            if obj is camera
            else RENDER_WINDOW_WASM_ID
            if obj is renderer._render_window
            else WRONG_OBJECT_WASM_ID
        )

        renderer.serialize_camera_state()

        renderer._object_manager.UpdateStateFromObject.assert_called_with(
            ACTIVE_CAMERA_WASM_ID
        )

    def test_serialize_camera_state_does_not_notify_the_client(self, renderer):
        """Serialise without pushing -- the whole reason this is not a flush.

        ``flush_wasm_state`` serialises *and* fires the client-side update,
        which rebuilds the scene and races the ``set_state`` that follows on
        the load path.  An implementation written as ``flush_wasm_state()``
        would make the camera current and would look correct here in every
        other respect; only this assertion separates them.
        """
        renderer.serialize_camera_state()

        renderer._local_view.update.assert_not_called()

    # -- set_projection -----------------------------------------------------
    #
    # The record half and the pipeline half are separate tests, and the
    # None-record path is two more: either half can silently do nothing while
    # the other succeeds, and the None path's two halves fail for different
    # reasons -- a seeded record is data loss deferred, a guarded pipeline
    # write is a projection that never reaches the view.

    def test_set_projection_writes_the_record_in_place_preserving_identity(
        self, renderer
    ):
        """Record half: the same object, mutated, never replaced.

        This is the assertion that pins Option A against Option B.  Object
        identity through ``get_camera_state`` is contractual -- the
        ``sync_camera`` docstring says callers rely on it -- so a body that
        rebuilt the record with ``model_copy`` would satisfy the value
        assertion and fail the identity one, which is what makes the two
        separable here.

        The record is seeded through ``sync_camera`` from a hand-written
        camera whose ``parallel_projection`` is the literal ``False``, so the
        write is a visible transition rather than a coincidence.
        """
        seeded = VisorCameraState(
            position=[1.0, 2.0, 3.0],
            focal_point=[4.0, 5.0, 6.0],
            view_up=[0.0, 0.0, 1.0],
            clipping_range=[7.0, 8.0],
            parallel_projection=False,
            view_angle=31.0,
            parallel_scale=9.0,
        )
        renderer.sync_camera(seeded)
        before = renderer.get_camera_state()

        renderer.set_projection(True)

        after = renderer.get_camera_state()
        assert before is after
        assert after is seeded
        assert after.parallel_projection is True

    def test_set_projection_writes_false_to_the_record(self, renderer):
        """The other direction, so a body hard-coding ``True`` fails.

        Record half only.  The seed carries ``True`` so that ``False`` is a
        transition and not the value that was already there.
        """
        seeded = VisorCameraState(
            position=[1.0, 2.0, 3.0],
            focal_point=[4.0, 5.0, 6.0],
            view_up=[0.0, 0.0, 1.0],
            clipping_range=[7.0, 8.0],
            parallel_projection=True,
            view_angle=31.0,
            parallel_scale=9.0,
        )
        renderer.sync_camera(seeded)

        renderer.set_projection(False)

        assert renderer.get_camera_state().parallel_projection is False

    def test_set_projection_applies_to_the_pipeline_camera(self, renderer):
        """Pipeline half: exactly one setter call, with the argument.

        Asserted as the whole call list, so a body that also wrote some other
        camera property fails rather than passing on the one call that was
        looked for.  The camera double's setters are recorded after the
        ``sync_camera`` seed is cleared, so the seven projection writes that
        seed performs do not appear here.
        """
        renderer._last_camera_state = None
        camera = renderer._vtk_renderer.GetActiveCamera.return_value
        camera.calls.clear()

        renderer.set_projection(True)

        assert camera.calls == [("SetParallelProjection", True)]

    def test_set_projection_with_no_record_leaves_the_record_none(self, renderer):
        """The ``None`` record is not seeded here, and that is deliberate.

        Sub-option (ii), pinned so a later session does not quietly seed it: a
        projection set before any camera has been written is not saved until
        the next ``reset_camera`` reads the pipeline and imports it.  That
        cost is named in the interface docstring, and this is the assertion
        that holds the tree to it.
        """
        assert renderer.get_camera_state() is None

        renderer.set_projection(True)

        assert renderer.get_camera_state() is None

    def test_set_projection_with_no_record_still_applies_to_the_pipeline(
        self, renderer
    ):
        """...and the pipeline write happens anyway, with one debug line.

        The pipeline write is unconditional, on both branches.  Its own test
        rather than another assertion above: "did not seed the record" and
        "still projected" are different failures, and a body that returned
        early on a ``None`` record would pass the first while leaving the
        toolbar click with no visible effect at all.
        """
        camera = renderer._vtk_renderer.GetActiveCamera.return_value
        camera.calls.clear()

        with patch("ansys.visor.viewer.renderer.local_renderer.logger") as log:
            renderer.set_projection(True)

        assert camera.calls == [("SetParallelProjection", True)]
        assert log.debug.call_count == 1


# ===========================================================================
# 5.  Render / flush delegation
# ===========================================================================

class TestRenderFlush:
    def test_render_calls_render_window_then_local_view_update(self, renderer):
        renderer.render()
        renderer._render_window.Render.assert_called_once()
        renderer._local_view.update.assert_called_once()

    def test_render_window_only_calls_render_window_not_local_view(self, renderer):
        renderer.render_window_only()
        renderer._render_window.Render.assert_called_once()
        renderer._local_view.update.assert_not_called()

    def test_flush_wasm_state_calls_local_view_update(self, renderer):
        """VisorLocalRenderer overrides the base no-op to push state to wasm."""
        renderer.flush_wasm_state()
        renderer._local_view.update.assert_called_once()



class TestPickGeometry:

    def test_pick_vertex_returns_nearest_point(self, renderer):
        """Vertex mode returns the cell point closest to the pick position."""
        pts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        dataset = _DummyDataset([_DummyCell(pts)])
        _seed_actor(renderer, 123, dataset)

        res = renderer.pick_geometry(123, 0, "vertex", (0.9, 0.1, 0.0))

        assert res["found"] is True
        assert res["mode"] == "vertex"
        assert tuple(res["position"]) == (1.0, 0.0, 0.0)

    def test_pick_edge_returns_closest_edge_endpoints_and_length(self, renderer):
        """Edge mode returns the two endpoints of the edge nearest to the pick."""
        pts = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)]
        dataset = _DummyDataset([_DummyCell(pts)])
        _seed_actor(renderer, 7, dataset)

        res = renderer.pick_geometry(7, 0, "edge", (2.01, 1.0, 0.0))

        assert res["found"] is True
        assert res["mode"] == "edge"
        assert tuple(res["pointA"]) == (2.0, 0.0, 0.0)
        assert tuple(res["pointB"]) == (2.0, 2.0, 0.0)
        assert pytest.approx(res["length"]) == 2.0

    def test_pick_face_returns_area_and_all_points(self, renderer):
        """Face mode returns the polygon area and every cell point."""
        pts = [(0, 0, 0), (1, 0, 0), (1, 2, 0), (0, 2, 0)]
        dataset = _DummyDataset([_DummyCell(pts)])
        _seed_actor(renderer, 5, dataset)

        res = renderer.pick_geometry(5, 0, "face", (0.5, 1.0, 0.0))

        assert res["found"] is True
        assert res["mode"] == "face"
        assert pytest.approx(res["area"]) == 2.0
        assert len(res["points"]) == 4

    def test_pick_negative_actor_id_returns_not_found(self, renderer):
        res = renderer.pick_geometry(-1, 0, "vertex", (0.0, 0.0, 0.0))
        assert res == {"found": False}

    def test_pick_negative_cell_id_returns_not_found(self, renderer):
        res = renderer.pick_geometry(1, -1, "vertex", (0.0, 0.0, 0.0))
        assert res == {"found": False}

    def test_pick_unregistered_actor_returns_not_found(self, renderer):
        """If no actor matches the given wasm id, pick returns not-found."""
        renderer._vtk_renderer.GetActors.return_value = _DummyActors([])
        res = renderer.pick_geometry(42, 0, "vertex", (0.0, 0.0, 0.0))
        assert res["found"] is False

    def test_pick_cell_id_out_of_range_returns_not_found(self, renderer):
        """Cell index beyond dataset size returns not-found."""
        dataset = _DummyDataset([_DummyCell([(0, 0, 0), (1, 0, 0), (0, 1, 0)])])
        _seed_actor(renderer, 10, dataset)
        res = renderer.pick_geometry(10, 99, "vertex", (0.0, 0.0, 0.0))
        assert res["found"] is False

    def test_pick_unknown_mode_returns_not_found(self, renderer):
        """An unrecognised mode string falls through to not-found."""
        pts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        dataset = _DummyDataset([_DummyCell(pts)])
        _seed_actor(renderer, 1, dataset)
        res = renderer.pick_geometry(1, 0, "INVALID_MODE", (0.0, 0.0, 0.0))
        assert res == {"found": False}

