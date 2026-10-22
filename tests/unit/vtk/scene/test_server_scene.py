"""
Unit tests for VisorServerScene.

Each test builds a real VisorServerScene, so a real ServerRenderer and a real
trame-rca capture over its off-screen window, with a recording bridge in
place of the ServerLoopBridge.  No test renders a frame.  Expected colours
are the client CSS's 0-255 triples, written by hand; the VTK background is
read back into that form.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.vtk.scene.server_scene import VisorServerScene
from tests.helpers.utils.locks import LockSpy, lock_held_by_another_thread

LIGHT_CSS_RGB = (247, 247, 247)
DARK_CSS_RGB = (54, 60, 67)


class _RecordingBridge:
    """Counts frame requests and retries."""

    def __init__(self) -> None:
        self.request_count = 0
        self.retry_count = 0

    def request_frame(self) -> None:
        self.request_count += 1

    def retry_frame(self) -> None:
        self.retry_count += 1


def _css_rgb(rgb) -> tuple[int, int, int]:
    """A 0-1 VTK colour as the 0-255 triple a CSS variable holds."""
    return tuple(round(c * 255) for c in rgb)


def _background(scene: VisorServerScene) -> tuple[int, int, int]:
    return _css_rgb(scene._renderer._vtk_renderer.GetBackground())


@pytest.fixture
def bridge() -> _RecordingBridge:
    return _RecordingBridge()


@pytest.fixture
def scene(bridge) -> VisorServerScene:
    """A light-theme scene with no datasets; bridge counts start at zero."""
    s = VisorServerScene(MagicMock(name="server"), False, bridge, MagicMock(name="camera_publisher"))
    bridge.request_count = 0
    bridge.retry_count = 0
    return s


# ---------------------------------------------------------------------------
# Background follows the theme
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dark_mode", "expected"),
    [(False, LIGHT_CSS_RGB), (True, DARK_CSS_RGB)],
    ids=["light", "dark"],
)
def test_initial_background_follows_theme(bridge, dark_mode, expected):
    s = VisorServerScene(MagicMock(name="server"), dark_mode, bridge, MagicMock(name="camera_publisher"))
    assert _background(s) == expected


def test_dark_theme_change_recolors_background(scene):
    scene.apply_state(PersistedViewerStateV1.model_validate({"ui": {"darkTheme": True}, "scene": {}}))
    assert _background(scene) == DARK_CSS_RGB


def test_push_runtime_state_requests_one_frame(scene, bridge):
    scene._push_runtime_state(scene._current_runtime_state())
    assert bridge.request_count == 1


# ---------------------------------------------------------------------------
# set_dark_mode: the theme change that does not go through apply_state
# ---------------------------------------------------------------------------


def test_set_dark_mode_recolors_without_apply_state(scene):
    scene.set_dark_mode(True)
    assert _background(scene) == DARK_CSS_RGB


def test_set_dark_mode_sets_dark_mode(scene):
    scene.set_dark_mode(True)
    assert scene.dark_mode is True


def test_set_dark_mode_requests_one_frame(scene, bridge):
    scene.set_dark_mode(True)
    assert bridge.request_count == 1


def test_set_dark_mode_holds_lock(scene):
    scene._vtk_lock = LockSpy()
    depths = []
    set_background_rgb = scene._renderer.set_background_rgb

    def recording_set_background_rgb(background_rgb):
        depths.append(scene._vtk_lock.depth)
        set_background_rgb(background_rgb)

    scene._renderer.set_background_rgb = recording_set_background_rgb
    scene.set_dark_mode(True)
    assert depths == [1]


# ---------------------------------------------------------------------------
# Picking
# ---------------------------------------------------------------------------


def test_pick_part_at_holds_lock(scene):
    scene._vtk_lock = LockSpy()
    depths = []

    def recording_pick_part_at(x, y):
        depths.append(scene._vtk_lock.depth)
        return None

    scene._renderer.pick_part_at = recording_pick_part_at
    scene.pick_part_at(31, 17)
    assert depths == [1]


def test_pick_part_at_returns_the_renderer_pick(scene):
    scene._renderer.pick_part_at = lambda x, y: 42 if (x, y) == (31, 17) else None
    assert scene.pick_part_at(31, 17) == 42


# ---------------------------------------------------------------------------
# RCA window
# ---------------------------------------------------------------------------


def test_rca_window_wraps_scene_lock(scene, bridge):
    with lock_held_by_another_thread(scene._vtk_lock):
        _ = scene.rca_window.img_cols_rows
    assert bridge.retry_count == 1

