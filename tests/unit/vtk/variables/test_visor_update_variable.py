# python
from dataclasses import FrozenInstanceError
from enum import Enum

import numpy as np
import pytest

# Module under test
from ansys.visor.viewer.vtk.variables import visor_variable_update as tvu


@pytest.fixture(autouse=True)
def patch_enum(monkeypatch):
    """Providdes a fake enum for testing, and patches the module to use it."""
    class FakeEnum(Enum):
        POINT = "POINT"
        CELL = "CELL"

    # Replace the enum used by the module so we do not depend on external code
    monkeypatch.setattr(tvu, "VisorVtkVariableType", FakeEnum, raising=True)
    return FakeEnum


# ---------- Constructor (__post_init__) tests ----------

def test_init_with_enum_success(patch_enum):
    """Verify that initializing with valid enum succeeds."""
    v = tvu.VisorVariableUpdate(
        type=patch_enum.POINT,
        name="var",
        num_components=2,
        data=[1, 2, 3, 4],
    )
    assert v.type is patch_enum.POINT
    assert v.name == "var"
    assert v.num_components == 2
    # Constructor does not reshape/convert data
    assert v.data == [1, 2, 3, 4]


@pytest.mark.parametrize("type_value, expected", [("POINT", "POINT"), ("point", "POINT"), ("cell", "CELL")])
def test_init_with_string_type_coercion(type_value, expected, patch_enum):
    """Verify that initializing with string type coercion succeeds."""
    v = tvu.VisorVariableUpdate(
        type=type_value,
        name="n",
        num_components=1,
        data=[1],
    )
    assert v.type is getattr(patch_enum, expected)


@pytest.mark.parametrize("bad_type", ["unknown", "not_an_enum"])
def test_init_with_invalid_type_raises(bad_type):
    """Verify that initializing with invalid type raises ValueError."""
    with pytest.raises(ValueError, match="Invalid type"):
        tvu.VisorVariableUpdate(type=bad_type, name="n", num_components=1, data=[1])


@pytest.mark.parametrize("bad_name", ["", None])
def test_init_with_bad_name_raises(bad_name):
    """Verify that initializing with bad name raises ValueError."""
    with pytest.raises(ValueError, match="name must be non-empty"):
        tvu.VisorVariableUpdate(type="POINT", name=bad_name, num_components=1, data=[1])


@pytest.mark.parametrize("bad_nc", [0, -1])
def test_init_with_non_positive_num_components_raises(bad_nc):
    """Verify that initializing with non-positive num_components raises ValueError."""
    with pytest.raises(ValueError, match="num_components must be > 0"):
        tvu.VisorVariableUpdate(type="POINT", name="n", num_components=bad_nc, data=[1])


def test_frozen_dataclass_cannot_be_modified(patch_enum):
    """Verify that VisorVariableUpdate is frozen and cannot be modified after creation."""
    v = tvu.VisorVariableUpdate(type=patch_enum.CELL, name="n", num_components=1, data=[1])
    with pytest.raises(FrozenInstanceError):
        v.name = "other"


# ---------- from_dict tests (covers data validation/reshaping via public API) ----------

def test_from_dict_valid_with_enum_type_and_list_1d():
    """Verify that from_dict works with valid enum type and 1D list data."""
    d = {
        "type": "POINT",
        "name": "pressure",
        "num_components": 3,
        "data": [1, 2, 3, 4, 5, 6],
    }
    v = tvu.VisorVariableUpdate.from_dict(d)
    assert v.name == "pressure"
    assert v.num_components == 3
    assert isinstance(v.data, np.ndarray)
    assert v.data.shape == (2, 3)
    assert v.data.dtype == np.float32


def test_from_dict_valid_with_lowercase_type_and_numpy_1d_nc1():
    """Verify that from_dict works with lowercase type and 1D numpy array with num_components=1."""
    arr = np.array([10, 20, 30], dtype=np.float64)
    v = tvu.VisorVariableUpdate.from_dict(
        {"type": "cell", "name": "scalar", "num_components": 1, "data": arr}
    )
    assert v.data.shape == (3, 1)
    assert v.data.dtype == np.float32


def test_from_dict_numpy_1d_multicomponent_raises():
    """Verify that from_dict raises ValueError when a 1D numpy array is provided for multi-component data."""
    arr = np.array([1, 2, 3], dtype=np.float32)
    with pytest.raises(ValueError, match="1D NumPy array provided"):
        tvu.VisorVariableUpdate.from_dict(
            {"type": "POINT", "name": "v", "num_components": 2, "data": arr}
        )


def test_from_dict_numpy_2d_last_dim_mismatch_raises():
    """Verify that from_dict raises ValueError when a 2D numpy array's last dimension does not match num_components."""
    arr = np.zeros((4, 2), dtype=np.float32)  # last dim=2
    with pytest.raises(ValueError, match="last dimension .* does not match"):
        tvu.VisorVariableUpdate.from_dict(
            {"type": "POINT", "name": "v", "num_components": 3, "data": arr}
        )


def test_from_dict_numpy_3d_flattens_to_neg1_nc_and_casts_dtype():
    """Verify that from_dict flattens a 3D numpy array to (-1, num_components) and casts dtype to float32."""
    arr = np.zeros((2, 5, 3), dtype=np.float64)  # last dim=3
    v = tvu.VisorVariableUpdate.from_dict(
        {"type": "POINT", "name": "vec", "num_components": 3, "data": arr}
    )
    assert v.data.shape == (10, 3)
    assert v.data.dtype == np.float32


def test_from_dict_list_1d_len_not_divisible_raises():
    """Verify that from_dict raises ValueError when a 1D list's length is not divisible by num_components."""
    with pytest.raises(ValueError, match="not divisible by num_components"):
        tvu.VisorVariableUpdate.from_dict(
            {"type": "POINT", "name": "v", "num_components": 3, "data": [1, 2, 3, 4, 5]}
        )


def test_from_dict_list_2d_last_dim_match_ok_and_dtype():
    """Verify that from_dict works with a 2D list whose last dimension matches num_components and casts dtype."""
    data = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]  # shape (2,3)
    v = tvu.VisorVariableUpdate.from_dict(
        {"type": "POINT", "name": "vec", "num_components": 3, "data": data}
    )
    assert v.data.shape == (2, 3)
    assert v.data.dtype == np.float32


def test_from_dict_list_2d_last_dim_mismatch_raises():
    """Verify that from_dict raises ValueError when a 2D list's last dimension does not match num_components."""
    data = [[1.0, 2.0], [3.0, 4.0]]  # last dim=2
    with pytest.raises(ValueError, match="iterator too short"):
        tvu.VisorVariableUpdate.from_dict(
            {"type": "POINT", "name": "vec", "num_components": 3, "data": data}
        )


@pytest.mark.parametrize("missing_key", ["type", "name", "num_components", "data"])
def test_from_dict_missing_required_field_raises(missing_key):
    """Verify that from_dict raises ValueError when a required field is missing."""
    base = {"type": "POINT", "name": "n", "num_components": 1, "data": [1.0]}
    base.pop(missing_key)
    with pytest.raises(ValueError, match=f"Missing required field: {missing_key}"):
        tvu.VisorVariableUpdate.from_dict(base)


def test_from_dict_num_components_not_int_raises():
    """Verify that from_dict raises ValueError when num_components is not an integer."""
    with pytest.raises(ValueError, match="num_components must be an integer"):
        tvu.VisorVariableUpdate.from_dict(
            {"type": "POINT", "name": "n", "num_components": "abc", "data": [1]}
        )


@pytest.mark.parametrize("bad_name", ["", "   ", None])
def test_from_dict_bad_name_raises(bad_name):
    """Verify that from_dict raises ValueError when name is empty or None."""
    with pytest.raises(ValueError, match="name must be non-empty"):
        tvu.VisorVariableUpdate.from_dict(
            {"type": "POINT", "name": bad_name, "num_components": 1, "data": [1]}
        )


def test_from_dict_data_none_raises():
    """Verify that from_dict raises ValueError when data is None."""
    with pytest.raises(ValueError, match="data must be provided"):
        tvu.VisorVariableUpdate.from_dict(
            {"type": "POINT", "name": "n", "num_components": 1, "data": None}
        )


def test_from_dict_data_string_raises_type_error():
    """Verify that from_dict raises TypeError when data is a string (not a sequence or ndarray)."""
    with pytest.raises(TypeError, match="data must be a numpy.ndarray or a sequence"):
        tvu.VisorVariableUpdate.from_dict(
            {"type": "POINT", "name": "n", "num_components": 1, "data": "not_valid"}
        )
