"""
Unit tests for IRenderer / VisorLocalRenderer.

Coverage targets
----------------
1.  Node lifecycle  -- register_node / deregister_node (the non-trivial seam).
2.  Interface conformance -- NullRenderer and VisorLocalRenderer both satisfy
    IRenderer's abstract contract.
3.  Per-part visual mutations -- one focused test per property;
    tests assert they accept their arguments and return None.
4.  Camera round-trip -- reset_camera, sync_camera / get_camera_state.
5.  Render / flush delegation.
6.  pick_geometry -- vertex, edge, face modes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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
    """Each method accepts its contract arguments and returns None without raising."""

    def test_apply_visibility(self, renderer):
        assert renderer.apply_visibility(1, True) is None

    def test_apply_opacity(self, renderer):
        assert renderer.apply_opacity(1, 0.5) is None

    def test_apply_diffuse_color(self, renderer):
        assert renderer.apply_diffuse_color(1, 1.0, 0.0, 0.0) is None

    def test_apply_edge_visibility(self, renderer):
        assert renderer.apply_edge_visibility(1, False) is None

    def test_apply_selected(self, renderer):
        assert renderer.apply_selected(1, True, [1.0, 0.0, 0.0]) is None

    def test_apply_color_variable(self, renderer):
        assert (
            renderer.apply_color_variable(1, "sp-1", "POINT", "pressure", -1, 0.0, 1.0)
            is None
        )

    def test_clear_color_variable(self, renderer):
        assert renderer.clear_color_variable(1) is None

    def test_refresh_color_variable_range(self, renderer):
        assert (
            renderer.refresh_color_variable_range(1, "sp-1", "CELL", "temp", 0)
            is None
        )


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

