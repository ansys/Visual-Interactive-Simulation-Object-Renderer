"""
ParaView session
================
The ``paraview.simple`` operations Visor uses, behind one seam.

:class:`ParaviewSession` is what :class:`ParaviewRenderer` and
:class:`ParaviewCapture` program against, so both are testable without
ParaView.  :class:`PvSimpleSession` implements it over ``paraview.simple`` and
is the only module that imports ``paraview``; it imports inside its
constructor, so importing this module never imports ParaView.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from ansys.visor.viewer.core.errors import PvserverConnectionError, VisorAddDatasetError
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState

if TYPE_CHECKING:
    from vtkmodules.vtkRenderingCore import vtkRenderWindow

    from ansys.visor.viewer.core.pvserver_address import PvserverAddress

logger = VisorDefaultLogger(__name__)

PvSource = Any
"""A ParaView source proxy on pvserver; opaque outside the session."""

PvRepresentation = Any
"""A ParaView representation proxy in the session's view; opaque outside the session."""

PvLookupTable = Any
"""A ParaView lookup-table proxy on pvserver; opaque outside the session."""

PVSERVER_CONNECT_TIMEOUT_S: int = 10
"""Seconds ``Connect`` retries before giving up on an unreachable pvserver."""

REMOTE_RENDER_THRESHOLD_MB: float = 0.0
"""Geometry size above which the view renders on pvserver; 0 renders every frame there."""


class ParaviewSession(Protocol):
    """The paraview.simple operations Visor uses, behind one seam so the renderer is testable without ParaView."""

    @property
    def render_window(self) -> vtkRenderWindow:
        """The view's client-side render window, which the RCA capture reads."""

    def open(self, path: str) -> PvSource:
        """Open path on pvserver."""

    def show(self, source: PvSource) -> PvRepresentation:
        """Show source in the view with scalar colouring off and its selection drawn as ParaView's default wireframe."""

    def delete(self, source: PvSource) -> None:
        """Hide and delete source on pvserver."""

    def point_count(self, source: PvSource) -> int:
        """Number of points pvserver reports for source."""

    def block_point_count(self, source: PvSource, selector: str) -> int:
        """Number of points pvserver reports for the block of source at selector."""

    def set_property(self, rep: PvRepresentation, name: str, value: object) -> None:
        """Write one representation property."""

    def clear_color(self, rep: PvRepresentation) -> None:
        """ColorBy None."""

    def new_color_map(self, component: int) -> PvLookupTable:
        """A new lookup table in the VTK modes' colours, mapping component, ``-1`` for magnitude, that ParaView never rescales."""

    def rescale_color_map(self, lut: PvLookupTable, lo: float, hi: float) -> None:
        """Rescale lut's transfer function to [lo, hi]."""

    def delete_color_map(self, lut: PvLookupTable) -> None:
        """Delete lut on pvserver."""

    def set_selected_blocks(self, source: PvSource, selectors: list[str]) -> None:
        """Make these blocks of source its whole selection; an empty list clears it."""

    def write_camera(self, camera: VisorCameraState) -> None:
        """Write the view camera properties."""

    def read_camera(self) -> VisorCameraState:
        """Read the view camera properties."""

    def reset_camera(self, bounds: list[float]) -> None:
        """ResetCamera to bounds."""

    def set_background(self, rgb: tuple[float, float, float]) -> None:
        """Set the view background, ignoring the palette."""

    def set_viewport_size(self, width: int, height: int) -> None:
        """Set ViewSize."""

    def render(self) -> None:
        """Render(view): only the capture path calls this."""


class PvSimpleSession:
    """ParaviewSession over paraview.simple; connects on construction."""

    def __init__(self, pvserver: PvserverAddress) -> None:
        """Connect to pvserver, create the render view, set RemoteRenderThreshold 0, stop interaction from rendering and draw the client-side window offscreen; raise PvserverConnectionError naming the address.

        ``Connect`` does not raise on an unreachable server: it retries for
        its timeout and returns ``None``.  The timeout is passed explicitly so
        the failure is bounded, and ``None`` is turned into the raise.

        By default each event the interactor handles makes the view render on
        pvserver, and the end of a gesture makes a still render, none of which
        is captured.  With ``EnableRenderOnInteraction`` off, an event only
        moves the camera, and the capture's render is the frame's one render.

        Without ``--force-offscreen-rendering`` the client-side window is an
        on-screen window, which the windowing system clamps to the screen, so
        a ViewSize larger than the screen would be read back smaller and the
        captured frame would not match the canvas.
        """
        from paraview import simple

        self._simple = simple
        connection = simple.Connect(
            ds_host=pvserver.host, ds_port=pvserver.port, timeout=PVSERVER_CONNECT_TIMEOUT_S
        )
        if connection is None:
            raise PvserverConnectionError(f"Could not connect to pvserver at {pvserver}")
        self._view = simple.CreateView("RenderView")
        self._view.RemoteRenderThreshold = REMOTE_RENDER_THRESHOLD_MB
        logger.info("RemoteRenderThreshold set to %s", self._view.RemoteRenderThreshold)
        self._view.EnableRenderOnInteraction = 0
        self._render_window = self._view.GetClientSideObject().GetRenderWindow()
        self._render_window.SetOffScreenRendering(1)

    def disconnect(self) -> None:
        """Disconnect from pvserver."""
        self._simple.Disconnect()

    @property
    def render_window(self) -> vtkRenderWindow:
        """The view's client-side render window, which the RCA capture reads."""
        return self._render_window

    def open(self, path: str) -> PvSource:
        """Open path on pvserver and update it; raise VisorAddDatasetError when no reader opens it."""
        source = self._simple.OpenDataFile(path)
        if source is None:
            raise VisorAddDatasetError("pvserver found no reader for the file", input_path=path)
        source.UpdatePipeline()
        return source

    def show(self, source: PvSource) -> PvRepresentation:
        """Show source in the view with scalar colouring off and its selection drawn as ParaView's default wireframe.

        A surface selection is coplanar with the faces it covers and
        z-fights with them; lines are offset towards the camera.
        """
        rep = self._simple.Show(source, self._view)
        self.clear_color(rep)
        return rep

    def delete(self, source: PvSource) -> None:
        """Hide and delete source on pvserver."""
        self._simple.Hide(source, self._view)
        self._simple.Delete(source)

    def point_count(self, source: PvSource) -> int:
        """Number of points pvserver reports for source."""
        return source.GetDataInformation().GetNumberOfPoints()

    def block_point_count(self, source: PvSource, selector: str) -> int:
        """Number of points pvserver reports for the block of source at selector, read from its hierarchy."""
        return source.SMProxy.GetSubsetDataInformation(0, selector, "Hierarchy").GetNumberOfPoints()

    def set_property(self, rep: PvRepresentation, name: str, value: object) -> None:
        """Write one representation property."""
        setattr(rep, name, value)

    def clear_color(self, rep: PvRepresentation) -> None:
        """ColorBy None, by clearing the colour array name.

        ``ColorBy(rep, None)`` raises when the rep is not coloured by an
        array, because it reads the association back as ``NONE``; clearing
        the name turns scalar colouring off in either state.
        """
        rep.ColorArrayName = ["POINTS", ""]

    def new_color_map(self, component: int) -> PvLookupTable:
        """A new lookup table mapping component, ``-1`` for magnitude, that ParaView never rescales.

        The table is not registered under an array name, so no other
        representation coloured by the same array picks it up.  Its colours
        are those of the VTK modes' table; ParaView's default preset is not used.
        """
        lut = self._simple.CreateLookupTable()
        lut.AutomaticRescaleRangeMode = "Never"
        self._write_visor_colors(lut)
        if component == -1:
            lut.VectorMode = "Magnitude"
        else:
            lut.VectorMode = "Component"
            lut.VectorComponent = component
        return lut

    @staticmethod
    def _write_visor_colors(lut: PvLookupTable) -> None:
        """Make lut map as the VTK modes' table does: its colours as RGB points, discretized to its size.

        Each table colour is placed at its normalised index, so the
        discretized map samples exactly that colour and indexes values as
        the VTK table does at every range.
        """
        from vtkmodules.vtkCommonCore import vtkLookupTable

        from ansys.visor.viewer.vtk.node_pipeline import LOOKUP_TABLE_HUE_RANGE

        table = vtkLookupTable()
        table.SetHueRange(*LOOKUP_TABLE_HUE_RANGE)
        table.Build()
        count = table.GetNumberOfTableValues()
        points: list[float] = []
        for index in range(count):
            red, green, blue, _ = table.GetTableValue(index)
            points += [index / (count - 1), red, green, blue]
        lut.ColorSpace = "RGB"
        lut.RGBPoints = points
        lut.NumberOfTableValues = count
        lut.Discretize = 1

    def rescale_color_map(self, lut: PvLookupTable, lo: float, hi: float) -> None:
        """Rescale lut's transfer function to [lo, hi]."""
        lut.RescaleTransferFunction(lo, hi)

    def delete_color_map(self, lut: PvLookupTable) -> None:
        """Delete lut on pvserver."""
        self._simple.Delete(lut)

    def set_selected_blocks(self, source: PvSource, selectors: list[str]) -> None:
        """Make these blocks of source its whole selection in one write; an empty list clears it.

        This is ``SelectBlocks`` with every selector in one selection source
        and no render: ``SelectBlocks`` takes one selector per call and
        renders the view after each.  The selection is of cells:
        ``SelectBlocks``' default of points extracts each block as vertices,
        so only its points would be highlighted.
        """
        if not selectors:
            source.SMProxy.SetSelectionInput(0, None, 0)
            return
        from paraview.modules.vtkRemotingViews import vtkSMSelectionHelper
        from paraview.vtk import vtkSelectionNode
        from vtkmodules.vtkFiltersSources import vtkSelectionSource

        selection = vtkSelectionSource()
        selection.SetFieldType(vtkSelectionNode.CELL)
        selection.SetContentType(vtkSelectionNode.BLOCK_SELECTORS)
        selection.SetArrayName("Hierarchy")
        for selector in selectors:
            selection.AddBlockSelector(selector)
        selection.Update()
        selection_proxy = vtkSMSelectionHelper.NewSelectionSourceFromSelection(
            source.GetSession(), selection.GetOutput()
        )
        append = vtkSMSelectionHelper.NewAppendSelectionsFromSelectionSource(selection_proxy)
        source.SMProxy.SetSelectionInput(0, append, 0)
        append.UnRegister(None)
        selection_proxy.UnRegister(None)

    def write_camera(self, camera: VisorCameraState) -> None:
        """Write the view camera properties; ParaView recomputes the clipping range at render."""
        view = self._view
        view.CameraPosition = list(camera.position)
        view.CameraFocalPoint = list(camera.focal_point)
        view.CameraViewUp = list(camera.view_up)
        view.CameraViewAngle = camera.view_angle
        view.CameraParallelScale = camera.parallel_scale
        view.CameraParallelProjection = 1 if camera.parallel_projection else 0

    def read_camera(self) -> VisorCameraState:
        """Read the view's client-side camera, which the interactor moves.

        The proxy's camera properties lag a gesture until they are
        synchronised, so the camera object is read instead.
        """
        camera = self._view.GetActiveCamera()
        return VisorCameraState(
            position=list(camera.GetPosition()),
            focal_point=list(camera.GetFocalPoint()),
            view_up=list(camera.GetViewUp()),
            clipping_range=list(camera.GetClippingRange()),
            parallel_projection=bool(camera.GetParallelProjection()),
            view_angle=camera.GetViewAngle(),
            parallel_scale=camera.GetParallelScale(),
        )

    def reset_camera(self, bounds: list[float]) -> None:
        """ResetCamera to bounds on the view proxy.

        ``paraview.simple.ResetCamera`` renders the view; this does not, so
        rendering stays on the capture path.  The bounds are passed as six
        arguments: a single sequence matches several overloads.
        """
        self._view.ResetCamera(*(float(b) for b in bounds))

    def set_background(self, rgb: tuple[float, float, float]) -> None:
        """Set the view background, ignoring the palette."""
        self._view.UseColorPaletteForBackground = 0
        self._view.Background = list(rgb)

    def set_viewport_size(self, width: int, height: int) -> None:
        """Set ViewSize."""
        self._view.ViewSize = [width, height]

    def render(self) -> None:
        """Render(view): only the capture path calls this."""
        self._simple.Render(self._view)
