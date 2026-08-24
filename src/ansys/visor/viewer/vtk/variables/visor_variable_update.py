"""Class for updating variables on a dataset part in Visor VTK viewer."""


import itertools
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.core.visor_types import ArrayLike


@dataclass(frozen=True)
class VisorVariableUpdate:
    """
    Class for updating variables on a dataset part in Visor VTK viewer.

    Attributes:
        type (VisorVtkVariableType): The type of variable (POINT or CELL).
        name (str): The name of the variable.
        num_components (int): The number of components per data point.
        data (ArrayLike): The variable data, which can be a Python list/sequence or a NumPy array.
        part_id (int | None): The part ID for composite datasets; None for single-block datasets.

    Methods:
        from_dict(cls, data: dict[str, Any]) -> 'VisorVariableUpdate':
            Class method to create an instance from a dictionary.
        _input_to_numpy_array(data: ArrayLike, num_components: int) -> np.ndarray:
            Static method to convert input data to a NumPy array and validate its shape.
    """
    type: VisorVtkVariableType  # enum: POINT/CELL
    name: str
    num_components: int
    data: ArrayLike
    # Required for composite (multiblock) datasets; omit for single-block datasets.
    part_id: int | None = None

    def __post_init__(self):
        """Validate the data class attributes."""
        # Ensure type is a valid enum instance
        if not isinstance(self.type, VisorVtkVariableType):
            # Allow string input and coerce to enum using its canonical names
            try:
                object.__setattr__(self, "type", VisorVtkVariableType[self.type.upper()])
            except Exception:
                raise ValueError("Invalid type for VisorVariableUpdate. Use POINT or CELL.")
        # Basic sanity checks
        if not self.name:
            raise ValueError("name must be non-empty.")
        if self.num_components <= 0:
            raise ValueError("num_components must be > 0.")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'VisorVariableUpdate':
        """Construct an instance from a dictionary."""
        # Required fields
        for key in ("type", "name", "num_components", "data"):
            if key not in data:
                raise ValueError(f"Missing required field: {key}")

        type_value = data["type"]  # can be enum or string; conversion handled in __post_init__
        name = data["name"]
        num_components_raw = data["num_components"]
        data_array = data["data"]

        # Basic shape/type checks prior to constructing
        try:
            num_components = int(num_components_raw)
        except Exception:
            raise ValueError("num_components must be an integer.")

        if name is None or (isinstance(name, str) and name.strip() == ""):
            raise ValueError("name must be non-empty.")

        if data_array is None:
            raise ValueError("data must be provided.")

        # Convert to numpy array and enforce shape checks
        arr = cls._input_to_numpy_array(data_array, num_components)

        return cls(
            type=type_value,
            name=name,
            num_components=num_components,
            data=arr,
            part_id=data.get("part_id", None),
        )

    @staticmethod
    def _input_to_numpy_array(data: ArrayLike, num_components: int) -> np.ndarray:
        """
        Convert input data to a numpy array and validate its shape.
        - Python lists/sequences: Automatically reshaped to (num_points, num_components)
        - NumPy arrays: Must already have correct shape with last dimension = num_components
        Args:
            data (ArrayLike): Input data as a Python list/sequence or NumPy array.
            num_components (int): Expected number of components per data point.
        Returns:
            np.ndarray: Reshaped NumPy array of shape (num_points, num_components).
        Raises:
            ValueError: If the input data cannot be reshaped to the expected format,
                or if the number of components does not match.
        """
        if not (isinstance(data, np.ndarray) or
                (isinstance(data, Sequence) and not isinstance(data, (str, bytes)))):
            raise TypeError("data must be a numpy.ndarray or a sequence (list, tuple, etc.),"
                            "not a string or bytes.")

        # --- numpy fast-path ---
        if isinstance(data, np.ndarray):
            if data.ndim == 1:
                if num_components == 1:
                    # Zero-copy if already float32 C-contiguous, otherwise convert.
                    arr = data if (data.dtype == np.float32 and data.flags['C_CONTIGUOUS']) \
                        else data.astype(np.float32)
                    return arr.reshape(-1, 1)
                else:
                    raise ValueError(
                        f"1D NumPy array provided but num_components is {num_components}. "
                        "Multi-component data must be pre-shaped to (num_points, num_components), "
                        "or provided as a flat Python list/sequence."
                    )
            # 2D+ arrays must be pre-shaped
            if data.shape[-1] != num_components:
                raise ValueError(
                    f"NumPy array last dimension {data.shape[-1]} does not match "
                    f"num_components {num_components}. Multi-dimensional arrays must be pre-shaped."
                )
            # Zero-copy if already float32 C-contiguous with the right shape.
            arr = data if (data.dtype == np.float32 and data.flags['C_CONTIGUOUS']) \
                else data.astype(np.float32)
            return arr.reshape(-1, num_components)

        # --- Python list/sequence fast-path ---
        # For nested sequences (list-of-tuples / list-of-lists) use
        # itertools.chain.from_iterable + np.fromiter — ~2× faster than np.asarray
        # because it avoids building an intermediate Python object array.
        first = data[0] if len(data) > 0 else None
        if first is not None and isinstance(first, (list, tuple)):
            total = len(data) * num_components
            arr = np.fromiter(
                itertools.chain.from_iterable(data),
                dtype=np.float32,
                count=total,
            ).reshape(-1, num_components)
            return arr

        # Flat sequence — standard path
        arr = np.asarray(data, dtype=np.float32)
        if arr.ndim == 1:
            if arr.size % num_components != 0:
                raise ValueError(
                    f"Data length {arr.size} is not divisible by num_components {num_components}."
                )
            return arr.reshape(-1, num_components)

        # 2D or higher-dimensional array
        if arr.shape[-1] != num_components:
            raise ValueError(
                f"Data last dimension {arr.shape[-1]} does not match num_components {num_components}."
            )
        return arr.reshape(-1, num_components)
