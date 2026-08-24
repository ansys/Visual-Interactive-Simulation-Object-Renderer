"""Class for creating an orientation widget in the Visor visualizer."""


from trame_vtklocal.widgets.vtklocal import LocalView
from vtkmodules.vtkInteractionWidgets import vtkCameraOrientationRepresentation, vtkCameraOrientationWidget
from vtkmodules.vtkRenderingCore import vtkRenderer, vtkRenderWindowInteractor

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger

logger = VisorDefaultLogger(__name__)


class VisorOrientationWidget:
    """
    Class for creating an orientation widget in the Visor visualizer.

    Attributes:
        __widget (vtkCameraOrientationWidget): The VTK camera orientation widget.
        __widget_wasm_id (int | None): The ID of the widget in the local view, or None if not registered.

    Methods:
        register_with_local_view(local_view)

    Properties:
        is_on (bool): Whether the widget is on or not.
        register_with_local_view(local_view)
    """
    def __init__(self, renderer: vtkRenderer, window_interactor: vtkRenderWindowInteractor):
        """Initialize the orientation widget."""
        try:
            logger.info("Beginning creating orientation widget")
            widget = vtkCameraOrientationWidget(parent_renderer=renderer, interactor=window_interactor)
            representation: vtkCameraOrientationRepresentation = widget.GetRepresentation()
            representation.AnchorToLowerLeft()
            widget.On()
            logger.info("Finished creating orientation widget")
        except RuntimeError as e:
            msg = f"could not create orientation widget: {e}"
            logger.error(msg)
            raise RuntimeError(msg)

        self.__widget: vtkCameraOrientationWidget = widget
        self.__widget_wasm_id: int | None = None

    @property
    def is_on(self):
        """Return whether the widget is on or not."""
        return self.__widget.GetEnabled() == 1

    def register_with_local_view(self, local_view: LocalView):
        """Register the widget with the local view."""
        self.__widget_wasm_id = local_view.register_vtk_object(self.__widget)

    @property
    def widget_wasm_id(self):
        """Return the widget WASM ID."""
        if self.__widget_wasm_id is None:
            method_name = self.register_with_local_view.__name__
            raise RuntimeError(f"{method_name}() must be called before this property is available")
        return self.__widget_wasm_id
