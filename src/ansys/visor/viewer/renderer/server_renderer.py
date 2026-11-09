"""
ServerRenderer
==============
:class:`VtkPipelineRenderer` implementation for server-side rendering.

Owns an off-screen VTK pipeline and presents each write by asking a
:class:`FrameRequester` for a streamed frame.  It never calls ``Render()``
itself: every render happens on the streaming path, under the scene lock.
Each camera and cross-section plane write also hands the record to a
:class:`ViewRecordPublisher`, since a client of a streamed view has no camera
or plane of its own to read.
"""

from __future__ import annotations

from typing import Protocol

# Registers the OpenGL2 factory overrides, so vtkRenderWindow() is a
# concrete off-screen-capable window rather than the abstract base.
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
from vtkmodules.vtkCommonCore import vtkObject
from vtkmodules.vtkRenderingCore import vtkRenderWindow

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState
from ansys.visor.viewer.renderer.pipeline_renderer import VtkPipelineRenderer

INITIAL_WINDOW_SIZE: tuple[int, int] = (300, 300)
"""Window size before the client reports its canvas; trame-rca's pre-resize image size."""


class FrameRequester(Protocol):
    """Where a ServerRenderer asks for a streamed frame."""

    def request_frame(self) -> None:
        """Ask for a streamed frame; callable from any thread."""


class ViewRecordPublisher(Protocol):
    """Where a ServerRenderer publishes its camera and cross-section plane records."""

    def publish_camera(self, camera_state: VisorCameraState | None) -> None:
        """Publish the camera record to clients, or None when there is none; callable from any thread."""

    def publish_cross_section(self, cross_section_state: VisorCrossSectionState | None) -> None:
        """Publish the plane record to clients, or None when there is none; callable from any thread."""


class ServerRenderer(VtkPipelineRenderer):
    """Off-screen VTK pipeline whose writes are presented by requesting a streamed frame."""

    _background_rgb: tuple[float, float, float]
    _frame_requester: FrameRequester
    _view_record_publisher: ViewRecordPublisher
    _bounding_box_visible: bool

    def __init__(
        self,
        background_rgb: tuple[float, float, float],
        frame_requester: FrameRequester,
        view_record_publisher: ViewRecordPublisher,
    ) -> None:
        """Build the off-screen pipeline; every write ends in a frame request, every camera or plane write also publishes the record."""
        # All three are read during the base build: the background by
        # _initialize_vtk_renderer, the requester and publisher by any publish hook.
        self._background_rgb = background_rgb
        self._frame_requester = frame_requester
        self._view_record_publisher = view_record_publisher
        self._bounding_box_visible = False
        super().__init__()
        self._cross_section_widget.link_plane_to_handle()
        self._orientation_widget.animate_off()

    # ------------------------------------------------------------------
    # Server-only surface
    # ------------------------------------------------------------------

    @property
    def render_window(self) -> vtkRenderWindow:
        """The window the RCA capture reads."""
        return self._render_window

    def set_viewport_size(self, width: int, height: int) -> None:
        """Resize the window and its interactor to the client canvas in device pixels, and fit the orientation widget to it.

        Requests no frame: the resize path that calls this schedules its own.
        """
        self._render_window_interactor.UpdateSize(width, height)
        self._orientation_widget.fit_to_window(width, height)

    def set_background_rgb(self, background_rgb: tuple[float, float, float]) -> None:
        """Clear to this colour from the next frame.

        Requests no frame: the caller requests one once its other writes are done.
        """
        self._background_rgb = background_rgb
        self._vtk_renderer.SetBackground(background_rgb)

    def record_pipeline_camera(self) -> None:
        """Record the pipeline camera through the ``sync_camera`` step and publish it.

        The step is :meth:`sync_camera`'s without its frame request: the
        caller is producing a frame already.  Takes no lock; the caller holds
        the scene lock.
        """
        self._write_camera(self._read_pipeline_camera())
        self._publish_camera_record()

    def record_cross_section_plane(self) -> None:
        """Record a dragged clip plane through the ``sync_cross_section_plane`` step and publish it; requests no frame.

        Does nothing when no drag step ran since the last call.  Reads the
        clip plane, not the handle: the handle clamps its origin to the widget
        bounds and normalises its normal, so reading it would rewrite a loaded
        plane that no drag touched.  The step is
        :meth:`sync_cross_section_plane`'s without its frame request: the
        caller is producing a frame already.  Takes no lock; the caller holds
        the scene lock.
        """
        if not self._cross_section_widget.take_handle_moved():
            return
        plane = self._cross_section_widget.plane
        self._write_cross_section(list(plane.GetOrigin()), list(plane.GetNormal()))
        self._publish_cross_section_record()

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

    def update_bounds(self, bounds: list[float]) -> None:
        """See :meth:`VtkPipelineRenderer.update_bounds`; then publish the plane record, which the first call seeds; requests no frame.

        Publishes after the base call, so the first call publishes the seeded
        record rather than ``None``.
        """
        super().update_bounds(bounds)
        self._publish_cross_section_record()

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
        """Publish the camera record, then request a frame from the written camera."""
        self._publish_camera_record()
        self._frame_requester.request_frame()

    def _publish_camera_record(self) -> None:
        """Hand the camera record to the record publisher; requests no frame."""
        self._view_record_publisher.publish_camera(self.get_camera_state())

    def _publish_cross_section(self) -> None:
        """Publish the plane record, then request a frame showing the written plane."""
        self._publish_cross_section_record()
        self._frame_requester.request_frame()

    def _publish_cross_section_record(self) -> None:
        """Hand the plane record to the record publisher; requests no frame."""
        self._view_record_publisher.publish_cross_section(self.get_cross_section_plane())

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


