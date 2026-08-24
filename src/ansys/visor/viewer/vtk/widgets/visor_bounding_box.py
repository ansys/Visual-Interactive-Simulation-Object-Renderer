"""Class for creating a bounding box around a set of nodes in a VTK scene."""

from typing import Callable

from trame_vtklocal.widgets.vtklocal import LocalView
from vtkmodules.vtkCommonExecutionModel import vtkPolyDataAlgorithm
from vtkmodules.vtkFiltersModeling import vtkOutlineFilter
from vtkmodules.vtkFiltersSources import vtkCubeSource
from vtkmodules.vtkRenderingAnnotation import vtkCubeAxesActor2D
from vtkmodules.vtkRenderingCore import vtkActor, vtkCamera, vtkPolyDataMapper, vtkRenderer, vtkTextProperty

from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphNode


class VisorBoundingBox:
    """
    Bounding box widget for a set of nodes in a VTK scene.
    This class creates a bounding box around a set of nodes in a VTK scene and provides
    methods to show, hide, and update the bounding box based on the nodes' bounds.

    Attributes:
        update_bounds (Callable[[list[float]], None]): Function to update the bounding box bounds.
        update_bounds_from_nodes (Callable[[dict[int, VisorSceneGraphNode]], None]): Function to update the bounding box bounds based on a dictionary of nodes.
        show (Callable[[], None]): Function to show the bounding box.
        hide (Callable[[], None]): Function to hide the bounding box.
        attach_to_renderer (Callable[[vtkRenderer], None]): Function to attach the bounding box to a VTK renderer.
        detach_from_renderer (Callable[[vtkRenderer], None]): Function to detach the bounding box from a VTK renderer.
        toggle (Callable[[], None]): Function to toggle the visibility of the bounding box.
        update_node_count (Callable[[int], None]): Function to update the node count for visibility control.

    Methods:
        register_with_local_view(local_view: LocalView): Register the VTK objects with a local view for WASM integration.

    Properties:
        box_algorithm_wasm_id: Returns the WASM ID of the box algorithm. Raises an error if register_with_local_view() has not been called.
        outline_wasm_actor_id: Returns the WASM ID of the outline actor. Raises an error if register_with_local_view() has not been called.
        axes_wasm_actor_id: Returns the WASM ID of the axes actor. Raises an error if register_with_local_view() has not been called.
    """
    def __init__(self, camera: vtkCamera, node_count: int = 0):

        outline_box = vtkCubeSource()
        # outline_box.SetCenter(0, 0, 0)
        outline_filter = vtkOutlineFilter()
        outline_filter.SetInputConnection(outline_box.GetOutputPort())

        outline_mapper = vtkPolyDataMapper()
        outline_mapper.SetInputConnection(outline_filter.GetOutputPort())

        outline_actor = vtkActor()
        outline_actor.SetMapper(outline_mapper)
        outline_actor.GetProperty().SetColor(0.184, 0.427, 0.620)

        # normals = vtkPolyDataNormals()
        # normals.SetInputConnection(outline_box.GetOutputPort());

        tprop = vtkTextProperty()
        tprop.SetColor(0.0, 0.0, 0.0)
        tprop.ShadowOn()
        tprop.SetFontSize(20)

        axes2 = vtkCubeAxesActor2D()
        axes2.SetCamera(camera)
        axes2.SetViewProp(outline_actor)
        axes2.SetLabelFormat("%6.4g")
        axes2.SetFlyModeToClosestTriad()
        axes2.ScalingOff()
        axes2.SetAxisTitleTextProperty(tprop)
        axes2.SetAxisLabelTextProperty(tprop)
        axes2.GetProperty().SetLineWidth(5)
        axes2.GetProperty().SetColor(0.184, 0.427, 0.620)

        def show():
            if node_count == 0:
                return
            outline_actor.SetVisibility(True)
            axes2.SetVisibility(True)

        def hide():
            outline_actor.SetVisibility(False)
            axes2.SetVisibility(False)

        # set the default state (hidden)
        hide()

        def update_node_count(count: int):
            nonlocal node_count
            node_count = count

        def toggle():
            if node_count == 0:
                return
            if outline_actor.GetVisibility():
                hide()
            else:
                show()

        def update_outline_bounds(bounds: list[float]):
            outline_box.SetBounds(bounds)

        def update_outline_bounds_from_nodes(nodes: dict[int, VisorSceneGraphNode]):
            nonlocal node_count
            node_count = len(nodes)
            if node_count == 0:
                hide()
                return
            show()
            x_min, x_max = float('inf'), float('-inf')
            y_min, y_max = float('inf'), float('-inf')
            z_min, z_max = float('inf'), float('-inf')
            for node in nodes.values():
                x_min = min(x_min, node.bounds[0])
                x_max = max(x_max, node.bounds[1])
                y_min = min(y_min, node.bounds[2])
                y_max = max(y_max, node.bounds[3])
                z_min = min(z_min, node.bounds[4])
                z_max = max(z_max, node.bounds[5])
            update_outline_bounds([x_min, x_max, y_min, y_max, z_min, z_max])

        def attach_to_renderer(renderer: vtkRenderer):
            renderer.AddActor(outline_actor)
            renderer.AddViewProp(axes2)

        def detach_from_renderer(renderer: vtkRenderer):
            renderer.RemoveActor(outline_actor)
            renderer.RemoveViewProp(axes2)

        self.update_bounds: Callable[[list[float]], None] = update_outline_bounds
        self.update_bounds_from_nodes: Callable[[dict[int, VisorSceneGraphNode]], None] = update_outline_bounds_from_nodes
        self.show: Callable[[], None] = show
        self.hide: Callable[[], None] = hide
        self.attach_to_renderer: Callable[[vtkRenderer], None] = attach_to_renderer
        self.detach_from_renderer: Callable[[vtkRenderer], None] = detach_from_renderer
        self.toggle: Callable[[], None] = toggle
        self.update_node_count: Callable[[int], None] = update_node_count
        self.__box_algorithm: vtkPolyDataAlgorithm = outline_box
        self.__box_algorithm_wasm_id: int | None = None
        self.__outline_actor: vtkActor = outline_actor
        self.__outline_wasm_actor_id: int | None = None
        self.__axes_actor: vtkCubeAxesActor2D = axes2
        self.__axes_wasm_actor_id: int | None = None

    @property
    def box_algorithm_wasm_id(self):
        """Return the WASM ID of the box algorithm. Raises an error if register_with_local_view() has not been called."""
        if self.__box_algorithm_wasm_id is None:
            method_name = self.register_with_local_view.__name__
            raise RuntimeError(f"{method_name}() must be called before this property is available")
        return self.__box_algorithm_wasm_id

    @property
    def outline_wasm_actor_id(self):
        """Return the WASm ID of the outline actor. Raises an error if register_with_local_view() has not been called."""
        if self.__outline_wasm_actor_id is None:
            method_name = self.register_with_local_view.__name__
            raise RuntimeError(f"{method_name}() must be called before this property is available")
        return self.__outline_wasm_actor_id

    @property
    def axes_wasm_actor_id(self):
        """Return the WASM ID of the axes actor. Raises an error if register_with_local_view() has not been called."""
        if self.__axes_wasm_actor_id is None:
            method_name = self.register_with_local_view.__name__
            raise RuntimeError(f"{method_name}() must be called before this property is available")
        return self.__axes_wasm_actor_id

    def register_with_local_view(self, local_view: LocalView):
        """Register the VTK objects with the local view"""
        box_algorithm = self.__box_algorithm
        outline_actor = self.__outline_actor
        axes_actor = self.__axes_actor
        local_view.register_vtk_object(box_algorithm)
        local_view.register_vtk_object(outline_actor)
        local_view.register_vtk_object(axes_actor)
        self.__box_algorithm_wasm_id = local_view.get_wasm_id(box_algorithm)
        self.__outline_wasm_actor_id = local_view.get_wasm_id(outline_actor)
        self.__axes_wasm_actor_id = local_view.get_wasm_id(axes_actor)
