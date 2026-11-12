"""
Unit tests for ParaviewRenderer.

Every test drives a real ParaviewRenderer over a recording fake session, so
no ParaView is imported.  The fake returns a distinct representation object
per ``show`` call, so a write can be checked against the part it targets.
Expected values are hand-written literals.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from vtkmodules.vtkCommonCore import vtkDoubleArray, vtkPoints
from vtkmodules.vtkCommonDataModel import vtkMultiBlockDataSet, vtkPolyData

from ansys.visor.viewer.core.errors import UnsupportedInModeError, VisorAddDatasetError
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.renderer.paraview_renderer import ParaviewRenderer

BACKGROUND = (0.1, 0.2, 0.3)


class _FakeSession:
    """Records every session call; ``show`` returns a new representation each time."""

    def __init__(self, point_count: int = 3) -> None:
        self.render_window = object()
        self.reported_points = point_count
        self.render_count = 0
        self.writes: list[tuple[object, str, object]] = []
        self.color_by_calls: list[tuple[object, str, str, str | None]] = []
        self.opened: list[str] = []
        self.reps: list[SimpleNamespace] = []

    def open(self, path):
        self.opened.append(path)
        return SimpleNamespace(path=path)

    def extract(self, source, selectors):
        return SimpleNamespace(source=source, selectors=selectors)

    def show(self, source):
        rep = SimpleNamespace(shows=source)
        self.reps.append(rep)
        return rep

    def delete(self, source):
        pass

    def point_count(self, source):
        return self.reported_points

    def set_property(self, rep, name, value):
        self.writes.append((rep, name, value))

    def color_by(self, rep, association, array, component):
        self.color_by_calls.append((rep, association, array, component))

    def clear_color(self, rep):
        pass

    def rescale(self, rep, lo, hi):
        pass

    def write_camera(self, camera):
        pass

    def read_camera(self):
        return None

    def reset_camera(self, bounds):
        pass

    def set_background(self, rgb):
        pass

    def set_viewport_size(self, width, height):
        pass

    def render(self):
        self.render_count += 1


class _CountingFrameRequester:
    def __init__(self) -> None:
        self.count = 0

    def request_frame(self) -> None:
        self.count += 1


class _NullPublisher:
    def publish_camera(self, camera_state) -> None:
        pass

    def publish_cross_section(self, cross_section_state) -> None:
        pass


def _triangle_points() -> vtkPolyData:
    """Three points carrying a three-component point array named ``velocity``."""
    points = vtkPoints()
    points.InsertNextPoint(0.0, 0.0, 0.0)
    points.InsertNextPoint(1.0, 0.0, 0.0)
    points.InsertNextPoint(0.0, 1.0, 0.0)
    velocity = vtkDoubleArray()
    velocity.SetName("velocity")
    velocity.SetNumberOfComponents(3)
    for _ in range(3):
        velocity.InsertNextTuple3(1.0, 2.0, 3.0)
    polydata = vtkPolyData()
    polydata.SetPoints(points)
    polydata.GetPointData().AddArray(velocity)
    return polydata


def _renderer(session: _FakeSession):
    requester = _CountingFrameRequester()
    renderer = ParaviewRenderer(session, BACKGROUND, requester, _NullPublisher())
    return renderer, requester


def _register(renderer: ParaviewRenderer, node_id: int, key: str) -> vtkPolyData:
    dataset = _triangle_points()
    renderer.open_source(key, f"/shared/{key}.vtp", dataset)
    renderer.register_node(SimpleNamespace(id=node_id, name=key), dataset)
    return dataset


def test_apply_visibility_requests_a_frame_and_never_renders():
    session = _FakeSession()
    renderer, requester = _renderer(session)
    _register(renderer, 1, "a")

    renderer.apply_visibility(1, False)

    assert session.render_count == 0
    assert requester.count == 1


def test_open_source_raises_for_composite_input():
    renderer, _ = _renderer(_FakeSession())

    with pytest.raises(UnsupportedInModeError):
        renderer.open_source("mb", "/shared/mb.vtm", vtkMultiBlockDataSet())


def test_register_node_raises_when_pvserver_point_count_differs():
    renderer, _ = _renderer(_FakeSession(point_count=4))
    dataset = _triangle_points()
    renderer.open_source("a", "/shared/a.vtp", dataset)

    with pytest.raises(VisorAddDatasetError):
        renderer.register_node(SimpleNamespace(id=1, name="a"), dataset)


def test_register_node_raises_for_a_dataset_no_source_holds():
    renderer, _ = _renderer(_FakeSession())

    with pytest.raises(VisorAddDatasetError):
        renderer.register_node(SimpleNamespace(id=1, name="a"), _triangle_points())


@pytest.mark.parametrize(("component", "expected_name"), [(-1, "Magnitude"), (1, "1")])
def test_apply_color_variable_passes_paraview_component_name(component, expected_name):
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register(renderer, 1, "a")

    renderer.apply_color_variable(1, VisorVtkVariableType.POINT, "velocity", component, 0.0, 5.0)

    assert [call[1:] for call in session.color_by_calls] == [("POINTS", "velocity", expected_name)]


@pytest.mark.parametrize(
    ("method", "args", "prop", "value"),
    [
        ("apply_visibility", (False,), "Visibility", 0),
        ("apply_opacity", (0.25,), "Opacity", 0.25),
        ("apply_diffuse_color", (1.0, 0.5, 0.0), "DiffuseColor", [1.0, 0.5, 0.0]),
    ],
)
def test_part_write_lands_on_that_parts_representation_only(method, args, prop, value):
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register(renderer, 1, "a")
    _register(renderer, 2, "b")
    rep_a = session.reps[0]

    getattr(renderer, method)(1, *args)

    assert session.writes == [(rep_a, prop, value)]
