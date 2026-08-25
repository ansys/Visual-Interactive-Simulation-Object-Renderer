# Copyright 2025 ANSYS, Inc. All Rights Reserved.
# Restricted Rights Legend: See LICENSE for details.
# ruff: noqa: F405

from __future__ import print_function as _

import json
import os
import sys

import dash as _dash
from typing_extensions import Buffer

# noinspection PyUnresolvedReferences
from ._imports_ import *  # noqa: F403
from ._imports_ import __all__

if not hasattr(_dash, '__plotly_dash') and not hasattr(_dash, 'development'):
    print('Dash was not successfully imported. '
          'Make sure you don\'t have a file '
          'named \n"dash.py" in your current directory.', file=sys.stderr)
    sys.exit(1)

_basepath = os.path.dirname(__file__)
_filepath = os.path.abspath(os.path.join(_basepath, 'package-info.json'))
with open(_filepath) as f:
    package = json.load(f)

package_name = package['name'].replace(' ', '_').replace('-', '_')
__version__ = package['version']

_current_path = os.path.dirname(os.path.abspath(__file__))

_this_module = sys.modules[__name__]

async_resources = []

_js_dist = []

_js_dist.extend(
    [
        {
            "relative_package_path": "async-{}.js".format(async_resource),
            "external_url": (
                "https://unpkg.com/{0}@{2}"
                "/{1}/async-{3}.js"
            ).format(package_name, __name__, __version__, async_resource),
            "namespace": package_name,
            "async": True,
        }
        for async_resource in async_resources
    ]
)

# TODO: Figure out if unpkg link works
_js_dist.extend(
    [
        {
            "relative_package_path": "async-{}.js.map".format(async_resource),
            "external_url": (
                "https://unpkg.com/{0}@{2}"
                "/{1}/async-{3}.js.map"
            ).format(package_name, __name__, __version__, async_resource),
            "namespace": package_name,
            "dynamic": True,
        }
        for async_resource in async_resources
    ]
)

_js_dist.extend(
    [
        {
            'relative_package_path': 'visordash.min.js',

            'namespace': package_name
        },
        {
            'relative_package_path': 'visordash.min.js.map',

            'namespace': package_name,
            'dynamic': True
        }
    ]
)

_css_dist = []

for _component in __all__:
    setattr(locals()[_component], '_js_dist', _js_dist)
    setattr(locals()[_component], '_css_dist', _css_dist)

########################################################################
########################################################################
########################################################################

import base64
import gzip

from dash import Dash
from flask import Response

from .utils import rewrite_css_urls

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

from __GITIGNORE_visor_css import getDarkThemeCss, getLightThemeCss
from __GITIGNORE_visor_font import getFontBase64
from __GITIGNORE_visor_react_assets import getCss, getJs


def init_endpoints(dash_app, base_path: str = "", flask_prefix: str | None = None):
    """
    Register Visordash asset endpoints on the given Dash (or DashProxy) application.

    Parameters
    ----------
    dash_app : Dash or DashProxy
        The Dash application instance.  Any object that exposes a ``server``
        attribute pointing to a Flask application is accepted, which means
        plain ``dash.Dash`` instances *and* ``dash_extensions`` ``DashProxy``
        instances both work.
    base_path : str, optional
        A URL prefix to prepend to every asset route, e.g. ``"/my-prefix"``.
        Must start with ``"/"`` when non-empty and must **not** end with
        ``"/"``.  Default is ``""`` (no prefix).
    flask_prefix : str or None, optional
        Controls the prefix used when registering routes on the Flask
        application. This is useful when the WSGI server or reverse proxy
        strips a mount prefix from ``PATH_INFO`` (for example, Waitress
        started with ``--url-prefix`` or a reverse proxy setting
        ``SCRIPT_NAME``). If ``None`` (the default) the value of
        ``base_path`` is used for Flask route registration, preserving
        backwards compatibility. To register routes without any prefix
        while still emitting asset URLs with ``base_path``, pass the
        empty string ``""`` for ``flask_prefix``.
    """
    if not isinstance(dash_app, Dash) and not hasattr(dash_app, 'server'):
        raise Exception(
            'dash_app must be a Dash instance (or a DashProxy / any object '
            'with a "server" Flask attribute)'
        )
    if hasattr(Visordash, 'endpoints_set') and Visordash.endpoints_set:
        raise Exception('Visordash endpoints have already been set')
    Visordash.endpoints_set = True

    if base_path and not base_path.startswith("/"):
        raise ValueError("base_path must start with '/' when non-empty")

    if flask_prefix is not None and flask_prefix and not flask_prefix.startswith("/"):
        raise ValueError("flask_prefix must start with '/' when non-empty")

    # Normalise base_path: strip trailing slash, keep empty string as-is.
    base_path = base_path.rstrip('/') if base_path else ""

    # Determine the prefix used for registering Flask routes. If not
    # provided, default to base_path for backwards compatibility.
    if flask_prefix is None:
        flask_prefix = base_path
    else:
        # Keep explicit empty string as-is; otherwise normalise trailing slash
        flask_prefix = flask_prefix.rstrip('/') if flask_prefix else ""

    _react_js: str | None = None
    _react_css: str | None = None
    _vtk_webassembly_mjs: str | None = None
    _vtk_webassembly_mjs_async: str | None = None
    _vtk_webassembly_wasm_bytes: bytes | None = None
    _vtk_webassembly_wasm_async_bytes: bytes | None = None
    _theme_dark_css: str | None = None
    _theme_light_css: str | None = None
    _font_bytes: bytes | None = None

    @dash_app.server.route(f'{flask_prefix}/visordash/js.js')
    def react_js():
        nonlocal _react_js
        if _react_js is None:
            _react_js = getJs()
        response = Response(_react_js, content_type='application/javascript')
        response.headers.set('Cache-Control', 'max-age=0')
        return response

    @dash_app.server.route(f'{flask_prefix}/visordash/css.css')
    def react_css():
        nonlocal _react_css
        if _react_css is None:
            raw = getCss()
            # Rewrite absolute asset paths embedded in the CSS bundle so that
            # they respect the configured base_path prefix. Use a helper to
            # keep this route handler concise and readable.
            if base_path:
                raw = rewrite_css_urls(raw, base_path)
            _react_css = raw
        response = Response(_react_css, content_type='text/css')
        response.headers.set('Cache-Control', 'max-age=0')
        return response

    @dash_app.server.route(f'{flask_prefix}/css/theme-dark.css')
    def theme_dark():
        nonlocal _theme_dark_css
        if _theme_dark_css is None:
            _theme_dark_css = getDarkThemeCss()
        response = Response(_theme_dark_css, content_type='text/css')
        response.headers.set('Cache-Control', 'max-age=0')
        return response

    @dash_app.server.route(f'{flask_prefix}/css/theme-light.css')
    def theme_light():
        nonlocal _theme_light_css
        if _theme_light_css is None:
            _theme_light_css = getLightThemeCss()
        response = Response(_theme_light_css, content_type='text/css')
        response.headers.set('Cache-Control', 'max-age=0')
        return response

    # @dash_app.server.route(f'{base_path}/wasm/vtkWebAssembly.mjs')
    # def vtk_webassembly_mjs():
    #     nonlocal _vtk_webassembly_mjs
    #     if _vtk_webassembly_mjs is None:
    #         _vtk_webassembly_mjs = getVtkMjs()
    #     response = Response(_vtk_webassembly_mjs, content_type='application/javascript')
    #     response.headers.set('Cache-Control', 'max-age=0')
    #     return response

    # @dash_app.server.route(f'{base_path}/wasm/vtkWebAssemblyAsync.mjs')
    # def vtk_webassembly_mjs_async():
    #     nonlocal _vtk_webassembly_mjs_async
    #     if _vtk_webassembly_mjs_async is None:
    #         _vtk_webassembly_mjs_async = getVtkAsyncMjs()
    #     response = Response(_vtk_webassembly_mjs_async, content_type='application/javascript')
    #     response.headers.set('Cache-Control', 'max-age=0')
    #     return response

    # @dash_app.server.route(f'{base_path}/wasm/vtkWebAssembly.wasm')
    # def vtk_webassembly_wasm():
    #     nonlocal _vtk_webassembly_wasm_bytes
    #     try:
    #         if _vtk_webassembly_wasm_bytes is None:
    #             zipped_base64_str = getVtkWasmBase64()
    #             zipped_bytes: Buffer | bytes = base64.b64decode(zipped_base64_str)
    #             _vtk_webassembly_wasm_bytes = gzip.decompress(zipped_bytes)
    #     except Exception as e:
    #         print(e)
    #     response = Response(_vtk_webassembly_wasm_bytes, content_type='application/wasm')
    #     response.headers.set('Cache-Control', 'max-age=0')
    #     return response

    # @dash_app.server.route(f'{base_path}/wasm/vtkWebAssemblyAsync.wasm')
    # def vtk_webassembly_wasm_async():
    #     nonlocal _vtk_webassembly_wasm_async_bytes
    #     try:
    #         if _vtk_webassembly_wasm_async_bytes is None:
    #             zipped_base64_str = getVtkAsyncWasmBase64()
    #             zipped_bytes: Buffer | bytes = base64.b64decode(zipped_base64_str)
    #             _vtk_webassembly_wasm_async_bytes = gzip.decompress(zipped_bytes)
    #     except Exception as e:
    #         print(e)
    #     response = Response(_vtk_webassembly_wasm_async_bytes, content_type='application/wasm')
    #     response.headers.set('Cache-Control', 'max-age=0')
    #     return response

    # @dash_app.server.route(f'{base_path}/wasm/<path:filename>')
    # def wasm_assets(filename: str):
    #     nonlocal _vtk_webassembly_mjs, _vtk_webassembly_wasm_bytes
    #     nonlocal _vtk_webassembly_mjs_async, _vtk_webassembly_wasm_async_bytes
    #     # handle known names that are embedded via helper getters
    #     print(f"\n\n\nRequest for wasm asset: {filename}\n\n\n")
    #     if filename.endswith('.mjs'):
    #         # prefer getting bundled mjs content if available
    #         if filename in ('vtkWebAssembly.mjs', 'vtkWebAssemblyAsync.mjs'):
    #             if filename == 'vtkWebAssembly.mjs':
    #                 content = getVtkMjs()
    #                 _vtk_webassembly_mjs = content
    #             else:
    #                 content = getVtkAsyncMjs()
    #                 _vtk_webassembly_mjs_async = content
    #         response = Response(content, content_type='application/javascript')
    #         response.headers.set('Cache-Control', 'max-age=0')
    #         return response
    #     if filename.endswith('.wasm'):
    #         if filename in ('vtkWebAssembly.wasm', 'vtkWebAssemblyAsync.wasm'):
    #             # return decompressed wasm bytes from base64 helpers
    #             if filename == 'vtkWebAssembly.wasm':
    #                 zipped_base64_str = getVtkWasmBase64()
    #             else:
    #                 zipped_base64_str = getVtkAsyncWasmBase64()
    #             zipped_bytes: Buffer | bytes = base64.b64decode(zipped_base64_str)
    #             wasm_bytes = gzip.decompress(zipped_bytes)
    #             if filename == 'vtkWebAssembly.wasm':
    #                 _vtk_webassembly_wasm_bytes = wasm_bytes
    #             else:
    #                 _vtk_webassembly_wasm_async_bytes = wasm_bytes
    #             response = Response(wasm_bytes, content_type='application/wasm')
    #             response.headers.set('Cache-Control', 'max-age=0')
    #             return response
    #     # return Response(status=404)

    @dash_app.server.route(f'{flask_prefix}/fonts/source-sans-3.woff2')
    def font():
        nonlocal _font_bytes
        if _font_bytes is None:
            zipped_base64_str = getFontBase64()
            zipped_bytes: Buffer | bytes = base64.b64decode(zipped_base64_str)
            _font_bytes = gzip.decompress(zipped_bytes)
        response = Response(_font_bytes, content_type='application/font-woff')
        response.headers.set('Cache-Control', 'max-age=0')
        return response


if 1:
    # Run this code in a guaranteed if-statement block so
    # we don't pollute the outer scope with the functions
    # defined here. This is just a 'hacky' way to write an
    # immediately invoked function expression (IIFE) in Python.
    def extra_init():
        endpoints_set = Visordash.endpoints_set if hasattr(Visordash, 'endpoints_set') else False
        if not endpoints_set:
            msg: str = 'init_endpoints(dash_app) must be called first, where'
            raise Exception(f'{msg} dash_app is the current Dash application')


    original_init = Visordash.__init__


    def new_init(self, **kwargs):
        extra_init()
        original_init(self, **kwargs)


    Visordash.__init__ = new_init
