"""Class for creating a cross-section widget in the Visor visualizer."""

from typing import Callable

from trame_vtklocal.widgets.vtklocal import LocalView
from vtkmodules.vtkCommonDataModel import vtkPlane
from vtkmodules.vtkCommonExecutionModel import vtkAlgorithm
from vtkmodules.vtkFiltersCore import vtkClipPolyData
from vtkmodules.vtkInteractionWidgets import vtkImplicitPlaneRepresentation, vtkImplicitPlaneWidget2
from vtkmodules.vtkRenderingCore import vtkRenderWindowInteractor

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger

logger = VisorDefaultLogger(__name__)


class VisorCrossSectionWidget:
    """
    Class for creating a cross-section widget in the Visor visualizer.

    Attributes:
        _plane (vtkPlane): The VTK plane used for clipping.
        _plane_representation (vtkImplicitPlaneRepresentation): The representation of the plane in the widget.
        _plane_widget (vtkImplicitPlaneWidget2): The VTK widget for interacting with the plane.
        _algorithm_filter (Callable[[vtkAlgorithm], vtkAlgorithm]): A callable that applies the clipping algorithm to a given VTK algorithm.
        _plane_wasm_id (int | None): The WebAssembly ID for the plane object, if registered with a local view.
        _plane_widget_wasm_id (int | None): The WebAssembly ID for the plane widget, if registered with a local view.
        _plane_representation_wasm_id (int | None): The WebAssembly ID for the plane representation, if registered with a local view.
        _place_factor (float): The factor applied to the plane representation.
        _inside_out (bool): Whether or not the plane is inside out or not.

    Methods:
        update_bounds(initial_bounds): Updates the bounding box around the given VTK bounding box.
        register_with_local_view(local_view): Registers the VTK objects with a local view and assigns their WebAssembly IDs.
        set_normal(normal): Sets the normal vector of the plane.
        set_origin(origin): Sets the origin point of the plane.
        toggle_on_off(): Toggles the visibility of the plane widget on or off.
        turn_on(): Turns on the plane widget.
        turn_off(): Turns off the plane widget.

    Properties:
        plane: Returns the VTK plane object.
        algorithm_filter: Returns the VTK algorithm filter.
        plane_wasm_id: Returns the WebAssembly ID for the plane object.
        plane_widget_wasm_id: Returns the WebAssembly ID for the plane widget.
        plane_representation_wasm_id: Returns the WebAssembly ID for the plane representation.
        is_on: Returns whether the plane widget is enabled or not.
    """
    _plane: vtkPlane
    _plane_representation: vtkImplicitPlaneRepresentation
    _plane_widget: vtkImplicitPlaneWidget2
    _algorithm_filter: Callable[[vtkAlgorithm], vtkAlgorithm]
    _plane_wasm_id: int | None
    _plane_widget_wasm_id: int | None
    _plane_representation_wasm_id: int | None

    def __init__(self, window_interactor: vtkRenderWindowInteractor):
        """"""
        self._place_factor: float = 1.25
        self._inside_out: bool = False
        self._plane_wasm_id = None
        self._plane_widget_wasm_id = None
        self._plane_representation_wasm_id = None
        # VTK objects will be initialized later in _initialize_cross_section_widget()

        logger.info("Beginning creating cross-section widget")
        try:
            # Initialize the plane and its representation
            self._plane = self._initialize_plane()
            self._plane_representation = self._initialize_plane_representation()

            # Set initial bounds
            initial_bounds: list[float] = [0, 0, 0, 0, 0, 0]
            self.update_bounds(initial_bounds)

            # Initialize the plane widget
            self._plane_widget = self._initialize_plane_widget(window_interactor)

            # Define the algorithm filter function
            def algorithm_filter(algorithm: vtkAlgorithm) -> vtkAlgorithm:
                clipper = vtkClipPolyData()
                clipper.SetClipFunction(self._plane)
                clipper.SetInsideOut(1 if self._inside_out else 0)
                clipper.SetInputConnection(algorithm.GetOutputPort())
                return clipper

            # Assign the algorithm filter
            self._algorithm_filter = algorithm_filter
            logger.info("Finished creating cross-section widget")
        except RuntimeError as e:
            msg = f"could not create cross-section widget: {e}"
            logger.error(msg)
            raise RuntimeError(msg)

    def update_bounds(self, bounds: list[float]):
        """Updates the bounding box around the given VTK bounding box."""
        if not hasattr(self, "_plane_representation"):
            raise RuntimeError("_plane_representation must be initialized before calling update_bounds()")
        self._plane_representation.PlaceWidget(bounds)
        (o_x, o_y, o_z, n_x, n_y, n_z) = self._get_default_plane_info(bounds)
        # oZ = bounds[4] + ((bounds[5] - bounds[4]) / 2)
        self.set_origin((o_x, o_y, o_z))
        self.set_normal((n_x, n_y, n_z))

    def _get_default_plane_info(self, bounds: list[float]) -> (
            tuple[float, float, float, float, float, float]
    ):
        """
        This function calculates an origin's coordinates from a given bounding box
        such that the origin is placed at one end of the bounding box's z-axis or
        the other depending on whether the clip function is inside out or not.
        """
        x = 0.5 * (bounds[0] + bounds[1])
        y = 0.5 * (bounds[2] + bounds[3])
        z = 0.5 * (bounds[4] + bounds[5])
        a = (bounds[4] - z) * self._place_factor
        return x, y, (z + (-a if self._inside_out else a)), 0, 0, 1

    @property
    def plane(self) -> vtkPlane:
        """Returns the widget VTK plane object."""
        return self._plane

    @property
    def algorithm_filter(self):
        """Returns the VTK algorithm filter."""
        return self._algorithm_filter

    @property
    def plane_wasm_id(self):
        """Returns the VTK plane wasm id."""
        if self._plane_wasm_id is None:
            method_name = self.register_with_local_view.__name__
            raise RuntimeError(f"{method_name}() must be called before this property is available")
        return self._plane_wasm_id

    @property
    def plane_widget_wasm_id(self):
        """Returns the VTK plane widget WASM ID."""
        if self._plane_widget_wasm_id is None:
            method_name = self.register_with_local_view.__name__
            raise RuntimeError(f"{method_name}() must be called before this property is available")
        return self._plane_widget_wasm_id

    @property
    def plane_representation_wasm_id(self):
        """Returns the VTK plane representation WASM ID."""
        if self._plane_representation_wasm_id is None:
            method_name = self.register_with_local_view.__name__
            raise RuntimeError(f"{method_name}() must be called before this property is available")
        return self._plane_representation_wasm_id

    @property
    def is_on(self):
        """Returns whether the plane widget is enabled or not."""
        return self._plane_widget.GetEnabled() == 1

    def register_with_local_view(self, local_view: LocalView):
        """Registers the VTK objects with a local view and assigns their WebAssembly IDs."""
        self._plane_wasm_id = local_view.register_vtk_object(self._plane)
        self._plane_widget_wasm_id = local_view.register_vtk_object(self._plane_widget)
        self._plane_representation_wasm_id = local_view.register_vtk_object(self._plane_representation)

    def set_normal(self, normal: tuple[float, float, float]):
        """Set the normal of the widget plane."""
        self._plane_representation.SetNormal(normal[0], normal[1], normal[2])
        self._plane.SetNormal(normal[0], normal[1], normal[2])

    def set_origin(self, origin: tuple[float, float, float]):
        """Set the origin of the widget plane."""
        self._plane_representation.SetOrigin(origin[0], origin[1], origin[2])
        self._plane.SetOrigin(origin[0], origin[1], origin[2])

    def toggle_on_off(self):
        """toggle the widget on or off."""
        if self.is_on:
            self.turn_off()
        else:
            self.turn_on()

    def turn_on(self):
        """Turn the widget on."""
        self._plane_widget.On()

    def turn_off(self):
        """Turn the widget off."""
        self._plane_widget.Off()

    # Private methods
    def _initialize_plane(self):
        """
        Initialize the plane for the cross-section widget.
        """
        return vtkPlane()

    def _initialize_plane_representation(self):
        """
        Initialize the plane representation for the cross-section widget.
        """
        if not hasattr(self, "_plane"):
            raise RuntimeError("_plane must be initialized before creating _plane_representation")
        rep = vtkImplicitPlaneRepresentation()
        rep.SetPlaceFactor(self._place_factor)
        rep.SetOutlineTranslation(False)
        rep.normal = self._plane.normal
        return rep

    def _initialize_plane_widget(self, window_interactor: vtkRenderWindowInteractor) -> vtkImplicitPlaneWidget2:
        """
        Initialize the plane widget for the cross-section widget.
        """
        if not hasattr(self, "_plane_representation"):
            raise RuntimeError("_plane_representation must be initialized before creating _plane_widget")
        plane_widget = vtkImplicitPlaneWidget2()
        plane_widget.SetInteractor(window_interactor)
        plane_widget.SetRepresentation(self._plane_representation)
        plane_widget.Off()
        return plane_widget

