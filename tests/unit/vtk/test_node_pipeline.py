"""Unit tests for VtkNodePipeline."""

from unittest.mock import MagicMock, patch

import pytest
from vtkmodules.vtkCommonCore import vtkFloatArray
from vtkmodules.vtkCommonDataModel import vtkPlane, vtkPolyData, vtkUnstructuredGrid
from vtkmodules.vtkFiltersCore import vtkAppendPolyData
from vtkmodules.vtkFiltersGeometry import vtkGeometryFilter
from vtkmodules.vtkFiltersSources import vtkSphereSource
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

from ansys.visor.viewer.core.visor_colors import VisorColors
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
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


@pytest.fixture
def array_dataset() -> vtkPolyData:
    """Sphere output carrying one named point array and one named cell array.

    Each array is sized from the dataset's own counts -- the point array to
    ``GetNumberOfPoints()`` and the cell array to ``GetNumberOfCells()`` -- so
    the arrays are valid for the association they are attached to.  For the
    default vtkSphereSource that is 50 points and 96 cells.
    """
    src = vtkSphereSource()
    src.Update()
    dataset = src.GetOutput()

    pressure = vtkFloatArray()
    pressure.SetName("pressure")
    pressure.SetNumberOfComponents(1)
    pressure.SetNumberOfTuples(dataset.GetNumberOfPoints())
    for i in range(dataset.GetNumberOfPoints()):
        pressure.SetTuple1(i, float(i))
    dataset.GetPointData().AddArray(pressure)

    temperature = vtkFloatArray()
    temperature.SetName("temperature")
    temperature.SetNumberOfComponents(1)
    temperature.SetNumberOfTuples(dataset.GetNumberOfCells())
    for i in range(dataset.GetNumberOfCells()):
        temperature.SetTuple1(i, float(i))
    dataset.GetCellData().AddArray(temperature)

    return dataset


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


# ---------------------------------------------------------------------------
# set_selected
#
# The selection highlight colour is ambient RGB 0, 62, 111 out of 255.  The
# expected values below are written as decimal literals so that the test does
# not restate the production expression.
# ---------------------------------------------------------------------------

SELECTION_AMBIENT_COLOR = (0.0, 0.24313725490196078, 0.43529411764705883)


def test_set_selected_true_sets_selection_ambient_color_and_lighting(poly_dataset):
    pipe = VtkNodePipeline.from_dataset(poly_dataset)

    pipe.set_selected(True, [0.1, 0.2, 0.3])

    prop = pipe.actor.GetProperty()
    assert prop.GetAmbientColor() == pytest.approx(SELECTION_AMBIENT_COLOR)
    assert prop.GetDiffuse() == pytest.approx(0.5)
    assert prop.GetAmbient() == pytest.approx(0.5)


def test_set_selected_true_still_applies_the_given_diffuse_color(poly_dataset):
    """Selecting changes the lighting terms; it does not replace the colour."""
    pipe = VtkNodePipeline.from_dataset(poly_dataset)

    pipe.set_selected(True, [1.0, 0.0, 0.0])

    assert pipe.actor.GetProperty().GetDiffuseColor() == pytest.approx((1.0, 0.0, 0.0))


def test_set_selected_false_restores_lighting_defaults(poly_dataset):
    pipe = VtkNodePipeline.from_dataset(poly_dataset)
    pipe.set_selected(True, [1.0, 0.0, 0.0])

    pipe.set_selected(False, [0.0, 1.0, 0.0])

    prop = pipe.actor.GetProperty()
    assert prop.GetDiffuse() == pytest.approx(1.0)
    assert prop.GetAmbient() == pytest.approx(0.0)
    assert prop.GetDiffuseColor() == pytest.approx((0.0, 1.0, 0.0))


def test_set_selected_false_leaves_ambient_color_untouched(poly_dataset):
    """Deselecting resets the ambient *term*, not the ambient colour."""
    pipe = VtkNodePipeline.from_dataset(poly_dataset)
    # Seeded ambient colour: a distinctive value neither branch writes.
    pipe.actor.GetProperty().SetAmbientColor(0.11, 0.22, 0.33)

    pipe.set_selected(False, [0.0, 1.0, 0.0])

    assert pipe.actor.GetProperty().GetAmbientColor() == pytest.approx(
        (0.11, 0.22, 0.33)
    )


# ---------------------------------------------------------------------------
# set_visibility
# ---------------------------------------------------------------------------

def test_set_visibility_true_shows_actor(poly_dataset):
    """set_visibility(True) leaves the actor's visibility flag set."""
    pipe = VtkNodePipeline.from_dataset(poly_dataset)
    pipe.actor.SetVisibility(0)

    pipe.set_visibility(True)

    assert pipe.actor.GetVisibility() == 1


def test_set_visibility_false_hides_actor(poly_dataset):
    """set_visibility(False) leaves the actor's visibility flag clear."""
    pipe = VtkNodePipeline.from_dataset(poly_dataset)
    pipe.actor.SetVisibility(1)

    pipe.set_visibility(False)

    assert pipe.actor.GetVisibility() == 0


# ---------------------------------------------------------------------------
# set_opacity
# ---------------------------------------------------------------------------

def test_set_opacity_sets_property_opacity(poly_dataset):
    """set_opacity writes the requested value onto the actor property."""
    pipe = VtkNodePipeline.from_dataset(poly_dataset)

    pipe.set_opacity(0.25)

    assert pipe.actor.GetProperty().GetOpacity() == pytest.approx(0.25)


def test_set_opacity_does_not_touch_visibility_or_diffuse_color(poly_dataset):
    """Opacity lands on the property's opacity field and nothing else."""
    pipe = VtkNodePipeline.from_dataset(poly_dataset)
    pipe.actor.SetVisibility(0)
    pipe.actor.GetProperty().SetDiffuseColor(0.25, 0.5, 0.75)

    pipe.set_opacity(0.25)

    assert pipe.actor.GetVisibility() == 0
    assert pipe.actor.GetProperty().GetDiffuseColor() == pytest.approx(
        (0.25, 0.5, 0.75)
    )


# ---------------------------------------------------------------------------
# set_diffuse_color
# ---------------------------------------------------------------------------

def test_set_diffuse_color_sets_property_diffuse_color(poly_dataset):
    """set_diffuse_color writes r, g, b onto the property's diffuse colour."""
    pipe = VtkNodePipeline.from_dataset(poly_dataset)

    pipe.set_diffuse_color(1.0, 0.0, 0.0)

    assert pipe.actor.GetProperty().GetDiffuseColor() == pytest.approx(
        (1.0, 0.0, 0.0)
    )


def test_set_diffuse_color_does_not_touch_ambient_color_or_opacity(poly_dataset):
    """SetDiffuseColor, not SetColor or SetAmbientColor, and opacity is left alone."""
    pipe = VtkNodePipeline.from_dataset(poly_dataset)
    pipe.actor.GetProperty().SetAmbientColor(0.25, 0.5, 0.75)
    pipe.actor.GetProperty().SetOpacity(0.75)

    pipe.set_diffuse_color(1.0, 0.0, 0.0)

    assert pipe.actor.GetProperty().GetAmbientColor() == pytest.approx(
        (0.25, 0.5, 0.75)
    )
    assert pipe.actor.GetProperty().GetOpacity() == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# set_color_variable
# ---------------------------------------------------------------------------

def test_set_color_variable_point_uses_point_field_data_and_selects_array(
    array_dataset,
):
    pipe = VtkNodePipeline.from_dataset(array_dataset)

    pipe.set_color_variable(VisorVtkVariableType.POINT, "pressure", 0, 0.0, 7.5)

    assert pipe.mapper.GetScalarModeAsString() == "UsePointFieldData"
    assert pipe.mapper.GetArrayName() == "pressure"


def test_set_color_variable_cell_uses_cell_field_data(array_dataset):
    pipe = VtkNodePipeline.from_dataset(array_dataset)

    pipe.set_color_variable(VisorVtkVariableType.CELL, "temperature", 0, 0.0, 7.5)

    assert pipe.mapper.GetScalarModeAsString() == "UseCellFieldData"
    assert pipe.mapper.GetArrayName() == "temperature"


def test_set_color_variable_sets_the_array_component(array_dataset):
    """Component selection lives on the mapper, not on a lookup table."""
    pipe = VtkNodePipeline.from_dataset(array_dataset)

    pipe.set_color_variable(VisorVtkVariableType.POINT, "pressure", 1, 0.0, 7.5)

    assert pipe.mapper.GetArrayComponent() == 1


def test_set_color_variable_sets_exact_scalar_range(array_dataset):
    """The mapper honours the passed range, not a table's own range.

    If SetUseLookupTableScalarRange(0) were omitted the mapper would defer to
    the lookup table and the range read back would not be what was passed.
    """
    pipe = VtkNodePipeline.from_dataset(array_dataset)

    pipe.set_color_variable(VisorVtkVariableType.POINT, "pressure", 0, 0.0, 7.5)

    assert pipe.mapper.GetScalarRange() == pytest.approx((0.0, 7.5))
    assert pipe.mapper.GetUseLookupTableScalarRange() == 0


def test_set_color_variable_enables_scalar_visibility_and_map_scalars(array_dataset):
    pipe = VtkNodePipeline.from_dataset(array_dataset)
    # Seeded scalar visibility: OFF, so an enabling call is visible.
    pipe.mapper.SetScalarVisibility(False)

    pipe.set_color_variable(VisorVtkVariableType.POINT, "pressure", 0, 0.0, 7.5)

    assert pipe.mapper.GetScalarVisibility() == 1
    assert pipe.mapper.GetColorModeAsString() == "MapScalars"


def test_set_color_variable_unknown_point_array_warns_and_mutates_nothing(
    array_dataset,
):
    pipe = VtkNodePipeline.from_dataset(array_dataset)
    # Seeded state: scalar visibility OFF and a sentinel array name.  If the
    # body wrongly proceeded, both would change.
    pipe.mapper.SetScalarVisibility(False)
    pipe.mapper.SelectColorArray("seeded-sentinel-array")

    with patch("ansys.visor.viewer.vtk.node_pipeline.logger") as mock_logger:
        pipe.set_color_variable(VisorVtkVariableType.POINT, "no-such-array", 0, 0.0, 7.5)

    mock_logger.warning.assert_called_once()
    assert pipe.mapper.GetScalarVisibility() == 0
    assert pipe.mapper.GetArrayName() == "seeded-sentinel-array"


def test_set_color_variable_unknown_cell_array_warns_and_mutates_nothing(array_dataset):
    pipe = VtkNodePipeline.from_dataset(array_dataset)
    # Seeded state, as above.  "pressure" exists but only as a *point* array,
    # so the cell-side lookup must miss.
    pipe.mapper.SetScalarVisibility(False)
    pipe.mapper.SelectColorArray("seeded-sentinel-array")

    with patch("ansys.visor.viewer.vtk.node_pipeline.logger") as mock_logger:
        pipe.set_color_variable(VisorVtkVariableType.CELL, "pressure", 0, 0.0, 7.5)

    mock_logger.warning.assert_called_once()
    assert pipe.mapper.GetScalarVisibility() == 0
    assert pipe.mapper.GetArrayName() == "seeded-sentinel-array"


def test_set_color_variable_non_enum_association_warns_and_mutates_nothing(
    array_dataset,
):
    """A bare string is not a VisorVtkVariableType and must not pick a branch."""
    pipe = VtkNodePipeline.from_dataset(array_dataset)
    # Seeded state: scalar visibility OFF and a sentinel array name.
    pipe.mapper.SetScalarVisibility(False)
    pipe.mapper.SelectColorArray("seeded-sentinel-array")

    with patch("ansys.visor.viewer.vtk.node_pipeline.logger") as mock_logger:
        pipe.set_color_variable("POINT", "pressure", 0, 0.0, 7.5)

    mock_logger.warning.assert_called_once()
    assert pipe.mapper.GetScalarVisibility() == 0
    assert pipe.mapper.GetArrayName() == "seeded-sentinel-array"


# ---------------------------------------------------------------------------
# clear_color_variable
# ---------------------------------------------------------------------------

def test_clear_color_variable_disables_scalar_visibility(array_dataset):
    pipe = VtkNodePipeline.from_dataset(array_dataset)
    pipe.set_color_variable(VisorVtkVariableType.POINT, "pressure", 0, 0.0, 7.5)
    assert pipe.mapper.GetScalarVisibility() == 1

    pipe.clear_color_variable()

    assert pipe.mapper.GetScalarVisibility() == 0


def test_clear_color_variable_leaves_diffuse_color_untouched(array_dataset):
    """Clearing does not restore or replace the part's diffuse colour."""
    pipe = VtkNodePipeline.from_dataset(array_dataset)
    # Seeded diffuse colour: distinctive, and not the default mesh colour.
    pipe.actor.GetProperty().SetDiffuseColor(0.11, 0.22, 0.33)

    pipe.clear_color_variable()

    assert pipe.actor.GetProperty().GetDiffuseColor() == pytest.approx(
        (0.11, 0.22, 0.33)
    )


