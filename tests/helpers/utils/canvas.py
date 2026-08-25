# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

"""
Playwright canvas helpers for e2e and smoke tests.

Provides reusable functions for:
  - Navigating to the Visor viewer and waiting for network idle
  - Waiting for a WebGL canvas to become alive (non-zero drawing buffer)
  - Asserting that the canvas remains alive at labeled checkpoints

"""

from __future__ import annotations

from playwright.sync_api import Page

# Default canvas CSS selector — matches the VTK WASM canvas used by Visor
DEFAULT_CANVAS_SELECTOR = "canvas.vtk-wasm-1"


def goto_and_wait(page: Page, url: str, *, wait_until: str = "networkidle") -> None:
    """Navigate to *url* and wait for the page to settle.

    Parameters
    ----------
    page : Page
        Playwright page instance.
    url : str
        Target URL (e.g. ``http://localhost:8081/index.html``).
    wait_until : str
        Playwright wait strategy (default ``"networkidle"``).
    """
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(url, wait_until=wait_until)


def wait_for_canvas(
    page: Page,
    *,
    selector: str = DEFAULT_CANVAS_SELECTOR,
    attached_timeout: int = 300_000,
    visible_timeout: int = 15_000,
):
    """Wait until the canvas element is attached and visible.

    Returns the Playwright Locator for the canvas.
    """
    canvas = page.locator(selector)
    canvas.wait_for(state="attached", timeout=attached_timeout)
    canvas.wait_for(state="visible", timeout=visible_timeout)
    return canvas


_WEBGL_ALIVE_JS = """
() => {
  const c = document.querySelector('canvas.vtk-wasm-1');
  if (!c) return false;
  const gl = c.getContext('webgl2') || c.getContext('webgl');
  if (!gl) return false;
  return gl.drawingBufferWidth > 0 && gl.drawingBufferHeight > 0;
}
"""


def wait_for_webgl(page: Page, *, timeout_ms: int = 10_000) -> None:
    """Block until the WebGL context on the canvas has a non-zero drawing buffer.

    Raises TimeoutError if the condition isn't met within *timeout_ms*.
    """
    page.wait_for_function(_WEBGL_ALIVE_JS, timeout=timeout_ms)


def assert_canvas_alive(page: Page, label: str, *, timeout_ms: int = 5_000) -> None:
    """Assert the canvas is present, visible, and has a valid WebGL context.

    Parameters
    ----------
    page : Page
        Playwright page instance.
    label : str
        Human-readable checkpoint name used in error messages.
    timeout_ms : int
        Maximum wait time in milliseconds.

    Raises
    ------
    AssertionError
        If the canvas/WebGL context is not alive within the timeout.
    """
    try:
        wait_for_webgl(page, timeout_ms=timeout_ms)
    except Exception as exc:
        # page.wait_for_function raises its own TimeoutError on failure, so this
        # is the only path that ever produces the labeled message below.
        raise AssertionError(f"[{label}] Canvas/WebGL not alive") from exc


def wait_for_canvas_alive(page: Page, label: str = "", *, timeout_ms: int = 15_000):
    """Wait until the canvas is visible and WebGL is alive; return the canvas locator.

    Unlike `assert_canvas_alive`, this also waits for the canvas to become
    visible first, so it's suited to initial page loads rather than post-interaction checks.
    """
    step = f" [{label}]" if label else ""
    try:
        canvas = wait_for_canvas(page, visible_timeout=timeout_ms)
    except Exception as exc:
        raise exc.__class__(f"Canvas not visible{step}") from exc

    try:
        wait_for_webgl(page, timeout_ms=timeout_ms)
    except Exception as exc:
        raise exc.__class__(f"Canvas WebGL not ready{step}") from exc

    return canvas


def settle(page: Page, ms: int = 200) -> None:
    """Small pause to allow rendering to settle after an interaction."""
    page.wait_for_timeout(ms)
