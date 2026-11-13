"""
Integration tests: a scene write on another thread leaves the next frame drawable.

Builds a real VisorServerScene, so its GlContextLock over a real off-screen
window, and draws every frame on the test's own thread through the scene's
RCA window.  The first frame is drawn on that thread too: the window's hidden
native window belongs to the thread that first draws it, and a thread that
exits takes it with it.  The writes under test run on a second thread, as a
REST call does.  Needs an OpenGL context; runs unmarked in the gates.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from vtkmodules.vtkFiltersSources import vtkSphereSource

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.vtk.scene.server_scene import VisorServerScene


class _NullBridge:
    """Accepts frame requests and retries."""

    def request_frame(self) -> None:
        pass

    def retry_frame(self) -> None:
        pass


def _run_on_other_thread(target, *args) -> None:
    thread = threading.Thread(target=target, args=args)
    thread.start()
    thread.join()


def _centre_pixel(scene: VisorServerScene) -> tuple[int, int, int]:
    image, _, _ = scene.rca_window.img_cols_rows
    return tuple(int(c) for c in image[150, 150])


def _look_at_origin_from_z(scene: VisorServerScene) -> None:
    """Point the camera down -z at the origin from z = 9; caller holds the lock."""
    scene._renderer.sync_camera(
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


@pytest.fixture
def scene() -> VisorServerScene:
    """A light-theme scene with no datasets and one frame drawn."""
    s = VisorServerScene(MagicMock(name="server"), False, _NullBridge(), MagicMock(name="publisher"))
    s.rca_window.img_cols_rows
    return s


def test_frame_after_cross_section_off_on_another_thread_is_background(scene):
    """Turning the plane widget off makes the context current on its thread; the next frame still draws."""
    with scene._vtk_lock:
        scene._renderer.update_bounds([-0.5, 0.5, -0.5, 0.5, -0.5, 0.5])
        _look_at_origin_from_z(scene)
        scene.set_cross_section_visibility(True)
    scene.rca_window.img_cols_rows

    _run_on_other_thread(scene.set_cross_section_visibility, False)

    assert _centre_pixel(scene) == (247, 247, 247)


def test_frame_after_clear_on_another_thread_is_background(scene):
    """Removing a part makes the context current on its thread; the next frame still draws."""
    source = vtkSphereSource()
    source.Update()
    with scene._vtk_lock:
        scene._renderer.register_node(SimpleNamespace(id=7), source.GetOutput())
        _look_at_origin_from_z(scene)
    scene.rca_window.img_cols_rows

    _run_on_other_thread(scene.clear)

    assert _centre_pixel(scene) == (247, 247, 247)
