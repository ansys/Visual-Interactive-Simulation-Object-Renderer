"""VTK scene management for Visor Viewer."""

import json
import threading
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

from trame_server import Server

from ansys.visor.viewer.core.metadata import ExtendedMetadata
from ansys.visor.viewer.core.perf_timer import PerfTimer
from ansys.visor.viewer.core.visor_colors import VisorColors
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.core.visor_types import VisorDatasetType
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.models.runtime.visor_scene_details import VisorSceneDetails
from ansys.visor.viewer.renderer.base import IRenderer
from ansys.visor.viewer.vtk.datasets.visor_dataset import VisorDataset
from ansys.visor.viewer.vtk.datasets.visor_dataset_registry import VisorDatasetRegistry
from ansys.visor.viewer.vtk.scene.scene_graph_state_builder import SceneGraphStateBuilder
from ansys.visor.viewer.vtk.scene.visor_state_mapper import VisorStateMapper
from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraph
from ansys.visor.viewer.vtk.variables.visor_part_variables import VisorPartVariables
from ansys.visor.viewer.vtk.variables.visor_variable_update import VisorVariableUpdate

if TYPE_CHECKING:
    from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState

logger = VisorDefaultLogger(__name__)

class VisorSceneBase(ABC):
    """
    Abstract coordinator for a Visor viewer scene.

    Owns the **scene description** side of the application:

    * :class:`VisorVTKSceneGraph`      – the pure scene-graph node tree
    * :class:`VisorDatasetRegistry` – dataset metadata, variables, unit
    * :class:`VisorStateMapper`     – persisted ↔ runtime state conversion

    All **rendering** concerns are delegated to an injected :class:`IRenderer`
    implementation (``self._vtk_renderer``): VTK pipeline objects, actor
    lifecycle, camera, and scene-state serialisation.

    Subclasses must implement two abstract hooks that capture the difference
    in *state authority* between rendering backends:

    * :meth:`_get_runtime_state_async` — wasm path does a frontend round-trip;
      RCA/headless paths build state server-side.
    * :meth:`_apply_runtime_state_to_render` — wasm path calls a JS
      ``set_state``; RCA path pushes camera onto ``vtkCamera``; headless
      is a no-op.

    This separation means that adding a new rendering backend requires only:

    1. A new :class:`IRenderer` implementation.
    2. A new :class:`VisorSceneBase` subclass that overrides the two hooks.
    """

    _server: Server
    _scene_graph: VisorSceneGraph | None
    _dataset_registry: VisorDatasetRegistry
    _renderer: IRenderer
    _state_mapper: VisorStateMapper

    def __init__(
            self,
            server: Server,
            dark_mode: bool = False,
            renderer: IRenderer | None = None
    ):
        """Initialize the scene coordinator and its local renderer backend."""
        logger.debug("Initializing %s", type(self).__name__)
        self.dark_mode: bool = dark_mode
        self._server = server
        self._scene_graph = None
        self._pipelines = {}

        # Serialises every server-side VTK mutation and wasm push.
        #
        # @trigger handlers run on the trame server's daemon background-thread
        # event loop, while the VTK objects they mutate are created and also
        # mutated from the caller's (notebook/main) thread.  Re-entrant because
        # the locked paths nest: finalize_scene -> populate_scene ->
        # update_widgets, finalize_scene -> render, and the per-part
        # coordinator methods -> apply -> flush.
        self._vtk_lock = threading.RLock()

        self._dataset_registry = self._initialize_dataset_registry()

        if renderer is not None:
            self._renderer = renderer
        else:
            # Subclass must have assigned self._vtk_renderer before calling
            # super().__init__() without a renderer, or override _initialize.
            raise TypeError(
                f"{type(self).__name__} must supply a renderer to VisorSceneBase.__init__"
            )

        self._initialize_scene_graph()
        self._state_mapper = VisorStateMapper(self._dataset_registry)

    # =========================================================================
    # Abstract hooks — subclasses differ on state authority
    # =========================================================================

    @abstractmethod
    async def _get_runtime_state_async(self, timeout: float) -> "RuntimeAppState":
        """
        Obtain the current runtime app state.

        * Wasm path: round-trip to the React frontend via
          :class:`VisorFrontendBridge`.
        * RCA / headless paths: build entirely from server-side VTK objects and
          the dataset registry — no frontend call.
        """

    @abstractmethod
    def _apply_runtime_state_to_render(self, runtime_app_state: "RuntimeAppState") -> None:
        """
        Push a runtime app state onto the renderer / frontend after the
        shared per-part state has already been restored.

        * Wasm path: ``render_window_only()`` + JS ``set_state`` call.
        * RCA path: push camera onto ``vtkCamera`` + ``render_window_only()``.
        * Headless path: no-op.
        """

    # =========================================================================
    # Public properties
    # =========================================================================

    @property
    def dataset_count(self) -> int:
        """Number of datasets registered in the scene."""
        return self._dataset_registry.count

    @property
    def datasets(self) -> dict[int, VisorDataset]:
        """List of datasets registered in the scene."""
        return self._dataset_registry.datasets

    def list_all_dataset_info(self) -> dict[int, dict]:
        """Convenience: metadata snapshot for UI without parts."""
        return self._dataset_registry.list_info()

    async def get_state(self, timeout: float) -> PersistedViewerStateV1:
        """
        Capture the current viewer state and return it as a
        :class:`PersistedViewerStateV1`.

        The renderer-specific part of state capture is handled by
        :meth:`_get_runtime_state_async`.
        """
        runtime_state = await self._get_runtime_state_async(timeout)
        persisted = self._state_mapper.runtime_to_persisted(runtime_state)
        return persisted

    def apply_state(self, state: PersistedViewerStateV1):
        """
        Apply a saved viewer state.

        Shared work (per-part state restoration) is done here; the
        renderer-specific final step is delegated to
        :meth:`_apply_runtime_state_to_render`.

        Holds ``_vtk_lock`` for the whole body: the delegated step mutates
        VTK and pushes to the frontend.
        """
        with self._vtk_lock:
            # Apply UI settings
            self.dark_mode = state.ui.dark_theme

            # Transform the frontend PersistedViewerStateV1 -> RuntimeAppState
            runtime_app_state = self._state_mapper.persisted_to_runtime(state)

            # Renderer-specific: flush VTK window and notify frontend (wasm), or
            # push camera to vtkCamera (RCA), or no-op (headless).
            self._apply_runtime_state_to_render(runtime_app_state)

    def get_scene_details(self) -> VisorSceneDetails:
        """Return the VisorState."""
        if self._scene_graph is None:
            self._initialize_scene_graph()
        annotation = self._renderer.build_renderer_annotation()
        scene_graph_state = self._build_scene_graph_state()
        return VisorSceneDetails.from_components(
            dark_mode=self.dark_mode,
            unit=self._dataset_registry.unit,
            dataset_states=self._dataset_registry.runtime_state_dict,
            scene_graph_state=scene_graph_state,
            renderer_annotation=annotation,
        )

    def get_scene_details_json(self) -> str:
        """Return the VisorVtkPipelineState as JSON string."""
        return json.dumps(self.get_scene_details().model_dump(exclude_none=True, by_alias=True))

    def handle_save_state_response(self, request_id: int, response: dict) -> None:
        """Called by LocalApp trigger when the frontend responds."""
        self._frontend_bridge.resolve_save_state_response(request_id, response)

    def clear(self):
        """Remove all actors from the renderer and reset the scene.

        Holds ``_vtk_lock``: deregistering actors mutates the VTK renderer.
        """
        with self._vtk_lock:
            if self._scene_graph is not None:
                self._renderer.deregister_all()
            self._dataset_registry.clear()
            self._scene_graph = None

    def populate_scene(self):
        """Update widgets to reflect the current scene contents.

        Actor attach is done per-leaf inside :meth:`add_dataset` via
        :meth:`IRenderer.register_node`, so this method only refreshes the
        widget bounds and count.

        Holds ``_vtk_lock``: the widget refresh mutates VTK widget objects.
        """
        with self._vtk_lock:
            if self._scene_graph is None:
                self._initialize_scene_graph()
            self.update_widgets()

    def finalize_scene(self, skip_reset_camera: bool = False):
        """Populate the scene, reset the camera if applicable, then render.

        Holds ``_vtk_lock`` across all three steps; the nested acquisitions in
        :meth:`populate_scene`, :meth:`reset_camera` and :meth:`render` are
        re-entrant on the same thread.
        """
        with self._vtk_lock:
            self.populate_scene()

            if not skip_reset_camera:
                # if there is one or zero datasets in the scene, reset the camera
                if self._dataset_registry.count <= 1:
                    self.reset_camera()

            self.render()

    def update_widgets(self):
        """Reset the widgets to fit the scene graph bounds.

        Holds ``_vtk_lock``: the widget bounds update mutates the
        cross-section representation/plane and the bounding-box outline.
        """
        with self._vtk_lock:
            if self._scene_graph is None:
                msg = "Scene graph has not been initialized, cannot reset widgets and camera."
                logger.error(msg)
                raise RuntimeError(msg)

            self._update_widget_bounds()
            self._update_actor_count()

    def add_dataset(self, input: VisorDatasetType, metadata: ExtendedMetadata) -> int:
        """Set the input dataset and metadata for the scene graph.

        Holds ``_vtk_lock``: node registration attaches actors to the VTK
        renderer.
        """
        with self._vtk_lock:
            if input is None:
                msg = "Input dataset is None, cannot load dataset."
                logger.error(msg)
                raise ValueError(msg)

            # Ensure unique dataset name
            dataset_name = self._dataset_registry.get_sanitized_metadata_name(metadata)

            # Initialize the scene graph if it does not exist
            if self._scene_graph is None:
                self._initialize_scene_graph()

            # Load the dataset into the scene graph
            dataset_id = self._scene_graph.load_dataset(input, dataset_name)

            # Register each leaf's pipeline with the renderer.
            subtree = self._scene_graph.get_descendant_node(dataset_id, include_self=True)
            if subtree is not None:
                for leaf in subtree.get_descendant_part_nodes(include_self=True):
                    self._renderer.register_node(leaf, leaf.dataset)

            # Seed PartIndex with scene-graph node IDs so that part_id == scene-graph node ID,
            # which is the contract the frontend relies on to apply per-part state (opacity etc.).
            part_name_to_id = self._scene_graph.get_part_name_to_id_map(dataset_id)

            self._dataset_registry.add(dataset_id, dataset_name, input, part_name_to_id, metadata)

            return dataset_id

    def remove_dataset(self, dataset_id: int):
        """Remove a dataset from the scene graph.

        Holds ``_vtk_lock``: node deregistration detaches actors from the VTK
        renderer.
        """
        with self._vtk_lock:
            if self._scene_graph is None:
                msg = "Scene graph has not been initialized, cannot load dataset."
                logger.error(msg)
                raise RuntimeError(msg)

            # Deregister each leaf's pipeline from the renderer before dropping
            # the subtree from the scene graph.
            node = self._scene_graph.get_descendant_node(dataset_id)
            if node is None:
                msg = f"Dataset with id {dataset_id} not found in scene graph."
                logger.error(msg)
                raise ValueError(msg)

            for leaf in node.get_descendant_part_nodes(include_self=True):
                self._renderer.deregister_node(leaf.id)

            # Remove dataset from the scene graph
            self._scene_graph.remove_dataset(dataset_id)

            # Unregister the dataset
            self._dataset_registry.remove(dataset_id)

    def list_variables_for_dataset(self, dataset_id: int) -> List[VisorPartVariables]:
        return self._dataset_registry.list_variables(dataset_id)

    def update_variables_for_dataset(self, dataset_id: int, variables: List[VisorVariableUpdate]) -> None:
        """Update the variables for the dataset in the scene graph.

        Holds ``_vtk_lock``: the registry update writes into VTK arrays in
        place and the render pushes to wasm.
        """
        with self._vtk_lock:
            timer = PerfTimer("update_variables_for_dataset", logger, dataset=dataset_id)

            with timer.phase("dataset_registry.update"):
                self._dataset_registry.update_variables(dataset_id, variables)

            # Refresh cached variable metadata on part nodes without re-wiring
            # the VTK pipeline (which would call SetInputConnection + mark the
            # mapper Modified, causing unnecessary re-serialisation of geometry
            # that has not changed).
            dataset_node = self._scene_graph.get_descendant_node(dataset_id)
            with timer.phase("update_descendant_parts"):
                dataset_node.refresh_descendant_variable_metadata(include_self=True)

            with timer.phase("render"):
                self.render()

            timer.log()

    def render(self):
        """Delegate to the renderer backend.

        Holds ``_vtk_lock``: renders the VTK window and pushes to wasm.
        """
        with self._vtk_lock:
            self._renderer.render()

    def reset_camera(self):
        """Reset the camera to fit the scene graph bounds.

        Holds ``_vtk_lock``: mutates the VTK renderer's camera.
        """
        with self._vtk_lock:
            if self._scene_graph is None:
                logger.debug("Scene graph not initialized; skipping camera reset.")
                return

            self._renderer.reset_camera(self._scene_graph.bounds)

    def pick_geometry(self, actor_wasm_id, cell_id, mode, world_x, world_y, world_z) -> dict:
        """
        Frontend-trigger entry point for cell picking.  Packs the world-space
        pick position into a tuple and delegates to the renderer backend.
        """
        return self._renderer.pick_geometry(
            actor_wasm_id, cell_id, mode, (world_x, world_y, world_z)
        )

    # =========================================================================
    # Per-part visual state — coordinator surface
    #
    # Each method does both halves of its trigger, in this order and all under
    # ``_vtk_lock``: write the registry record, apply to the server's VTK
    # pipeline, then push the mutated state to the wasm client with
    # ``flush_wasm_state()``.  An unresolvable node id is a logged no-op at
    # every layer: nothing is applied and nothing is flushed.
    #
    # Every value that arrives here is absolute, never relative: the caller
    # always supplies the target value, never a toggle or a delta.
    # =========================================================================

    def set_part_visibility(self, node_id: int, visible: bool) -> None:
        """Set whether the part identified by *node_id* is visible."""
        with self._vtk_lock:
            if not self._dataset_registry.set_part_visibility(node_id, visible):
                logger.debug("set_part_visibility: no dataset owns node %s; skipping.", node_id)
                return
            self._renderer.apply_visibility(node_id, visible)
            self._renderer.flush_wasm_state()

    def set_part_opacity(self, node_id: int, opacity: float) -> None:
        """Set the opacity of the part identified by *node_id*."""
        with self._vtk_lock:
            if not self._dataset_registry.set_part_opacity(node_id, opacity):
                logger.debug("set_part_opacity: no dataset owns node %s; skipping.", node_id)
                return
            self._renderer.apply_opacity(node_id, opacity)
            self._renderer.flush_wasm_state()

    def set_part_diffuse_color(self, node_id: int, diffuse_rgb: list[float] | None) -> None:
        """
        Set the custom diffuse colour of the part identified by *node_id*, or
        clear it with ``None``.

        The store records the absence as absence: ``diffuse_rgb=None`` is
        written through as ``None``.  The pipeline needs a concrete colour, so
        the apply falls back to :attr:`VisorColors.DefaultMeshColor` — "no
        custom colour" means "the scene-wide default".
        """
        with self._vtk_lock:
            if not self._dataset_registry.set_part_diffuse_color(node_id, diffuse_rgb):
                logger.debug("set_part_diffuse_color: no dataset owns node %s; skipping.", node_id)
                return
            applied_rgb = (
                diffuse_rgb if diffuse_rgb is not None else list(VisorColors.DefaultMeshColor)
            )
            self._renderer.apply_diffuse_color(
                node_id, applied_rgb[0], applied_rgb[1], applied_rgb[2]
            )
            self._renderer.flush_wasm_state()

    def set_part_selected(self, node_id: int, selected: bool) -> None:
        """
        Select or deselect the part identified by *node_id*.

        No colour crosses the trigger for this class: the server reads the
        part's stored ``diffuse_rgb`` from its own record and falls back to
        :attr:`VisorColors.DefaultMeshColor` when it is ``None``.  The record
        is guaranteed to exist here — the setter above returned ``True``,
        which means it either found the record or upserted one — so
        ``get_part_state`` cannot return ``None`` at this point.
        """
        with self._vtk_lock:
            if not self._dataset_registry.set_part_selected(node_id, selected):
                logger.debug("set_part_selected: no dataset owns node %s; skipping.", node_id)
                return
            stored_rgb = self._dataset_registry.get_part_state(node_id).diffuse_rgb
            diffuse_rgb = (
                stored_rgb if stored_rgb is not None else list(VisorColors.DefaultMeshColor)
            )
            self._renderer.apply_selected(node_id, selected, diffuse_rgb)
            self._renderer.flush_wasm_state()

    def set_part_color_variable(
            self,
            node_id: int,
            variable_id: str,
            association: VisorVtkVariableType,
            array_name: str,
            component: int,
            min_val: float,
            max_val: float,
    ) -> None:
        """
        Colour the part identified by *node_id* by a scalar variable.

        *variable_id* is stored opaquely and is never parsed here; the
        association and array name arrive as explicit arguments.  *association*
        is already a :class:`VisorVtkVariableType` — it is parsed at the
        trigger boundary, never derived from a string here.  The range travels
        as a parameter only and is not persisted per part.
        """
        with self._vtk_lock:
            if not self._dataset_registry.set_part_color_variable(node_id, variable_id, component):
                logger.debug("set_part_color_variable: no dataset owns node %s; skipping.", node_id)
                return
            self._renderer.apply_color_variable(
                node_id, variable_id, association, array_name, component, min_val, max_val
            )
            self._renderer.flush_wasm_state()

    def clear_part_color_variable(self, node_id: int) -> None:
        """
        Stop colouring the part identified by *node_id* by a scalar variable.

        The variable reference is cleared atomically in the store (id and
        component together), matching the atomic set.
        """
        with self._vtk_lock:
            if not self._dataset_registry.clear_part_color_variable(node_id):
                logger.debug(
                    "clear_part_color_variable: no dataset owns node %s; skipping.", node_id
                )
                return
            self._renderer.clear_color_variable(node_id)
            self._renderer.flush_wasm_state()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _initialize_scene_graph(self):
        """Initialize an empty scene graph."""
        self._scene_graph = VisorSceneGraph()

    def _initialize_dataset_registry(self) -> VisorDatasetRegistry:
        """Initialize the dataset registry to manage datasets in the scene."""
        return VisorDatasetRegistry()

    def _update_widget_bounds(self):
        """Update the cross-section and bounding box widgets with the current scene graph bounds."""
        self._renderer.update_bounds(self._scene_graph.bounds)

    def _update_actor_count(self):
        """Update the bounding box widget with the current part-node count."""
        self._renderer.update_actor_count(self._scene_graph.descendant_part_count())

    def _build_scene_graph_state(self):
        """Assemble the pure scene-graph ``SceneGraphNodeInfo`` tree.

        Structure and metadata only, read from the scene-graph nodes. Renderer
        handles live entirely on the renderer's annotation
        (:meth:`IRenderer.build_renderer_annotation`); this method never reads
        the renderer.
        """
        return SceneGraphStateBuilder(self._scene_graph).build()


