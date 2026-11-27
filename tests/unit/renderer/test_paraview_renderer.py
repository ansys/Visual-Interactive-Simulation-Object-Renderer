"""
Unit tests for ParaviewRenderer.

Every test drives a real ParaviewRenderer over a recording fake session, so
no ParaView is imported.  The fake returns a distinct representation object
per ``show`` call and a distinct colour map per ``new_color_map`` call, so a
write can be checked against the part and the map it targets.  Expected
values are hand-written literals.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from vtkmodules.vtkCommonCore import vtkDoubleArray, vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCompositeDataSet, vtkMultiBlockDataSet, vtkPolyData

from ansys.visor.viewer.core.errors import VisorAddDatasetError
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.renderer.paraview_renderer import BlockLeaf, CompositeBlocks, ParaviewRenderer

BACKGROUND = (0.1, 0.2, 0.3)


class _FakeSession:
    """Records every session call; ``show`` returns a new representation each time."""

    def __init__(self, point_count: int = 3) -> None:
        self.render_window = object()
        self.reported_points = point_count
        self.render_count = 0
        self.writes: list[tuple[object, str, object]] = []
        self.opened: list[str] = []
        self.deleted: list[object] = []
        self.reps: list[SimpleNamespace] = []
        self.maps: list[SimpleNamespace] = []
        self.rescaled: list[tuple[int, float, float]] = []
        self.deleted_maps: list[int] = []
        self.extracts: list[SimpleNamespace] = []
        self.extracted: list[tuple[str, list[str]]] = []
        self.centers: list[list[float]] = []

    def open(self, path):
        self.opened.append(path)
        return SimpleNamespace(path=path)

    def show(self, source):
        rep = SimpleNamespace(shows=source)
        self.reps.append(rep)
        return rep

    def delete(self, source):
        self.deleted.append(source)

    def extract_blocks(self, source, selectors):
        extract = SimpleNamespace(path=f"extract{len(self.extracts)}", of=source, selectors=list(selectors))
        self.extracts.append(extract)
        return extract

    def set_extracted_blocks(self, extract, selectors):
        self.extracted.append((extract.path, list(selectors)))

    def point_count(self, source):
        return self.reported_points

    def block_point_count(self, source, selector):
        return self.reported_points

    def set_property(self, rep, name, value):
        self.writes.append((rep, name, value))

    def clear_color(self, rep):
        pass

    def new_color_map(self, component, tint_rgb=None, tint_strength=0.0):
        tint = None if tint_rgb is None else (list(tint_rgb), tint_strength)
        lut = SimpleNamespace(index=len(self.maps), component=component, tint=tint)
        self.maps.append(lut)
        return lut

    def rescale_color_map(self, lut, lo, hi):
        self.rescaled.append((lut.index, lo, hi))

    def delete_color_map(self, lut):
        self.deleted_maps.append(lut.index)

    def write_camera(self, camera):
        pass

    def read_camera(self):
        return None

    def reset_camera(self, bounds):
        pass

    def set_center_of_rotation(self, point):
        self.centers.append(point)

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


def _named(parent: vtkMultiBlockDataSet, index: int, name: str, block) -> None:
    parent.SetBlock(index, block)
    parent.GetMetaData(index).Set(vtkCompositeDataSet.NAME(), name)


def _wing_and_body(second_name: str | None = None):
    """Root with leaf ``wing`` and group ``body`` holding ``rib`` and an optional second leaf; returns root, rib."""
    root = vtkMultiBlockDataSet()
    body = vtkMultiBlockDataSet()
    rib = _triangle_points()
    _named(root, 0, "wing", _triangle_points())
    _named(body, 0, "rib", rib)
    if second_name is not None:
        _named(body, 1, second_name, _triangle_points())
    _named(root, 1, "body", body)
    return root, rib


def _register_wing_and_rib(renderer: ParaviewRenderer) -> None:
    """Open the wing-and-body source and register wing as node 1 and rib as node 2."""
    root, rib = _wing_and_body()
    renderer.open_source("mb", "/shared/mb.vtm", root)
    renderer.register_node(SimpleNamespace(id=1, name="wing"), root.GetBlock(0))
    renderer.register_node(SimpleNamespace(id=2, name="rib"), rib)


def _last_write(session: _FakeSession, name: str):
    return [value for _, prop, value in session.writes if prop == name][-1]


def _last_write_to(session: _FakeSession, rep, name: str):
    return [value for target, prop, value in session.writes if target is rep and prop == name][-1]


def _color(renderer: ParaviewRenderer, node_id: int, max_val: float = 5.0) -> None:
    renderer.apply_color_variable(node_id, VisorVtkVariableType.POINT, "velocity", 0, 0.0, max_val)


def test_apply_visibility_requests_a_frame_and_never_renders():
    session = _FakeSession()
    renderer, requester = _renderer(session)
    _register(renderer, 1, "a")

    renderer.apply_visibility(1, False)

    assert session.render_count == 0
    assert requester.count == 1


def test_register_node_shows_the_leafs_block_on_one_representation():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    root, rib = _wing_and_body()
    renderer.open_source("mb", "/shared/mb.vtm", root)

    renderer.register_node(SimpleNamespace(id=1, name="rib"), rib)
    renderer.flush_writes()

    assert (len(session.reps), _last_write(session, "BlockSelectors")) == (1, ["/Root/body/rib"])


@pytest.mark.parametrize(
    ("method", "args", "prop", "value"),
    [
        ("apply_visibility", (False,), "BlockSelectors", ["/Root/wing"]),
        ("apply_opacity", (0.25,), "BlockOpacities", ["/Root/body/rib", "0.25"]),
        ("apply_diffuse_color", (1.0, 0.5, 0.0), "BlockColors", ["/Root/body/rib", "1.0", "0.5", "0.0"]),
    ],
)
def test_block_write_lands_on_that_block_only(method, args, prop, value):
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)
    renderer.flush_writes()
    session.writes.clear()

    getattr(renderer, method)(2, *args)
    renderer.flush_writes()

    assert session.writes == [(session.reps[0], prop, value)]


def test_open_source_refuses_duplicate_sibling_names_before_opening():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    root, _ = _wing_and_body(second_name="rib")

    with pytest.raises(VisorAddDatasetError, match="rib"):
        renderer.open_source("mb", "/shared/mb.vtm", root)
    assert session.opened == []


def test_check_unique_names_the_shared_selector():
    blocks = CompositeBlocks(
        [
            BlockLeaf(_triangle_points(), "rib", ("/Root/body/rib",)),
            BlockLeaf(_triangle_points(), "rib", ("/Root/body/rib",)),
        ]
    )

    with pytest.raises(VisorAddDatasetError, match="/Root/body/rib"):
        blocks.check_unique()


def test_open_source_refuses_a_block_whose_point_count_differs():
    session = _FakeSession(point_count=4)
    renderer, _ = _renderer(session)
    root, _ = _wing_and_body()

    with pytest.raises(VisorAddDatasetError, match="'/Root/wing': pvserver reports 4 points"):
        renderer.open_source("mb", "/shared/mb.vtm", root)
    assert ([d.path for d in session.deleted], session.reps) == (["/shared/mb.vtm"], [])


def test_open_source_raises_when_pvserver_point_count_differs():
    renderer, _ = _renderer(_FakeSession(point_count=4))

    with pytest.raises(VisorAddDatasetError):
        renderer.open_source("a", "/shared/a.vtp", _triangle_points())


def test_register_node_raises_for_a_dataset_no_source_holds():
    renderer, _ = _renderer(_FakeSession())

    with pytest.raises(VisorAddDatasetError):
        renderer.register_node(SimpleNamespace(id=1, name="a"), _triangle_points())


@pytest.mark.parametrize("component", [-1, 1])
def test_apply_color_variable_creates_a_map_for_the_component(component):
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register(renderer, 1, "a")

    renderer.apply_color_variable(1, VisorVtkVariableType.POINT, "velocity", component, 0.0, 5.0)

    assert [lut.component for lut in session.maps] == [component]


def test_apply_color_variable_colors_the_representation_through_its_map():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register(renderer, 1, "a")

    _color(renderer, 1)

    assert [(prop, value) for _, prop, value in session.writes] == [
        ("UseSeparateColorMap", 1),
        ("LookupTable", session.maps[0]),
        ("ColorArrayName", ["POINTS", "velocity"]),
    ]


def test_blocks_with_equal_color_keys_share_one_map():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)

    _color(renderer, 1)
    _color(renderer, 2)

    assert len(session.maps) == 1


def test_block_coloring_gives_every_block_an_entry():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)

    _color(renderer, 1)
    renderer.flush_writes()

    assert (
        _last_write(session, "BlockColorArrayNames"),
        _last_write(session, "BlockLookupTables"),
        _last_write(session, "ColorArrayName"),
    ) == (
        ["/Root/wing", "0", "velocity", "/Root/body/rib", "0", ""],
        [session.maps[0], session.maps[0]],
        ["POINTS", "velocity"],
    )


def test_a_new_map_is_rescaled_once_and_a_shared_map_never_again():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)
    _color(renderer, 1)
    _color(renderer, 2)

    _color(renderer, 2, max_val=6.0)

    assert (session.rescaled, session.deleted_maps) == ([(0, 0.0, 5.0), (1, 0.0, 6.0)], [])


def test_range_change_moves_the_part_and_deletes_its_old_map():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register(renderer, 1, "a")
    _color(renderer, 1)

    _color(renderer, 1, max_val=6.0)
    renderer.flush_writes()

    assert (_last_write(session, "LookupTable"), session.deleted_maps) == (session.maps[1], [0])


def test_clear_color_forgets_an_unused_map():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register(renderer, 1, "a")
    _color(renderer, 1)

    renderer.clear_color_variable(1)
    renderer.flush_writes()

    assert session.deleted_maps == [0]


def test_deregister_node_releases_its_map():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)
    _color(renderer, 2)

    renderer.deregister_node(2)
    renderer.flush_writes()

    assert session.deleted_maps == [0]


def test_a_selected_block_is_drawn_tinted_by_its_own_group_not_by_the_representation():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)

    renderer.apply_selected(2, True, [1.0, 0.5, 0.0])
    renderer.flush_writes()
    group = session.reps[1]

    assert (_last_write_to(session, session.reps[0], "BlockSelectors"), [e.selectors for e in session.extracts]) == (
        ["/Root/wing"],
        [["/Root/body/rib"]],
    )
    assert [(prop, value) for rep, prop, value in session.writes if rep is group] == [
        ("AmbientColor", [0.0, 62 / 255, 111 / 255]),
        ("Ambient", 0.5),
        ("Diffuse", 0.5),
        ("Visibility", 1),
        ("DiffuseColor", [1.0, 0.5, 0.0]),
        ("Opacity", 1.0),
        ("LookupTable", None),
    ]


def test_hiding_a_selected_block_drops_it_from_its_group():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)
    renderer.apply_selected(1, True, [1.0, 1.0, 1.0])
    renderer.apply_selected(2, True, [1.0, 1.0, 1.0])
    renderer.flush_writes()

    renderer.apply_visibility(2, False)
    renderer.flush_writes()

    assert ([e.selectors for e in session.extracts], session.extracted) == (
        [["/Root/wing", "/Root/body/rib"]],
        [("extract0", ["/Root/wing"])],
    )


def test_selected_blocks_of_different_colours_are_drawn_by_one_group_each():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)

    renderer.apply_selected(1, True, [1.0, 0.0, 0.0])
    renderer.apply_selected(2, True, [0.0, 1.0, 0.0])
    renderer.flush_writes()

    assert [e.selectors for e in session.extracts] == [["/Root/wing"], ["/Root/body/rib"]]


def test_reselecting_reuses_the_hidden_group():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)
    renderer.apply_selected(1, True, [1.0, 0.0, 0.0])
    renderer.flush_writes()
    renderer.apply_selected(1, False, [1.0, 0.0, 0.0])
    renderer.flush_writes()

    renderer.apply_selected(2, True, [0.0, 1.0, 0.0])
    renderer.flush_writes()
    group = session.reps[1]

    assert (len(session.extracts), session.extracted) == (1, [("extract0", ["/Root/body/rib"])])
    assert (_last_write_to(session, group, "Visibility"), _last_write_to(session, group, "DiffuseColor")) == (
        1,
        [0.0, 1.0, 0.0],
    )


def test_opacity_and_edges_of_a_selected_block_reach_its_group():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)
    renderer.apply_selected(2, True, [1.0, 1.0, 1.0])
    renderer.flush_writes()
    group = session.reps[1]

    renderer.apply_opacity(2, 0.25)
    renderer.set_edges_visible(True)
    renderer.flush_writes()

    assert (_last_write_to(session, group, "Opacity"), _last_write_to(session, group, "Representation")) == (
        0.25,
        "Surface With Edges",
    )


def test_a_selected_block_coloured_by_an_array_is_drawn_through_a_tinted_map():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)
    _color(renderer, 2)

    renderer.apply_selected(2, True, [1.0, 1.0, 1.0])
    renderer.flush_writes()
    lut = _last_write_to(session, session.reps[1], "LookupTable")

    assert (lut.index, lut.tint, session.rescaled) == (
        1,
        ([0.0, 62 / 255, 111 / 255], 0.5),
        [(0, 0.0, 5.0), (1, 0.0, 5.0)],
    )


def test_a_tinted_map_is_deleted_only_after_its_group_stops_naming_it():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)
    _color(renderer, 2)
    renderer.apply_selected(2, True, [1.0, 1.0, 1.0])
    renderer.flush_writes()

    renderer.clear_color_variable(2)
    deleted_before_flush = list(session.deleted_maps)
    renderer.flush_writes()

    assert (deleted_before_flush, session.deleted_maps, _last_write_to(session, session.reps[1], "LookupTable")) == (
        [],
        [0, 1],
        None,
    )


def test_a_selected_whole_part_coloured_by_an_array_uses_the_tinted_map_until_deselected():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register(renderer, 1, "a")
    _color(renderer, 1)

    renderer.apply_selected(1, True, [1.0, 1.0, 1.0])
    tinted = _last_write(session, "LookupTable")
    renderer.apply_selected(1, False, [1.0, 1.0, 1.0])
    renderer.flush_writes()

    assert (tinted.tint, _last_write(session, "LookupTable"), session.deleted_maps) == (
        ([0.0, 62 / 255, 111 / 255], 0.5),
        session.maps[0],
        [1],
    )


def test_close_source_deletes_its_selected_groups_before_the_source():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)
    renderer.apply_selected(2, True, [1.0, 1.0, 1.0])
    renderer.flush_writes()

    renderer.close_source("mb")

    assert [d.path for d in session.deleted] == ["extract0", "/shared/mb.vtm"]


def test_deregister_node_hides_only_that_block():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)

    renderer.deregister_node(2)
    renderer.flush_writes()

    assert _last_write(session, "BlockSelectors") == ["/Root/wing"]


def test_close_source_deletes_the_source_and_the_maps_its_parts_used():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_wing_and_rib(renderer)
    _color(renderer, 1)

    renderer.close_source("mb")
    renderer.flush_writes()

    assert ([d.path for d in session.deleted], session.deleted_maps) == (["/shared/mb.vtm"], [0])


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


def _register_blocks(renderer: ParaviewRenderer, count: int) -> None:
    """Open one composite source of count leaves ``b0``.. and register leaf i as node i + 1."""
    root = vtkMultiBlockDataSet()
    for index in range(count):
        _named(root, index, f"b{index}", _triangle_points())
    renderer.open_source("mb", "/shared/mb.vtm", root)
    for index in range(count):
        renderer.register_node(SimpleNamespace(id=index + 1, name=f"b{index}"), root.GetBlock(index))


def test_a_burst_of_block_changes_writes_each_list_once_at_the_flush():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_blocks(renderer, 3)
    renderer.flush_writes()
    session.writes.clear()

    for node_id in (1, 2, 3):
        _color(renderer, node_id)
        renderer.apply_opacity(node_id, 0.5)
    held = list(session.writes)
    renderer.flush_writes()

    assert (held, [prop for _, prop, _ in session.writes]) == (
        [],
        ["BlockOpacities", "ColorArrayName", "BlockLookupTables", "BlockUseSeparateColorMaps", "BlockColorArrayNames"],
    )


def test_a_burst_of_selection_changes_makes_one_group():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_blocks(renderer, 3)

    for node_id in (1, 2, 3):
        renderer.apply_selected(node_id, True, [1.0, 1.0, 1.0])
    renderer.apply_selected(2, False, [1.0, 1.0, 1.0])
    renderer.flush_writes()

    assert ([e.selectors for e in session.extracts], session.extracted) == ([["/Root/b0", "/Root/b2"]], [])


def test_a_released_map_is_deleted_only_after_the_lists_are_written():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_blocks(renderer, 2)
    _color(renderer, 1, max_val=1.0)
    _color(renderer, 2, max_val=2.0)
    renderer.clear_color_variable(1)

    deleted_before_flush = list(session.deleted_maps)
    renderer.flush_writes()

    assert (deleted_before_flush, session.deleted_maps, session.maps[0] in _last_write(session, "BlockLookupTables")) == (
        [],
        [0],
        False,
    )


def test_flush_writes_nothing_when_nothing_changed():
    session = _FakeSession()
    renderer, _ = _renderer(session)
    _register_blocks(renderer, 2)
    renderer.flush_writes()
    session.writes.clear()

    renderer.flush_writes()

    assert (session.writes, session.extracts) == ([], [])


def test_record_pipeline_camera_rotates_about_the_focal_point_a_gesture_left():
    """A pan moves the focal point and leaves ParaView's centre of rotation where it was."""
    session = _FakeSession()
    session.read_camera = lambda: VisorCameraState(
        position=[0.0, 0.0, 50.0],
        focal_point=[5.0, 6.0, 7.0],
        view_up=[0.0, 1.0, 0.0],
        clipping_range=[1.0, 100.0],
        parallel_projection=False,
        view_angle=30.0,
        parallel_scale=1.0,
    )
    renderer, _ = _renderer(session)

    renderer.record_pipeline_camera()

    assert session.centers == [[5.0, 6.0, 7.0]]
