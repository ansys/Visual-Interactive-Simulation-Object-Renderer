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
    simple.Connect = lambda **kwargs: connection
    simple.CreateView = lambda name: simple.view
    simple.CreateLookupTable = lambda: SimpleNamespace()
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


def _session(monkeypatch):
    simple = _install_fake_simple(monkeypatch, connection=object())
    return simple, PvSimpleSession(PvserverAddress(host="localhost", port=11111))


def test_block_point_count_reads_the_blocks_hierarchy_subset(monkeypatch):
    _, session = _session(monkeypatch)
    calls = []

    def subset(port, selector, assembly):
        calls.append((port, selector, assembly))
        return SimpleNamespace(GetNumberOfPoints=lambda: 88)

    source = SimpleNamespace(SMProxy=SimpleNamespace(GetSubsetDataInformation=subset))

    assert (session.block_point_count(source, "/Root/body/rib"), calls) == (88, [(0, "/Root/body/rib", "Hierarchy")])


@pytest.mark.parametrize(
    ("component", "expected"),
    [(-1, {"AutomaticRescaleRangeMode": "Never", "VectorMode": "Magnitude"}),
     (1, {"AutomaticRescaleRangeMode": "Never", "VectorMode": "Component", "VectorComponent": 1})],
)
def test_new_color_map_maps_the_component_and_never_rescales(monkeypatch, component, expected):
    _, session = _session(monkeypatch)

    assert vars(session.new_color_map(component)) == expected


class _FakeSelectionHelper:
    """vtkSMSelectionHelper's two factories, recording the selection each is given."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def NewSelectionSourceFromSelection(self, session, selection):
        node = selection.GetNode(0)
        selectors = [node.GetSelectionList().GetValue(i) for i in range(node.GetSelectionList().GetNumberOfValues())]
        self.calls.append(("source", session, node.GetContentType(), node.GetFieldType(), selectors))
        return _Unregistering(self.calls, "selection-proxy")

    def NewAppendSelectionsFromSelectionSource(self, selection_proxy):
        self.calls.append(("append", selection_proxy.name))
        return _Unregistering(self.calls, "append-proxy")


class _Unregistering:
    def __init__(self, calls: list[tuple], name: str) -> None:
        self.calls = calls
        self.name = name

    def UnRegister(self, owner) -> None:
        self.calls.append(("unregister", self.name))


def _selection_source(calls: list[tuple]):
    proxy = SimpleNamespace(SetSelectionInput=lambda port, append, out: calls.append(("input", port, append, out)))
    return SimpleNamespace(SMProxy=proxy, GetSession=lambda: "pv-session")


def test_set_selected_blocks_writes_every_block_in_one_selection_and_never_renders(monkeypatch):
    from vtkmodules.vtkCommonDataModel import vtkSelectionNode

    simple, session = _session(monkeypatch)
    helper = _FakeSelectionHelper()
    monkeypatch.setitem(sys.modules, "paraview.modules", types.ModuleType("paraview.modules"))
    views = types.ModuleType("paraview.modules.vtkRemotingViews")
    views.vtkSMSelectionHelper = helper
    monkeypatch.setitem(sys.modules, "paraview.modules.vtkRemotingViews", views)
    pv_vtk = types.ModuleType("paraview.vtk")
    pv_vtk.vtkSelectionNode = vtkSelectionNode
    monkeypatch.setitem(sys.modules, "paraview.vtk", pv_vtk)
    simple.Render = lambda *args: helper.calls.append(("render",))
    source = _selection_source(helper.calls)

    session.set_selected_blocks(source, ["/Root/body/rib", "/Root/wing"])

    # 8 is BLOCK_SELECTORS; 0 is CELL, which extracts a block's faces where POINT extracts only its vertices.
    assert [(c[0], c[2].name) if c[0] == "input" else c for c in helper.calls] == [
        ("source", "pv-session", 8, 0, ["/Root/body/rib", "/Root/wing"]),
        ("append", "selection-proxy"),
        ("input", "append-proxy"),
        ("unregister", "append-proxy"),
        ("unregister", "selection-proxy"),
    ]


def test_set_selected_blocks_with_no_blocks_clears_the_selection(monkeypatch):
    _, session = _session(monkeypatch)
    calls: list[tuple] = []

    session.set_selected_blocks(_selection_source(calls), [])

    assert calls == [("input", 0, None, 0)]
