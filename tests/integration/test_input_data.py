import os

import vtk
from vtkmodules.vtkCommonDataModel import vtkMultiBlockDataSet, vtkPolyData, vtkUnstructuredGrid

from ansys.visor.viewer.vtk.io.file_to_dataset import file_to_dataset
from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraph

input_file_plate = os.path.join(os.path.dirname(__file__),"..", "files","plate.vtp")
input_file_mesh = os.path.join(os.path.dirname(__file__),"..", "files","mesh.vtu")
input_file_many_blocks = os.path.join(os.path.dirname(__file__), "..", "files", "many_blocks", "many_blocks.vtm")

# vtkhdf equivalents
input_file_plate_vtkhdf = os.path.join(os.path.dirname(__file__), "..", "files", "plate.vtkhdf")
input_file_mesh_vtkhdf = os.path.join(os.path.dirname(__file__), "..", "files", "mesh.vtkhdf")
input_file_multiblock_vtkhdf = os.path.join(os.path.dirname(__file__), "..", "files", "simple_multiblock.vtkhdf")


def test_input_vtp_file_to_dataset():
    """Test file_to_dataset with VTP input."""
    dataset = file_to_dataset(input_file_plate)
    assert dataset.IsA("vtkDataSet")


def test_input_vtu_file_to_dataset():
    """Test file_to_dataset with VTKU input."""
    dataset = file_to_dataset(input_file_mesh)
    assert dataset.IsA("vtkDataSet")


def test_input_vtm_file_to_dataset():
    """Test file_to_dataset with VTM input."""
    dataset = file_to_dataset(input_file_many_blocks)
    assert dataset.IsA("vtkCompositeDataSet")


def test_input_data_read_multi_block_input():
    """Test multiblock Python input is read correctly."""
    dataset = file_to_dataset(input_file_many_blocks)
    # test root node
    root_node = VisorSceneGraph()
    root_node.load_dataset(dataset, None)
    descendant_nodes_or_self = root_node.get_descendant_nodes(include_self=True)
    descendant_nodes = root_node.get_descendant_nodes(include_self=False)
    assert root_node.vtk_dataset_type == "root"
    assert root_node.is_group_node
    assert len(descendant_nodes) == 75
    assert len(descendant_nodes_or_self) == 76
    assert descendant_nodes_or_self[0] == root_node
    assert len(root_node.children) == 1
    # test file node
    file_node = root_node.children[0]
    assert file_node.vtk_dataset_type == "vtkMultiBlockDataSet"
    assert file_node.is_group_node
    assert file_node.bounds == root_node.bounds
    descendant_nodes_or_self = file_node.get_descendant_nodes(include_self=True)
    descendant_nodes = file_node.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 74
    assert len(descendant_nodes_or_self) == 75
    assert descendant_nodes_or_self[0] == file_node
    assert len(file_node.children) == 2
    # test Group A
    group_a = file_node.children[0]
    assert group_a.vtk_dataset_type == "vtkMultiBlockDataSet"
    assert group_a.is_group_node
    descendant_nodes_or_self = group_a.get_descendant_nodes(include_self=True)
    descendant_nodes = group_a.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 65
    assert len(descendant_nodes_or_self) == 66
    assert descendant_nodes_or_self[0] == group_a
    assert len(group_a.children) == 3    # test Group AA
    group_aa = group_a.children[0]
    assert group_aa.vtk_dataset_type == "vtkMultiBlockDataSet"
    assert group_aa.is_group_node
    descendant_nodes_or_self = group_aa.get_descendant_nodes(include_self=True)
    descendant_nodes = group_aa.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 20
    assert len(descendant_nodes_or_self) == 21
    assert descendant_nodes_or_self[0] == group_aa
    assert len(group_aa.children) == 10
    for node in group_aa.children:
        if node.is_group_node:
            continue
        assert node.vtk_dataset_type == "vtkPolyData"
        assert not node.is_group_node
        descendant_nodes_or_self = node.get_descendant_nodes(include_self=True)
        descendant_nodes = node.get_descendant_nodes(include_self=False)
        assert len(descendant_nodes) == 0
        assert len(descendant_nodes_or_self) == 1
        assert descendant_nodes_or_self[0] == node
    # test Group AAA
    group_aaa = [node for node in group_aa.children if node.is_group_node][0]
    assert group_aaa.vtk_dataset_type == "vtkMultiBlockDataSet"
    assert group_aaa.is_group_node
    descendant_nodes_or_self = group_aaa.get_descendant_nodes(include_self=True)
    descendant_nodes = group_aaa.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 10
    assert len(descendant_nodes_or_self) == 11
    assert descendant_nodes_or_self[0] == group_aaa
    assert len(group_aaa.children) == 10
    for node in group_aaa.children:
        if node.is_group_node:
            continue
        assert node.vtk_dataset_type == "vtkPolyData"
        assert not node.is_group_node
        descendant_nodes_or_self = node.get_descendant_nodes(include_self=True)
        descendant_nodes = node.get_descendant_nodes(include_self=False)
        assert len(descendant_nodes) == 0
        assert len(descendant_nodes_or_self) == 1
        assert descendant_nodes_or_self[0] == node
    # test Group AB
    group_ab = group_a.children[1]
    assert group_ab.vtk_dataset_type == "vtkMultiBlockDataSet"
    assert group_ab.is_group_node
    descendant_nodes_or_self = group_ab.get_descendant_nodes(include_self=True)
    descendant_nodes = group_ab.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 10
    assert len(descendant_nodes_or_self) == 11
    assert descendant_nodes_or_self[0] == group_ab
    assert len(group_ab.children) == 10
    for node in group_ab.children:
        if node.is_group_node:
            continue
        assert node.vtk_dataset_type == "vtkPolyData"
        assert not node.is_group_node
        descendant_nodes_or_self = node.get_descendant_nodes(include_self=True)
        descendant_nodes = node.get_descendant_nodes(include_self=False)
        assert len(descendant_nodes) == 0
        assert len(descendant_nodes_or_self) == 1
        assert descendant_nodes_or_self[0] == node
    # test Group AC
    group_ac = group_a.children[2]
    assert group_ac.vtk_dataset_type == "vtkMultiBlockDataSet"
    assert group_ac.is_group_node
    descendant_nodes_or_self = group_ac.get_descendant_nodes(include_self=True)
    descendant_nodes = group_ac.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 32
    assert len(descendant_nodes_or_self) == 33
    assert descendant_nodes_or_self[0] == group_ac
    assert len(group_ac.children) == 1
    # test Group ACA
    group_aca = group_ac.children[0]
    assert group_aca.vtk_dataset_type == "vtkMultiBlockDataSet"
    assert group_aca.is_group_node
    descendant_nodes_or_self = group_aca.get_descendant_nodes(include_self=True)
    descendant_nodes = group_aca.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 31
    assert len(descendant_nodes_or_self) == 32
    assert descendant_nodes_or_self[0] == group_aca
    assert len(group_aca.children) == 20
    for node in group_aca.children:
        if node.is_group_node:
            continue
        assert node.vtk_dataset_type == "vtkPolyData"
        assert not node.is_group_node
        descendant_nodes_or_self = node.get_descendant_nodes(include_self=True)
        descendant_nodes = node.get_descendant_nodes(include_self=False)
        assert len(descendant_nodes) == 0
        assert len(descendant_nodes_or_self) == 1
        assert descendant_nodes_or_self[0] == node
    # test Group ACAA
    group_acaa = [node for node in group_aca.children if node.is_group_node][0]
    assert group_acaa.vtk_dataset_type == "vtkMultiBlockDataSet"
    assert group_acaa.is_group_node
    descendant_nodes_or_self = group_acaa.get_descendant_nodes(include_self=True)
    descendant_nodes = group_acaa.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 11
    assert len(descendant_nodes_or_self) == 12
    assert descendant_nodes_or_self[0] == group_acaa
    assert len(group_acaa.children) == 11
    for node in group_acaa.children:
        if node.is_group_node:
            continue
        assert node.vtk_dataset_type == "vtkPolyData"
        assert not node.is_group_node
        descendant_nodes_or_self = node.get_descendant_nodes(include_self=True)
        descendant_nodes = node.get_descendant_nodes(include_self=False)
        assert len(descendant_nodes) == 0
        assert len(descendant_nodes_or_self) == 1
        assert descendant_nodes_or_self[0] == node
    # test Group B
    group_b = file_node.children[1]
    assert group_b.vtk_dataset_type == "vtkMultiBlockDataSet"
    assert group_b.is_group_node
    descendant_nodes_or_self = group_b.get_descendant_nodes(include_self=True)
    descendant_nodes = group_b.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 7
    assert len(descendant_nodes_or_self) == 8
    assert descendant_nodes_or_self[0] == group_b
    assert len(group_b.children) == 7
    for node in group_b.children:
        if node.is_group_node:
            continue
        assert node.vtk_dataset_type == "vtkPolyData"
        assert not node.is_group_node
        descendant_nodes_or_self = node.get_descendant_nodes(include_self=True)
        descendant_nodes = node.get_descendant_nodes(include_self=False)
        assert len(descendant_nodes) == 0
        assert len(descendant_nodes_or_self) == 1
        assert descendant_nodes_or_self[0] == node


def test_input_data_read_poly_data_input():
    """Test that PolyData Python input is read correctly."""
    dataset = file_to_dataset(input_file_plate)

    # test root node
    root_node = VisorSceneGraph()
    root_node.load_dataset(dataset, None)
    assert root_node.vtk_dataset_type == "root"
    assert root_node.is_group_node
    descendant_nodes_or_self = root_node.get_descendant_nodes(include_self=True)
    descendant_nodes = root_node.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 1
    assert len(descendant_nodes_or_self) == 2
    assert descendant_nodes_or_self[0] == root_node
    assert len(root_node.children) == 1
    # test file node
    file_node = root_node.children[0]
    assert file_node.vtk_dataset_type == "vtkPolyData"
    assert not file_node.is_group_node
    assert file_node.bounds == root_node.bounds
    descendant_nodes_or_self = file_node.get_descendant_nodes(include_self=True)
    descendant_nodes = file_node.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 0
    assert len(descendant_nodes_or_self) == 1
    assert descendant_nodes_or_self[0] == file_node


def test_input_data_read_unstructured_grid_input():
    """Test that unstructured grid Python input is read correctly."""
    dataset = file_to_dataset(input_file_mesh)

    # test root node
    root_node = VisorSceneGraph()
    root_node.load_dataset(dataset, None)
    assert root_node.vtk_dataset_type == "root"
    assert root_node.is_group_node
    descendant_nodes_or_self = root_node.get_descendant_nodes(include_self=True)
    descendant_nodes = root_node.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 1
    assert len(descendant_nodes_or_self) == 2
    assert descendant_nodes_or_self[0] == root_node
    assert len(root_node.children) == 1
    # test file node
    file_node = root_node.children[0]
    assert file_node.vtk_dataset_type == "vtkUnstructuredGrid"
    assert not file_node.is_group_node
    assert file_node.bounds == file_node.bounds
    descendant_nodes_or_self = file_node.get_descendant_nodes(include_self=True)
    descendant_nodes = file_node.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 0
    assert len(descendant_nodes_or_self) == 1
    assert descendant_nodes_or_self[0] == file_node

def test_input_data_read_dataset_input():
    """ Test that a random vtkPolyData Python input is read correctly."""
    polydata_input = create_random_polydata_object()
    root_node = VisorSceneGraph()
    root_node.load_dataset(polydata_input, None)
    assert root_node.vtk_dataset_type == "root"
    assert root_node.is_group_node
    descendant_nodes_or_self = root_node.get_descendant_nodes(include_self=True)
    descendant_nodes = root_node.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 1
    assert len(descendant_nodes_or_self) == 2
    assert descendant_nodes_or_self[0] == root_node
    assert len(root_node.children) == 1
    # test file node
    file_node = root_node.children[0]
    assert file_node.vtk_dataset_type == "vtkPolyData"
    assert not file_node.is_group_node
    assert file_node.bounds == root_node.bounds
    descendant_nodes_or_self = file_node.get_descendant_nodes(include_self=True)
    descendant_nodes = file_node.get_descendant_nodes(include_self=False)
    assert len(descendant_nodes) == 0
    assert len(descendant_nodes_or_self) == 1
    assert descendant_nodes_or_self[0] == file_node

def create_random_polydata_object():
        """Create a random vtkPolyData object for testing."""
        points = vtk.vtkPoints()
        for i in range(10):
            points.InsertNextPoint(i, i, i)
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        return polydata

def create_random_unstructured_grid_object():
        """Create a random vtkUnstructuredGrid object for testing."""
        points = vtk.vtkPoints()
        for i in range(10):
            points.InsertNextPoint(i, i, i)
        unstructured_grid = vtk.vtkUnstructuredGrid()
        unstructured_grid.SetPoints(points)
        return unstructured_grid

def create_random_multiblock_dataset_object():
        """Create a random vtkMultiBlockDataSet object for testing."""
        multiblock_dataset = vtk.vtkMultiBlockDataSet()
        block1 = create_random_polydata_object()
        block2 = create_random_unstructured_grid_object()
        multiblock_dataset.SetBlock(0, block1)
        multiblock_dataset.SetBlock(1, block2)
        return multiblock_dataset

# ================================================================== #
# vtkhdf read support ??? file_to_dataset
# ================================================================== #

def test_input_vtkhdf_polydata_file_to_dataset():
    """plate.vtkhdf must be read as a vtkPolyData (vtkDataSet)."""
    dataset = file_to_dataset(input_file_plate_vtkhdf)
    assert isinstance(dataset, vtkPolyData)
    assert dataset.IsA("vtkDataSet")
    assert dataset.GetNumberOfPoints() > 0
    assert dataset.GetNumberOfCells() > 0


def test_input_vtkhdf_unstructured_grid_file_to_dataset():
    """mesh.vtkhdf must be read as a vtkUnstructuredGrid (vtkDataSet)."""
    dataset = file_to_dataset(input_file_mesh_vtkhdf)
    assert isinstance(dataset, vtkUnstructuredGrid)
    assert dataset.IsA("vtkDataSet")
    assert dataset.GetNumberOfPoints() > 0
    assert dataset.GetNumberOfCells() > 0


def test_input_vtkhdf_multiblock_file_to_dataset():
    """simple_multiblock.vtkhdf must be read as a vtkMultiBlockDataSet (vtkCompositeDataSet)."""
    dataset = file_to_dataset(input_file_multiblock_vtkhdf)
    assert isinstance(dataset, vtkMultiBlockDataSet)
    assert dataset.IsA("vtkCompositeDataSet")
    assert dataset.GetNumberOfBlocks() > 0


# ================================================================== #
# vtkhdf read support ??? point/cell parity with legacy equivalents
# ================================================================== #

def test_vtkhdf_polydata_matches_vtp_point_and_cell_count():
    """plate.vtkhdf and plate.vtp must contain the same geometry."""
    vtp_dataset = file_to_dataset(input_file_plate)
    vtkhdf_dataset = file_to_dataset(input_file_plate_vtkhdf)
    assert vtkhdf_dataset.GetNumberOfPoints() == vtp_dataset.GetNumberOfPoints()
    assert vtkhdf_dataset.GetNumberOfCells() == vtp_dataset.GetNumberOfCells()


def test_vtkhdf_unstructured_grid_matches_vtu_point_and_cell_count():
    """mesh.vtkhdf and mesh.vtu must contain the same geometry."""
    vtu_dataset = file_to_dataset(input_file_mesh)
    vtkhdf_dataset = file_to_dataset(input_file_mesh_vtkhdf)
    assert vtkhdf_dataset.GetNumberOfPoints() == vtu_dataset.GetNumberOfPoints()
    assert vtkhdf_dataset.GetNumberOfCells() == vtu_dataset.GetNumberOfCells()


# ================================================================== #
# vtkhdf read support ??? scene graph construction
# ================================================================== #

def test_vtkhdf_polydata_scene_graph_is_single_part_node():
    """Loading plate.vtkhdf must produce a single vtkPolyData part node ??? same
    shape as loading plate.vtp."""
    dataset = file_to_dataset(input_file_plate_vtkhdf)
    root_node = VisorSceneGraph()
    root_node.load_dataset(dataset, None)

    assert root_node.vtk_dataset_type == "root"
    assert root_node.is_group_node is True
    assert len(root_node.children) == 1

    file_node = root_node.children[0]
    assert file_node.vtk_dataset_type == "vtkPolyData"
    assert file_node.is_group_node is False
    assert file_node.is_part_node is True
    assert file_node.dataset is not None
    assert file_node.dataset.IsA("vtkPolyData")
    assert len(file_node.get_descendant_nodes(include_self=False)) == 0


def test_vtkhdf_unstructured_grid_scene_graph_is_single_part_node():
    """Loading mesh.vtkhdf must produce a single vtkUnstructuredGrid part node ???
    same shape as loading mesh.vtu."""
    dataset = file_to_dataset(input_file_mesh_vtkhdf)
    root_node = VisorSceneGraph()
    root_node.load_dataset(dataset, None)

    assert root_node.vtk_dataset_type == "root"
    assert len(root_node.children) == 1

    file_node = root_node.children[0]
    assert file_node.vtk_dataset_type == "vtkUnstructuredGrid"
    assert file_node.is_group_node is False
    assert file_node.is_part_node is True
    assert len(file_node.get_descendant_nodes(include_self=False)) == 0


def test_vtkhdf_multiblock_scene_graph_is_group_node():
    """Loading simple_multiblock.vtkhdf must produce a vtkMultiBlockDataSet group
    node with at least one child actor ??? same structure as loading an equivalent .vtm."""
    dataset = file_to_dataset(input_file_multiblock_vtkhdf)
    root_node = VisorSceneGraph()
    root_node.load_dataset(dataset, None)

    assert root_node.vtk_dataset_type == "root"
    assert len(root_node.children) == 1

    file_node = root_node.children[0]
    assert file_node.vtk_dataset_type == "vtkMultiBlockDataSet"
    assert file_node.is_group_node is True

    part_nodes = file_node.get_descendant_nodes(
        include_self=False,
        filter_func=lambda n: n.is_part_node
    )
    assert len(part_nodes) > 0
    for part_node in part_nodes:
        assert part_node.dataset is not None


def test_vtkhdf_multiblock_block_names_are_preserved():
    """Block names written into the vtkhdf multiblock file must survive the
    read and appear in the scene graph node names."""
    dataset = file_to_dataset(input_file_multiblock_vtkhdf)
    root_node = VisorSceneGraph()
    root_node.load_dataset(dataset, None)

    file_node = root_node.children[0]
    name_to_id = file_node.get_descendant_node_name_to_id_map()
    # simple_multiblock.vtkhdf was written with a block named "sphere"
    assert "sphere" in name_to_id


def test_vtkhdf_polydata_scene_graph_bounds_are_non_trivial():
    """bounds reported by the scene graph node must be non-zero for real geometry."""
    dataset = file_to_dataset(input_file_plate_vtkhdf)
    root_node = VisorSceneGraph()
    root_node.load_dataset(dataset, None)

    file_node = root_node.children[0]
    bounds = file_node.bounds
    assert len(bounds) == 6
    # At least one axis must span a non-zero range
    assert any(bounds[i + 1] - bounds[i] > 0 for i in range(0, 6, 2))
