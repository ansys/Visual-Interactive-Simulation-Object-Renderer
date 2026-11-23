"""
ParaviewCapture
===============
trame-rca capture over a ParaView view's client-side render window.

The base area renders the raw window before each capture.  Rendering through
the session instead renders the view proxy, so pvserver renders and
composites the frame the window then holds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trame_rca.rca import VtkRemoteControlledArea

if TYPE_CHECKING:
    from ansys.visor.viewer.renderer.paraview_session import ParaviewSession


class ParaviewCapture(VtkRemoteControlledArea):
    """trame-rca area over the view's client-side render window that renders through ParaView."""

    def __init__(self, session: ParaviewSession) -> None:
        """Capture session.render_window."""
        super().__init__(session.render_window)
        self._session = session

    def _render(self) -> None:
        """Render the view through the session, so pvserver renders and composites the frame."""
        with self._timer_render:
            self._session.render()
