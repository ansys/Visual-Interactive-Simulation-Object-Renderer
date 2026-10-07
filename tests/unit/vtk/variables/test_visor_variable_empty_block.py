"""G4: variable metadata on a multiblock with an empty (None) block.

The scene graph and the dataset's PartIndex must name the same parts with the
same variables, or the record's ``part_ids`` name ids the client's nodes lack.

Expected to fail today on F-E: ``VisorGroupNode._post_init`` walks every
``GetBlock(i)`` including ``None``, and node creation raises RuntimeError.
PartIndex skips empty blocks.  Found-not-fixed.
"""
import pytest
from vtkmodules.vtkCommonCore import vtkFloatArray
from vtkmodules.vtkCommonDataModel import vtkMultiBlockDataSet
from vtkmodules.vtkFiltersSources import vtkSphereSource

from ansys.visor.viewer.core.metadata import ExtendedMetadata
from ansys.visor.viewer.vtk.datasets.visor_dataset import VisorDataset
from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraph


def _sphere_with_point_array(name: str):
    src = vtkSphereSource()
    src.Update()
    poly = src.GetOutput()
    array = vtkFloatArray()
    array.SetName(name)
    array.SetNumberOfComponents(1)
    array.SetNumberOfTuples(poly.GetNumberOfPoints())
    for i in range(poly.GetNumberOfPoints()):
        array.SetTuple1(i, float(i))
    poly.GetPointData().AddArray(array)
    return poly


def _multiblock_with_an_empty_block() -> vtkMultiBlockDataSet:
    mb = vtkMultiBlockDataSet()
    mb.SetNumberOfBlocks(3)
    mb.SetBlock(0, _sphere_with_point_array("pressure"))
    # Block 1 is left None: the empty block.
    mb.SetBlock(2, _sphere_with_point_array("temperature"))
    return mb


@pytest.mark.xfail(
    strict=True,
    raises=RuntimeError,
    reason="VisorGroupNode._post_init walks the None block and node creation raises "
           "RuntimeError; PartIndex skips it.  Found, not fixed.",
)
def test_part_node_data_arrays_and_list_variables_agree_on_an_empty_block():
    """#23: per part id, part_node.data_arrays and dataset.list_variables() name the same arrays."""
    mb = _multiblock_with_an_empty_block()

    graph = VisorSceneGraph()
    graph.load_dataset(mb, "ds")
    part_nodes = graph.get_descendant_part_nodes(include_self=False)
    node_ids = [node.id for node in part_nodes]
    dataset = VisorDataset(1, "ds", mb, node_ids, ExtendedMetadata(name="ds", unit="m"))

    # Hand-written, in leaf order: the two non-empty blocks.
    expected_names = [["pressure"], ["temperature"]]
    assert len(node_ids) == 2
    expected = dict(zip(node_ids, expected_names))

    from_graph = {node.id: [info.name for info in node.data_arrays] for node in part_nodes}
    from_dataset = {
        part.part_id: [variable.name for variable in part.variables]
        for part in dataset.list_variables()
    }
    assert from_graph == expected
    assert from_dataset == expected

