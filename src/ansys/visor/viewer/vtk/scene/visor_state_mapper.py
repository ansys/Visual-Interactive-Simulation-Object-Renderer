"""State mapping helpers.

This module defines :class:`VisorStateMapper`, which is responsible for converting
between:

- frontend/runtime state (:class:`~ansys.visor.viewer.models.runtime.scene.runtime_app_state.RuntimeAppState`)
- persisted viewer state (:class:`~ansys.visor.viewer.models.persist.persisted_viewer_state.PersistedViewerStateV1`)

The dataset registry is required to look up :class:`VisorDataset` objects by ID or
name.  Per-dataset translation between runtime part IDs and persisted part names is
delegated to :meth:`VisorDataset.runtime_to_persisted_state` and
:meth:`VisorDataset.persisted_to_runtime_state`.
"""

from __future__ import annotations

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState
from ansys.visor.viewer.vtk.datasets.visor_dataset_registry import VisorDatasetRegistry

logger = VisorDefaultLogger(__name__)


class VisorStateMapper:
    """Convert between runtime and persisted viewer state."""

    def __init__(self, dataset_registry: VisorDatasetRegistry):
        """Initialize the mapper."""
        if dataset_registry is None:
            raise ValueError("dataset_registry is required")
        self._dataset_registry = dataset_registry

    def runtime_to_persisted(self, runtime_app_state: RuntimeAppState) -> PersistedViewerStateV1:
        """Convert frontend RuntimeAppState to PersistedViewerStateV1.

        Logic parity with ``VisorScene._runtime_to_persisted``.
        """
        # UI
        ui_state = runtime_app_state.ui

        # Scene
        scene_state = runtime_app_state.scene
        # Scene - unit
        unit = scene_state.unit
        # Scene - camera
        camera = scene_state.camera
        # Scene - variables: Pass through as-is since they are already keyed by stable variable identifier
        variable_states = scene_state.spectrum_states
        # Scene - datasets
        runtime_dataset_states = scene_state.dataset_states
        persisted_dataset_states = {}
        for dataset_id, dataset_state in runtime_dataset_states.items():
            dataset = self._dataset_registry.datasets.get(dataset_id)
            if dataset is None:
                continue
            persisted_dataset_states[dataset.name] = dataset.runtime_to_persisted_state(dataset_state)

        return PersistedViewerStateV1.from_components(
            ui_state=ui_state,
            camera=camera,
            unit=unit,
            cross_section=scene_state.cross_section,
            orthographic_enabled=scene_state.orthographic_enabled,
            cross_section_enabled=scene_state.cross_section_enabled,
            edges_enabled=scene_state.edges_enabled,
            bounding_box_enabled=scene_state.bounding_box_enabled,
            datasets=persisted_dataset_states,
            variable_states=variable_states,
        )

    def persisted_to_runtime(self, state: PersistedViewerStateV1) -> RuntimeAppState:
        """Convert PersistedViewerStateV1 back to runtime RuntimeAppState.

        Logic parity with ``VisorScene._persisted_to_runtime``.

        This is **not**, and never has been, the registry-population path.  It
        builds runtime dataset states and returns them on the RuntimeAppState;
        it never assigns its result back onto ``VisorDataset.state``, so no
        registry record is written by calling it.
        :meth:`VisorSceneBase._restore_part_states_from_runtime` now populates
        the registry explicitly, from the state this method returns.
        """
        # UI settings
        ui_state = state.ui

        # scene state
        scene_state = state.scene

        # scene - unit
        unit = scene_state.unit

        # scene - camera
        camera = scene_state.camera

        # scene - variables: Pass through as-is since they are already keyed by stable variable identifier
        variable_states = scene_state.variable_states or {}

        # scene - datasets: Convert persisted dataset states to runtime
        runtime_dataset_states = {}
        for dataset_name, persisted_dataset_state in scene_state.dataset_states.items():
            # dataset_key is the dataset name

            # Get the VisorDataset object by name from the registry
            dataset = self._dataset_registry.get_by_name(dataset_name)
            if dataset is None:
                logger.warning(f"Dataset with name '{dataset_name}' not found in registry. Skipping.")
                continue
            runtime_state = dataset.persisted_to_runtime_state(persisted_dataset_state.parts)
            runtime_dataset_states[dataset.id] = runtime_state

        return RuntimeAppState.from_components(
            dark_mode=ui_state.dark_theme,
            unit=unit,
            camera=camera,
            cross_section=scene_state.cross_section,
            orthographic_enabled=scene_state.orthographic_enabled,
            cross_section_enabled=scene_state.cross_section_enabled,
            edges_enabled=scene_state.edges_enabled,
            bounding_box_enabled=scene_state.bounding_box_enabled,
            dataset_states=runtime_dataset_states,
            variable_states=variable_states,
        )
