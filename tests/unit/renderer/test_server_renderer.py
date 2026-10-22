"""
Unit tests for ServerRenderer.

Every test builds a real ServerRenderer (an off-screen VTK window that is
never rendered) with a recording frame requester and a recording camera
publisher.  Expected values are hand-written literals.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from vtkmodules.vtkCommonCore import vtkCommand
from vtkmodules.vtkFiltersSources import vtkSphereSource
from vtkmodules.vtkRenderingCore import vtkRenderWindow

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.renderer.server_renderer import ServerRenderer

PART_NODE_ID = 7
PART_BOUNDS = [-1.0, 1.0, -1.0, 1.0, -1.0, 1.0]


class _RecordingFrameRequester:
    """Counts frame requests."""

    def __init__(self) -> None:
        self.count = 0

    def request_frame(self) -> None:
        self.count += 1


class _RecordingCameraPublisher:
    """Records every published camera record."""

    def __init__(self) -> None:
        self.cameras: list = []

    def publish_camera(self, camera_state) -> None:
        self.cameras.append(camera_state)


def _unit_sphere():
    source = vtkSphereSource()
    source.SetRadius(1.0)
    source.SetThetaResolution(32)
    source.SetPhiResolution(32)
    source.Update()
    return source.GetOutput()


def _register_part(renderer: ServerRenderer) -> None:
    renderer.register_node(SimpleNamespace(id=PART_NODE_ID), _unit_sphere())


@pytest.fixture
def requester() -> _RecordingFrameRequester:
    return _RecordingFrameRequester()


@pytest.fixture
def publisher() -> _RecordingCameraPublisher:
    return _RecordingCameraPublisher()


@pytest.fixture
def renderer(requester, publisher) -> ServerRenderer:
    """ServerRenderer with one unit-sphere part registered and the camera reset to it."""
    r = ServerRenderer((0.2, 0.4, 0.6), requester, publisher)
    _register_part(r)
    r.reset_camera(PART_BOUNDS)
    requester.count = 0
    return r


def _outline_actor(renderer: ServerRenderer):
    """The bounding-box outline: the one renderer actor that is not a part."""
    part_actors = [pipe.actor for pipe in renderer._pipelines.values()]
    actors = renderer._vtk_renderer.GetActors()
    others = [actors.GetItemAsObject(i) for i in range(actors.GetNumberOfItems())]
    others = [a for a in others if not any(a is p for p in part_actors)]
    assert len(others) == 1
    return others[0]


# ---------------------------------------------------------------------------
# Every write ends in exactly one frame request
# ---------------------------------------------------------------------------

_CAMERA = VisorCameraState(
    position=[0.0, 0.0, 9.0],
    focal_point=[0.0, 0.0, 0.0],
    view_up=[0.0, 1.0, 0.0],
    clipping_range=[1.0, 20.0],
    parallel_projection=False,
    view_angle=25.0,
    parallel_scale=3.0,
)

_WRITES = {
    "apply_visibility": lambda r: r.apply_visibility(PART_NODE_ID, False),
    "apply_opacity": lambda r: r.apply_opacity(PART_NODE_ID, 0.5),
    "apply_diffuse_color": lambda r: r.apply_diffuse_color(PART_NODE_ID, 0.9, 0.1, 0.3),
    "apply_selected": lambda r: r.apply_selected(PART_NODE_ID, True, [0.9, 0.1, 0.3]),
    "apply_color_variable": lambda r: r.apply_color_variable(
        PART_NODE_ID, VisorVtkVariableType.POINT, "Normals", -1, 0.0, 1.0
    ),
    "clear_color_variable": lambda r: r.clear_color_variable(PART_NODE_ID),
    "reset_camera": lambda r: r.reset_camera(PART_BOUNDS),
    "sync_camera": lambda r: r.sync_camera(_CAMERA),
    "set_projection": lambda r: r.set_projection(True),
    "set_edges_visible": lambda r: r.set_edges_visible(True),
    "sync_cross_section_plane": lambda r: r.sync_cross_section_plane(
        [0.0, 0.0, 0.5], [0.0, 1.0, 0.0]
    ),
    "set_cross_section_visibility": lambda r: r.set_cross_section_visibility(True),
    "set_bounding_box_visibility": lambda r: r.set_bounding_box_visibility(True),
}


@pytest.mark.parametrize("write", list(_WRITES.values()), ids=list(_WRITES.keys()))
def test_each_write_requests_one_frame(renderer, requester, write):
    write(renderer)
    assert requester.count == 1


def test_render_requests_a_frame(renderer, requester):
    renderer.render()
    assert requester.count == 1


# ---------------------------------------------------------------------------
# Camera writes publish the camera record
# ---------------------------------------------------------------------------


def test_sync_camera_publishes_record(renderer, publisher):
    # A record of its own: sync_camera stores it by identity, and a later
    # set_projection on that renderer would mutate a shared one in place.
    renderer.sync_camera(
        VisorCameraState(
            position=[0.0, 0.0, 9.0],
            focal_point=[0.0, 0.0, 0.0],
            view_up=[0.0, 1.0, 0.0],
            clipping_range=[1.0, 20.0],
            parallel_projection=False,
            view_angle=25.0,
            parallel_scale=3.0,
        )
    )
    assert publisher.cameras[-1].model_dump(by_alias=True) == {
        "position": [0.0, 0.0, 9.0],
        "focalPoint": [0.0, 0.0, 0.0],
        "viewUp": [0.0, 1.0, 0.0],
        "clippingRange": [1.0, 20.0],
        "parallelProjection": False,
        "viewAngle": 25.0,
        "parallelScale": 3.0,
    }


# ---------------------------------------------------------------------------
# Never renders
# ---------------------------------------------------------------------------


class _ObservedServerRenderer(ServerRenderer):
    """Counts StartEvent on its window from the moment the window exists."""

    def _initialize_render_window(self) -> vtkRenderWindow:
        window = super()._initialize_render_window()
        self.render_starts = 0

        def count_start(*_):
            self.render_starts += 1

        window.AddObserver(vtkCommand.StartEvent, count_start)
        return window


def test_never_renders(requester, publisher):
    r = _ObservedServerRenderer((0.2, 0.4, 0.6), requester, publisher)
    _register_part(r)
    r.reset_camera(PART_BOUNDS)
    for write in _WRITES.values():
        write(r)
    r.update_bounds(PART_BOUNDS)
    r.update_actor_count(1)
    r.set_viewport_size(64, 48)
    r.pick_part_at(32, 24)
    r.render()
    assert r.render_starts == 0


# ---------------------------------------------------------------------------
# Server-only surface and widgets
# ---------------------------------------------------------------------------


def test_set_viewport_size_resizes_window(renderer):
    renderer.set_viewport_size(64, 48)
    assert renderer.render_window.GetSize() == (64, 48)


def test_set_viewport_size_fits_orientation_widget(renderer):
    renderer.set_viewport_size(1200, 700)
    representation = renderer._orientation_widget._VisorOrientationWidget__widget.GetRepresentation()
    assert representation.GetSize() == (105, 105)


def test_set_background_rgb_sets_vtk_background(renderer):
    renderer.set_background_rgb((0.25, 0.5, 0.75))
    assert renderer._vtk_renderer.GetBackground() == (0.25, 0.5, 0.75)


def test_set_background_rgb_sets_background_rgb(renderer):
    renderer.set_background_rgb((0.25, 0.5, 0.75))
    assert renderer.background_rgb == (0.25, 0.5, 0.75)


def test_cross_section_visibility_turns_widget_on(renderer):
    renderer.set_cross_section_visibility(True)
    assert renderer._cross_section_widget.is_on is True


def test_bounding_box_visibility_reapplied_on_part_count(requester, publisher):
    r = ServerRenderer((0.2, 0.4, 0.6), requester, publisher)
    r.set_bounding_box_visibility(True)
    assert _outline_actor(r).GetVisibility() == 0
    r.update_actor_count(1)
    assert _outline_actor(r).GetVisibility() == 1


def test_bounding_box_hidden_when_part_count_drops_to_zero(requester, publisher):
    r = ServerRenderer((0.2, 0.4, 0.6), requester, publisher)
    r.set_bounding_box_visibility(True)
    r.update_actor_count(1)
    r.update_actor_count(0)
    assert _outline_actor(r).GetVisibility() == 0


def test_annotation_is_none(renderer):
    assert renderer.build_renderer_annotation() is None


# ---------------------------------------------------------------------------
# Picking
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [(150, 150, PART_NODE_ID), (2, 2, None)],
    ids=["hit", "miss"],
)
def test_pick_part_at_hit_and_miss(renderer, x, y, expected):
    assert renderer.pick_part_at(x, y) == expected


@pytest.mark.parametrize(
    ("outline_bounds", "x", "y", "expected"),
    [
        # An outline edge beside the part, with nothing behind it.
        ([-1.3, 1.3, -1.3, 1.3, -0.5, 0.5], 267, 150, None),
        # An outline edge between the camera and the part.
        ([0.0, 0.5, -0.5, 0.5, 1.2, 1.5], 150, 150, PART_NODE_ID),
    ],
    ids=["outline_outside_part", "outline_in_front_of_part"],
)
def test_pick_part_at_skips_the_outline(renderer, outline_bounds, x, y, expected):
    renderer.update_bounds(outline_bounds)
    # update_bounds moves the cross-section plane, which clips the part;
    # put the plane behind everything so the part is whole.
    renderer.sync_cross_section_plane([0.0, 0.0, -5.0], [0.0, 0.0, 1.0])
    renderer.set_bounding_box_visibility(True)
    renderer.update_actor_count(1)
    assert _outline_actor(renderer).GetVisibility() == 1
    assert renderer.pick_part_at(x, y) == expected

