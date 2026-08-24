import pytest

from ansys.visor.viewer.vtk.widgets.visor_cross_section import VisorCrossSectionWidget


@pytest.fixture
def mocks(mocker):
    """Provides mocks for VTK classes used in VisorCrossSectionWidget."""
    # Patch VTK classes in the module under test (must use its real import path)
    plane = mocker.patch('ansys.visor.viewer.vtk.widgets.visor_cross_section.vtkPlane').return_value
    rep = mocker.patch('ansys.visor.viewer.vtk.widgets.visor_cross_section.vtkImplicitPlaneRepresentation').return_value
    widget = mocker.patch('ansys.visor.viewer.vtk.widgets.visor_cross_section.vtkImplicitPlaneWidget2').return_value
    algo = mocker.patch('ansys.visor.viewer.vtk.widgets.visor_cross_section.vtkAlgorithm').return_value
    clipper = mocker.patch('ansys.visor.viewer.vtk.widgets.visor_cross_section.vtkClipPolyData').return_value
    mocker.patch('ansys.visor.viewer.vtk.widgets.visor_cross_section.logger')
    localview = mocker.patch('ansys.visor.viewer.vtk.widgets.visor_cross_section.LocalView').return_value

    widget.GetEnabled.return_value = 1
    rep.PlaceWidget = mocker.Mock()
    rep.SetNormal = mocker.Mock()
    rep.SetOrigin = mocker.Mock()
    rep.SetPlaceFactor = mocker.Mock()
    rep.SetOutlineTranslation = mocker.Mock()
    widget.On = mocker.Mock()
    widget.Off = mocker.Mock()
    widget.SetInteractor = mocker.Mock()
    widget.SetRepresentation = mocker.Mock()
    plane.SetNormal = mocker.Mock()
    plane.SetOrigin = mocker.Mock()
    plane.normal = (0, 0, 1)
    algo.GetOutputPort = mocker.Mock(return_value='output_port')
    clipper.SetClipFunction = mocker.Mock()
    clipper.SetInsideOut = mocker.Mock()
    clipper.SetInputConnection = mocker.Mock()
    localview.register_vtk_object = mocker.Mock(side_effect=[1, 2, 3])
    interactor = mocker.Mock()
    return {
        'plane': plane,
        'rep': rep,
        'widget': widget,
        'algo': algo,
        'clipper': clipper,
        'localview': localview,
        'interactor': interactor
    }

def test_initialization(mocks):
    """Verify that VisorCrossSectionWidget initializes correctly with the provided interactor."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    assert widget._plane is not None
    assert widget._plane_representation is not None
    assert widget._plane_widget is not None
    assert callable(widget._algorithm_filter)
    assert widget._place_factor == 1.25
    assert widget._inside_out is False
    assert widget._plane_wasm_id is None
    assert widget._plane_widget_wasm_id is None
    assert widget._plane_representation_wasm_id is None

def test_update_bounds_calls_methods(mocks):
    """Verify that update_bounds calls the appropriate methods on the representation and plane."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    bounds = [1, 2, 3, 4, 5, 6]
    widget.update_bounds(bounds)
    assert mocks['rep'].PlaceWidget.call_count >= 1
    mocks['rep'].PlaceWidget.assert_any_call(bounds)
    mocks['rep'].SetOrigin.assert_called()
    mocks['rep'].SetNormal.assert_called()
    mocks['plane'].SetOrigin.assert_called()
    mocks['plane'].SetNormal.assert_called()

def test_plane_property(mocks):
    """Verify that the plane property returns the internal plane object."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    assert widget.plane is widget._plane

def test_algorithm_filter_property(mocks):
    """Verify that the algorithm_filter property returns the internal algorithm filter object."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    assert widget.algorithm_filter is widget._algorithm_filter

def test_plane_wasm_id_property_raises(mocks):
    """Verify that accessing plane_wasm_id before registration raises a RuntimeError."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    with pytest.raises(RuntimeError):
        _ = widget.plane_wasm_id

def test_plane_widget_wasm_id_property_raises(mocks):
    """Verify that accessing plane_widget_wasm_id before registration raises a RuntimeError."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    with pytest.raises(RuntimeError):
        _ = widget.plane_widget_wasm_id

def test_plane_representation_wasm_id_property_raises(mocks):
    """Verify that accessing plane_representation_wasm_id before registration raises a RuntimeError."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    with pytest.raises(RuntimeError):
        _ = widget.plane_representation_wasm_id

def test_is_on_property(mocks):
    """Verify that the is_on property returns the correct value."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    assert widget.is_on
    widget._plane_widget.GetEnabled.return_value = 0
    assert not widget.is_on

def test_register_with_local_view_sets_ids(mocks):
    """Verify that register_with_local_view sets the correct local view."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    widget.register_with_local_view(mocks['localview'])
    assert widget._plane_wasm_id == 1
    assert widget._plane_widget_wasm_id == 2
    assert widget._plane_representation_wasm_id == 3

def test_set_normal(mocks):
    """Verify that set_normal sets the correct value."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    normal = (1.0, 0.0, 0.0)
    widget.set_normal(normal)
    mocks['rep'].SetNormal.assert_called_with(*normal)
    mocks['plane'].SetNormal.assert_called_with(*normal)

def test_set_origin(mocks):
    """Verify that set_origin sets the correct value."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    origin = (0.0, 1.0, 2.0)
    widget.set_origin(origin)
    mocks['rep'].SetOrigin.assert_called_with(*origin)
    mocks['plane'].SetOrigin.assert_called_with(*origin)

def test_toggle_on_off(mocks):
    """Verify that toggle_on_off sets the correct value."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    widget._plane_widget.GetEnabled.return_value = 1
    widget.toggle_on_off()
    mocks['widget'].Off.assert_called()
    widget._plane_widget.GetEnabled.return_value = 0
    widget.toggle_on_off()
    mocks['widget'].On.assert_called()

def test_turn_on(mocks):
    """Verify that turn_on sets the correct value."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    widget.turn_on()
    mocks['widget'].On.assert_called()

def test_turn_off(mocks):
    """Verify that turn_off sets the correct value."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    widget.turn_off()
    mocks['widget'].Off.assert_called()

def test_update_bounds_missing_plane_representation(mocks):
    """Verify that update_bounds_missing_plane_representation raises a RuntimeError."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    del widget._plane_representation
    bounds = [1, 2, 3, 4, 5, 6]
    with pytest.raises(RuntimeError, match="_plane_representation must be initialized before calling update_bounds\(\)"):
        widget.update_bounds(bounds)

def test_plane_wasm_id_property_happy(mocks):
    """Verify the plane_wasm_id property happy case."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    widget.register_with_local_view(mocks['localview'])
    assert widget.plane_wasm_id == 1

def test_plane_widget_wasm_id_property_happy(mocks):
    """Verify the PlaneWidth property happy case."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    widget.register_with_local_view(mocks['localview'])
    assert widget.plane_widget_wasm_id == 2

def test_plane_representation_wasm_id_property_happy(mocks):
    """Verify the PlaneRepresentationId property happy case."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    widget.register_with_local_view(mocks['localview'])
    assert widget.plane_representation_wasm_id == 3

def test_algorithm_filter_hits_clipper_code(mocks):
    """Verify that the algorithm filter hits the clipper code."""
    widget = VisorCrossSectionWidget(mocks['interactor'])
    # Use the public algorithm_filter property to get the clipper
    clipper = widget.algorithm_filter(mocks['algo'])
    # Check that the returned object is the mocked clipper
    assert clipper is mocks['clipper']
    # Check that the clipper was configured correctly
    mocks['clipper'].SetClipFunction.assert_called_with(widget._plane)
    mocks['clipper'].SetInsideOut.assert_called_with(1 if widget._inside_out else 0)
    mocks['clipper'].SetInputConnection.assert_called_with(mocks['algo'].GetOutputPort())

def test_init_runtime_error_patch(mocks, mocker):
    """Verify that init_runtime_error_patch raises a RuntimeError."""
    # Patch the private method used in __init__ to raise RuntimeError
    mocker.patch(
        'ansys.visor.viewer.vtk.widgets.visor_cross_section.VisorCrossSectionWidget._initialize_plane',
        side_effect=RuntimeError("fail"),
    )
    with pytest.raises(RuntimeError, match="could not create cross-section widget: fail"):
        VisorCrossSectionWidget(mocks['interactor'])
