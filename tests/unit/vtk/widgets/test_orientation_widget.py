from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.vtk.widgets.visor_orientation import VisorOrientationWidget


@pytest.fixture
def mock_renderer():
    """Provides a mock renderer for testing."""
    return MagicMock()

@pytest.fixture
def mock_interactor():
    """Provides a mock interactor for testing."""
    return MagicMock()

@pytest.fixture
def mock_widget():
    """Provides a mock widget for testing."""
    widget = MagicMock()
    widget.GetEnabled.return_value = 1
    widget.GetRepresentation.return_value = MagicMock()
    return widget

@pytest.fixture
def mock_representation():
    """Provides a mock representation for testing."""
    rep = MagicMock()
    return rep

def test_init_creates_widget(monkeypatch, mock_renderer, mock_interactor, mock_widget, mock_representation):
    """Verify that widget is created."""
    # Patch vtkCameraOrientationWidget to return our mock
    with patch("ansys.visor.viewer.vtk.widgets.visor_orientation.vtkCameraOrientationWidget", return_value=mock_widget):
        mock_widget.GetRepresentation.return_value = mock_representation
        # Should not raise
        widget = VisorOrientationWidget(mock_renderer, mock_interactor)
        assert widget._VisorOrientationWidget__widget is mock_widget

def test_is_on_property(monkeypatch, mock_renderer, mock_interactor, mock_widget):
    """Verify that is_on property returns correct value based on widget's enabled state."""
    with patch("ansys.visor.viewer.vtk.widgets.visor_orientation.vtkCameraOrientationWidget", return_value=mock_widget):
        widget = VisorOrientationWidget(mock_renderer, mock_interactor)
        mock_widget.GetEnabled.return_value = 1
        assert widget.is_on is True
        mock_widget.GetEnabled.return_value = 0
        assert widget.is_on is False

def test_register_with_local_view(monkeypatch, mock_renderer, mock_interactor, mock_widget):
    """Verify that register_with_local_view method registers widget with local view."""
    with patch("ansys.visor.viewer.vtk.widgets.visor_orientation.vtkCameraOrientationWidget", return_value=mock_widget):
        widget = VisorOrientationWidget(mock_renderer, mock_interactor)
        local_view = MagicMock()
        local_view.register_vtk_object.return_value = 42
        widget.register_with_local_view(local_view)
        assert widget._VisorOrientationWidget__widget_wasm_id == 42

def test_widget_wasm_id_property(monkeypatch, mock_renderer, mock_interactor, mock_widget):
    """Verify that widget_wasm_id property returns correct value based on widget's enabled state."""
    with patch("ansys.visor.viewer.vtk.widgets.visor_orientation.vtkCameraOrientationWidget", return_value=mock_widget):
        widget = VisorOrientationWidget(mock_renderer, mock_interactor)
        # Not registered yet, should raise
        with pytest.raises(RuntimeError, match="register_with_local_view\\(\\) must be called before this property is available"):
            _ = widget.widget_wasm_id
        # Register and check
        local_view = MagicMock()
        local_view.register_vtk_object.return_value = 99
        widget.register_with_local_view(local_view)
        assert widget.widget_wasm_id == 99

