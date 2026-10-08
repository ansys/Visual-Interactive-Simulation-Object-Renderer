"""VTK scene management for Visor Viewer."""

import json
import math
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List

from trame_server import Server

from ansys.visor.viewer.core.metadata import ExtendedMetadata
from ansys.visor.viewer.core.perf_timer import PerfTimer
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.core.visor_types import VisorDatasetType
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_ui_state import VisorUIState
from ansys.visor.viewer.models.common.visor_variable_record import (
    VisorVariableRecord,
    VisorVariableRecords,
)
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import RuntimePartProperties
from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState
from ansys.visor.viewer.models.runtime.visor_scene_details import VisorSceneDetails
from ansys.visor.viewer.renderer.base import IRenderer
from ansys.visor.viewer.vtk.datasets.visor_dataset import VisorDataset
from ansys.visor.viewer.vtk.datasets.visor_dataset_registry import VisorDatasetRegistry
from ansys.visor.viewer.vtk.scene.scene_graph_state_builder import SceneGraphStateBuilder
from ansys.visor.viewer.vtk.scene.visor_state_mapper import VisorStateMapper
from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraph
from ansys.visor.viewer.vtk.variables.visor_part_variables import VisorPartVariables
from ansys.visor.viewer.vtk.variables.visor_variable_update import VisorVariableUpdate

logger = VisorDefaultLogger(__name__)


@dataclass(frozen=True)
class _ColorVariableBinding:
    """A part's resolved color-variable reference: the record, the slot, and that slot's effective range."""

    part_id: int
    record: VisorVariableRecord
    component: int
    min_val: float
    max_val: float

    def matches(self, association: VisorVtkVariableType, array_name: str) -> bool:
        """Return whether *association* and *array_name* name this binding's array."""
        return association is self.record.type and array_name == self.record.array_name

    def apply_to(self, renderer: IRenderer) -> None:
        """Configure the part's mapper at this range and re-serialize it; caller holds ``_vtk_lock``."""
        renderer.apply_color_variable(
            self.part_id,
            self.record.id,
            self.record.type,
            self.record.array_name,
            self.component,
            self.min_val,
            self.max_val,
        )


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

    Subclasses must implement one abstract hook, which captures the difference
    in *state delivery* between rendering backends:

    * :meth:`_push_runtime_state` — wasm path calls a JS
      ``set_state``; RCA path pushes camera onto ``vtkCamera``; headless
      is a no-op.

    The saved state is built here, from the server's own records, for every
    backend; no backend asks a client for it.

    This separation means that adding a new rendering backend requires only:

    1. A new :class:`IRenderer` implementation.
    2. A new :class:`VisorSceneBase` subclass that overrides the hook.
    """

    _server: Server
    _scene_graph: VisorSceneGraph | None
    _dataset_registry: VisorDatasetRegistry
    _renderer: IRenderer
    _state_mapper: VisorStateMapper
    _cross_section_enabled: bool
    _edges_enabled: bool
    _bounding_box_enabled: bool
    _ui_state: VisorUIState
    _variable_records: VisorVariableRecords

    def __init__(
            self,
            server: Server,
            dark_mode: bool = False,
            renderer: IRenderer | None = None
    ):
        """Initialize the scene coordinator and its local renderer backend."""
        logger.debug("Initializing %s", type(self).__name__)

        # The server's UI record, held as a model like the camera record.
        # Built first because ``dark_mode`` is a property over its
        # ``dark_theme`` field.
        #
        # The theme comes from the constructor; the four panel fields match
        # the client panels' own mount defaults (collapsed=False,
        # tab_index=0), so a get_state before the client has spoken reports
        # what the client would.  They're initialised rather than left unset
        # because the payload dump excludes ``None``, and an unset field
        # would be omitted, letting the client fall back to its own default
        # instead of the server's record.
        #
        # Written only by the four panel triggers and the load path, always
        # as absolute values, never toggles.  Projection is deliberately
        # absent here: it's derived from the camera record, not stored twice.
        self._ui_state = VisorUIState(
            dark_theme=dark_mode,
            panel_top_left_panel_collapsed=False,
            panel_top_right_panel_collapsed=False,
            panel_top_right_legend_collapsed=False,
            panel_top_right_tab_index=0,
        )

        # The server's variable records, keyed by composed identifier.  Created once
        # here and never rebound.  Written only by _rebuild_variable_records_from_registry
        # and _load_variable_records, under _vtk_lock, by assigning a new dict
        # (copy-on-write) so the unlocked reader in
        # get_scene_details never sees a dict change size.  Handed out only as
        # model_copy(deep=True): a shallow copy would share the dict and its entries.
        self._variable_records = VisorVariableRecords()

        # Server-tracked widget toggles.  Absolute values, never toggles.
        # Initialised to the client widgets' own constructor defaults so a
        # get_state before the client has ever spoken reports what the client
        # would report.  Projection is deliberately absent: it is derived from
        # the camera record, so a fourth field here would be the second source
        # that derivation exists to remove.
        self._cross_section_enabled: bool = False
        self._edges_enabled: bool = False
        self._bounding_box_enabled: bool = False


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
    # Abstract hook — subclasses differ on state delivery
    # =========================================================================

    @abstractmethod
    def _push_runtime_state(self, runtime_app_state: "RuntimeAppState") -> None:
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
    def dark_mode(self) -> bool | None:
        """Whether the viewer is in dark theme.

        A property over the UI record's ``dark_theme`` field rather than a
        separate attribute, so the theme has exactly one holder.

        Typed ``bool | None`` to match that field: the constructor always
        supplies a ``bool``, but :meth:`apply_state` writes
        ``state.ui.dark_theme`` through unguarded, and that field is optional.
        """
        return self._ui_state.dark_theme

    @dark_mode.setter
    def dark_mode(self, dark_mode: bool | None) -> None:
        """Set the theme on the UI record."""
        self._ui_state.dark_theme = dark_mode

    @property
    def datasets(self) -> dict[int, VisorDataset]:
        """List of datasets registered in the scene."""
        return self._dataset_registry.datasets

    def list_all_dataset_info(self) -> dict[int, dict]:
        """Convenience: metadata snapshot for UI without parts."""
        return self._dataset_registry.list_info()

    def get_state(self) -> PersistedViewerStateV1:
        """
        Build the current viewer state from the server's own records and
        return it as a :class:`PersistedViewerStateV1`.

        No client is consulted, so a save works with no browser connected.
        The runtime state starts empty and every one of its fields is assigned
        below; a field left unassigned here would be saved at its model default.

        Per-part state comes from the registry.  The registry hands out live
        ``RuntimeDatasetState`` objects that the per-part setters mutate from the
        trame daemon thread, so each one is deep-copied under ``_vtk_lock``.

        The widget toggles come from this object's own store, and the UI record
        is a copy of this object's own record, so a panel trigger landing after
        the call cannot mutate the state already returned.

        The camera comes from the renderer's record, which is authoritative, rather than
        from the pipeline ``vtkCamera``: the pipeline is the
        record's projection, and reading it back would re-import whatever drift
        VTK introduced -- ``ResetCamera`` rewrites ``clipping_range``.  The
        assignment is unconditional.  A ``None`` record means no camera was ever
        written, and writing that ``None`` through is what says so; the guard for
        "absent says nothing" belongs to the load path, in :meth:`apply_state`,
        not here.

        ``orthographic_enabled`` is derived from that same record, not stored
        separately, so it can't disagree with the camera. ``None`` means
        "nothing was ever written."

        The cross-section plane is the camera's twin, taken from the
        renderer's record on exactly the same terms -- see the camera
        paragraph above for why the assignment is unconditional and what
        ``None`` means.  In normal operation there is no ``None`` case to
        guard because the renderer seeds the record from its own widget the
        first time bounds are pushed.

        Variables and unit are the server's: the variable records and the
        registry's unit.
        """
        runtime_state = RuntimeAppState()

        with self._vtk_lock:
            registry_dataset_states = {
                dataset_id: dataset_state.model_copy(deep=True)
                for dataset_id, dataset_state in self._dataset_registry.runtime_state_dict.items()
            }
            camera_record = self._renderer.get_camera_state()
            runtime_state.scene.camera = camera_record
            runtime_state.scene.orthographic_enabled = (
                camera_record.parallel_projection if camera_record is not None else None
            )
            runtime_state.scene.cross_section = self._renderer.get_cross_section_plane()
            runtime_state.scene.cross_section_enabled = self._cross_section_enabled
            runtime_state.scene.edges_enabled = self._edges_enabled
            runtime_state.scene.bounding_box_enabled = self._bounding_box_enabled
            runtime_state.ui = self._ui_state.model_copy()
            runtime_state.scene.variable_states = self._variable_records.model_copy(deep=True).variables
            runtime_state.scene.unit = self._dataset_registry.unit
        runtime_state.scene.dataset_states = registry_dataset_states

        persisted = self._state_mapper.runtime_to_persisted(runtime_state)
        return persisted

    def apply_state(self, state: PersistedViewerStateV1):
        """
        Apply a saved viewer state.

        One ``_restore_*`` step per state class, each making the server's own
        copy of that class match the loaded state: its stored state, and the
        VTK objects that the state drives.

        The renderer-speific delivery step is delegated to :meth:`_push_runtime_state`,
        and runs last, once every record above it has been written.

        Holds ``_vtk_lock`` for the whole body, including the delegated render step.
        """
        with self._vtk_lock:
            # Transform the frontend PersistedViewerStateV1 -> RuntimeAppState
            runtime_app_state = self._state_mapper.persisted_to_runtime(state)

            # Variable records: rebuilt from the registry and overlaid with the file's
            # ranges, then placed on the runtime state for the push, all before
            # _restore_part_states, which resolves each colored part against the held record.
            self._load_variable_records(state.scene.variable_states)
            runtime_app_state.scene.variable_states = self._variable_records.model_copy(deep=True).variables

            # One call per state class: updates the server's stored state and its VTK objects.
            self._restore_part_states(runtime_app_state)
            self._restore_widget_state(runtime_app_state)
            self._restore_ui_state(runtime_app_state)
            self._restore_camera_state(runtime_app_state)

            # Finalize here, not on the load path.  On a cold load -- viewer started with no dataset,
            # then a state loaded -- load_state adds the datasets and only then calls apply_state, so a
            # finalize on the load path syncs wasm from a scene that predates every restore above: the
            # client was served a scene with no cross-section plane, and neither the plane nor its
            # handle ever rendered.  Finalizing here syncs after the restores.
            #
            # Before _push_runtime_state, never after.  finalize_scene -> render() ends in
            # LocalView.update(), the same wasm flush flush_wasm_state performs; placed after the push
            # it *is* the flush the note below refuses, racing the client's rebuild against the
            # fire-and-forget set_state.  See VisorLocalScene._push_runtime_state, which is written on
            # the assumption that the full render and wasm sync have already happened by the time it runs.
            #
            # Correct only after _restore_widget_state: populate_scene reaches IRenderer.update_bounds,
            # which writes an existing cross-section record back to the widget rather than seeding from
            # the widget's defaults.  With no record -- which is what the load path had on a cold load --
            # that branch seeds the defaults instead.
            if self.dataset_count > 0:
                self.finalize_scene(skip_reset_camera=True)


            # The server's copy is now current; deliver it to the rendering backend.
            # wasm: set_state() to the browser; RCA: a rendered frame; headless: no-op.
            self._push_runtime_state(runtime_app_state)

            # Note: There is intentionally no wasm flush here: the bridge call is fire-and-forget, so a flush
            # at this point races the client's rebuild against a half-written object graph.

    def get_scene_details(self) -> VisorSceneDetails:
        """Return the VisorState.

        How a rebuilt or reconnecting client learns the server's widget
        toggles; the client branches that apply these fields already existed
        and were dead only because nothing populated them.

        ``orthographic_enabled`` is derived from the camera record, not
        stored, so it can't disagree with the camera. ``None`` means
        "nothing was ever written."

        No ``_vtk_lock``: the reads here (three booleans, one camera field)
        aren't consumed as a mutually consistent snapshot, and locking a
        request-path read against the trigger thread belongs with the
        round-trip/thread-affinity work, not here. Accepted exposure: one
        stale field in a delivered payload.

        The UI record is passed as a copy and never as the instance, for the
        reason :meth:`get_state` gives: a panel trigger landing after this
        call would otherwise mutate a payload already served.

        The variable records are passed as a deep copy of the holder, also
        without the lock: writers rebind ``variables`` to a new dict, so this
        read sees either the old dict or the new one, never one in flux.
        """
        if self._scene_graph is None:
            self._initialize_scene_graph()
        annotation = self._renderer.build_renderer_annotation()
        scene_graph_state = self._build_scene_graph_state()
        camera_record = self._renderer.get_camera_state()
        return VisorSceneDetails.from_components(
            ui=self._ui_state.model_copy(),
            unit=self._dataset_registry.unit,
            dataset_states=self._dataset_registry.runtime_state_dict,
            scene_graph_state=scene_graph_state,
            renderer_annotation=annotation,
            orthographic_enabled=(
                camera_record.parallel_projection if camera_record is not None else None
            ),
            cross_section_enabled=self._cross_section_enabled,
            edges_enabled=self._edges_enabled,
            bounding_box_enabled=self._bounding_box_enabled,
            variable_states=self._variable_records.model_copy(deep=True).variables,
        )

    def get_scene_details_json(self) -> str:
        """Return the VisorVtkPipelineState as JSON string."""
        return json.dumps(self.get_scene_details().model_dump(exclude_none=True, by_alias=True))

    def clear(self):
        """Remove all actors from the renderer and reset the scene.

        Holds ``_vtk_lock``: deregistering actors mutates the VTK renderer.
        """
        with self._vtk_lock:
            if self._scene_graph is not None:
                self._renderer.deregister_all()
            self._dataset_registry.clear()
            self._scene_graph = None
            self._rebuild_variable_records_from_registry()

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

            # Register each leaf's pipeline with the renderer.  The same list object
            # is the positional seed below, so the PartIndex entries and the
            # renderer's pipeline keys are the same node IDs by construction.
            node_ids: list[int] | None = None
            subtree = self._scene_graph.get_descendant_node(dataset_id, include_self=True)
            if subtree is not None:
                part_nodes = subtree.get_descendant_part_nodes(include_self=True)
                for leaf in part_nodes:
                    self._renderer.register_node(leaf, leaf.dataset)

                # Seed PartIndex positionally with scene-graph node IDs so that
                # part_id == scene-graph node ID, which is the contract the frontend
                # relies on to apply per-part state (opacity etc.).
                node_ids = [leaf.id for leaf in part_nodes]

            self._dataset_registry.add(dataset_id, dataset_name, input, node_ids, metadata)
            self._rebuild_variable_records_from_registry()

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
            self._rebuild_variable_records_from_registry()

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

            # After the reload and the metadata refresh: a width change changes the id.
            self._rebuild_variable_records_from_registry()

            with timer.phase("render"):
                self.render()

            timer.log()

    def _rebuild_variable_records_from_registry(self) -> None:
        """Rebuild the held records from the registry, carrying custom ranges, then reconcile part references;
        under ``_vtk_lock``.

        Used at add, remove, clear and update.  Assigns a new dict to the holder
        (copy-on-write); never mutates the live dict or its entries, so the dict
        it replaces is still intact when it is handed to
        :meth:`_reconcile_part_color_variables` as the previous records.
        """
        with self._vtk_lock:
            previous = self._variable_records.variables
            records = VisorVariableRecords.from_registry(self._dataset_registry, self._variable_records).variables
            self._variable_records.variables = records
            logger.debug("variable records rebuilt from registry: %d records", len(records))
            self._reconcile_part_color_variables(previous)

    def _reconcile_part_color_variables(self, previous: Dict[str, VisorVariableRecord]) -> None:
        """Re-apply or clear each part's color variable against the current records, skipping a part whose
        effective range is unchanged from *previous*.  Caller holds the scene lock.

        Only a part with a colour-variable reference is reconciled.  A
        reference that resolves is
        re-applied through :meth:`_ColorVariableBinding.apply_to`, unless the
        part participated in the same record in *previous* at the same range.
        A reference that no longer resolves is cleared through
        :meth:`clear_part_color_variable`, which clears the store, resets the
        mapper and re-serializes it.
        """
        references = [
            (part_id, part_state.color_variable.variable_id, part_state.color_variable.variable_component)
            for dataset in list(self._dataset_registry.datasets.values())
            for part_id, part_state in list(dataset.state.part_states.items())
            if part_state.color_variable is not None
        ]
        for part_id, variable_id, component in references:
            binding = self._resolve_color_variable(part_id, variable_id, component)
            if binding is None:
                self.clear_part_color_variable(part_id)
                logger.debug(
                    "reconcile: part %s cleared; '%s' component %s no longer resolves.",
                    part_id, variable_id, component
                )
                continue
            old_record = previous.get(variable_id)
            if (
                    old_record is not None
                    and part_id in old_record.part_ids
                    and old_record.range_for(component) == (binding.min_val, binding.max_val)
            ):
                continue
            binding.apply_to(self._renderer)
            logger.debug(
                "reconcile: part %s re-applied at '%s' component %s [%g, %g].",
                part_id, variable_id, component, binding.min_val, binding.max_val
            )

    def _load_variable_records(self, file_states: Dict[str, VisorVariableState]) -> None:
        """Build the held records fresh from the registry and overlay the file's ranges; under ``_vtk_lock``.

        Used at load.  Assigns a new dict to the holder (copy-on-write); never
        mutates the live dict or its entries.
        """
        with self._vtk_lock:
            records = VisorVariableRecords.from_file(self._dataset_registry, file_states).variables
            self._variable_records.variables = records
            logger.debug("variable records loaded from file: %d records", len(records))

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
            self._renderer.serialize_camera_state()

    def sync_camera(self, camera_state: VisorCameraState) -> None:
        """Record a camera the frontend reported, and project it.

        The trigger path's coordinator method.  It is the camera twin of the
        per-part coordinator surface below: the trigger handler arrives on
        trame's daemon thread and must route through a method that takes
        ``_vtk_lock``, never call the renderer directly.

        Both halves run in one critical section, and the re-serialisation is
        part of the write rather than an afterthought.  The backend advertises
        a version number read from the live VTK object while serving content
        from a cache, so a write with no re-serialise publishes a new version
        against old content: the client then fetches the *pre*-gesture camera
        and applies it over the one the user just set, and a refresh shows the
        framing they moved away from.  The load path proved this in
        Increment 2b; the trigger path has the same gap for the same reason.

        What this method deliberately does **not** do is notify.  No
        ``render()``, no ``flush_wasm_state()``, no ``set_state``.  A push here
        rebuilds the client, the rebuild re-delivers state, the reapply moves
        the camera and emits further settle reports, and each report pushes
        again.  It would also race the rebuild against a half-written object
        graph -- the hazard ``_apply_runtime_state_to_render`` already refuses
        to reopen.  Serialising without notifying is the whole point.
        """
        with self._vtk_lock:
            self._renderer.sync_camera(camera_state)
            self._renderer.serialize_camera_state()

    def sync_cross_section_plane(
        self, origin: list[float], normal: list[float]
    ) -> None:
        """Record a cross-section plane the frontend reported, and project it.

        Both halves in one critical section, re-serialisation part of the
        write, no notify -- for the reasons :meth:`sync_camera` gives.  The
        plane has exactly one delivery channel to a rebuilt or reconnecting
        client, the wasm state fetch that follows this re-serialisation, so an
        id that is not re-serialised here is simply not delivered and the
        user's drag reappears where it started after a page reload.
        """
        with self._vtk_lock:
            self._renderer.sync_cross_section_plane(origin, normal)
            self._renderer.serialize_cross_section_state()

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
    # pipeline.  Nothing is pushed to the client from here.  The client applies
    # its own change, and a push at this layer rebuilds the client, which
    # re-delivers state and fires further triggers.  Presenting a server-originated
    # change is the renderer's, since it is not mode-agnostic.
    # An unresolvable node id is a logged no-op at the apply layer.
    #
    # Every value that arrives here is absolute, never relative: the caller
    # always supplies the target value, never a toggle or a delta.
    # =========================================================================

    def set_part_visibility(self, node_id: int, visible: bool) -> None:
        """Set whether the part identified by *node_id* is visible.

        Fans out to the widget layer after the apply, so that hiding a part
        reaches the bounds-consuming widgets at all.  The two private helpers
        rather than :meth:`update_widgets`: that method raises ``RuntimeError``
        when the scene graph is ``None``, and a trigger thread is where a raise
        has no caller to handle it, so a path that today logs at debug and
        returns would start raising.  The cost is that a later addition to
        ``update_widgets``' body will not reach here.

        The box will not change size when a part is hidden.  The server's root
        bounds are computed across all loaded datasets with no visibility
        filter, so the same numbers arrive at the widget.  That is the current
        bounds semantics, not a defect in this fan-out.
        """
        with self._vtk_lock:
            if not self._dataset_registry.set_part_visibility(node_id, visible):
                logger.debug("set_part_visibility: no dataset owns node %s; skipping.", node_id)
                return
            self._renderer.apply_visibility(node_id, visible)
            self._update_widget_bounds()
            self._update_actor_count()

    def set_part_opacity(self, node_id: int, opacity: float) -> None:
        """Set the opacity of the part identified by *node_id*."""
        with self._vtk_lock:
            if not self._dataset_registry.set_part_opacity(node_id, opacity):
                logger.debug("set_part_opacity: no dataset owns node %s; skipping.", node_id)
                return
            self._renderer.apply_opacity(node_id, opacity)

    def set_part_diffuse_color(self, node_id: int, diffuse_rgb: list[float] | None) -> None:
        """
        Set the custom diffuse colour of the part identified by *node_id*, or
        reset it with ``None``.

        A reset writes the default colour into the record.  Either way the
        pipeline is given the colour the record then holds.
        """
        with self._vtk_lock:
            if diffuse_rgb is None:
                written = self._dataset_registry.reset_part_diffuse_color(node_id)
            else:
                written = self._dataset_registry.set_part_diffuse_color(node_id, diffuse_rgb)
            if not written:
                logger.debug("set_part_diffuse_color: no dataset owns node %s; skipping.", node_id)
                return
            applied_rgb = self._dataset_registry.get_part_state(node_id).diffuse_rgb
            self._renderer.apply_diffuse_color(
                node_id, applied_rgb[0], applied_rgb[1], applied_rgb[2]
            )

    def set_part_selected(self, node_id: int, selected: bool) -> None:
        """
        Select or deselect the part identified by *node_id*.

        No colour crosses the trigger for this class: the server reads the
        part's stored ``diffuse_rgb`` from its own record.  The record is
        guaranteed to exist here — the setter above returned ``True``,
        which means it either found the record or upserted one — so
        ``get_part_state`` cannot return ``None`` at this point.
        """
        with self._vtk_lock:
            if not self._dataset_registry.set_part_selected(node_id, selected):
                logger.debug("set_part_selected: no dataset owns node %s; skipping.", node_id)
                return
            diffuse_rgb = self._dataset_registry.get_part_state(node_id).diffuse_rgb
            self._renderer.apply_selected(node_id, selected, diffuse_rgb)

    def set_part_color_variable(
            self,
            node_id: int,
            variable_id: str,
            association: VisorVtkVariableType,
            array_name: str,
            component: int,
    ) -> bool:
        """
        Colour one part at the record's effective range; False, writing nothing, when refused.

        *variable_id* is stored opaquely and is never parsed here.  It is
        resolved against the held records: the part must participate in it
        and *component* must name one of its slots.  *association* and
        *array_name* must name the record's array.  The range applied is the
        record's, never the caller's.  A refusal logs one WARNING and leaves
        both the registry and the mapper untouched.
        """
        with self._vtk_lock:
            binding = self._resolve_color_variable(node_id, variable_id, component)
            if binding is None:
                return False
            if not binding.matches(association, array_name):
                logger.warning(
                    "set_part_color_variable: %s '%s' does not name the array of '%s' "
                    "(part %s); refused.", association, array_name, variable_id, node_id
                )
                return False
            if not self._dataset_registry.set_part_color_variable(node_id, variable_id, component):
                logger.debug("set_part_color_variable: no dataset owns node %s; skipping.", node_id)
                return False
            binding.apply_to(self._renderer)
            return True

    def set_variable_range(
            self, variable_id: str, component: int, min_val: float, max_val: float
    ) -> bool:
        """
        Store one slot's effective range and apply it to every part referencing that slot; False, writing
        nothing, when refused.

        Refused, with a WARNING, for an unknown id, a component outside
        ``[-1, num_components)``, a non-finite value, or ``min > max``.  The
        entry is replaced by copy-on-write and ``variables`` is rebound, so
        the unlocked reader never sees the live dict change.  Each applied
        mapper is re-serialized inside the lock.  Nothing is pushed: the
        client applied the range before it sent.
        """
        with self._vtk_lock:
            record = self._variable_records.variables.get(variable_id)
            if record is None:
                logger.warning("set_variable_range: no record for '%s'; refused.", variable_id)
                return False
            if not -1 <= component < record.num_components:
                logger.warning(
                    "set_variable_range: component %s is outside [-1, %s) for '%s'; refused.",
                    component, record.num_components, variable_id
                )
                return False
            if not (math.isfinite(min_val) and math.isfinite(max_val)):
                logger.warning(
                    "set_variable_range: non-finite range [%s, %s] for '%s'; refused.",
                    min_val, max_val, variable_id
                )
                return False
            if min_val > max_val:
                logger.warning(
                    "set_variable_range: min %s is above max %s for '%s'; refused.",
                    min_val, max_val, variable_id
                )
                return False

            variables = dict(self._variable_records.variables)
            variables[variable_id] = record.with_range(component, (min_val, max_val))
            self._variable_records.variables = variables
            logger.debug(
                "variable range stored: %s component %d [%g, %g]",
                variable_id, component, min_val, max_val
            )

            for part_id in variables[variable_id].part_ids:
                part_state = self._dataset_registry.get_part_state(part_id)
                if part_state is None:
                    continue
                reference = part_state.color_variable
                if (
                        reference is None
                        or reference.variable_id != variable_id
                        or reference.variable_component != component
                ):
                    continue
                binding = self._resolve_color_variable(part_id, variable_id, component)
                if binding is not None:
                    binding.apply_to(self._renderer)
            return True

    def _resolve_color_variable(
            self, part_id: int, variable_id: str, component: int
    ) -> _ColorVariableBinding | None:
        """
        Resolve a part's reference against the held records; None, with one WARNING, when refused.

        Refused when the id has no record, the part does not participate in
        it, or *component* names no slot.  The id encodes association, name
        and width, so a same-named array of another width is another record
        and fails participation.  Caller holds ``_vtk_lock``.
        """
        record = self._variable_records.variables.get(variable_id)
        if record is None:
            logger.warning(
                "_resolve_color_variable: no record for '%s' (part %s); refused.", variable_id, part_id
            )
            return None
        if part_id not in record.part_ids:
            logger.warning(
                "_resolve_color_variable: part %s does not participate in '%s'; refused.",
                part_id, variable_id
            )
            return None
        value_range = record.range_for(component)
        if value_range is None:
            logger.warning(
                "_resolve_color_variable: component %s names no slot of '%s' (%s components, part %s); "
                "refused.", component, variable_id, record.num_components, part_id
            )
            return None
        return _ColorVariableBinding(
            part_id=part_id,
            record=record,
            component=component,
            min_val=value_range[0],
            max_val=value_range[1],
        )

    def clear_part_color_variable(self, node_id: int) -> None:
        """
        Stop colouring the part identified by *node_id* by a scalar variable.

        The variable reference is cleared atomically in the store (id and
        component together), matching the atomic set.  The renderer's clear
        then re-serializes the mapper inside the lock, as its apply does, so
        the state served to the client is current.
        """
        with self._vtk_lock:
            if not self._dataset_registry.clear_part_color_variable(node_id):
                logger.debug(
                    "clear_part_color_variable: no dataset owns node %s; skipping.", node_id
                )
                return
            self._renderer.clear_color_variable(node_id)

    # =========================================================================
    # Widget state — coordinator surface
    #
    # Each method does both halves of its trigger, in this order and all under
    # ``_vtk_lock``: write the server's record, apply to the server's VTK
    # objects.  Nothing is pushed to the client from here, for the same reason
    # the per-part surface pushes nothing: the client applied its own change
    # before it sent, and a push rebuilds the client, which re-delivers state
    # and fires further triggers.
    #
    # Every value that arrives here is absolute, never relative.
    #
    # None of these is abstract.  The subclasses differ on state authority,
    # not on widget state, and the abstract set is asserted by equality.
    # =========================================================================

    def set_cross_section_visibility(self, visible: bool) -> None:
        """Set whether the cross-section plane is shown.

        The renderer call is a no-op today and is made anyway: the server's
        cross-section widget is driven by the client through the wasm mirror,
        so the store is what is authoritative and delivered, and the call is
        the seam a server-rendering mode would fill.
        """
        with self._vtk_lock:
            self._cross_section_enabled = visible
            self._renderer.set_cross_section_visibility(visible)

    def set_edges_visible(self, visible: bool) -> None:
        """Set whether edges are shown on every part."""
        with self._vtk_lock:
            self._edges_enabled = visible
            self._renderer.set_edges_visible(visible)

    def set_bounding_box_visibility(self, visible: bool) -> None:
        """Set whether the bounding-box outline is shown.

        As with the cross-section, the renderer call is a no-op today and the
        store is the authority.
        """
        with self._vtk_lock:
            self._bounding_box_enabled = visible
            self._renderer.set_bounding_box_visibility(visible)

    def set_projection(self, parallel: bool) -> None:
        """Set parallel or perspective projection on the camera record.

        No store field, and that is the point: projection lives on the camera
        record and nowhere else, so ``get_state`` derives it rather than
        reading a second copy that could disagree.

        Both halves run in one critical section and the re-serialisation is
        part of the write, exactly as in :meth:`sync_camera`: the backend
        advertises a version number read from the live VTK object while
        serving content from a cache, so a write with no re-serialise
        publishes a new version against old content and the client fetches
        and re-applies the pre-write camera.  Because a projection flip is
        visually obvious, omitting the re-serialise shows up as the view
        snapping back.

        No notify.  No ``render()``, no ``flush_wasm_state()``, no
        ``set_state``.
        """
        with self._vtk_lock:
            self._renderer.set_projection(parallel)
            self._renderer.serialize_camera_state()

    # =========================================================================
    # UI panel layout — coordinator surface
    #
    # Same shape as the widget toggles above, minus the renderer half: each
    # writes one store field under ``_vtk_lock`` and stops.  No ``IRenderer``
    # seam to fill, no notify — panel layout is browser-side chrome, and the
    # reasons are the same as above.
    #
    # Every value that arrives here is absolute, never relative.
    # =========================================================================

    def set_panel_top_left_panel_collapsed(self, collapsed: bool) -> None:
        """Record whether the top-left panel is collapsed."""
        with self._vtk_lock:
            self._ui_state.panel_top_left_panel_collapsed = collapsed

    def set_panel_top_right_panel_collapsed(self, collapsed: bool) -> None:
        """Record whether the top-right panel is collapsed."""
        with self._vtk_lock:
            self._ui_state.panel_top_right_panel_collapsed = collapsed

    def set_panel_top_right_legend_collapsed(self, collapsed: bool) -> None:
        """Record whether the top-right legend overlay is collapsed."""
        with self._vtk_lock:
            self._ui_state.panel_top_right_legend_collapsed = collapsed

    def set_panel_top_right_tab_index(self, tab_index: int) -> None:
        """Record which top-right tab is active.

        The value is stored opaquely and is never interpreted here; it is
        only ever handed back to the client's ``selectTab``, which is where
        the range guard lives.
        """
        with self._vtk_lock:
            self._ui_state.panel_top_right_tab_index = tab_index

    def _restore_part_states(self, runtime_app_state: "RuntimeAppState") -> None:
        """
        Restore per-part state from a runtime app state, on the load path.

        Installs the part records of each dataset named in the supplied states, which
        are that dataset's current records overlaid with the loaded entries, one per
        part.  Then applies every part to this process's VTK pipeline through ``IRenderer``.
        Datasets the registry does not hold are skipped and logged.  Every other failure
        is a logged no-op.

        Callers must hold ``_vtk_lock``.
        """
        dataset_states = runtime_app_state.scene.dataset_states or {}

        self._dataset_registry.replace_part_states(dataset_states)

        for dataset_id, dataset_state in dataset_states.items():
            dataset = self._dataset_registry.datasets.get(dataset_id)
            if dataset is None:
                logger.warning(
                    "_restore_part_states: dataset %s is not registered; "
                    "its part state was not applied to the pipeline.", dataset_id
                )
                continue

            for part_id, part_state in dataset_state.part_states.items():
                self._restore_one_part_state(part_id, part_state)

    def _restore_camera_state(self, runtime_app_state: "RuntimeAppState") -> None:
        """
        Restore the camera state from a runtime app state, on the load path.

        Write the loaded camera to the record and the pipeline camera, so a client rebuilt
        from server state (refresh) gets it.  Must precede the render step.  The re-serialize
        is required: the server advertises the camera's live MTime but serves its cached state,
        so without it a client fetches the pre-load camera.  A state with no camera leaves both
        alone.

        Callers must hold ``_vtk_lock``.
        """
        if runtime_app_state.scene.camera is not None:
            self._renderer.sync_camera(runtime_app_state.scene.camera)
            self._renderer.serialize_camera_state()

    def _restore_widget_state(self, runtime_app_state: "RuntimeAppState") -> None:
        """
        Restore the camera state from a runtime app state, on the load path.

        The widget toggles.  Absent says nothing: a state that does not
        carry a toggle leaves the server's value alone, which is this
        path's guard and not get_state's.  Store first, renderer second,
        matching the coordinator surface below.


        ``orthographic_enabled`` is deliberately not read.  Projection
        arrives on the camera, whose sync_camera writes it to the
        record and the pipeline; the persisted toggle is emitted for
        compatibility and ignored here, because two readers of one
        property is the divergence this story removed.

        The cross-section plane is restored here too, and both-or-neither:
        ``sync_cross_section_plane`` takes an origin and a normal together
        and the model allows either to be absent, so a half-plane says
        nothing rather than half-applying.  The re-serialisation follows the
        write for the reason :meth:`sync_cross_section_plane` gives -- a
        loaded plane that is written but not re-serialised leaves the client
        fetching the pre-load one.

        Callers must hold ``_vtk_lock``.
        """
        scene = runtime_app_state.scene
        if scene.cross_section_enabled is not None:
            self._cross_section_enabled = scene.cross_section_enabled
            self._renderer.set_cross_section_visibility(scene.cross_section_enabled)
        if scene.edges_enabled is not None:
            self._edges_enabled = scene.edges_enabled
            self._renderer.set_edges_visible(scene.edges_enabled)
        if scene.bounding_box_enabled is not None:
            self._bounding_box_enabled = scene.bounding_box_enabled
            self._renderer.set_bounding_box_visibility(scene.bounding_box_enabled)
        if scene.cross_section is not None:
            cs = scene.cross_section
            if cs.origin is not None and cs.normal is not None:
                self._renderer.sync_cross_section_plane(cs.origin, cs.normal)
                self._renderer.serialize_cross_section_state()

    def _restore_ui_state(self, runtime_app_state: "RuntimeAppState") -> None:
        """
        Restore the UI panel layout from a runtime app state, on the load path.

        Absent says nothing: a state that does not carry a panel field leaves
        the server's value alone.  Four independent guards and not one, because
        a file can carry any subset -- anything written before this record
        existed carries none of them.

        Callers must hold ``_vtk_lock``.
        """
        ui = runtime_app_state.ui

        if ui.dark_theme is not None:
            self.dark_mode = ui.dark_theme
        if ui.panel_top_left_panel_collapsed is not None:
            self._ui_state.panel_top_left_panel_collapsed = ui.panel_top_left_panel_collapsed
        if ui.panel_top_right_panel_collapsed is not None:
            self._ui_state.panel_top_right_panel_collapsed = ui.panel_top_right_panel_collapsed
        if ui.panel_top_right_legend_collapsed is not None:
            self._ui_state.panel_top_right_legend_collapsed = ui.panel_top_right_legend_collapsed
        if ui.panel_top_right_tab_index is not None:
            self._ui_state.panel_top_right_tab_index = ui.panel_top_right_tab_index

    def _restore_one_part_state(self, part_id: int, part_state: RuntimePartProperties) -> None:
        """
        Apply one restored part record to the pipeline, every field.
        """
        self._renderer.apply_visibility(part_id, part_state.visible)
        self._renderer.apply_opacity(part_id, part_state.opacity)

        rgb = part_state.diffuse_rgb
        self._renderer.apply_diffuse_color(part_id, rgb[0], rgb[1], rgb[2])
        self._renderer.apply_selected(part_id, part_state.selected, rgb)

        self._restore_part_color_variable(part_id, part_state)

    def _restore_part_color_variable(self, part_id: int, part_state: RuntimePartProperties) -> None:
        """
        Restore one part's color-variable reference through the resolve helper, or clear it.

        No reference clears the mapper.  A reference resolves against the
        held records, which the load path has rebuilt and overlaid with the
        file's ranges before this runs.  A refused reference is a logged
        no-op; the mapper is re-serialized after an applied or cleared one.
        """
        reference = part_state.color_variable
        if reference is None:
            self._renderer.clear_color_variable(part_id)
            return

        binding = self._resolve_color_variable(
            part_id, reference.variable_id, reference.variable_component
        )
        if binding is None:
            return
        binding.apply_to(self._renderer)

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


