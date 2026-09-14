/**
 * Helpers to resolve a scoped portal root for UI elements that would
 * otherwise be appended to `document.body` (tooltips, popups, invisible
 * DOM containers used by wasm).  Prefer an element with the
 * `.visor-embed-style` class (added by host integrations), then fall back
 * to the client container id `TheiaContainer` for compatibility, then to
 * `VisorContainer`, and finally to `document.body`.
 */
export function getPortalRoot(): HTMLElement {
    const el =
        document.querySelector('.visor-embed-style') ||
        document.getElementById('TheiaContainer') ||
        document.getElementById('VisorContainer') ||
        document.body;
    return el as HTMLElement;
}

export function appendToPortal(el: HTMLElement): void {
    getPortalRoot().appendChild(el);
}

export function removeFromPortal(el: HTMLElement): void {
    if (el && el.parentElement) {
        el.parentElement.removeChild(el);
    }
}
