"""
Integration test: one real off-screen frame through VisorRcaWindow.

Builds a real ServerRenderer, trame-rca's real VtkRemoteControlledArea over its
window, and a real lock, then reads one frame with the lock free.  Needs an
OpenGL context; runs unmarked in the gates.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from trame_rca.rca.vtk_rca import VtkRemoteControlledArea

from ansys.visor.viewer.renderer.server_renderer import ServerRenderer
from ansys.visor.viewer.renderer.server_window import VisorRcaWindow


class _RecordingFrameRequester:
    """Counts frame requests."""

    def __init__(self) -> None:
        self.count = 0

    def request_frame(self) -> None:
        self.count += 1


def test_first_frame_is_background():
    renderer = ServerRenderer((0.2, 0.4, 0.6), _RecordingFrameRequester(), MagicMock(name="camera_publisher"))
    capture = VtkRemoteControlledArea(renderer.render_window)
    window = VisorRcaWindow(capture, renderer, threading.RLock(), lambda: None)

    image, cols, rows = window.img_cols_rows

    assert (cols, rows) == (300, 300)
    assert tuple(int(c) for c in image[150, 150]) == (51, 102, 153)

