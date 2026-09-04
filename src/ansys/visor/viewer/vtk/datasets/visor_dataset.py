"""Class representing a Visor dataset."""

import copy
from collections.abc import Sequence
from typing import Dict, List

import numpy as np
from vtkmodules.util.numpy_support import vtk_to_numpy
from vtkmodules.vtkCommonDataModel import vtkDataObject

from ansys.visor.viewer.core.metadata import ExtendedMetadata
from ansys.visor.viewer.core.perf_timer import PerfTimer
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.core.visor_helpers import is_composite_dataset
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.core.visor_types import VisorDatasetType
from ansys.visor.viewer.models.common.part_properties import PartProperties
from ansys.visor.viewer.models.info.visor_dataset_info import VisorDatasetInfo
from ansys.visor.viewer.models.persist.dataset.persisted_dataset_state import PersistedDatasetState
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import RuntimeDatasetState
from ansys.visor.viewer.vtk.datasets.part_index import PartIndex
from ansys.visor.viewer.vtk.variables.visor_part_variables import VisorPartVariables
from ansys.visor.viewer.vtk.variables.visor_variable_update import VisorVariableUpdate
from ansys.visor.viewer.vtk.variables.visor_variables import VisorVariables

"""Logging configuration"""
logger = VisorDefaultLogger(__name__)


class VisorDataset:
    """Base class for Visor datasets."""

    def __init__(self, id: int, name: str, data: vtkDataObject, node_ids: Sequence[int] | None,
                 metadata: ExtendedMetadata):
        self.id: int = id
        self.data: vtkDataObject = data

        # PartIndex is the single source of truth for part topology and IDs.
        # It is built directly from the VTK data object — no scene graph required.
        # node_ids is the positional seed (scene-graph node IDs in leaf order); it
        # pins part IDs to those node IDs so the frontend can correlate part_states
        # entries with VTK actor properties.
        self.part_index: PartIndex = PartIndex(data, name, seed_ids=node_ids)

        # Get the dataset info from metadata
        self.info: VisorDatasetInfo = self._build_dataset_info(id, name, metadata)
        # Build the initial runtime dataset state from persisted part names -> IDs via PartIndex
        self.state: RuntimeDatasetState = self.persisted_to_runtime_state(metadata.state.parts)

        # Per-part variable metadata, keyed by part_id.
        # Works for both composite and non-composite datasets.
        self._part_variables: Dict[int, VisorVariables] = self._load_variables(data)

        # Every newly loaded dataset needs its snapshot written at least once.
        self.is_dirty: bool = True


    @property
    def name(self) -> str:
        """Return the name of the dataset."""
        return self.info.name

    @property
    def info_dict(self) -> dict:
        """Return the dataset info dictionary."""
        return self.info.model_dump()

    def is_composite(self) -> bool:
        """Return whether the dataset is a composite dataset."""
        return is_composite_dataset(self.data)

    # ------------------------------------------------------------------
    # Variable operations
    # ------------------------------------------------------------------

    def list_variables(self) -> List[VisorPartVariables]:
        """
        List all variables in the dataset, grouped by part.

        Returns a list of VisorPartVariables — one entry per part.
        For non-composite datasets this is a single-element list.
        """
        result = []
        for part_id, part_vars in self._part_variables.items():
            entry = self.part_index.get_entry(part_id)
            result.append(VisorPartVariables(
                part_id=part_id,
                part_name=entry.name if entry else "",
                variables=part_vars.list(),
            ))
        return result

    def set_state(self, new_state: PersistedDatasetState) -> None:
        """
        Set the state of the dataset from persisted, name-keyed part state.

        This is the persisted-state conversion path: it converts
        new_state.parts (keyed by part name) into this dataset's runtime
        state (keyed by part ID) via persisted_to_runtime_state.

        Note: a second, id-keyed replacement path also exists, on the
        registry rather than here: VisorDatasetRegistry.replace_part_states
        replaces a dataset's .state directly with an already-runtime,
        id-keyed RuntimeDatasetState, without going through this method or
        its name-to-id conversion.
        """
        self.state = self.persisted_to_runtime_state(new_state.parts)

    def mark_clean(self) -> None:
        """Clear the dirty flag after a successful snapshot write."""
        self.is_dirty = False

    def update_variables(self, variable_list: List[VisorVariableUpdate]) -> None:
        """
        Update variables in the dataset with new data.

        For composite (multiblock) datasets each VisorVariableUpdate must
        carry a ``part_id`` identifying which leaf block to target.
        For non-composite datasets ``part_id`` is optional and ignored.
        """
        timer = PerfTimer("VisorDataset.update_variables", logger, n_vars=len(variable_list))

        if self.is_composite():
            self._update_variables_composite(variable_list, timer)
        else:
            self._update_variables_simple(variable_list, timer)

        self.is_dirty = True
        timer.log()

    # ------------------------------------------------------------------
    # Internal update helpers
    # ------------------------------------------------------------------

    def _update_variables_simple(
            self,
            variable_list: List[VisorVariableUpdate],
            timer: PerfTimer,
    ) -> None:
        """Update path for a non-composite (single-block) dataset."""
        part_ids = self.part_index.part_ids
        if not part_ids:
            raise RuntimeError("PartIndex is empty for a non-composite dataset.")
        part_vars = self._part_variables[part_ids[0]]

        with timer.phase("validate"):
            if not part_vars.validate_new_variables(variable_list):
                raise ValueError("One or more variables are invalid and cannot be updated.")

        with timer.phase("vtk_set_loop"):
            for new_variable in variable_list:
                self._update_variable(new_variable, self.data)

        with timer.phase("reload"):
            part_vars.reload(self.data)

    def _update_variables_composite(
            self,
            variable_list: List[VisorVariableUpdate],
            timer: PerfTimer,
    ) -> None:
        """
        Update path for a composite (multiblock) dataset.

        Each update may either target a specific part (``part_id`` set) or be
        broadcast to all parts (``part_id=None``).  A broadcast update is
        applied to every part for which the variable exists and the data length
        matches; parts that do not satisfy both conditions are skipped with a
        warning rather than raising, so that heterogeneous multiblock datasets
        where not every block carries every variable are handled gracefully.
        """
        targeted = [v for v in variable_list if v.part_id is not None]
        broadcast = [v for v in variable_list if v.part_id is None]

        # Build per-part update lists, starting from targeted updates.
        by_part: Dict[int, List[VisorVariableUpdate]] = {}
        for var in targeted:
            by_part.setdefault(var.part_id, []).append(var)

        # Expand broadcast updates: add to every part where validation passes.
        if broadcast:
            for part_id in self.part_index.part_ids:
                part_vars = self._part_variables.get(part_id)
                if part_vars is None:
                    continue
                accepted = [v for v in broadcast if part_vars.validate_new_variables([v])]
                skipped = [v.name for v in broadcast if not part_vars.validate_new_variables([v])]
                if skipped:
                    logger.warning(
                        f"Broadcast update skipped variable(s) {skipped} on part_id {part_id} "
                        f"(variable not found or data shape mismatch)."
                    )
                if accepted:
                    by_part.setdefault(part_id, []).extend(accepted)

        with timer.phase("validate"):
            for part_id, part_vars_list in by_part.items():
                part_vars = self._part_variables.get(part_id)
                if part_vars is None:
                    raise ValueError(f"part_id {part_id} not found in dataset {self.id}.")
                if not part_vars.validate_new_variables(part_vars_list):
                    raise ValueError(
                        f"One or more variables are invalid for part_id {part_id}."
                    )

        with timer.phase("vtk_set_loop"):
            for part_id, part_vars_list in by_part.items():
                leaf = self.part_index.get_leaf_block(part_id, self.data)
                for new_variable in part_vars_list:
                    self._update_variable(new_variable, leaf)

        with timer.phase("reload"):
            for part_id in by_part:
                leaf = self.part_index.get_leaf_block(part_id, self.data)
                self._part_variables[part_id].reload(leaf)

    def _update_variable(
            self,
            new_variable: VisorVariableUpdate,
            dataset: VisorDatasetType,
    ) -> None:
        """
        Write new data into a single variable array on *dataset* in-place.
        Uses zero-copy numpy view + np.copyto for C-level memcpy speed
        while preserving VTK array object identity.
        """
        data = self._get_data_for_type(dataset, new_variable.type)
        array = data.GetArray(new_variable.name)

        if array is None:
            raise ValueError(f"Variable '{new_variable.name}' not found in dataset.")
        if array.GetNumberOfTuples() != len(new_variable.data):
            raise ValueError(
                f"Data length mismatch for variable '{new_variable.name}': "
                f"expected {array.GetNumberOfTuples()}, got {len(new_variable.data)}."
            )

        timer = PerfTimer(
            f"_update_variable '{new_variable.name}'", logger,
            n_tuples=array.GetNumberOfTuples(),
            n_components=new_variable.num_components,
        )
        with timer.phase("set_loop+modified"):
            buf = vtk_to_numpy(array)
            np.copyto(buf.ravel(), new_variable.data.ravel(), casting="unsafe")
            array.Modified()
        timer.log()

    def _get_data_for_type(self, dataset: VisorDatasetType, var_type: VisorVtkVariableType):
        if var_type == VisorVtkVariableType.POINT:
            return dataset.GetPointData()
        elif var_type == VisorVtkVariableType.CELL:
            return dataset.GetCellData()
        else:
            raise ValueError(f"Unsupported variable type: {var_type}")

    def _load_variables(self, data: vtkDataObject) -> Dict[int, VisorVariables]:
        """
        Build per-part VisorVariables from the VTK data object.
        For non-composite datasets there is a single entry.
        For composite datasets there is one entry per non-empty leaf block.
        """
        result: Dict[int, VisorVariables] = {}
        for part_id in self.part_index.part_ids:
            leaf = self.part_index.get_leaf_block(part_id, data)
            if leaf is not None:
                result[part_id] = VisorVariables(leaf)
        return result

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_dataset_info(
            dataset_id: int,
            dataset_name: str,
            metadata: ExtendedMetadata,
    ) -> VisorDatasetInfo:
        """Construct a VisorDatasetInfo from the dataset ID, name, and ExtendedMetadata."""
        return VisorDatasetInfo(
            id=dataset_id,
            name=dataset_name,
            unit=metadata.unit,
            file_path=metadata.file_path,
            metadata_path=metadata.metadata_path,
        )

    def persisted_to_runtime_state(
            self,
            parts_by_name: dict[str, PartProperties],
    ) -> RuntimeDatasetState:
        """Convert persisted part states (keyed by part name) to runtime part states (keyed by part ID)."""
        name_to_id = self.part_index.name_to_id_map
        part_states = {}
        for part_name, part_properties in parts_by_name.items():
            part_id = name_to_id.get(part_name)
            if part_id is not None:
                part_states[part_id] = copy.deepcopy(part_properties)
        return RuntimeDatasetState.from_components(id=self.id, part_states=part_states)

    def runtime_to_persisted_state(self, runtime_state: RuntimeDatasetState) -> PersistedDatasetState:
        """Convert runtime state to persisted state (keyed by run ID)."""
        id_to_name = self.part_index.id_to_name_map
        part_states = {}
        for part_id, runtime_properties in runtime_state.part_states.items():
            part_name = id_to_name.get(part_id)
            if part_name is None:
                continue
            part_states[part_name] = runtime_properties.to_part_properties()
        return PersistedDatasetState(
            source_file_path=getattr(self.info, "file_path", None),
            source_metadata_path=getattr(self.info, "metadata_path", None),
            parts=part_states,
        )

