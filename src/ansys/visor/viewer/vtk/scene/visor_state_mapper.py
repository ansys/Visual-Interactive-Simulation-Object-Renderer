"""State mapping helpers.

This module defines :class:`VisorStateMapper`, which is responsible for converting
between:

- the server's runtime state (:class:`~ansys.visor.viewer.models.runtime.scene.runtime_app_state.RuntimeAppState`)
- persisted viewer state (:class:`~ansys.visor.viewer.models.persist.persisted_viewer_state.PersistedViewerStateV1`)

The dataset registry is required to look up :class:`VisorDataset` objects by ID or
name.  Per-dataset translation between runtime part IDs and persisted part names is
delegated to :meth:`VisorDataset.runtime_to_persisted_state` and
:meth:`VisorDataset.persisted_to_runtime_state`.
"""

from __future__ import annotations

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState
from ansys.visor.viewer.models.runtime.scene.runtime_scene_state import RuntimeSceneState
from ansys.visor.viewer.models.runtime.scene.runtime_ui_state import RuntimeUIState
from ansys.visor.viewer.models.runtime.scene.runtime_view_state import RuntimeViewState
from ansys.visor.viewer.vtk.datasets.visor_dataset_registry import VisorDatasetRegistry

logger = VisorDefaultLogger(__name__)


class VisorStateMapper:
    """Convert between runtime and persisted viewer state.

    Loading resolves the file against the server's current state here and
    nowhere else.
    """

    def __init__(self, dataset_registry: VisorDatasetRegistry, ui_defaults: RuntimeUIState):
        """Initialize the mapper.

        *ui_defaults* is the UI record a null field in a loaded file resolves
        to.  It is copied, so later writes to the caller's record do not reach it.
        """
        if dataset_registry is None:
            raise ValueError("dataset_registry is required")
        if ui_defaults is None:
            raise ValueError("ui_defaults is required")
        self._dataset_registry = dataset_registry
        self._ui_defaults = ui_defaults.model_copy()

    def runtime_to_persisted(self, runtime_app_state: RuntimeAppState) -> PersistedViewerStateV1:
        """Convert the server's RuntimeAppState to PersistedViewerStateV1."""
        scene_state = runtime_app_state.scene
        view_state = runtime_app_state.view

        # Scene - variables: the server's records, projected onto the persisted entry
        variable_states = {
            variable_id: record.to_variable_state()
            for variable_id, record in scene_state.variable_states.items()
        }
        # Scene - datasets
        persisted_dataset_states = {}
        for dataset_id, dataset_state in scene_state.dataset_states.items():
            dataset = self._dataset_registry.datasets.get(dataset_id)
            if dataset is None:
                continue
            persisted_dataset_states[dataset.name] = dataset.runtime_to_persisted_state(dataset_state)

        return PersistedViewerStateV1.from_components(
            ui_state=runtime_app_state.ui.to_persisted(),
            camera=view_state.camera,
            unit=scene_state.unit,
            cross_section=view_state.cross_section,
            orthographic_enabled=scene_state.orthographic_enabled,
            cross_section_enabled=scene_state.cross_section_enabled,
            edges_enabled=scene_state.edges_enabled,
            bounding_box_enabled=scene_state.bounding_box_enabled,
            datasets=persisted_dataset_states,
            variable_states=variable_states,
        )

    def persisted_to_runtime(self, state: PersistedViewerStateV1, current: RuntimeAppState) -> RuntimeAppState:
        """Overlay a loaded file onto the server's *current* state.

        Each scene-level field the file does not name keeps its current value;
        one it names as null takes its default; one it names with a value
        takes that value.  The UI defaults are the ones this mapper was built
        with, the scene defaults are :meth:`RuntimeSceneState.default`.

        The camera and the plane have no default value: null is treated as
        absent and the current record is kept.  A plane missing its origin or
        its normal is treated the same way.

        ``orthographic_enabled`` is derived from the resolved camera; the
        file's flag is not read.

        The dataset states are the file's datasets only, each the dataset's
        current records overlaid with its loaded entries; a dataset the file
        does not name is left to its current records.  They are returned, not
        assigned to ``VisorDataset.state``; :meth:`VisorSceneBase._restore_part_states`
        installs them.  The variable states are empty: the load path fills
        them from the server's rebuilt records.
        """
        ui = current.ui.overlaid_with(state.ui, self._ui_defaults)

        view = RuntimeViewState(
            camera=self._resolved_camera(state.scene.camera, current.view.camera),
            cross_section=self._resolved_plane(state.scene.cross_section, current.view.cross_section),
        )

        runtime_dataset_states = {}
        for dataset_name, persisted_dataset_state in state.scene.dataset_states.items():
            dataset = self._dataset_registry.get_by_name(dataset_name)
            if dataset is None:
                logger.warning(f"Dataset with name '{dataset_name}' not found in registry. Skipping.")
                continue
            runtime_dataset_states[dataset.id] = dataset.persisted_to_runtime_state(persisted_dataset_state.parts)

        scene = current.scene.overlaid_with(state.scene, RuntimeSceneState.default()).model_copy(update={
            "orthographic_enabled": view.camera.parallel_projection if view.camera is not None else None,
            "dataset_states": runtime_dataset_states,
            "variable_states": {},
        })

        return RuntimeAppState(ui=ui, view=view, scene=scene)

    @staticmethod
    def _resolved_camera(
            persisted: VisorCameraState | None, current: VisorCameraState | None
    ) -> VisorCameraState | None:
        """The file's camera, or the current one where the file has none."""
        return persisted if persisted is not None else current

    @staticmethod
    def _resolved_plane(
            persisted: VisorCrossSectionState | None, current: VisorCrossSectionState | None
    ) -> VisorCrossSectionState | None:
        """The file's plane, or the current one where the file has none or only half of one."""
        if persisted is None or persisted.origin is None or persisted.normal is None:
            return current
        return persisted
