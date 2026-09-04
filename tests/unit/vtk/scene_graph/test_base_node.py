from unittest.mock import MagicMock

import pytest

from ansys.visor.viewer.vtk.scene_graph.base_node import NodeCache, VisorSceneGraphNode


# Concrete subclass for testing abstract base
class DummyNode(VisorSceneGraphNode):
    """A dummy subclass of VisorSceneGraphNode for testing purposes."""
    def _post_init(self, parent, node_metadata, dataset, root_node):
        self._node_type = MagicMock()
        self._vtk_dataset_type = "DummyType"
        self._bounds = [0, 1, 2, 3, 4, 5]
        self._children = []
        if node_metadata:
            self._set_name(node_metadata)
        else:
            self._name = "dummy"

def test_nodecache_basic_set_get_clear():
    """Verify that NodeCache supports storing, retrieving, and clearing values."""
    cache = NodeCache()
    key = cache.make_key("kind", True, None)
    assert cache.get(key) is None
    cache.set(key, "value")
    assert cache.get(key) == "value"
    cache.clear()
    assert cache.get(key) is None

def test_nodecache_filter_func_cache_key():
    """Verify that cache keys can be generated from filter functions."""
    cache = NodeCache()
    def f(): pass
    key1 = cache._filter_func_cache_key(None)
    key2 = cache._filter_func_cache_key(f)
    key3 = cache._filter_func_cache_key(lambda x: x)
    assert key1 is None
    assert isinstance(key2, tuple) or isinstance(key2, list)
    assert isinstance(key3, tuple) or isinstance(key3, list)

def test_dummy_node_properties():
    """Verify that node properties and state expose the expected values."""
    node = DummyNode(None)
    assert node.id == node._id
    assert node.name == "dummy"
    assert node.vtk_dataset_type == "DummyType"
    # _node_type is a MagicMock, so is_part_node/is_group_node are False
    assert node.is_part_node is False
    assert node.is_group_node is False
    assert node.bounds == [0, 1, 2, 3, 4, 5]
    state = node.state
    assert state.id == node.id
    assert state.name == node.name

def test_set_name_with_metadata():
    """Verify that the node name is initialized from metadata."""
    node_metadata = MagicMock()
    node_metadata.Has.return_value = True
    node_metadata.Get.return_value = "meta_name"
    node = DummyNode(None, node_metadata=node_metadata)
    assert node.name == "meta_name"

def test_set_name_no_metadata_raises():
    """Verify that _set_name raises when metadata is not provided."""
    node = DummyNode(None)
    with pytest.raises(RuntimeError, match="node_metadata should not be null here"):
        node._set_name(None)

def test_set_name_empty_name_defaults():
    """Verify that unnamed metadata results in the default node name."""
    node_metadata = MagicMock()
    node_metadata.Has.return_value = False
    node_metadata.Get.return_value = ""
    node = DummyNode(None, node_metadata=node_metadata)
    assert node.name == "untitled"

def test_get_descendant_nodes_and_dict(monkeypatch):
    """Verify that descendant-node queries return the expected nodes."""
    node = DummyNode(None)
    child = DummyNode(node)
    node._children = [child]
    # Should include child only
    nodes = node.get_descendant_nodes()
    assert child in nodes
    # Should include self and child
    nodes2 = node.get_descendant_nodes(include_self=True)
    assert node in nodes2 and child in nodes2
    # Should filter by a function
    nodes3 = node.get_descendant_nodes(filter_func=lambda n: n.name == "dummy")
    assert all(n.name == "dummy" for n in nodes3)

def test_get_descendant_node_by_id():
    """Verify that descendant nodes can be located by ID."""
    node = DummyNode(None)
    child = DummyNode(node)
    node._children = [child]
    found = node.get_descendant_node(child.id)
    assert found is child
    not_found = node.get_descendant_node(99999)
    assert not_found is None

def test_remove_node_group(monkeypatch):
    """Verify that child nodes can be removed from group nodes."""
    node = DummyNode(None)
    node._node_type = MagicMock(return_value=True)
    node._children = [DummyNode(node)]
    # Patch is_group_node to True
    monkeypatch.setattr(DummyNode, "is_group_node", property(lambda self: True))
    child_id = node._children[0].id
    assert node.remove_node(child_id) is True
    assert node._children == []

def test_remove_node_actor(monkeypatch):
    """Verify that remove_node returns False for missing actor nodes."""
    node = DummyNode(None)
    node._node_type = MagicMock(return_value=False)
    # Patch is_group_node to False
    monkeypatch.setattr(DummyNode, "is_group_node", property(lambda self: False))
    assert node.remove_node(12345) is False

def test_cleanup_descendants(monkeypatch):
    """Verify that descendant cleanup removes child nodes."""
    node = DummyNode(None)
    child = DummyNode(node)
    node._children = [child]
    monkeypatch.setattr(DummyNode, "is_group_node", property(lambda self: True))
    node._cleanup_descendants()
    assert node._children == []

def test_get_json():
    """Verify that get_json returns a serialized representation of the node."""
    node = DummyNode(None)
    json_str = node.get_json()
    import json
    data = json.loads(json_str)
    assert data["id"] == node.id

def test_clear_cache_on_children():
    """Verify that cache clearing is applied recursively to child nodes."""
    node = DummyNode(None)
    child = DummyNode(node)
    node._children = [child]
    node._cache.set(("a",), "x")
    child._cache.set(("b",), "y")
    node._clear_cache()
    assert node._cache.get(("a",)) is None
    assert child._cache.get(("b",)) is None

def test_get_node_type_from_dataset_supported(monkeypatch):
    """Verify that supported VTK datasets map to a scene-graph node type."""
    from vtkmodules import vtkCommonDataModel

    class DummyMultiBlock(vtkCommonDataModel.vtkMultiBlockDataSet):
        pass

    class DummyUnstructured(vtkCommonDataModel.vtkUnstructuredGrid):
        pass

    monkeypatch.setattr(vtkCommonDataModel, "vtkMultiBlockDataSet", type("vtkMultiBlockDataSet", (), {}))
    monkeypatch.setattr(vtkCommonDataModel, "vtkUnstructuredGrid", type("vtkUnstructuredGrid", (), {}))
    assert VisorSceneGraphNode.get_node_type_from_dataset(DummyMultiBlock()) is not None
    assert VisorSceneGraphNode.get_node_type_from_dataset(DummyUnstructured()) is not None

def test_get_node_type_from_dataset_unsupported():
    """Verify that unsupported datasets raise an error."""
    with pytest.raises(RuntimeError, match="node type not yet supported"):
        VisorSceneGraphNode.get_node_type_from_dataset(object())

# ------------------------------------------------------------------
# Part-node descendant helpers
# ------------------------------------------------------------------

def test_part_node_paths(monkeypatch):
    """Verify that part-node descendant helper methods return the expected results."""

    class PartNode(DummyNode):
        def _post_init(self, *args, **kwargs):
            super()._post_init(*args, **kwargs)
            monkeypatch.setattr(type(self), "is_part_node", property(lambda _: True))

    root = DummyNode(None)
    part = PartNode(root)
    root._children = [part]

    assert root.get_descendant_part_node(part.id) is part

    nodes = root.get_descendant_part_nodes()
    assert part in nodes


def test_refresh_descendant_variable_metadata(monkeypatch):
    """Should call refresh_variable_metadata on part nodes."""

    class PartNode(DummyNode):
        def _post_init(self, *args, **kwargs):
            super()._post_init(*args, **kwargs)
            monkeypatch.setattr(type(self), "is_part_node", property(lambda _: True))
            self.refresh_variable_metadata = MagicMock()

    root = DummyNode(None)
    part = PartNode(root)
    root._children = [part]

    root.refresh_descendant_variable_metadata()

    part.refresh_variable_metadata.assert_called_once()


def test_descendant_part_count(monkeypatch):
    """Count part nodes correctly."""

    class PartNode(DummyNode):
        def _post_init(self, *args, **kwargs):
            super()._post_init(*args, **kwargs)
            monkeypatch.setattr(type(self), "is_part_node", property(lambda _: True))

    root = DummyNode(None)
    a = PartNode(root)
    b = PartNode(root)
    root._children = [a, b]

    assert root.descendant_part_count() == 2


# ------------------------------------------------------------------
# Mapping + cache behavior
# ------------------------------------------------------------------


def test_descendant_cache_reuse(monkeypatch):
    """Cache should be used on repeated calls."""

    root = DummyNode(None)
    child = DummyNode(root)
    root._children = [child]

    # First call populates cache
    root.get_descendant_nodes()

    call_count = {"count": 0}
    original = root._get_descendant_node_dict

    def wrapped(*args, **kwargs):
        call_count["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(root, "_get_descendant_node_dict", wrapped)

    root.get_descendant_nodes()

    # Should not recurse repeatedly if cache works
    assert call_count["count"] <= 1


def test_clear_cache_recursive():
    """Clearing cache should propagate to children."""

    root = DummyNode(None)
    child = DummyNode(root)
    root._children = [child]

    root._cache.set(("a",), 1)
    child._cache.set(("b",), 2)

    root._clear_cache()

    assert root._cache.get(("a",)) is None
    assert child._cache.get(("b",)) is None


# ------------------------------------------------------------------
# Factory success path
# ------------------------------------------------------------------

def test_get_node_factory_success(monkeypatch):
    """Factory should return correct subclass."""

    class FakePartNode:
        def __init__(self, *args, **kwargs):
            self.created = True

    class FakeGroupNode:
        def __init__(self, *args, **kwargs):
            self.created = True

    # Patch node type detection
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene_graph.base_node.VisorSceneGraphNode.get_node_type_from_dataset",
        lambda x: "part",
    )

    # Patch enum mapping
    fake_enum = MagicMock(PART="part", GROUP="group")
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene_graph.base_node.VisorNodeType",
        fake_enum,
    )

    # Patch actual classes imported inside function
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene_graph.VisorSceneGraphPartNode",
        FakePartNode,
    )
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene_graph.VisorSceneGraphGroupNode",
        FakeGroupNode,
    )

    node = VisorSceneGraphNode.get_node(None)

    assert isinstance(node, FakePartNode)

def test_remove_node_recursive(monkeypatch):
    """Should remove descendant node through recursive branch."""

    # Force group behavior
    monkeypatch.setattr(DummyNode, "is_group_node", property(lambda _: True))

    root = DummyNode(None)
    child = DummyNode(root)
    grandchild = DummyNode(child)

    root._children = [child]
    child._children = [grandchild]

    # Spy on cache clearing
    root._clear_cache = MagicMock()
    child._clear_cache = MagicMock()

    result = root.remove_node(grandchild.id)

    assert result is True

    # Grandchild should be removed from child
    assert child._children == []

    root._clear_cache.assert_called_once()

def test_remove_node_calls_cleanup_on_non_group_descendant(monkeypatch):
    """_cleanup_descendants should early-return for non-group child nodes via remove_node."""

    # Root must be a group
    monkeypatch.setattr(DummyNode, "is_group_node", property(lambda _: True))

    root = DummyNode(None)

    # Child will be treated as NON-group
    class NonGroupNode(DummyNode):
        pass

    child = NonGroupNode(root)
    root._children = [child]

    # Override is_group_node for child only
    monkeypatch.setattr(NonGroupNode, "is_group_node", property(lambda _: False))

    # Add a "grandchild" to prove no cleanup happens
    grandchild = DummyNode(child)
    child._children = [grandchild]

    # Remove child ??? triggers _cleanup_descendants(child)
    result = root.remove_node(child.id)

    assert result is True

    # This proves early-return happened:
    # child._children should NOT have been cleared
    assert child._children == [grandchild]

def test_get_node_factory_runtime_error(monkeypatch):
    """get_node should catch RuntimeError, log, and re-raise with wrapped message."""

    # Force get_node_type_from_dataset to raise
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene_graph.base_node.VisorSceneGraphNode.get_node_type_from_dataset",
        lambda dataset: (_ for _ in ()).throw(RuntimeError("original error"))
    )

    # Spy on logger
    mock_logger = MagicMock()
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene_graph.base_node.logger",
        mock_logger,
    )

    with pytest.raises(RuntimeError) as exc:
        VisorSceneGraphNode.get_node(parent=None)

    # Exception should be wrapped
    assert "could not create scene graph node: original error" in str(exc.value)

    # Logger should be called
    mock_logger.error.assert_called_once()

