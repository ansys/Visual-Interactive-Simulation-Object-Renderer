"""
Integration test: a server-rendering viewer pushes its first frame.

Starts a real ``Visor(rendering_mode="server")`` with no client attached and
waits for trame-rca to hand a frame to ``StreamManager.push_content``.  Needs
an OpenGL context; runs unmarked in the gates.
"""

from __future__ import annotations

import time
from unittest.mock import patch

from trame_rca.protocol import StreamManager

from ansys.visor.viewer import Visor
from ansys.visor.viewer.core.net import find_unused_port

FIRST_FRAME_TIMEOUT_S = 5.0


def test_first_frame_is_pushed():
    calls: list[str] = []
    errors: list[BaseException] = []
    original = StreamManager.push_content

    def recording_push(self, area_name, metadata, content):
        calls.append(area_name)
        try:
            return original(self, area_name, metadata, content)
        except BaseException as exc:
            errors.append(exc)
            raise

    port = find_unused_port("localhost")
    with patch.object(StreamManager, "push_content", recording_push):
        vis = Visor(rendering_mode="server", url=f"http://localhost:{port}")
        vis.start()
        try:
            deadline = time.monotonic() + FIRST_FRAME_TIMEOUT_S
            while not calls and time.monotonic() < deadline:
                time.sleep(0.05)
        finally:
            vis.stop()

    assert calls[:1] == ["view"]
    assert errors == []

