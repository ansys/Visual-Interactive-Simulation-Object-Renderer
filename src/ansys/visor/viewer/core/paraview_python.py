# Copyright 2026 ANSYS, Inc. All Rights Reserved.
# Restricted Rights Legend: See LICENSE for details.
"""The Python version PARAVIEW mode runs on.

PARAVIEW mode runs Visor inside ``pvpython``, so it runs on the Python that
ParaView embeds, not the API's.  Standard library only, so this imports on
every supported Python.
"""

PARAVIEW_VERSION: str = "6.2"
"""The ParaView release PARAVIEW mode targets."""

PARAVIEW_PYTHON_VERSION: tuple[int, int] = (3, 12)
"""Major and minor version of the Python that ParaView ``PARAVIEW_VERSION``'s pvpython embeds."""
