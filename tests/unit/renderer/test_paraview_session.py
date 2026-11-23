"""
Unit tests for PvSimpleSession.

A fake ``paraview.simple`` module is placed in ``sys.modules``, so the
session's constructor-time import finds it and no ParaView is needed.
Expected values are hand-written literals.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ansys.visor.viewer.core.errors import PvserverConnectionError
from ansys.visor.viewer.core.pvserver_address import PvserverAddress
from ansys.visor.viewer.renderer.paraview_session import PvSimpleSession


class _FakeWindow:
    """A client-side render window that records its offscreen flag."""

    def __init__(self) -> None:
        self.offscreen = 0

    def SetOffScreenRendering(self, value: int) -> None: # noqa: N802
        self.offscreen = value


class _FakeView:
    """A render view whose attributes record writes, with a client-side window."""

    def __init__(self) -> None:
        self.RemoteRenderThreshold = 20.0
        self.window = _FakeWindow()

    def GetClientSideObject(self): # noqa: N802
        return SimpleNamespace(GetRenderWindow=lambda: self.window)


def _install_fake_simple(monkeypatch, connection: object | None) -> types.ModuleType:
    """Put a fake paraview.simple in sys.modules; Connect returns connection."""
    simple = types.ModuleType("paraview.simple")
    simple.view = _FakeView()
    simple.color_by_calls = []
    simple.Connect = lambda **kwargs: connection
    simple.CreateView = lambda name: simple.view
    simple.ColorBy = lambda rep, value, separate=False: simple.color_by_calls.append((rep, value, separate))
    paraview = types.ModuleType("paraview")
    paraview.simple = simple
    monkeypatch.setitem(sys.modules, "paraview", paraview)
    monkeypatch.setitem(sys.modules, "paraview.simple", simple)
    return simple


def test_init_writes_remote_render_threshold_zero_and_logs_it(monkeypatch):
    simple = _install_fake_simple(monkeypatch, connection=object())

    with patch("ansys.visor.viewer.renderer.paraview_session.logger") as log:
        PvSimpleSession(PvserverAddress(host="localhost", port=11111))

    assert simple.view.RemoteRenderThreshold == 0.0
    fmt, *args = log.info.call_args.args
    assert fmt % tuple(args) == "RemoteRenderThreshold set to 0.0"


def test_init_draws_the_client_side_window_offscreen(monkeypatch):
    simple = _install_fake_simple(monkeypatch, connection=object())

    session = PvSimpleSession(PvserverAddress(host="localhost", port=11111))

    assert session.render_window is simple.view.window
    assert simple.view.window.offscreen == 1


def test_init_raises_naming_the_address_when_connect_returns_none(monkeypatch):
    _install_fake_simple(monkeypatch, connection=None)

    with pytest.raises(PvserverConnectionError, match="localhost:11111"):
        PvSimpleSession(PvserverAddress(host="localhost", port=11111))


def test_color_by_requests_a_separate_color_map(monkeypatch):
    simple = _install_fake_simple(monkeypatch, connection=object())
    session = PvSimpleSession(PvserverAddress(host="localhost", port=11111))
    rep = SimpleNamespace()

    session.color_by(rep, "POINTS", "velocity", "Magnitude")

    assert simple.color_by_calls == [(rep, ("POINTS", "velocity", "Magnitude"), True)]
