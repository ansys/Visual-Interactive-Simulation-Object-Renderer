"""Unit tests for VtkNodePipeline."""

from unittest.mock import MagicMock

import pytest
from vtkmodules.vtkCommonDataModel import vtkPlane, vtkPolyData, vtkUnstructuredGrid
from vtkmodules.vtkFiltersCore import vtkAppendPolyData
from vtkmodules.vtkFiltersGeometry import vtkGeometryFilter
from vtkmodules.vtkFiltersSources import vtkSphereSource
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

from ansys.visor.viewer.core.visor_colors import VisorColors
from ansys.visor.viewer.vtk.node_pipeline import VtkNodePipeline


@pytest.fixture
def poly_dataset() -> vtkPolyData:
    src = vtkSphereSource()
    src.Update()
    return src.GetOutput()


@pytest.fixture
def unstructured_dataset() -> vtkUnstructuredGrid:
    # Minimal empty vtkUnstructuredGrid is sufficient for pipeline wiring tests.
    return vtkUnstructuredGrid()


# ---------------------------------------------------------------------------
# from_dataset
# ---------------------------------------------------------------------------

def test_from_dataset_polydata_builds_append_algorithm(poly_dataset):
    pipe = VtkNodePipeline.from_dataset(poly_dataset)

    assert isinstance(pipe.base_algorithm, vtkAppendPolyData)
    assert isinstance(pipe.mapper, vtkPolyDataMapper)
    assert isinstance(pipe.actor, vtkActor)
    assert pipe.actor.GetMapper() is pipe.mapper
    # Mapper is wired to the base algorithm's output port.
    assert pipe.mapper.GetInputConnection(0, 0).GetProducer() is pipe.base_algorithm


def test_from_dataset_unstructured_builds_geometry_filter(unstructured_dataset):
    pipe = VtkNodePipeline.from_dataset(unstructured_dataset)

    assert isinstance(pipe.base_algorithm, vtkGeometryFilter)
    assert pipe.base_algorithm.GetNonlinearSubdivisionLevel() == 0
    assert pipe.mapper.GetInputConnection(0, 0).GetProducer() is pipe.base_algorithm


def test_from_dataset_sets_default_color_and_flat_shading(poly_dataset):
    pipe = VtkNodePipeline.from_dataset(poly_dataset)

    diffuse = pipe.actor.GetProperty().GetDiffuseColor()
    assert tuple(diffuse) == tuple(VisorColors.DefaultMeshColor)
    # Interpolation 0 == flat shading in VTK.
    assert pipe.actor.GetProperty().GetInterpolation() == 0


def test_from_dataset_unsupported_type_raises():
    with pytest.raises(RuntimeError, match="node type not yet supported"):
        VtkNodePipeline.from_dataset(object())


# ---------------------------------------------------------------------------
# set_clipping_plane
# ---------------------------------------------------------------------------

def test_set_clipping_plane_none_clears_planes():
    mapper = MagicMock()
    pipe = VtkNodePipeline(actor=MagicMock(), mapper=mapper, base_algorithm=MagicMock())

    pipe.set_clipping_plane(None)

    mapper.RemoveAllClippingPlanes.assert_called_once()
    mapper.AddClippingPlane.assert_not_called()


def test_set_clipping_plane_with_plane_adds_it():
    mapper = MagicMock()
    pipe = VtkNodePipeline(actor=MagicMock(), mapper=mapper, base_algorithm=MagicMock())
    plane = vtkPlane()

    pipe.set_clipping_plane(plane)

    mapper.RemoveAllClippingPlanes.assert_called_once()
    mapper.AddClippingPlane.assert_called_once_with(plane)


def test_set_clipping_plane_end_to_end_on_real_mapper(poly_dataset):
    pipe = VtkNodePipeline.from_dataset(poly_dataset)
    plane = vtkPlane()

    pipe.set_clipping_plane(plane)
    assert pipe.mapper.GetNumberOfClippingPlanes() == 1

    pipe.set_clipping_plane(None)
    assert pipe.mapper.GetNumberOfClippingPlanes() == 0


# ---------------------------------------------------------------------------
# update_input
# ---------------------------------------------------------------------------

def test_update_input_without_filter_reconnects_base(poly_dataset):
    pipe = VtkNodePipeline.from_dataset(poly_dataset)

    # Point the mapper somewhere else, then call update_input(None) and confirm
    # it reconnects to the base algorithm.
    other = vtkAppendPolyData()
    other.SetInputData(poly_dataset)
    pipe.mapper.SetInputConnection(other.GetOutputPort())
    assert pipe.mapper.GetInputConnection(0, 0).GetProducer() is other

    pipe.update_input(None)

    assert pipe.mapper.GetInputConnection(0, 0).GetProducer() is pipe.base_algorithm


def test_update_input_with_filter_uses_returned_algorithm(poly_dataset):
    pipe = VtkNodePipeline.from_dataset(poly_dataset)
    wrapper = vtkAppendPolyData()

    def algorithm_filter(base):
        # Chain: base -> wrapper
        wrapper.SetInputConnection(base.GetOutputPort())
        return wrapper

    pipe.update_input(algorithm_filter)

    assert pipe.mapper.GetInputConnection(0, 0).GetProducer() is wrapper


