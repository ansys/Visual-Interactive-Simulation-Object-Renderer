"""
ServerRenderer
==============
:class:`VtkPipelineRenderer` implementation for server-side rendering.

Owns an off-screen VTK pipeline and presents each write by asking a
:class:`FrameRequester` for a streamed frame.  It never calls ``Render()``
itself: every render happens on the streaming path, under the scene lock.
"""

from __future__ import annotations

from typing import Protocol

# Registers the OpenGL2 factory overrides, so vtkRenderWindow() is a
# concrete off-screen-capable window rather than the abstract base.
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
from vtkmodules.vtkCommonCore import vtkObject
from vtkmodules.vtkRenderingCore import vtkRenderWindow

from ansys.visor.viewer.renderer.pipeline_renderer import VtkPipelineRenderer

INITIAL_WINDOW_SIZE: tuple[int, int] = (300, 300)
"""Window size before the client reports its canvas; trame-rca's pre-resize image size."""


class FrameRequester(Protocol):
    """Where a ServerRenderer asks for a streamed frame."""

    def request_frame(self) -> None:
        """Ask for a streamed frame; callable from any thread."""


class ServerRenderer(VtkPipelineRenderer):
    """Off-screen VTK pipeline whose writes are presented by requesting a streamed frame."""

    _background_rgb: tuple[float, float, float]
    _frame_requester: FrameRequester
    _bounding_box_visible: bool

    def __init__(
        self,
        background_rgb: tuple[float, float, float],
        frame_requester: FrameRequester,
    ) -> None:
        """Build the off-screen pipeline; every write ends in a frame request."""
        # Both are read during the base build: the background by
        # _initialize_vtk_renderer, the requester by any publish hook.
        self._background_rgb = background_rgb
        self._frame_requester = frame_requester
        self._bounding_box_visible = False
        super().__init__()

    # ------------------------------------------------------------------
    # Server-only surface
    # ------------------------------------------------------------------

    @property
    def render_window(self) -> vtkRenderWindow:
        """The window the RCA capture reads."""
        return self._render_window

    def set_viewport_size(self, width: int, height: int) -> None:
        """Resize the window and its interactor to the client canvas in device pixels.

        Requests no frame: the resize path that calls this schedules its own.
        """
        self._render_window_interactor.UpdateSize(width, height)

    # ------------------------------------------------------------------
    # IRenderer: wire contract
    # ------------------------------------------------------------------

    def build_renderer_annotation(self) -> None:
        """None: no client-side handles."""
        return None

    # ------------------------------------------------------------------
    # IRenderer: widget visibility
    # ------------------------------------------------------------------

    def set_cross_section_visibility(self, visible: bool) -> None:
        """Turn the plane widget on or off, then request a frame."""
        if visible:
            self._cross_section_widget.turn_on()
        else:
            self._cross_section_widget.turn_off()
        self._frame_requester.request_frame()

    def set_bounding_box_visibility(self, visible: bool) -> None:
        """Show or hide the outline, then request a frame; remembered for part-count changes."""
        self._bounding_box_visible = visible
        self._apply_bounding_box_visibility()
        self._frame_requester.request_frame()

    def update_actor_count(self, count: int) -> None:
        """Record the part count and re-apply the remembered outline visibility.

        The outline's ``show`` does nothing while the part count is zero, so a
        visibility set before any part exists takes effect only here.
        """
        super().update_actor_count(count)
        self._apply_bounding_box_visibility()

    def _apply_bounding_box_visibility(self) -> None:
        """Hide the outline, then show it if remembered visible; show() is a no-op with no parts."""
        self._bounding_box_widget.hide()
        if self._bounding_box_visible:
            self._bounding_box_widget.show()

    # ------------------------------------------------------------------
    # IRenderer: render
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Request a frame; never renders on the calling thread."""
        self._frame_requester.request_frame()

    # ------------------------------------------------------------------
    # VtkPipelineRenderer: publish hooks
    # ------------------------------------------------------------------

    def _publish_object(self, vtk_object: vtkObject) -> None:
        """Request a frame showing the written object."""
        self._frame_requester.request_frame()

    def _publish_part_mapper(self, node_id: int) -> None:
        """Request a frame showing the written mapper."""
        self._frame_requester.request_frame()

    def _publish_camera(self) -> None:
        """Request a frame from the written camera."""
        self._frame_requester.request_frame()

    def _publish_cross_section(self) -> None:
        """Request a frame showing the written plane."""
        self._frame_requester.request_frame()

    # ------------------------------------------------------------------
    # VtkPipelineRenderer: backend hooks
    # ------------------------------------------------------------------

    @property
    def background_rgb(self) -> tuple[float, float, float]:
        """The colour the window clears to."""
        return self._background_rgb

    def _initialize_render_window(self) -> vtkRenderWindow:
        render_window = vtkRenderWindow()
        render_window.SetOffScreenRendering(1)
        render_window.ShowWindowOff()
        render_window.SetMultiSamples(0)
        render_window.SetSize(*INITIAL_WINDOW_SIZE)
        render_window.AddRenderer(self._vtk_renderer)
        return render_window

    def _prepare_widgets(self) -> None:
        """Stop the interactor from rendering, before any widget is turned on."""
        self._render_window_interactor.EnableRenderOff()


