# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

"""
UI selector strategy for Visor frontend Playwright tests.

1. Structural selectors (CSS class + :has() for panel identity)
2. Role/input type selectors
3. page.evaluate() for complex DOM queries

Since the frontend uses fully randomized numeric IDs, this module provides stable
locator factories based on classes and element structure that tests should use
instead of raw selectors.
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page

# ---------------------------------------------------------------------------
# 1. Structural selectors (panel containers)
# ---------------------------------------------------------------------------

def tree_panel(page: Page) -> Locator:
    """Top-left panel containing the scene tree."""
    return page.locator('.theme-panel-1:has(.visor-tree-view)')


def properties_panel(page: Page) -> Locator:
    """Top-right panel containing properties/legend."""
    return page.locator('.theme-panel-1:has(input[type="color"])')


def canvas_container(page: Page) -> Locator:
    """VTK canvas container."""
    return page.locator('.visor-viewer-background')


def bottom_panel(page: Page) -> Locator:
    """Bottom-middle panel (table/info)."""
    return page.locator('[id^="tableElem-"]').locator('..')


# ---------------------------------------------------------------------------
# 2. Structural selectors (CSS class + context)
# ---------------------------------------------------------------------------

def tree_root(page: Page) -> Locator:
    """Root tree view container (.visor-tree-view)."""
    return tree_panel(page).locator(".visor-tree-view")


def tree_node_by_name(page: Page, name: str) -> Locator:
    """Locate a tree node row by its text content."""
    return tree_root(page).locator(f"table:has-text('{name}')")


def selected_tree_node(page: Page) -> Locator:
    """Currently selected tree row (highlighted)."""
    return tree_root(page).locator("table.theme-selected-background")


# ---------------------------------------------------------------------------
# 3. Role/input type selectors within panels
# ---------------------------------------------------------------------------

def opacity_slider(page: Page) -> Locator:
    """Opacity range input in the properties panel."""
    return properties_panel(page).locator('input[type="range"]')


def opacity_text_input(page: Page) -> Locator:
    """Opacity text input in the properties panel."""
    return properties_panel(page).locator('input[type="text"]').first


def color_picker(page: Page) -> Locator:
    """Native color picker input in the properties panel."""
    return properties_panel(page).locator('input[type="color"]')


# ---------------------------------------------------------------------------
# 4. page.evaluate() helpers
# ---------------------------------------------------------------------------

def get_tree_node_names(page: Page) -> list[str]:
    """Extract all tree node names via JS."""
    return page.evaluate("""
        () => {
            const treeView = document.querySelector('.visor-tree-view');
            if (!treeView) return [];
            const tables = treeView.querySelectorAll('table');
            return Array.from(tables).map(t => t.textContent.trim()).filter(Boolean);
        }
    """)


def get_opacity_value(page: Page) -> float:
    """Get current opacity value (0-1 scale) from the slider."""
    val = page.evaluate("""
        () => {
            const panel = document.querySelector('.theme-panel-1:has(input[type="color"])');
            if (!panel) return null;
            const range = panel.querySelector('input[type="range"]');
            return range ? parseInt(range.value) / 100.0 : null;
        }
    """)
    return float(val) if val is not None else 1.0


def get_color_value(page: Page) -> str:
    """Get current color picker hex value."""
    return page.evaluate("""
        () => {
            const panel = document.querySelector('.theme-panel-1:has(input[type="color"])');
            if (!panel) return '#000000';
            const input = panel.querySelector('input[type="color"]');
            return input ? input.value : '#000000';
        }
    """)


def get_visor_viewer_background(page: Page) -> str | None:
    """Extract --visor-viewer-background CSS variable value from #__visorThemeStyle."""
    return page.evaluate("""
        () => {
            const style = document.getElementById('__visorThemeStyle');
            if (!style) return null;
            const match = style.textContent.match(/--visor-viewer-background:\\s*([^;]+)/);
            return match ? match[1].trim() : null;
        }
    """)


def get_container_aspect_ratio(page: Page) -> str | None:
    """Extract aspect-ratio style value from the Visor App root container.

    """
    return page.evaluate("""
        () => {
            const canvas = document.querySelector('.visor-viewer-background');
            if (!canvas) return null;
            const scaffold = canvas.parentElement;
            if (!scaffold) return null;
            const appRoot = scaffold.parentElement;
            return appRoot ? (appRoot.style.aspectRatio || null) : null;
        }
    """)


def _parse_scale_from_transform(raw: str) -> float | None:
    """Parse the scale value from an inline CSS transform string.

    Visor's setScale() always writes ``scale(x, y)`` to inline style.
    """
    import re

    if not raw or raw == "none":
        return None

    m = re.search(r"scale(?:3d)?\(\s*([-+]?\d*\.?\d+)", raw, re.I)
    return float(m[1]) if m else None


def get_ui_panel_scale(page: Page) -> float | None:
    """Extract UI transform scale from the top-left panel's scaled wrapper.

    """
    transform = page.evaluate("""
        () => {
            const panel = document.querySelector('.theme-panel-1:has(.visor-tree-view)');
            if (!panel || !panel.parentElement) return null;
            const wrapper = panel.parentElement;
            return wrapper.style.transform || getComputedStyle(wrapper).transform || null;
        }
    """)
    return _parse_scale_from_transform(transform) if transform else None
