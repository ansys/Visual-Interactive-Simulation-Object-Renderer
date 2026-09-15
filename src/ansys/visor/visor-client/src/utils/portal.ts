/**
 * Helpers to resolve a scoped portal root for UI elements that would
 * otherwise be appended to `document.body` (tooltips, popups, invisible
 * DOM containers used by wasm). Prefer an element with the
 * `.visor-embed-style` class (added by host integrations), then fall back
 * to the client container id `VisorContainer`, and finally to `document.body`.
 */
export function getPortalRoot(): HTMLElement {
    const doc = typeof document !== 'undefined' ? document : null;
    if (!doc) {
        // Non-browser environment (SSR). Return a harmless stub to avoid
        // throwing in places that call this helper during static analysis.
        // Callers should guard when used outside the browser.
        return {} as HTMLElement;
    }

    // Prefer an explicit Visor embed root when present, then fall back to
    // legacy container ids for compatibility. If no suitable container is
    // present, create a dedicated portal root under document.body so callers
    // don't have to append directly to body.
    const el = doc.querySelector('.visor-embed-style') || doc.getElementById('VisorContainer');
    if (el) return el as HTMLElement;

    let portalRoot = doc.getElementById('visor-portal-root') as HTMLElement | null;
    if (!portalRoot) {
        portalRoot = doc.createElement('div');
        portalRoot.id = 'visor-portal-root';
        portalRoot.setAttribute('data-visor-portal', '1');
        doc.body.appendChild(portalRoot);
    }

    return portalRoot;
}

export function appendToPortal(el: HTMLElement): void {
    getPortalRoot().appendChild(el);
}

export function removeFromPortal(el: HTMLElement): void {
    if (el && el.parentElement) {
        el.parentElement.removeChild(el);
    }
}
