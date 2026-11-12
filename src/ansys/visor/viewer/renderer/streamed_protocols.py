"""
Streamed-render protocols
=========================
The names a streamed view's renderer, window, loop bridge and state publisher
share, kept apart from :mod:`ansys.visor.viewer.renderer.server_renderer` so
that importing them does not import the off-screen VTK pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState

if TYPE_CHECKING:
    from vtkmodules.vtkRenderingCore import vtkRenderWindow

INITIAL_WINDOW_SIZE: tuple[int, int] = (300, 300)
"""Window size before the client reports its canvas; trame-rca's pre-resize image size."""

BACKGROUND_RGB: dict[bool, tuple[float, float, float]] = {
    False: (247 / 255, 247 / 255, 247 / 255),
    True: (54 / 255, 60 / 255, 67 / 255),
}
"""Viewer background per theme, keyed on dark.

The values of ``--visor-viewer-background`` in the client's
``public/css/theme-light.css`` and ``public/css/theme-dark.css``.
"""


class FrameRequester(Protocol):
    """Where a streamed renderer asks for a streamed frame."""

    def request_frame(self) -> None:
        """Ask for a streamed frame; callable from any thread."""


class ViewRecordPublisher(Protocol):
    """Where a streamed renderer publishes its camera and cross-section plane records."""

    def publish_camera(self, camera_state: VisorCameraState | None) -> None:
        """Publish the camera record to clients, or None when there is none; callable from any thread."""

    def publish_cross_section(self, cross_section_state: VisorCrossSectionState | None) -> None:
        """Publish the plane record to clients, or None when there is none; callable from any thread."""


class RcaRenderTarget(Protocol):
    """The renderer surface VisorRcaWindow captures from and resizes."""

    @property
    def render_window(self) -> vtkRenderWindow:
        """The window the capture reads and releases."""

    @property
    def background_rgb(self) -> tuple[float, float, float]:
        """The colour the placeholder frame is filled with."""

    def set_viewport_size(self, width: int, height: int) -> None:
        """Resize to the client canvas in device pixels."""

    def set_pixel_scale(self, pixel_scale: float) -> None:
        """Take the client's device pixels per CSS pixel."""

    def record_pipeline_camera(self) -> None:
        """Record and publish the camera after a gesture; caller holds the lock."""

    def record_cross_section_plane(self) -> None:
        """Record and publish a dragged plane after a gesture; caller holds the lock."""
