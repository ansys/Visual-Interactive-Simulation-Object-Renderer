# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.
"""
Unit tests for the two new features added to visordash.init_endpoints():

1.  DashProxy compatibility  – any object with a `server` Flask attribute
    should be accepted, not just plain ``dash.Dash`` instances.

2.  Prefix-aware asset routing – when ``base_path="/my-prefix"`` is passed,
    every asset endpoint must be reachable under that prefix, and the built
    CSS bundle must have its internal ``url("/fonts/…")`` references rewritten
    to ``url("/my-prefix/fonts/…")``.

The tests use Flask's built-in test client so no real browser or Visor server
is required.
"""

import re

import pytest
from dash import Dash
from flask import Flask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeDashProxy:
    """Minimal stand-in for dash_extensions.enrich.DashProxy.

    It only needs a ``.server`` attribute (a Flask app) to satisfy the new
    duck-typing check in init_endpoints().
    """

    def __init__(self):
        self.server = Flask(__name__ + "_fake_proxy")

    def route(self, *args, **kwargs):
        """Delegate route registration to the underlying Flask app."""
        return self.server.route(*args, **kwargs)


def _make_dash_app(name: str = __name__) -> Dash:
    """Return a plain Dash app with a unique name and a minimal layout."""
    from dash import html
    app = Dash(name)
    app.layout = html.Div()   # Dash requires a layout before it will serve any route
    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_endpoints_flag():
    """Each test gets a clean slate: reset the class-level flag on Visordash."""
    from visordash import Visordash
    Visordash.endpoints_set = False
    yield
    Visordash.endpoints_set = False


# ---------------------------------------------------------------------------
# 1.  DashProxy compatibility
# ---------------------------------------------------------------------------

class TestDashProxyCompatibility:

    def test_plain_dash_is_accepted(self):
        """init_endpoints should still work with a plain Dash instance."""
        from visordash import init_endpoints
        app = _make_dash_app("plain_dash_test")
        # Should not raise
        init_endpoints(app)

    def test_dashproxy_lookalike_is_accepted(self):
        """Any object with a `.server` Flask attribute must be accepted."""
        from visordash import init_endpoints
        proxy = _FakeDashProxy()
        # Should not raise
        init_endpoints(proxy)

    def test_invalid_object_raises(self):
        """An arbitrary object without a `.server` attribute must raise."""
        from visordash import init_endpoints

        class NotADash:
            pass

        with pytest.raises(Exception, match="dash_app must be"):
            init_endpoints(NotADash())

    def test_calling_init_endpoints_twice_raises(self):
        """Calling init_endpoints a second time should raise."""
        from visordash import init_endpoints
        app = _make_dash_app("double_init_test")
        init_endpoints(app)
        with pytest.raises(Exception, match="already been set"):
            init_endpoints(app)


# ---------------------------------------------------------------------------
# 2.  Prefix-aware asset routing – route registration
# ---------------------------------------------------------------------------

class TestPrefixRouteRegistration:
    """Verify that the Flask routes are registered under the given prefix."""

    ASSETS = [
        "/visordash/js.js",
        "/visordash/css.css",
        "/css/theme-dark.css",
        "/css/theme-light.css",
        "/fonts/source-sans-3.woff2",
    ]

    def _registered_routes(self, flask_app: Flask) -> set:
        return {rule.rule for rule in flask_app.url_map.iter_rules()}

    def test_no_prefix_registers_default_routes(self):
        """With base_path='', routes must match the original absolute paths."""
        from visordash import init_endpoints
        app = _make_dash_app("no_prefix_test")
        init_endpoints(app)
        routes = self._registered_routes(app.server)
        for asset in self.ASSETS:
            assert asset in routes, f"Expected route '{asset}' not found"

    def test_prefix_routes_are_registered(self):
        """With base_path='/pfx', every asset route must start with /pfx."""
        from visordash import Visordash, init_endpoints
        Visordash.endpoints_set = False
        app = _make_dash_app("prefix_test")
        init_endpoints(app, base_path="/pfx")
        routes = self._registered_routes(app.server)
        for asset in self.ASSETS:
            expected = "/pfx" + asset
            assert expected in routes, f"Expected route '{expected}' not found"

    def test_prefix_routes_do_not_include_unprefixed(self):
        """With a prefix set, the un-prefixed routes must NOT be registered."""
        from visordash import Visordash, init_endpoints
        Visordash.endpoints_set = False
        app = _make_dash_app("no_unprefixed_test")
        init_endpoints(app, base_path="/pfx")
        routes = self._registered_routes(app.server)
        for asset in self.ASSETS:
            assert asset not in routes, (
                f"Un-prefixed route '{asset}' should not exist when base_path is set"
            )

    def test_trailing_slash_in_base_path_is_normalised(self):
        """Trailing slash on base_path must be stripped gracefully."""
        from visordash import Visordash, init_endpoints
        Visordash.endpoints_set = False
        app = _make_dash_app("trailing_slash_test")
        # Should not raise and should register /pfx/visordash/js.js (not //pfx/…)
        init_endpoints(app, base_path="/pfx/")
        routes = self._registered_routes(app.server)
        assert "/pfx/visordash/js.js" in routes

    def test_dashproxy_with_prefix_registers_routes(self):
        """DashProxy + base_path must register prefixed routes on its Flask server."""
        from visordash import init_endpoints
        proxy = _FakeDashProxy()
        init_endpoints(proxy, base_path="/my-solution")
        routes = self._registered_routes(proxy.server)
        assert "/my-solution/visordash/js.js" in routes
        assert "/my-solution/visordash/css.css" in routes


# ---------------------------------------------------------------------------
# 3.  CSS font-URL rewriting
# ---------------------------------------------------------------------------

class TestCssFontRewrite:
    """Verify the @font-face url() is rewritten at serve-time."""

    @staticmethod
    def _contains_font_url(css: str, path: str) -> bool:
        # Accept url("...") / url('...') / url(...) with optional whitespace.
        escaped = re.escape(path)
        pattern = rf"url\(\s*(['\"]?){escaped}\1\s*\)"
        return re.search(pattern, css) is not None

    def _get_css(self, app: Dash, base_path: str = "") -> str:
        """Hit the css.css endpoint and return the response body as text."""
        url = f"{base_path}/visordash/css.css"
        with app.server.test_client() as client:
            response = client.get(url)
        assert response.status_code == 200, (
            f"GET {url} returned {response.status_code}"
        )
        return response.data.decode("utf-8")

    def test_no_prefix_css_has_absolute_font_url(self):
        """With no prefix, the CSS must reference /fonts/source-sans-3.woff2."""
        from visordash import init_endpoints
        app = _make_dash_app("css_no_prefix_test")
        init_endpoints(app)
        css = self._get_css(app)
        assert self._contains_font_url(css, "/fonts/source-sans-3.woff2"), (
            "Expected absolute font URL in CSS when no base_path is set"
        )

    def test_prefix_css_rewrites_font_url(self):
        """With base_path=/pfx, the font URL must be /pfx/fonts/source-sans-3.woff2."""
        from visordash import Visordash, init_endpoints
        Visordash.endpoints_set = False
        app = _make_dash_app("css_prefix_test")
        init_endpoints(app, base_path="/pfx")
        css = self._get_css(app, base_path="/pfx")
        assert self._contains_font_url(css, "/pfx/fonts/source-sans-3.woff2"), (
            "Font URL in CSS was not rewritten to include the base_path prefix"
        )
        assert not self._contains_font_url(css, "/fonts/source-sans-3.woff2"), (
            "Old un-prefixed font URL should not appear in CSS when base_path is set"
        )
