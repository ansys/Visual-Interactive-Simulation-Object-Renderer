"""
Unit tests for PvSimpleSession.

A fake ``paraview.simple`` module is placed in ``sys.modules``, so the
session's constructor-time import finds it and no ParaView is needed.
Expected values are hand-written literals.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkPolyData

from ansys.visor.viewer.core.errors import PvserverConnectionError
from ansys.visor.viewer.core.pvserver_address import PvserverAddress
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.renderer.paraview_session import PvSimpleSession
from ansys.visor.viewer.vtk.node_pipeline import VtkNodePipeline


def _triangle() -> vtkPolyData:
    points = vtkPoints()
    for x, y in ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)):
        points.InsertNextPoint(x, y, 0.0)
    polydata = vtkPolyData()
    polydata.SetPoints(points)
    return polydata


class _FakeWindow:
    """A client-side render window that records its offscreen flag."""

    def __init__(self) -> None:
        self.offscreen = 0

    def SetOffScreenRendering(self, value: int) -> None: # noqa: N802
        self.offscreen = value


class _FakeView:
    """A render view whose attributes record writes, with a client-side window."""

    def __init__(self) -> None:
        self.RemoteRenderThreshold = 20.0
        self.EnableRenderOnInteraction = 1
        self.window = _FakeWindow()

    def GetClientSideObject(self): # noqa: N802
        return SimpleNamespace(GetRenderWindow=lambda: self.window)


def _install_fake_simple(monkeypatch, connection: object | None) -> types.ModuleType:
    """Put a fake paraview.simple in sys.modules; Connect returns connection."""
    simple = types.ModuleType("paraview.simple")
    simple.view = _FakeView()
    simple.Connect = lambda **kwargs: connection
    simple.CreateView = lambda name: simple.view
    simple.CreateLookupTable = lambda: SimpleNamespace()
    paraview = types.ModuleType("paraview")
    paraview.simple = simple
    monkeypatch.setitem(sys.modules, "paraview", paraview)
    monkeypatch.setitem(sys.modules, "paraview.simple", simple)
    return simple


def test_init_writes_remote_render_threshold_zero_and_logs_it(monkeypatch):
    simple = _install_fake_simple(monkeypatch, connection=object())

    with patch("ansys.visor.viewer.renderer.paraview_session.logger") as log:
        PvSimpleSession(PvserverAddress(host="localhost", port=11111))

    assert simple.view.RemoteRenderThreshold == 0.0
    fmt, *args = log.info.call_args.args
    assert fmt % tuple(args) == "RemoteRenderThreshold set to 0.0"


def test_init_draws_the_client_side_window_offscreen(monkeypatch):
    simple = _install_fake_simple(monkeypatch, connection=object())

    session = PvSimpleSession(PvserverAddress(host="localhost", port=11111))

    assert session.render_window is simple.view.window
    assert simple.view.window.offscreen == 1


def test_init_turns_off_renders_on_interaction(monkeypatch):
    """An interactor event moves the camera only; ParaView's default of 1 renders on pvserver per event."""
    simple = _install_fake_simple(monkeypatch, connection=object())

    PvSimpleSession(PvserverAddress(host="localhost", port=11111))

    assert simple.view.EnableRenderOnInteraction == 0


def test_init_raises_naming_the_address_when_connect_returns_none(monkeypatch):
    _install_fake_simple(monkeypatch, connection=None)

    with pytest.raises(PvserverConnectionError, match="localhost:11111"):
        PvSimpleSession(PvserverAddress(host="localhost", port=11111))


def _session(monkeypatch):
    simple = _install_fake_simple(monkeypatch, connection=object())
    return simple, PvSimpleSession(PvserverAddress(host="localhost", port=11111))


def test_show_turns_off_interpolate_scalars_before_mapping(monkeypatch):
    """A colour map is applied as vertex colours, not as a texture, so maps do not consume texture units."""
    simple, session = _session(monkeypatch)
    simple.Show = lambda source, view: SimpleNamespace(InterpolateScalarsBeforeMapping=1)

    assert session.show(object()).InterpolateScalarsBeforeMapping == 0


def test_block_point_count_reads_the_blocks_hierarchy_subset(monkeypatch):
    _, session = _session(monkeypatch)
    calls = []

    def subset(port, selector, assembly):
        calls.append((port, selector, assembly))
        return SimpleNamespace(GetNumberOfPoints=lambda: 88)

    source = SimpleNamespace(SMProxy=SimpleNamespace(GetSubsetDataInformation=subset))

    assert (session.block_point_count(source, "/Root/body/rib"), calls) == (88, [(0, "/Root/body/rib", "Hierarchy")])


@pytest.mark.parametrize(
    ("component", "expected"),
    [(-1, {"AutomaticRescaleRangeMode": "Never", "VectorMode": "Magnitude"}),
     (1, {"AutomaticRescaleRangeMode": "Never", "VectorMode": "Component", "VectorComponent": 1})],
)
def test_new_color_map_maps_the_component_and_never_rescales(monkeypatch, component, expected):
    _, session = _session(monkeypatch)

    lut = vars(session.new_color_map(component))

    assert {name: lut[name] for name in expected} == expected


def _sampled(colors, lo: float, hi: float) -> list[tuple[float, ...]]:
    """colors' RGB at 101 evenly spaced values over [lo, hi]."""
    samples = []
    for step in range(101):
        rgb = [0.0, 0.0, 0.0]
        colors.GetColor(lo + (hi - lo) * step / 100, rgb)
        samples.append(tuple(rgb))
    return samples


def test_new_color_map_samples_the_colors_of_the_vtk_modes_table(monkeypatch):
    from vtkmodules.vtkRenderingCore import vtkDiscretizableColorTransferFunction

    _, session = _session(monkeypatch)
    lut = session.new_color_map(-1)
    # ParaView rescales the normalised points onto [lo, hi], here [-3, 17].
    paraview_map = vtkDiscretizableColorTransferFunction()
    paraview_map.SetColorSpaceToRGB()
    for i in range(0, len(lut.RGBPoints), 4):
        x, red, green, blue = lut.RGBPoints[i : i + 4]
        paraview_map.AddRGBPoint(-3.0 + 20.0 * x, red, green, blue)
    paraview_map.SetNumberOfValues(lut.NumberOfTableValues)
    paraview_map.SetDiscretize(lut.Discretize)
    paraview_map.Build()
    vtk_table = VtkNodePipeline.from_dataset(_triangle()).lookup_table
    vtk_table.SetRange(-3.0, 17.0)

    samples = _sampled(paraview_map, -3.0, 17.0)

    assert (lut.ColorSpace, samples[0], samples[-1]) == ("RGB", (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
    assert samples == _sampled(vtk_table, -3.0, 17.0)


def test_new_color_map_mixes_each_colour_towards_the_tint(monkeypatch):
    _, session = _session(monkeypatch)
    plain = session.new_color_map(-1).RGBPoints
    tinted = session.new_color_map(-1, (0.0, 0.0, 1.0), 0.25).RGBPoints

    # The first point is the table's blue end, the last its red end, each a quarter of the way to blue.
    assert (plain[:4], tinted[:4], tinted[-4:]) == ([0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0], [1.0, 0.75, 0.0, 0.25])


def test_extract_blocks_keeps_the_selectors_and_set_extracted_blocks_rewrites_them(monkeypatch):
    simple, session = _session(monkeypatch)
    simple.ExtractBlock = lambda **kwargs: SimpleNamespace(**kwargs)
    source = object()

    extract = session.extract_blocks(source, ["/Root/wing"])
    first = (extract.Input, extract.Selectors)
    session.set_extracted_blocks(extract, ["/Root/body/rib"])

    assert (first, extract.Selectors) == ((source, ["/Root/wing"]), ["/Root/body/rib"])


def test_reset_camera_rotates_about_the_centre_of_the_bounds(monkeypatch):
    """ParaView rotates about CenterOfRotation, which ResetCamera leaves at its default of the origin."""
    simple, session = _session(monkeypatch)
    simple.view.CenterOfRotation = [0.0, 0.0, 0.0]
    simple.view.ResetCamera = lambda *bounds: None

    session.reset_camera([0, 4, -2, 2, 10, 30])

    assert simple.view.CenterOfRotation == [2.0, 0.0, 20.0]


def test_write_camera_rotates_about_its_focal_point(monkeypatch):
    simple, session = _session(monkeypatch)
    simple.view.CenterOfRotation = [0.0, 0.0, 0.0]

    session.write_camera(
        VisorCameraState(
            position=[0.0, 0.0, 50.0],
            focal_point=[1.0, 2.0, 3.0],
            view_up=[0.0, 1.0, 0.0],
            clipping_range=[1.0, 100.0],
            parallel_projection=False,
            view_angle=30.0,
            parallel_scale=1.0,
        )
    )

    assert simple.view.CenterOfRotation == [1.0, 2.0, 3.0]
