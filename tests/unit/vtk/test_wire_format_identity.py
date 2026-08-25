"""End-to-end wire-format identity test for the split scene graph.

Exercises the full path
    VisorSceneGraph.load_dataset(...)
        -> VisorSceneGraphPartNode
        -> VtkNodePipeline.from_dataset(part.dataset)
        -> VisorSceneBase.get_scene_details()
           -> _build_scene_graph_state() -> SceneGraphStateBuilder.build()
        -> SceneGraphNodeInfo tree

and asserts the emitted payload has the shape and value types this story's
split produces: renderer handles live only on ``vtkInfo.rendererAnnotation``,
never on ``sceneGraph``.
"""

import json
import re
from unittest.mock import MagicMock

from vtkmodules.vtkCommonCore import vtkFloatArray
from vtkmodules.vtkCommonDataModel import vtkMultiBlockDataSet, vtkPolyData
from vtkmodules.vtkFiltersSources import vtkSphereSource

from ansys.visor.viewer.core.visor_colors import VisorColors
from ansys.visor.viewer.models.runtime.vtk.renderer_annotation import (
    WasmNodeHandles,
    WasmRendererAnnotation,
    WasmWidgetHandles,
)
from ansys.visor.viewer.models.runtime.vtk.scene_graph_node_info import SceneGraphNodeInfo
from ansys.visor.viewer.vtk.node_pipeline import VtkNodePipeline
from ansys.visor.viewer.vtk.scene.base import VisorSceneBase
from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraph


def _sphere_polydata() -> vtkPolyData:
    src = vtkSphereSource()
    src.Update()
    return src.GetOutput()


def _sphere_polydata_with_point_and_cell_arrays() -> vtkPolyData:
    """Sphere polydata carrying one real point-data array and one real
    cell-data array, so the emitted ``dataArrays`` wire payload is non-empty
    and exercises both ``VisorVtkVariableType`` members end to end."""
    poly = _sphere_polydata()

    point_array = vtkFloatArray()
    point_array.SetName("PointScalar")
    point_array.SetNumberOfComponents(1)
    point_array.SetNumberOfTuples(poly.GetNumberOfPoints())
    for i in range(poly.GetNumberOfPoints()):
        point_array.SetValue(i, float(i))
    poly.GetPointData().AddArray(point_array)

    cell_array = vtkFloatArray()
    cell_array.SetName("CellScalar")
    cell_array.SetNumberOfComponents(1)
    cell_array.SetNumberOfTuples(poly.GetNumberOfCells())
    for i in range(poly.GetNumberOfCells()):
        cell_array.SetValue(i, float(i))
    poly.GetCellData().AddArray(cell_array)

    return poly



class _CountingObjectManager:
    """Assigns a stable, unique positive id per unique VTK object.

    Mirrors the observed behavior of ``vtkObjectManager``.
    """

    def __init__(self):
        self._ids: dict[int, int] = {}
        self._next = 1

    def GetId(self, obj) -> int: # noqa: N802
        key = id(obj)
        if key not in self._ids:
            self._ids[key] = self._next
            self._next += 1
        return self._ids[key]


class _StubRenderer:
    """Minimal ``IRenderer`` stand-in.

    Builds a real ``WasmRendererAnnotation`` from a real pipeline registry
    and a real (counting) object-manager-like id source -- the same
    construction :class:`VisorLocalRenderer.build_renderer_annotation` does.
    This is the one unavoidable test double a call to the real
    ``VisorSceneBase.get_scene_details()`` needs; nothing about scene-graph
    building or wasm-id stamping is reimplemented here -- both happen inside
    ``get_scene_details()`` itself.
    """

    def __init__(self, pipelines, object_manager):
        self._pipelines = pipelines
        self._object_manager = object_manager

    def build_renderer_annotation(self) -> WasmRendererAnnotation:
        get_id = self._object_manager.GetId
        nodes = {
            str(node_id): WasmNodeHandles(
                actor_id=get_id(pipe.actor),
                property_id=get_id(pipe.actor.GetProperty()),
                mapper_id=get_id(pipe.mapper),
            )
            for node_id, pipe in self._pipelines.items()
        }
        widgets = WasmWidgetHandles(
            orientation_widget_id=1,
            cross_section_plane_id=2,
            cross_section_plane_widget_id=3,
            cross_section_plane_representation_id=4,
            bounding_box_algorithm_id=5,
            bounding_box_outline_actor_id=6,
            bounding_box_axes_actor_id=7,
        )
        return WasmRendererAnnotation(nodes=nodes, widgets=widgets)


class _WireFormatScene(VisorSceneBase):
    """Minimal concrete ``VisorSceneBase`` for exercising the real
    ``get_scene_details()`` path end to end. The two abstract hooks are
    unused by that path and are never called by this test."""

    async def _get_runtime_state_async(self, timeout: float):
        raise NotImplementedError

    def _apply_runtime_state_to_render(self, runtime_app_state) -> None:
        raise NotImplementedError


def _build_scene(dataset) -> _WireFormatScene:
    """Load ``dataset``, spin up real pipelines, and return the fully wired
    ``_WireFormatScene`` (a real, unmodified ``VisorSceneBase``) so callers
    can exercise either ``get_scene_details()`` or ``get_scene_details_json()``
    -- the same production entry point."""
    graph = VisorSceneGraph()
    graph.load_dataset(dataset, name="ds")

    # Simulate VisorSceneBase's pipeline registry: one VtkNodePipeline per leaf.
    pipelines = {
        part.id: VtkNodePipeline.from_dataset(part.dataset)
        for part in graph.get_descendant_part_nodes(include_self=False)
    }
    assert pipelines, "test setup: expected at least one part node in graph"

    object_manager = _CountingObjectManager()
    renderer = _StubRenderer(pipelines, object_manager)

    scene = _WireFormatScene(server=MagicMock(), renderer=renderer)
    scene._scene_graph = graph

    return scene


def _build_full_scene_details(dataset):
    """Load ``dataset`` and return the ``VisorSceneDetails`` produced by the
    real, unmodified ``VisorSceneBase.get_scene_details()`` path."""
    return _build_scene(dataset).get_scene_details()



def _build_end_to_end_payload(dataset) -> SceneGraphNodeInfo:
    """Load ``dataset`` and return the ``SceneGraphNodeInfo`` produced by the
    real, unmodified ``VisorSceneBase.get_scene_details()`` path."""
    return _build_full_scene_details(dataset).vtk_info.scene_graph



# ---------------------------------------------------------------------------
# Wire-format field inventory (frozen contract with the frontend).
# ---------------------------------------------------------------------------

# These are the fields SceneGraphNodeInfo exposes on ``main``. Any change to
# this set is a wire-format break and must be a coordinated frontend change
_WIRE_FIELDS = {
    "id", "name", "isActorNode", "isGroupNode",
    "dataArrays", "nodeType", "bounds", "children", "diffuseColor",
}


def _assert_wire_shape(info: SceneGraphNodeInfo) -> None:
    """Every node in the tree must expose exactly the frozen field set."""
    d = info.model_dump(by_alias=True)
    assert set(d.keys()) == _WIRE_FIELDS, (
        f"wire-format drift: got {sorted(d.keys())}, expected {sorted(_WIRE_FIELDS)}"
    )
    for child in info.children:
        _assert_wire_shape(child)


# ---------------------------------------------------------------------------
# Single-part scene (vtkPolyData sphere loaded as a leaf).
# ---------------------------------------------------------------------------

def test_single_part_payload_shape_and_types():
    poly = _sphere_polydata()
    out = _build_end_to_end_payload(poly)

    # Root
    _assert_wire_shape(out)
    assert out.name == "root"
    assert out.node_type == "root"
    assert out.is_group_node is True
    assert out.is_actor_node is False
    assert len(out.children) == 1

    # Dataset "group" wrapping the loaded polydata (single-leaf load creates a
    # part node directly as the dataset child, since polydata is not composite).
    part = out.children[0]
    assert part.is_actor_node is True  # wire-format contract preserved
    assert part.is_group_node is False
    assert part.node_type == "vtkPolyData"
    assert part.children == []
    assert isinstance(part.bounds, list) and len(part.bounds) == 6

    # dataArrays is a list (possibly empty for a raw sphere).
    assert isinstance(part.data_arrays, list)

    # diffuseColor is the Visor default.
    assert part.diffuse_color == VisorColors.DefaultMeshColor


# ---------------------------------------------------------------------------
# Composite (multi-block) scene: exercises group recursion.
# ---------------------------------------------------------------------------

def _two_block_dataset() -> vtkMultiBlockDataSet:
    mb = vtkMultiBlockDataSet()
    mb.SetNumberOfBlocks(2)
    mb.SetBlock(0, _sphere_polydata())
    mb.SetBlock(1, _sphere_polydata())
    return mb


def test_multiblock_payload_recurses_through_groups():
    mb = _two_block_dataset()
    out = _build_end_to_end_payload(mb)

    _assert_wire_shape(out)
    assert out.is_group_node is True
    # root -> multiblock-group -> [part, part]
    (group,) = out.children
    assert group.is_group_node is True
    assert group.is_actor_node is False
    assert group.node_type == "vtkMultiBlockDataSet"
    assert len(group.children) == 2

    for leaf in group.children:
        assert leaf.is_actor_node is True
        assert leaf.is_group_node is False
        assert leaf.node_type == "vtkPolyData"


# ---------------------------------------------------------------------------
# JSON round-trip: proves the payload is fully JSON-serialisable, which is
# what actually ships over the wire.
# ---------------------------------------------------------------------------

def test_payload_is_json_serialisable():
    out = _build_end_to_end_payload(_sphere_polydata())
    text = json.dumps(out.model_dump(by_alias=True))
    assert '"isActorNode"' in text
    # Round-trip parse.
    parsed = json.loads(text)
    assert parsed["name"] == "root"
    assert parsed["children"][0]["isActorNode"] is True


# ---------------------------------------------------------------------------
# The payload splits into a scene description and a renderer
# annotation, and no wasm*Id key appears anywhere under sceneGraph. Recursive
# sweep, not a spot check.
# ---------------------------------------------------------------------------

_WASM_ID_KEY_RE = re.compile(r"^wasm[A-Za-z]*Id$")


def _find_wasm_id_keys(obj, path: str = "") -> list:
    """Recursively collect every dict key that looks like a legacy
    ``wasm*Id`` renderer handle, anywhere in a JSON-shaped structure."""
    hits = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_path = f"{path}.{key}" if path else key
            if _WASM_ID_KEY_RE.match(key):
                hits.append(key_path)
            hits.extend(_find_wasm_id_keys(value, key_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            hits.extend(_find_wasm_id_keys(item, f"{path}[{i}]"))
    return hits


def test_payload_splits_scene_graph_and_renderer_annotation_with_no_wasm_ids_under_scene_graph():
    scene = _build_scene(_sphere_polydata())
    # Call the real production payload path -- get_scene_details_json() itself
    # does `json.dumps(self.get_scene_details().model_dump(exclude_none=True,
    # by_alias=True))` (vtk/scene/base.py) -- so a later change to those dump
    # kwargs is caught here rather than in a re-derived copy.
    payload = json.loads(scene.get_scene_details_json())

    assert "sceneGraph" in payload["vtkInfo"]
    assert "rendererAnnotation" in payload["vtkInfo"]
    assert _find_wasm_id_keys(payload["vtkInfo"]["sceneGraph"]) == []


# ---------------------------------------------------------------------------
# The `type` field of an emitted dataArrays entry is the plain wire
# string ("POINT"/"CELL"), not the VisorVtkVariableType enum member, in the
# actual emitted bytes -- exercised through the real get_scene_details_json()
# production path, not a re-derived model_dump call.
# ---------------------------------------------------------------------------

def _collect_data_arrays(node: dict) -> list:
    """Recursively collect every ``dataArrays`` entry under a sceneGraph node."""
    hits = list(node.get("dataArrays", []))
    for child in node.get("children", []):
        hits.extend(_collect_data_arrays(child))
    return hits


def test_data_array_type_is_str_and_point_or_cell_in_emitted_json():
    scene = _build_scene(_sphere_polydata_with_point_and_cell_arrays())
    payload = json.loads(scene.get_scene_details_json())

    all_data_arrays = _collect_data_arrays(payload["vtkInfo"]["sceneGraph"])

    # An empty dataArrays list cannot satisfy either assertion below.
    assert any(d["type"] == "POINT" for d in all_data_arrays)
    assert any(d["type"] == "CELL" for d in all_data_arrays)

    for d in all_data_arrays:
        assert isinstance(d["type"], str)
        assert d["type"] in {"POINT", "CELL"}


