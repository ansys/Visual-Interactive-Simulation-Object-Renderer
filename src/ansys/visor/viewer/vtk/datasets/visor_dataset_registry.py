"""Registry for managing multiple Visor datasets within a scene."""

import re
from typing import Dict, List

from ansys.visor.viewer.core.metadata import ExtendedMetadata
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.core.visor_types import VisorDatasetType
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import (
    RuntimeDatasetState,
    RuntimePartProperties,
)
from ansys.visor.viewer.vtk.datasets.visor_dataset import VisorDataset
from ansys.visor.viewer.vtk.variables.visor_part_variables import VisorPartVariables
from ansys.visor.viewer.vtk.variables.visor_variable_update import VisorVariableUpdate

logger = VisorDefaultLogger(__name__)



class VisorDatasetRegistry:
    """
    Registry for managing multiple Visor datasets within a scene.

    It allows adding, removing, and retrieving datasets, as well as managing their states and variables
    collectively.

    Attributes:
        datasets (Dict[int, VisorDataset]): A dictionary mapping dataset IDs to VisorDataset instances.
        unit (str): The unit associated with the datasets in the registry.
    """
    def __init__(self):
        """Initialize the registry."""
        self.datasets: Dict[int, VisorDataset] = {}
        self.unit: str = ""

    @property
    def runtime_state_dict(self) -> Dict[int, RuntimeDatasetState]:
        """
        Get the combined state of all datasets in the registry.

        Returns:
            Dict[str, Dict[int, PartProperties]]: A dict with a single key 'parts' mapping
            to a flat dict of all parts across all dataset states.

        Note:
            The structure is flat to mirror the current JSON schema used by the frontend.
        """
        return {id:dataset.state for id, dataset in self.datasets.items()}

    @property
    def count(self) -> int:
        """
        Get the number of datasets in the registry.

        Returns:
            int: The count of datasets.
        """
        return len(self.datasets)

    def list_info(self) -> Dict[int, dict]:
        """
        Get the state information for all datasets in the registry.

        Returns a dictionary mapping dataset IDs to their respective state information.
        """
        return {k: dataset.info_dict for k, dataset in self.datasets.items()}

    def get_by_name(self, name: str) -> VisorDataset | None:
        """
        Retrieve a dataset by its name.

        Args:
            name (str): The name of the dataset to retrieve.

        Returns:
            VisorDataset | None: The dataset with the specified name, or None if not found.
        """
        for dataset in self.datasets.values():
            if dataset.name == name:
                return dataset
        return None

    def add(self,
            dataset_id: int,
            dataset_name: str,
            input: VisorDatasetType,
            part_name_to_id: Dict[str, int],
            metadata: ExtendedMetadata,
            ) -> VisorDataset:
        """
        Add a new dataset to the registry with associated metadata.
        """
        self._update_unit(metadata)

        # VisorDataset builds its own PartIndex directly from the VTK data object,
        # seeded with the scene-graph node IDs so part_id == scene-graph node ID.
        dataset = VisorDataset(dataset_id, dataset_name, input, part_name_to_id, metadata)

        # Store the dataset in the registry
        self.datasets[dataset_id] = dataset

        return dataset

    def remove(self, dataset_id: int) -> None:
        """
        Remove a dataset from the registry by its ID.
        """
        if dataset_id in self.datasets:
            self.datasets.pop(dataset_id)

    # ------------------------------------------------------------------
    # Per-part state: write path
    # ------------------------------------------------------------------

    def find_dataset_id_for_part(self, part_id: int) -> int | None:
        """
        Find the ID of the dataset that owns the given part.

        Args:
            part_id (int): The scene-graph node ID identifying the part.

        Returns:
            int | None: The dataset ID that owns the part, or None if no
            dataset in the registry has this part_id in its PartIndex.
        """
        for dataset_id, dataset in self.datasets.items():
            if part_id in dataset.part_index.part_ids:
                return dataset_id
        return None

    def get_part_state(self, part_id: int) -> RuntimePartProperties | None:
        """
        Get the current runtime state record for a single part.

        This is a read-only lookup: unlike the setters, it does not upsert
        a record for a part that has no state yet.

        Args:
            part_id (int): The scene-graph node ID identifying the part.

        Returns:
            RuntimePartProperties | None: The live state record for the
            part, or None if part_id resolves to no dataset, or the owning
            dataset has no recorded state for it.
        """
        dataset_id = self.find_dataset_id_for_part(part_id)
        if dataset_id is None:
            return None
        return self.datasets[dataset_id].state.part_states.get(part_id)

    def _get_or_create_part_state(self, part_id: int) -> RuntimePartProperties | None:
        """
        Resolve the live part-state record for part_id, upserting if needed.

        If the owning dataset has no part_states entry yet for part_id (e.g.
        a freshly added dataset with no persisted part state), a
        RuntimePartProperties(id=part_id) record is created and inserted
        into the dataset's part_states dict first. This is mandatory: a
        freshly added dataset has an empty part_states dict, so without
        this upsert every setter would silently no-op for it.

        Returns:
            RuntimePartProperties | None: The live state record, or None if
            part_id resolves to no dataset.
        """
        dataset_id = self.find_dataset_id_for_part(part_id)
        if dataset_id is None:
            return None
        dataset = self.datasets[dataset_id]
        part_state = dataset.state.part_states.get(part_id)
        if part_state is None:
            part_state = RuntimePartProperties(id=part_id)
            dataset.state.part_states[part_id] = part_state
        return part_state

    def set_part_visibility(self, part_id: int, visible: bool) -> bool:
        """
        Set whether a part is visible.

        Returns:
            bool: True when the record was written, False when part_id
            resolves to no dataset. Never raises.
        """
        part_state = self._get_or_create_part_state(part_id)
        if part_state is None:
            return False
        part_state.visible = visible
        return True

    def set_part_opacity(self, part_id: int, opacity: float) -> bool:
        """
        Set a part's opacity.

        Returns:
            bool: True when the record was written, False when part_id
            resolves to no dataset. Never raises.
        """
        part_state = self._get_or_create_part_state(part_id)
        if part_state is None:
            return False
        part_state.opacity = opacity
        return True

    def set_part_diffuse_color(self, part_id: int, diffuse_rgb: list[float] | None) -> bool:
        """
        Set a part's custom diffuse colour, or clear it with None.

        Returns:
            bool: True when the record was written, False when part_id
            resolves to no dataset. Never raises.
        """
        part_state = self._get_or_create_part_state(part_id)
        if part_state is None:
            return False
        part_state.diffuse_rgb = diffuse_rgb
        return True

    def set_part_selected(self, part_id: int, selected: bool) -> bool:
        """
        Set whether a part is selected.

        Returns:
            bool: True when the record was written, False when part_id
            resolves to no dataset. Never raises.
        """
        part_state = self._get_or_create_part_state(part_id)
        if part_state is None:
            return False
        part_state.selected = selected
        return True

    def set_part_color_variable(self, part_id: int, variable_id: str, component: int | None) -> bool:
        """
        Set the variable a part is coloured by, and its component.

        variable_id and component are set together, atomically, in this one
        call, mirroring clear_part_color_variable's atomic clear.

        Returns:
            bool: True when the record was written, False when part_id
            resolves to no dataset. Never raises.
        """
        part_state = self._get_or_create_part_state(part_id)
        if part_state is None:
            return False
        part_state.spectrum_id = variable_id
        part_state.spectrum_component = component
        return True

    def clear_part_color_variable(self, part_id: int) -> bool:
        """
        Clear the variable a part is coloured by.

        Sets spectrum_id and spectrum_component to None together, in one
        call — the compound class is only ever set or cleared atomically,
        never field by field.

        Returns:
            bool: True when the record was written, False when part_id
            resolves to no dataset. Never raises.
        """
        part_state = self._get_or_create_part_state(part_id)
        if part_state is None:
            return False
        part_state.spectrum_id = None
        part_state.spectrum_component = None
        return True

    def replace_part_states(self, dataset_states: Dict[int, RuntimeDatasetState]) -> None:
        """
        Replace the runtime state of registered datasets in bulk.

        For each dataset ID present in both dataset_states and the
        registry, that dataset's .state is replaced directly with the
        supplied RuntimeDatasetState (already-runtime, id-keyed input).
        Dataset IDs in dataset_states that are not present in the registry
        are skipped silently; processing continues for the remaining
        entries. Never raises.
        """
        for dataset_id, runtime_state in dataset_states.items():
            dataset = self.datasets.get(dataset_id)
            if dataset is None:
                continue
            dataset.state = runtime_state

    def _get_unique_dataset_name(self, name: str) -> str:
        """
        Rename the dataset by appending a suffix to ensure uniqueness.

        @return
        A unique dataset name. If the original name is unique, it is returned as is.
        """
        # Get existing dataset names
        dataset_names = [dataset.name for dataset in self.datasets.values()]

        # If the name is unique, return it as is
        if name not in dataset_names:
            return name

        # Extract base name and suffix if present
        match = re.match(r"^(.*?)(?:_(\d+))?$", name)
        base_name = match.group(1)
        suffix = int(match.group(2)) if match.group(2) else 1

        # Generate new name with incremented suffix until unique
        new_name = f"{base_name}_{suffix}"
        while new_name in dataset_names:
            suffix += 1
            new_name = f"{base_name}_{suffix}"
        return new_name

    def get_sanitized_metadata_name(self, metadata: ExtendedMetadata) -> str:
        """
        Normalize the metadata by ensuring unique dataset names.
        """
        # TODO: move to protected after composite dataset support is added
        # and Scene.add_dataset delegates more cleanly to DatasetRegistry

        if metadata is None:
            raise ValueError("Metadata cannot be None.")

        new_name = self._get_unique_dataset_name(metadata.name)
        if new_name != metadata.name:
            logger.warning(f"Dataset name '{metadata.name}' already exists. Renaming to '{new_name}'.")

        return new_name

    def clear(self):
        """
        Clear all datasets from the registry.
        """
        self.datasets.clear()
        self._reset_unit()

    def list_variables(self, dataset_id: int) -> List[VisorPartVariables]:
        """
        Get the variable information from the scene graph.
        """
        dataset = self.datasets.get(dataset_id)
        if dataset is None:
            msg = f"Dataset with id {dataset_id} not found."
            logger.error(msg)
            raise ValueError(msg)
        return dataset.list_variables()

    def update_variables(self, dataset_id: int, variables: List[VisorVariableUpdate]) -> None:
        """
        Update the variables in the scene graph.
        """
        dataset = self.datasets.get(dataset_id)
        if dataset is None:
            msg = f"Dataset with id {dataset_id} not found."
            logger.error(msg)
            raise ValueError(msg)
        dataset.update_variables(variables)

    def _validate_unit(self, metadata: ExtendedMetadata) -> bool:
        """
        Validate that the unit of the new metadata matches the existing unit.

        @return
        True if the units match or if the existing unit is empty, False otherwise.
        """
        # TODO: move to protected after composite dataset support is added
        # and Scene.add_dataset delegates more cleanly to DatasetRegistry

        if metadata is None:
            return False

        if len(self.datasets) == 0:
            # if this is the first dataset being added into a blank scene, accept any unit
            return True

        if metadata.unit != self.unit:
            msg = (f"Unit mismatch: existing ('{self.unit}') vs new ('{metadata.unit}')."
                   f" Setting unit to null.")
            logger.warning(msg)
            return False

        return True

    def _update_unit(self, metadata: ExtendedMetadata):
        """
        Update the unit to the specified value.
        """
        if self._validate_unit(metadata):
            # store unit to this class
            self.unit = metadata.unit
        else:
            # reset unit to empty string
            self._reset_unit()

    def _reset_unit(self):
        """
        Reset the unit to an empty string.
        """
        self.unit = ""

