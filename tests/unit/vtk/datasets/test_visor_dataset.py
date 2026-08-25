from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from vtkmodules.util.vtkConstants import VTK_FLOAT

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType

# Target import
from ansys.visor.viewer.vtk.datasets.visor_dataset import VisorDataset


# Lightweight mocks for external enum and types
class MockVisorVtkVariableType:
    POINT = object()
    CELL = object()

class MockVisorDatasetInfo:
    def __init__(self, name="dataset_name", id=123, unit="mm", file_path=None, metadata_path=None):
        self.name = name
        self.id = id
        self.unit = unit
        self.file_path = file_path
        self.metadata_path = metadata_path

    def model_dump(self):
        return {"name": self.name, "id": self.id, "unit": self.unit, "file_path": self.file_path, "metadata_path": self.metadata_path}

class MockVisorDatasetState:
    def __init__(self, state_dict=None):
        self._state_dict = state_dict or {"foo": "bar", "parts": ["p1", "p2"]}

    def model_dump(self, exclude=None):
        return dict(self._state_dict)


@pytest.fixture
def mock_data_object():
    """PyTest fixture for mock data object."""
    # Mock of vtkDataObject with Modified
    m = MagicMock()
    m.Modified = MagicMock()
    return m





@pytest.fixture
def mock_info():
    """PyTest fixture for mock info."""
    return MockVisorDatasetInfo()


@pytest.fixture
def mock_state():
    """PyTest fixture for mock state."""
    return MockVisorDatasetState()


@pytest.fixture
def dataset_factory(mock_data_object):
    """PyTest fixture for dataset factory."""
    def make_dataset(is_composite=False, variables_instance=None):
        # Patch `is_composite_dataset` to control composite status
        is_comp_patch = patch(
            "ansys.visor.viewer.vtk.datasets.visor_dataset.is_composite_dataset",
            return_value=is_composite,
        )
        is_comp_ctx = is_comp_patch.start()

        # Patch `VisorVariables` to return provided or mocked instance
        if variables_instance is None and not is_composite:
            variables_instance = MagicMock()
        tv_patch = patch(
            "ansys.visor.viewer.vtk.datasets.visor_dataset.VisorVariables",
            return_value=variables_instance,
        )
        tv_ctx = tv_patch.start()

        # Patch PartIndex so it doesn't try to traverse the mock VTK object
        mock_part_index = MagicMock()
        mock_part_index.name_to_id_map = {}
        mock_part_index.part_ids = [] if is_composite else [999]
        mock_part_index.get_entry.return_value = None
        mock_part_index.get_leaf_block.return_value = mock_data_object
        pi_patch = patch(
            "ansys.visor.viewer.vtk.datasets.visor_dataset.PartIndex",
            return_value=mock_part_index,
        )
        pi_ctx = pi_patch.start()

        # Create mock metadata with required structure
        mock_metadata = MagicMock()
        mock_metadata.unit = "mm"
        mock_metadata.file_path = None
        mock_metadata.metadata_path = None
        mock_metadata.state.parts = {}  # Empty parts dict for simplicity

        # Use correct constructor signature
        ds = VisorDataset(
            id=123,
            name="dataset_name",
            data=mock_data_object,
            part_name_to_id={},
            metadata=mock_metadata
        )

        # Cleanup function to stop patches
        def _cleanup():
            is_comp_ctx.stop()
            tv_ctx.stop()
            pi_ctx.stop()

        return ds, variables_instance, _cleanup

    return make_dataset


def test_name_returns_state_name(dataset_factory):
    """Test that name returns state name."""
    ds, _, cleanup = dataset_factory(is_composite=False)
    try:
        assert ds.name == "dataset_name"
    finally:
        cleanup()


def test_state_info_excludes_parts(dataset_factory, mock_state):
    """Test that state info excludes parts."""
    ds, _, cleanup = dataset_factory(is_composite=False)
    try:
        info = ds.info_dict
        assert "parts" not in info
        assert info == {"name": "dataset_name", "id": 123, "unit": "mm", "file_path": None, "metadata_path": None}
    finally:
        cleanup()


def test_is_composite_true(dataset_factory):
    """Test that is composite is true."""
    ds, _, cleanup = dataset_factory(is_composite=True)
    try:
        assert ds.is_composite() is True
    finally:
        cleanup()


def test_is_composite_false(dataset_factory):
    """Test that is composite is false."""
    ds, _, cleanup = dataset_factory(is_composite=False)
    try:
        assert ds.is_composite() is False
    finally:
        cleanup()


def test_list_variables_on_composite_returns_per_part(dataset_factory):
    """Composite datasets now return a per-part list (not raise NotImplementedError)."""
    ds, _, cleanup = dataset_factory(is_composite=True, variables_instance=None)
    try:
        # With the mock PartIndex returning part_ids=[], the result should be an empty list.
        result = ds.list_variables()
        assert isinstance(result, list)
    finally:
        cleanup()


def test_list_variables_calls_variables_list(dataset_factory):
    """Test that list variables calls variables list."""
    ds, variables, cleanup = dataset_factory(is_composite=False)
    variables.list.return_value = ["var1", "var2"]
    try:
        result = ds.list_variables()
        variables.list.assert_called_once()
        # list_variables now returns List[VisorPartVariables]; check the variables on the first entry
        assert len(result) == 1
        assert result[0].variables == ["var1", "var2"]
    finally:
        cleanup()


def test_update_variables_on_composite_broadcast_applies_to_all_matching_parts(dataset_factory):
    """part_id=None on a composite dataset broadcasts to every part where validation passes."""
    # Build a dataset_factory-style composite with two parts
    mock_vars_0 = MagicMock()
    mock_vars_0.validate_new_variables = MagicMock(return_value=True)
    mock_vars_1 = MagicMock()
    mock_vars_1.validate_new_variables = MagicMock(return_value=True)

    is_comp_patch = patch(
        "ansys.visor.viewer.vtk.datasets.visor_dataset.is_composite_dataset",
        return_value=True,
    )
    is_comp_ctx = is_comp_patch.start()

    part_id_0, part_id_1 = 111, 222
    mock_part_index = MagicMock()
    mock_part_index.name_to_id_map = {}
    mock_part_index.id_to_name_map = {}
    mock_part_index.part_ids = [part_id_0, part_id_1]
    mock_part_index.get_entry.return_value = None
    mock_part_index.get_leaf_block.return_value = MagicMock()
    pi_patch = patch(
        "ansys.visor.viewer.vtk.datasets.visor_dataset.PartIndex",
        return_value=mock_part_index,
    )
    pi_ctx = pi_patch.start()

    call_count = [0]
    def fake_variables_factory(*args, **kwargs):
        call_count[0] += 1
        return mock_vars_0 if call_count[0] == 1 else mock_vars_1
    tv_patch = patch(
        "ansys.visor.viewer.vtk.datasets.visor_dataset.VisorVariables",
        side_effect=fake_variables_factory,
    )
    tv_ctx = tv_patch.start()

    mock_metadata = MagicMock()
    mock_metadata.unit = "mm"
    mock_metadata.file_path = None
    mock_metadata.metadata_path = None
    mock_metadata.state.parts = {}
    mock_data = MagicMock()

    ds = VisorDataset(id=1, name="ds", data=mock_data, part_name_to_id={}, metadata=mock_metadata)

    broadcast_var = MagicMock()
    broadcast_var.part_id = None  # broadcast

    try:
        with patch.object(ds, "_update_variable") as upd:
            ds.update_variables([broadcast_var])
            # Should have been called once per part
            assert upd.call_count == 2
        mock_vars_0.reload.assert_called_once()
        mock_vars_1.reload.assert_called_once()
    finally:
        is_comp_ctx.stop()
        tv_ctx.stop()
        pi_ctx.stop()


def test_update_variables_on_composite_broadcast_skips_non_matching_parts(dataset_factory):
    """Broadcast skips parts where validation fails (e.g. variable doesn't exist)."""
    mock_vars_ok = MagicMock()
    mock_vars_ok.validate_new_variables = MagicMock(return_value=True)
    mock_vars_bad = MagicMock()
    mock_vars_bad.validate_new_variables = MagicMock(return_value=False)

    is_comp_patch = patch(
        "ansys.visor.viewer.vtk.datasets.visor_dataset.is_composite_dataset",
        return_value=True,
    )
    is_comp_ctx = is_comp_patch.start()

    part_id_ok, part_id_bad = 111, 222
    mock_part_index = MagicMock()
    mock_part_index.name_to_id_map = {}
    mock_part_index.id_to_name_map = {}
    mock_part_index.part_ids = [part_id_ok, part_id_bad]
    mock_part_index.get_entry.return_value = None
    mock_part_index.get_leaf_block.return_value = MagicMock()
    pi_patch = patch(
        "ansys.visor.viewer.vtk.datasets.visor_dataset.PartIndex",
        return_value=mock_part_index,
    )
    pi_ctx = pi_patch.start()

    call_count = [0]
    def fake_variables_factory(*args, **kwargs):
        call_count[0] += 1
        return mock_vars_ok if call_count[0] == 1 else mock_vars_bad
    tv_patch = patch(
        "ansys.visor.viewer.vtk.datasets.visor_dataset.VisorVariables",
        side_effect=fake_variables_factory,
    )
    tv_ctx = tv_patch.start()

    mock_metadata = MagicMock()
    mock_metadata.unit = "mm"
    mock_metadata.file_path = None
    mock_metadata.metadata_path = None
    mock_metadata.state.parts = {}

    ds = VisorDataset(id=1, name="ds", data=MagicMock(), part_name_to_id={}, metadata=mock_metadata)

    broadcast_var = MagicMock()
    broadcast_var.part_id = None

    try:
        with patch.object(ds, "_update_variable") as upd:
            ds.update_variables([broadcast_var])
            # Only the matching part should be updated
            assert upd.call_count == 1
        mock_vars_ok.reload.assert_called_once()
        mock_vars_bad.reload.assert_not_called()
    finally:
        is_comp_ctx.stop()
        tv_ctx.stop()
        pi_ctx.stop()


def test_update_variables_validation_failure_raises(dataset_factory):
    """Test that updating variables validation failure raises."""
    ds, variables, cleanup = dataset_factory(is_composite=False)
    variables.validate_new_variables.return_value = False
    try:
        with pytest.raises(ValueError):
            ds.update_variables(variable_list=[MagicMock()])
        variables.validate_new_variables.assert_called_once()
        variables.reload.assert_not_called()
    finally:
        cleanup()


def test_update_variables_happy_path_calls_reload_and_modifies(dataset_factory, mock_data_object):
    """Test that updating variables happy path calls reload and modifies."""
    ds, variables, cleanup = dataset_factory(is_composite=False)
    variables.validate_new_variables.return_value = True

    # Create a mock update object; content is irrelevant due to heavy mocking
    mock_update = MagicMock()

    # Patch the internal `_update_variable` to avoid touching private behavior but ensure it gets invoked via public API
    with patch.object(ds, "_update_variable") as upd:
        ds.update_variables(variable_list=[mock_update, mock_update])
        variables.validate_new_variables.assert_called_once_with([mock_update, mock_update])
        assert upd.call_count == 2
        variables.reload.assert_called_once_with(mock_data_object)
        # Note: The implementation no longer calls data.Modified() after reload.
        mock_data_object.Modified.assert_not_called()


def test_update_variables_empty_list_validates_and_reloads(dataset_factory, mock_data_object):
    """Test that updating variables empty list validates and reloads."""
    ds, variables, cleanup = dataset_factory(is_composite=False)
    variables.validate_new_variables.return_value = True
    with patch.object(ds, "_update_variable") as upd:
        ds.update_variables(variable_list=[])
        variables.validate_new_variables.assert_called_once_with([])
        upd.assert_not_called()
        variables.reload.assert_called_once_with(mock_data_object)


@pytest.fixture
def mock_point_data():
    """PyTest fixture for mock point data."""
    return MagicMock()

@pytest.fixture
def mock_cell_data():
    """PyTest fixture for mock cell data."""
    return MagicMock()

@pytest.fixture
def mock_array():
    """PyTest fixture for mock array."""
    a = MagicMock()
    a.GetNumberOfTuples.return_value = 3
    a.GetDataType.return_value = VTK_FLOAT
    a.GetName.return_value = "pressure"
    return a

@pytest.fixture
def mock_data_object(mock_point_data, mock_cell_data):  # noqa: F811
    """PyTest fixture for mock data object."""
    m = MagicMock()
    # Expose VTK-like API used by _get_data_for_type
    m.GetPointData.return_value = mock_point_data
    m.GetCellData.return_value = mock_cell_data
    m.Modified = MagicMock()
    return m

@pytest.fixture
def mock_state_class():
    """PyTest fixture for mock state class."""
    class MockState:
        name = "dataset_name"
        def model_dump(self, exclude=None):
            return {"foo": "bar"} if exclude == "parts" else {"foo": "bar", "parts": ["p1"]}
    return MockState()


@pytest.fixture
def dataset_with_variables(mock_data_object):
    """PyTest fixture for dataset with variables."""
    # Ensure non-composite
    is_comp_patch = patch(
        "ansys.visor.viewer.vtk.datasets.visor_dataset.is_composite_dataset",
        return_value=False,
    )
    is_comp_ctx = is_comp_patch.start()

    # Provide a VisorVariables mock
    variables = MagicMock()
    tv_patch = patch(
        "ansys.visor.viewer.vtk.datasets.visor_dataset.VisorVariables",
        return_value=variables,
    )
    tv_ctx = tv_patch.start()

    # Patch PartIndex so it doesn't traverse the mock VTK object
    mock_part_index = MagicMock()
    mock_part_index.name_to_id_map = {}
    mock_part_index.part_ids = [999]
    mock_part_index.get_entry.return_value = None
    mock_part_index.get_leaf_block.return_value = mock_data_object
    pi_patch = patch(
        "ansys.visor.viewer.vtk.datasets.visor_dataset.PartIndex",
        return_value=mock_part_index,
    )
    pi_ctx = pi_patch.start()

    # Create mock metadata
    mock_metadata = MagicMock()
    mock_metadata.unit = "mm"
    mock_metadata.file_path = None
    mock_metadata.metadata_path = None
    mock_metadata.state.parts = {}

    ds = VisorDataset(
        id=1,
        name="dataset_name",
        data=mock_data_object,
        part_name_to_id={},
        metadata=mock_metadata
    )

    def _cleanup():
        is_comp_ctx.stop()
        tv_ctx.stop()
        pi_ctx.stop()

    return ds, variables, _cleanup


def test_update_variables_point_scalar_updates(dataset_with_variables, mock_point_data, mock_array):
    """Test that updating variables point scalar updates."""
    ds, variables, cleanup = dataset_with_variables
    variables.validate_new_variables.return_value = True

    # Prepare point data to return our array
    mock_point_data.GetArray.return_value = mock_array

    # Variable update: scalar values on POINT data
    update = MagicMock()
    update.type = VisorVtkVariableType.POINT
    update.name = "pressure"
    update.num_components = 1
    update.data = np.array([[1.0], [2.0], [3.0]], dtype=float)

    try:
        # Patch vtk_to_numpy to return a real numpy buffer view so np.copyto works
        with patch("ansys.visor.viewer.vtk.datasets.visor_dataset.vtk_to_numpy") as vtknp:
            vtknp.return_value = np.zeros((mock_array.GetNumberOfTuples.return_value, update.num_components), dtype=float)
            ds.update_variables([update])

        variables.validate_new_variables.assert_called_once_with([update])
        # Implementation writes into the existing array buffer and calls Modified() on the array
        mock_array.Modified.assert_called_once()
        # The dataset object itself is not Modified by the current implementation
        ds.data.Modified.assert_not_called()
        variables.reload.assert_called_once_with(ds.data)
    finally:
        cleanup()


def test_update_variables_cell_vector_updates(dataset_with_variables, mock_cell_data, mock_array):
    """Test that updating variables cell vector updates."""
    ds, variables, cleanup = dataset_with_variables
    variables.validate_new_variables.return_value = True

    mock_cell_data.GetArray.return_value = mock_array

    update = MagicMock()
    update.type = VisorVtkVariableType.CELL
    update.name = "velocity"
    update.num_components = 3
    update.data = np.array([[1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0]], dtype=float)

    try:
        # Patch vtk_to_numpy so np.copyto can operate on a concrete numpy buffer
        with patch("ansys.visor.viewer.vtk.datasets.visor_dataset.vtk_to_numpy") as vtknp:
            vtknp.return_value = np.zeros((mock_array.GetNumberOfTuples.return_value, update.num_components), dtype=float)
            ds.update_variables([update])

        variables.validate_new_variables.assert_called_once_with([update])
        mock_array.Modified.assert_called_once()
        ds.data.Modified.assert_not_called()
        variables.reload.assert_called_once_with(ds.data)
    finally:
        cleanup()


def test_update_variables_array_not_found_raises(dataset_with_variables, mock_point_data):
    """Test that updating variables array not found raises."""
    ds, variables, cleanup = dataset_with_variables
    variables.validate_new_variables.return_value = True

    mock_point_data.GetArray.return_value = None

    update = MagicMock()
    update.type = VisorVtkVariableType.POINT
    update.name = "missing"
    update.num_components = 1
    update.data = np.array([[0.0], [0.0], [0.0]], dtype=float)

    try:
        with pytest.raises(ValueError, match="Variable 'missing' not found"):
            ds.update_variables([update])
        variables.reload.assert_not_called()
        ds.data.Modified.assert_not_called()
    finally:
        cleanup()


def test_update_variables_length_mismatch_raises(dataset_with_variables, mock_point_data, mock_array):
    """Test that updating variables length mismatch raises."""
    ds, variables, cleanup = dataset_with_variables
    variables.validate_new_variables.return_value = True

    # Force array length that will mismatch with provided data
    mock_array.GetNumberOfTuples.return_value = 2
    mock_point_data.GetArray.return_value = mock_array

    update = MagicMock()
    update.type = VisorVtkVariableType.POINT
    update.name = "pressure"
    update.num_components = 1
    update.data = np.array([[1.0], [2.0], [3.0]], dtype=float)  # 3 items vs 2 tuples

    try:
        with pytest.raises(ValueError, match="Data length mismatch"):
            ds.update_variables([update])
        variables.reload.assert_not_called()
        ds.data.Modified.assert_not_called()
        mock_array.Modified.assert_not_called()
        mock_array.DeepCopy.assert_not_called()
    finally:
        cleanup()


def test_update_variables_unsupported_type_raises(dataset_with_variables):
    """Test that updating variables unsupported type raises."""
    ds, variables, cleanup = dataset_with_variables
    variables.validate_new_variables.return_value = True

    # Use an unsupported type that is not POINT or CELL
    unsupported_type = object()

    update = MagicMock()
    update.type = unsupported_type
    update.name = "var"
    update.num_components = 1
    update.data = np.array([[0.0], [0.0], [0.0]], dtype=float)

    try:
        with pytest.raises(ValueError, match="Unsupported variable type"):
            ds.update_variables([update])
        variables.reload.assert_not_called()
        ds.data.Modified.assert_not_called()
    finally:
        cleanup()


# ================================================================== #
# is_dirty / mark_clean
# ================================================================== #

def test_new_dataset_is_dirty(dataset_factory):
    """Test that new dataset is is dirty."""
    ds, _, cleanup = dataset_factory(is_composite=False)
    try:
        assert ds.is_dirty is True
    finally:
        cleanup()


def test_mark_clean_clears_dirty_flag(dataset_factory):
    """Test that mark clean clears dirty flag."""
    ds, _, cleanup = dataset_factory(is_composite=False)
    try:
        ds.mark_clean()
        assert ds.is_dirty is False
    finally:
        cleanup()


def test_update_variables_marks_dataset_dirty(dataset_with_variables, mock_point_data, mock_array):
    """Test that updating variables marks dataset is dirty."""
    ds, variables, cleanup = dataset_with_variables
    variables.validate_new_variables.return_value = True
    mock_point_data.GetArray.return_value = mock_array

    update = MagicMock()
    update.type = VisorVtkVariableType.POINT
    update.name = "pressure"
    update.num_components = 1
    update.data = np.array([[1.0], [2.0], [3.0]], dtype=float)

    try:
        ds.mark_clean()
        assert ds.is_dirty is False
        # Patch vtk_to_numpy to allow the update to succeed without TypeError
        with patch("ansys.visor.viewer.vtk.datasets.visor_dataset.vtk_to_numpy") as vtknp:
            vtknp.return_value = np.zeros((mock_array.GetNumberOfTuples.return_value, update.num_components), dtype=float)
            ds.update_variables([update])

        assert ds.is_dirty is True
    finally:
        cleanup()

