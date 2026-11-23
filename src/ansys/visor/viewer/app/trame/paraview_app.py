"""
ParaviewApp
===========
:class:`ServerApp` for a scene rendered by pvserver: the same triggers and
streamed view, reporting the PARAVIEW rendering mode.

Not decorated again: ``ServerApp``'s decoration already registers every
trigger this class inherits, and a second decoration would register each one
twice.
"""

from __future__ import annotations

from ansys.visor.viewer.app.trame.server_app import ServerApp
from ansys.visor.viewer.core.visor_enums import RenderingMode


class ParaviewApp(ServerApp):
    """ServerApp that reports RenderingMode.PARAVIEW."""

    @property
    def rendering_mode(self) -> RenderingMode:
        """RenderingMode.PARAVIEW."""
        return RenderingMode.PARAVIEW
