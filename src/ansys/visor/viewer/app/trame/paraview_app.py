"""
ParaviewApp
===========
:class:`ServerApp` for a scene rendered by pvserver: the same triggers and
streamed view, reporting the PARAVIEW rendering mode, with every frame
streamed at one quality.

Not decorated again: ``ServerApp``'s decoration already registers every
trigger this class inherits, and a second decoration would register each one
twice.
"""

from __future__ import annotations

from ansys.visor.viewer.app.trame.server_app import ServerApp
from ansys.visor.viewer.core.visor_enums import RenderingMode


class ParaviewApp(ServerApp):
    """ServerApp that reports RenderingMode.PARAVIEW."""

    INTERACTIVE_QUALITY: int = 90
    """Equal to STILL_QUALITY, so an unchanged scene is never rendered through pvserver again to re-encode it."""

    @property
    def rendering_mode(self) -> RenderingMode:
        """RenderingMode.PARAVIEW."""
        return RenderingMode.PARAVIEW
