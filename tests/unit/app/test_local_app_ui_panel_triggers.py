"""Unit tests for LocalApp's four UI panel triggers.

A module of its own rather than an addition to
``test_local_app_widget_triggers.py``: that module's tests are written
against a single ``visible`` boolean shared by all three widget toggles,
and its registration test names those three.  These four are neither
toggles nor uniform -- three carry ``collapsed`` and the fourth carries
``tabIndex``, an ``int`` behind a camelCase alias.

Coverage targets
----------------
1.  Each of the four triggers delegates the value it arrived with, exactly
    once, to the identically-named coordinator method.  Four tests and not
    one: a wrong trigger name and a delegation to the wrong coordinator
    method are distinct failures that a single test could not tell apart.
2.  A payload missing ``tabIndex`` is a logged no-op: nothing is delegated.

What is deliberately **not** re-tested here.  ``@parse_payload`` is one
shared decorator, already pinned four times over in
``test_local_app_widget_triggers.py``; a second, third and fourth
malformed-payload case here would restate it.  The "no coordinator
injected" path and the "trigger names are registered after decoration"
case are likewise already pinned in that module, against the same
``_mutation_api`` helper and the same registration loop these four
handlers use unchanged.

Every payload here is a hand-written literal.  ``tabIndex`` is written in
its wire spelling, so a model that lost the alias fails here rather than
passing on a snake_case key the client never sends.
"""

from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.app.trame.local_app import LocalApp

# Hand-written literals, each the opposite of the server's own initial value
# (``False`` for the three collapse flags, ``0`` for the tab index), so a
# handler that delegated a default rather than its payload would fail.
COLLAPSED = True
TAB_INDEX = 1


class MockController:
    """Minimal trame controller stand-in that records added handlers."""

    def __init__(self):
        self.handlers = {}
        self.add_call_count = 0

    def add(self, event):
        self.add_call_count += 1

        def decorator(fn):
            self.handlers[event] = fn
            return fn

        return decorator


@pytest.fixture
def mock_server():
    """Provide a mock Trame server."""
    server = MagicMock()
    server.controller = MockController()
    server.http_headers.set_header = MagicMock()
    server.name = "TestServer"
    server._www = None
    return server


@pytest.fixture
def api():
    """Stand-in for the injected scene coordinator."""
    return MagicMock(name="scene_mutation_api")


@pytest.fixture
def app(mock_server, api):
    """LocalApp with a coordinator injected."""
    return LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        handle_save_state_response=MagicMock(),
        standalone=True,
        scene_mutation_api=api,
    )


# ===========================================================================
# Delegation
# ===========================================================================

def test_set_panel_top_left_panel_collapsed_delegates_the_collapsed_value(app, api):
    """The top-left panel trigger hands the coordinator the value it received."""
    result = app.set_panel_top_left_panel_collapsed({"collapsed": COLLAPSED})

    assert result is None
    api.set_panel_top_left_panel_collapsed.assert_called_once_with(True)


def test_set_panel_top_right_panel_collapsed_delegates_the_collapsed_value(app, api):
    """The top-right panel trigger hands the coordinator the value it received."""
    result = app.set_panel_top_right_panel_collapsed({"collapsed": COLLAPSED})

    assert result is None
    api.set_panel_top_right_panel_collapsed.assert_called_once_with(True)


def test_set_panel_top_right_legend_collapsed_delegates_the_collapsed_value(app, api):
    """The legend trigger hands the coordinator the value it received."""
    result = app.set_panel_top_right_legend_collapsed({"collapsed": COLLAPSED})

    assert result is None
    api.set_panel_top_right_legend_collapsed.assert_called_once_with(True)


def test_set_panel_top_right_tab_index_delegates_the_tab_index(app, api):
    """The tab trigger hands the coordinator the index it received.

    The payload key is the wire spelling ``tabIndex``; the coordinator is
    called with the snake_case value, which is what the alias is for.
    """
    result = app.set_panel_top_right_tab_index({"tabIndex": TAB_INDEX})

    assert result is None
    api.set_panel_top_right_tab_index.assert_called_once_with(1)


# ===========================================================================
# Validation -- a malformed payload reaches no handler body
# ===========================================================================

def test_set_panel_top_right_tab_index_missing_tab_index_is_a_logged_no_op(app, api):
    """An empty payload never reaches the handler body.

    Asserted against the whole mock, so a leak under any other method name
    still fails.  One such test for the four triggers rather than four: they
    share one decorator, and reverting ``@parse_payload`` on this one is the
    case this test exists to report.
    """
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app.set_panel_top_right_tab_index({})

    assert result is None
    assert api.mock_calls == []
    assert log.warning.call_count == 1


