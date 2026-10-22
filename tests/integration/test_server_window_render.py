"""
Integration test: one real off-screen frame through VisorRcaWindow.

Builds a real ServerRenderer, trame-rca's real VtkRemoteControlledArea over its
window, and a real lock, then reads one frame with the lock free.  Needs an
OpenGL context; runs unmarked in the gates.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from trame_rca.rca.vtk_rca import VtkRemoteControlledArea
from vtkmodules.vtkFiltersSources import vtkSphereSource

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.renderer.server_renderer import ServerRenderer
from ansys.visor.viewer.renderer.server_window import VisorRcaWindow


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


def test_first_frame_is_background():
    renderer = ServerRenderer((0.2, 0.4, 0.6), _RecordingFrameRequester(), MagicMock(name="camera_publisher"))
    capture = VtkRemoteControlledArea(renderer.render_window)
    window = VisorRcaWindow(capture, renderer, threading.RLock(), lambda: None)

    image, cols, rows = window.img_cols_rows

    assert (cols, rows) == (300, 300)
    assert tuple(int(c) for c in image[150, 150]) == (51, 102, 153)


# ---------------------------------------------------------------------------
# Gesture end records and publishes the pipeline camera
# ---------------------------------------------------------------------------


def _event(event_type: str, x: int, y: int, **extra) -> dict:
    """One trame-rca interaction event over the 300 x 300 window."""
    return {"type": event_type, "x": x, "y": y, "w": 300, "h": 300, "ctrlKey": 0, "altKey": 0, "shiftKey": 0, **extra}


@pytest.fixture
def requester() -> _RecordingFrameRequester:
    return _RecordingFrameRequester()


@pytest.fixture
def publisher() -> _RecordingCameraPublisher:
    return _RecordingCameraPublisher()


@pytest.fixture
def renderer(requester, publisher) -> ServerRenderer:
    """A unit sphere viewed from z = 9, with one frame drawn; recorders cleared after setup."""
    r = ServerRenderer((0.2, 0.4, 0.6), requester, publisher)
    source = vtkSphereSource()
    source.Update()
    r.register_node(SimpleNamespace(id=7), source.GetOutput())
    r.sync_camera(
        VisorCameraState(
            position=[0.0, 0.0, 9.0],
            focal_point=[0.0, 0.0, 0.0],
            view_up=[0.0, 1.0, 0.0],
            clipping_range=[1.0, 20.0],
            parallel_projection=False,
            view_angle=30.0,
            parallel_scale=3.0,
        )
    )
    requester.count = 0
    publisher.cameras.clear()
    return r


@pytest.fixture
def window(renderer) -> VisorRcaWindow:
    w = VisorRcaWindow(VtkRemoteControlledArea(renderer.render_window), renderer, threading.RLock(), lambda: None)
    w.img_cols_rows
    return w


def test_wheel_records_pipeline_camera(window, renderer):
    window.process_interaction_event(_event("MouseWheel", 150, 150, spinY=1))
    window.img_cols_rows
    record = renderer.get_camera_state()
    assert record.position != [0.0, 0.0, 9.0]
    assert record.focal_point == [0.0, 0.0, 0.0]


def test_wheel_publishes_recorded_camera(window, renderer, publisher):
    window.process_interaction_event(_event("MouseWheel", 150, 150, spinY=1))
    window.img_cols_rows
    assert len(publisher.cameras) == 1
    assert publisher.cameras[0] is renderer.get_camera_state()


def test_wheel_requests_no_frame(window, requester):
    window.process_interaction_event(_event("MouseWheel", 150, 150, spinY=1))
    window.img_cols_rows
    assert requester.count == 0


def test_drag_publishes_camera_at_release_only(window, publisher):
    window.process_interaction_event(_event("LeftButtonPress", 150, 150))
    window.process_interaction_event(_event("MouseMove", 170, 160))
    window.process_interaction_event(_event("MouseMove", 190, 170))
    window.img_cols_rows
    assert publisher.cameras == []
    window.process_interaction_event(_event("LeftButtonRelease", 190, 170))
    window.img_cols_rows
    assert len(publisher.cameras) == 1


# ---------------------------------------------------------------------------
# A cross-section drag moves the clip plane and records it at gesture end
# ---------------------------------------------------------------------------


@pytest.fixture
def plane_window(renderer, requester) -> VisorRcaWindow:
    """The sphere scene with the widget placed on its bounds and turned on; one frame drawn, requests cleared."""
    renderer.update_bounds([-0.5, 0.5, -0.5, 0.5, -0.5, 0.5])
    renderer.set_cross_section_visibility(True)
    w = VisorRcaWindow(VtkRemoteControlledArea(renderer.render_window), renderer, threading.RLock(), lambda: None)
    w.img_cols_rows
    requester.count = 0
    return w


def _drag_plane_handle(window: VisorRcaWindow) -> None:
    """Press on the plane's normal arrow at the view centre and move up, then draw a frame; no release."""
    window.process_interaction_event(_event("LeftButtonPress", 150, 150))
    for step in range(1, 6):
        window.process_interaction_event(_event("MouseMove", 150, 150 + 15 * step))
    window.img_cols_rows


def _release_plane_handle(window: VisorRcaWindow) -> None:
    window.process_interaction_event(_event("LeftButtonRelease", 150, 225))
    window.img_cols_rows


def test_plane_drag_moves_clip_plane_before_release(plane_window, renderer):
    _drag_plane_handle(plane_window)
    assert renderer._cross_section_widget.plane.GetNormal() != (0.0, 0.0, 1.0)


def test_plane_drag_records_plane_at_release_only(plane_window, renderer):
    _drag_plane_handle(plane_window)
    assert renderer.get_cross_section_plane().normal == [0.0, 0.0, 1.0]
    _release_plane_handle(plane_window)
    assert renderer.get_cross_section_plane().normal != [0.0, 0.0, 1.0]


def test_plane_drag_release_requests_no_frame(plane_window, requester):
    _drag_plane_handle(plane_window)
    _release_plane_handle(plane_window)
    assert requester.count == 0


def test_gesture_before_bounds_leaves_plane_seed(window, renderer):
    window.process_interaction_event(_event("MouseWheel", 150, 150, spinY=1))
    window.img_cols_rows
    renderer.update_bounds([-0.5, 0.5, -0.5, 0.5, -0.5, 0.5])
    assert renderer.get_cross_section_plane().origin == [0.0, 0.0, -0.625]

