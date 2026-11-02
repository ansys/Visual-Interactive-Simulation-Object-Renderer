"""
GeometryHighlight
=================
One server-side actor that draws a geometry pick: a dot at a vertex, a line
along an edge, or a cell as a translucent polygon with an opaque outline.  Point
sizes and line widths are set in CSS pixels and drawn in device pixels.

It is a scene actor like any other, so the parts in front of it hide it.  It is
never pickable: a part pick must pass through it.
"""

from __future__ import annotations

from typing import Sequence

from vtkmodules.vtkCommonCore import vtkPoints, vtkUnsignedCharArray
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

HIGHLIGHT_RGB: tuple[int, int, int] = (255, 165, 0)
"""Orange, as 0-255 components."""

OUTLINE_ALPHA: int = 255
"""Dots and lines are opaque."""

FILL_ALPHA: int = 89
"""A face's fill opacity, 0.35 of 255."""

EDGE_DOT_ALPHA: int = 89
"""An edge's end dots are drawn at the face fill opacity, 0.35 of 255."""

VERTEX_DIAMETER_CSS: float = 21.0
"""A vertex dot's diameter in CSS pixels."""

EDGE_DOT_DIAMETER_CSS: float = 10.0
"""An edge end dot's diameter in CSS pixels."""

EDGE_LINE_WIDTH_CSS: float = 4.0
"""An edge's line width in CSS pixels."""

FACE_LINE_WIDTH_CSS: float = 3.0
"""A face outline's line width in CSS pixels."""

# Negative offsets pull the highlight towards the camera, so it does not fight
# the part surface it lies on.
COINCIDENT_POLYGON_OFFSET: tuple[float, float] = (-2.0, -2.0)
COINCIDENT_LINE_OFFSET: tuple[float, float] = (-2.0, -2.0)
COINCIDENT_POINT_OFFSET: float = -2.0


class GeometryHighlight:
    """A non-pickable actor drawing one geometry pick: a dot, a line, or a filled outline."""

    _polydata: vtkPolyData
    _actor: vtkActor
    _pixel_scale: float
    _point_diameter_css: float
    _line_width_css: float

    def __init__(self, pixel_scale: float) -> None:
        """Hidden and non-pickable, drawn in orange cell colours with lighting off; pixel_scale is device pixels per CSS pixel."""
        self._pixel_scale = pixel_scale
        self._point_diameter_css = VERTEX_DIAMETER_CSS
        self._line_width_css = FACE_LINE_WIDTH_CSS
        self._polydata = vtkPolyData()

        mapper = vtkPolyDataMapper()
        mapper.SetInputData(self._polydata)
        mapper.ScalarVisibilityOn()
        mapper.SetScalarModeToUseCellData()
        mapper.SetColorModeToDirectScalars()
        mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(*COINCIDENT_POLYGON_OFFSET)
        mapper.SetRelativeCoincidentTopologyLineOffsetParameters(*COINCIDENT_LINE_OFFSET)
        mapper.SetRelativeCoincidentTopologyPointOffsetParameter(COINCIDENT_POINT_OFFSET)

        self._actor = vtkActor()
        self._actor.SetMapper(mapper)
        self._actor.PickableOff()
        self._actor.VisibilityOff()
        prop = self._actor.GetProperty()
        prop.LightingOff()
        prop.RenderPointsAsSpheresOn()
        self._apply_sizes()

    @property
    def actor(self) -> vtkActor:
        """The actor to add to a renderer."""
        return self._actor

    @property
    def visible(self) -> bool:
        """Whether the actor is shown."""
        return bool(self._actor.GetVisibility())

    def set_pixel_scale(self, pixel_scale: float) -> None:
        """Set the device pixels per CSS pixel and rescale the drawn point size and line width; the geometry is kept."""
        self._pixel_scale = pixel_scale
        self._apply_sizes()

    def show_vertex(self, position: Sequence[float]) -> None:
        """Draw one dot at position and show the actor."""
        self._set_sizes_css(VERTEX_DIAMETER_CSS, FACE_LINE_WIDTH_CSS)
        self._draw([position], verts=[[0]], lines=[], polys=[], vert_alpha=OUTLINE_ALPHA)

    def show_edge(self, point_a: Sequence[float], point_b: Sequence[float]) -> None:
        """Draw a line between the two points, with a translucent dot at each end, and show the actor."""
        self._set_sizes_css(EDGE_DOT_DIAMETER_CSS, EDGE_LINE_WIDTH_CSS)
        self._draw([point_a, point_b], verts=[[0], [1]], lines=[[0, 1]], polys=[], vert_alpha=EDGE_DOT_ALPHA)

    def show_face(self, points: Sequence[Sequence[float]]) -> None:
        """Draw the points as a translucent polygon with an opaque closed outline, and show the actor."""
        self._set_sizes_css(VERTEX_DIAMETER_CSS, FACE_LINE_WIDTH_CSS)
        ids = list(range(len(points)))
        self._draw(points, verts=[], lines=[ids + [0]], polys=[ids], vert_alpha=OUTLINE_ALPHA)

    def hide(self) -> None:
        """Hide the actor; the drawn geometry is kept."""
        self._actor.VisibilityOff()

    def _set_sizes_css(self, point_diameter_css: float, line_width_css: float) -> None:
        """Record the point diameter and line width in CSS pixels and apply them at the current pixel scale."""
        self._point_diameter_css = point_diameter_css
        self._line_width_css = line_width_css
        self._apply_sizes()

    def _apply_sizes(self) -> None:
        """Write the recorded CSS sizes to the actor in device pixels."""
        prop = self._actor.GetProperty()
        prop.SetPointSize(self._point_diameter_css * self._pixel_scale)
        prop.SetLineWidth(self._line_width_css * self._pixel_scale)

    def _draw(
        self,
        points: Sequence[Sequence[float]],
        verts: list[list[int]],
        lines: list[list[int]],
        polys: list[list[int]],
        vert_alpha: int,
    ) -> None:
        """Replace the drawn geometry: point coordinates, then vertex, line and polygon cells as point-index lists.

        Cell colours follow VTK's cell order for polydata: verts, then lines,
        then polys.
        """
        vtk_points = vtkPoints()
        for point in points:
            vtk_points.InsertNextPoint(float(point[0]), float(point[1]), float(point[2]))

        colors = vtkUnsignedCharArray()
        colors.SetNumberOfComponents(4)
        colors.SetName("HighlightColors")
        cell_arrays = []
        for cells, alpha in ((verts, vert_alpha), (lines, OUTLINE_ALPHA), (polys, FILL_ALPHA)):
            cell_array = vtkCellArray()
            for cell in cells:
                cell_array.InsertNextCell(len(cell), cell)
                colors.InsertNextTypedTuple((*HIGHLIGHT_RGB, alpha))
            cell_arrays.append(cell_array)

        self._polydata.Initialize()
        self._polydata.SetPoints(vtk_points)
        self._polydata.SetVerts(cell_arrays[0])
        self._polydata.SetLines(cell_arrays[1])
        self._polydata.SetPolys(cell_arrays[2])
        self._polydata.GetCellData().SetScalars(colors)
        self._actor.VisibilityOn()
