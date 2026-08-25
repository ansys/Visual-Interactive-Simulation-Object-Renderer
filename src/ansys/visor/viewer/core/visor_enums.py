"""Enums used in the Visor visualizer application.."""


from enum import Enum
from typing import Union


class RenderingEngine(Enum):
    """
    An enumeration representing different rendering engines.

    Attributes:
        VTK (int): Represents the VTK rendering engine.
    """

    VTK = 0

    @classmethod
    def from_string(cls, value: Union[str, "RenderingEngine"]) -> "RenderingEngine":
        """
        Accept an enum member or a case-insensitive string name.

        Examples
        --------
        >>> RenderingEngine.from_string("vtk")
        <RenderingEngine.VTK: 'vtk'>
        >>> RenderingEngine.from_string("VTK")
        <RenderingEngine.VTK: 'vtk'>
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls[value.upper()]
            except KeyError:
                pass
        valid = [e.name for e in cls]
        raise ValueError(f"Invalid RenderingEngine {value!r}. Valid values: {valid}")


class RenderingMode(Enum):
    """
    How the chosen rendering engine is deployed.

    Attributes:
        LOCAL:    Client-side rendering via VTK-WASM in the browser.
    """
    LOCAL    = "local"

    @classmethod
    def from_string(cls, value: Union[str, "RenderingMode"]) -> "RenderingMode":
        """
        Accept an enum member or a case-insensitive string name.

        Examples
        --------
        >>> RenderingMode.from_string("local")
        <RenderingMode.LOCAL: 'local'>
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls[value.upper()]
            except KeyError:
                pass
        valid = [e.name for e in cls]
        raise ValueError(f"Invalid RenderingMode {value!r}. Valid values: {valid}")


class VisorNodeType(Enum):
    """
    An enumeration of the different types of nodes in the Visor scene graph.
    """
    ROOT = "root"
    GROUP = "group"
    PART = "part"

class VisorVtkVariableType(Enum):
    """
    An enumeration of the different types of VTK variables.
    """
    POINT = "POINT"
    CELL = "CELL"
