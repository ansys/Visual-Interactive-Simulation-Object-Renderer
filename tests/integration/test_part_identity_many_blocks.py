# python
# File: `tests/integration/test_part_identity_many_blocks.py`
"""Part identity over an unnamed, ragged multiblock.

``many_blocks.vtm`` is 66 vtkPolyData leaves nested at four different depths,
and not one of its 66 ``<DataSet>`` elements carries a ``name`` attribute, so
every leaf takes the ``"untitled"`` fallback.  Under the old name-keyed seed
the whole file collapsed to a single part.  These tests pin the positional
seed: one part per leaf, part_id == scene-graph node ID == renderer pipeline
key, and flat_index order equal to part-node order on object identity.

All expected counts are hand-written literals, never derived from the VTK
object under test.
"""
import os

import pytest
from trame.app import get_server

from ansys.visor.viewer.core.metadata import ExtendedMetadata
from ansys.visor.viewer.vtk.io.file_to_dataset import file_to_dataset
from ansys.visor.viewer.vtk.scene.local_scene import VisorLocalScene

# many_blocks.vtm holds exactly 66 non-empty leaf blocks.
MANY_BLOCKS_LEAF_COUNT = 66


@pytest.fixture
def pipeline_instance():
    """PyTest fixture for pipeline instance."""
    server = get_server()
    assert server is not None, "get_server() returned None"
    scene = VisorLocalScene(server)
    yield scene
    try:
        scene.clear()
        scene.cleanup_state()
    except Exception:
        pass


def get_many_blocks_file():
    """Get the path to the ragged, unnamed multiblock test file."""
    return os.path.join(os.path.dirname(__file__), "..", "files", "many_blocks", "many_blocks.vtm")


@pytest.fixture
def loaded_many_blocks(pipeline_instance):
    """Load many_blocks.vtm through the real scene and return the pieces under test."""
    dataset = file_to_dataset(get_many_blocks_file())
    metadata = ExtendedMetadata(name="many_blocks", unit="m")
    dataset_id = pipeline_instance.add_dataset(dataset, metadata)

    subtree = pipeline_instance._scene_graph.get_descendant_node(dataset_id, include_self=True)
    part_nodes = subtree.get_descendant_part_nodes(include_self=True)
    part_index = pipeline_instance.datasets[dataset_id].part_index

    return pipeline_instance, dataset, part_nodes, part_index


def test_part_index_length_matches_leaf_count(loaded_many_blocks):
    """One part per non-empty leaf, all IDs distinct.

    Before the positional seed this was 1: all 66 leaves are named "untitled",
    so the name-keyed seed handed the same ID to every one of them.
    """
    _scene, _data, part_nodes, part_index = loaded_many_blocks

    assert len(part_index.part_ids) == MANY_BLOCKS_LEAF_COUNT
    assert len(set(part_index.part_ids)) == MANY_BLOCKS_LEAF_COUNT
    assert len(part_nodes) == MANY_BLOCKS_LEAF_COUNT


def test_flat_index_order_matches_part_node_order_by_object_identity(loaded_many_blocks):
    """Composite-iterator order and part-node order refer to the same leaves.

    The discriminator is Python object identity of the leaf ``vtkDataObject``,
    not bounds: two leaves sharing a bounding box would match by accident.
    """
    _scene, data, part_nodes, part_index = loaded_many_blocks

    assert len(part_nodes) == MANY_BLOCKS_LEAF_COUNT
    for node in part_nodes:
        assert part_index.get_leaf_block(node.id, data) is node.dataset


def test_part_ids_equal_node_ids_equal_pipeline_keys(loaded_many_blocks):
    """part_id == scene-graph node ID == renderer pipeline key, as three equal sets."""
    scene, _data, part_nodes, part_index = loaded_many_blocks

    part_ids = set(part_index.part_ids)
    node_ids = {node.id for node in part_nodes}
    pipeline_keys = set(scene._renderer._pipelines.keys())

    assert len(part_ids) == MANY_BLOCKS_LEAF_COUNT
    assert part_ids == node_ids
    assert part_ids == pipeline_keys

