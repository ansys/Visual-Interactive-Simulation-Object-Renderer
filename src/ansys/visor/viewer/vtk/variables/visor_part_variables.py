"""VisorPartVariables: per-part variable listing returned by list_variables."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ansys.visor.viewer.vtk.variables.visor_variables import VisorVariable


@dataclass(frozen=True)
class VisorPartVariables:
    """
    Variables for a single part of a dataset.

    Attributes
    ----------
    part_id : int
        Stable runtime part ID (from PartIndex).  Pass this back to
        ``update_variables`` to target this specific part.
    part_name : str
        Human-readable block / part name.
    variables : List[VisorVariable]
        All point and cell variables available on this part.
    """
    part_id: int
    part_name: str
    variables: List[VisorVariable]

    def to_dict(self) -> dict:
        return {
            "part_id": self.part_id,
            "part_name": self.part_name,
            "variables": [v.to_dict() for v in self.variables],
        }

