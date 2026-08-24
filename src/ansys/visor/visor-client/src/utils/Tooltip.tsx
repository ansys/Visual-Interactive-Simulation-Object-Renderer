/**
 * A unique property key used to mark elements that already have a tooltip.
 *
 * The randomized key prevents collisions with other properties attached to
 * the target element.
 */
const skipKey = `_${crypto.randomUUID()}`;

/**
 * Adds a tooltip to an HTML element.
 *
 * The tooltip is displayed when the target is hovered or focused and hidden
 * when the pointer leaves the target or the target loses focus. Calling this
 * function more than once for the same element has no additional effect.
 *
 * @param target - The HTML element to which the tooltip will be attached.
 * @param text - The text displayed inside the tooltip.
 * @returns A cleanup function that removes the tooltip event listeners.
 *
 * @example
 * ```ts
 * const button = document.querySelector<HTMLButtonElement>('#save');
 *
 * if (button) {
 *     const disposeTooltip = makeTooltip(button, 'Save changes');
 *
 *     // Remove the tooltip listeners when they are no longer needed.
 *     disposeTooltip();
 * }
 * ```
 */
export function makeTooltip(target: HTMLElement, text: string): () => void {
    if ((target as any)[skipKey] === true) {
        // if the tooltip has already been added, return early
        return () => undefined;
    }

    (target as any)[skipKey] = true;

    const tip = document.createElement('div');
    tip.className = 'visor-tooltip';
    tip.textContent = text;
    tip.classList.add('theme-background-1');

    // Inline minimal styling to avoid depending on CSS files
    const style = tip.style;
    style.position = 'absolute';
    style.padding = '6px 8px';
    style.borderWidth = '1px';
    style.borderRadius = '4px';
    style.fontSize = '12px';
    style.pointerEvents = 'none';
    style.transform = 'translateY(-8px)';
    style.transition = 'opacity 0.12s ease, transform 0.12s ease';
    style.opacity = '0';
    style.zIndex = '10000';
    style.whiteSpace = 'nowrap';

    document.body.appendChild(tip);

    /**
     * Positions and displays the tooltip.
     *
     * @param e - The mouse-enter or focus event that triggered the tooltip.
     */
    const onEnter = (e: Event): void => {
        const r = target.getBoundingClientRect();
        const left = Math.round(r.left + r.width / 2 - tip.offsetWidth / 2);
        const top = Math.round(r.top - tip.offsetHeight - 8);

        tip.style.left = `${Math.max(8, left)}px`;
        tip.style.top = `${Math.max(8, top)}px`;
        tip.style.opacity = '1';
        tip.style.transform = 'translateY(0px)';
    };

    /**
     * Hides the tooltip.
     *
     * @param e - The mouse-leave or blur event that triggered the tooltip.
     */
    const onLeave = (e: Event): void => {
        tip.style.opacity = '0';
        tip.style.transform = 'translateY(-8px)';
    };

    target.addEventListener('mouseenter', onEnter);
    target.addEventListener('focus', onEnter);
    target.addEventListener('mouseleave', onLeave);
    target.addEventListener('blur', onLeave);

    return () => {
        target.removeEventListener('mouseenter', onEnter);
        target.removeEventListener('focus', onEnter);
        target.removeEventListener('mouseleave', onLeave);
        target.removeEventListener('blur', onLeave);
    };
}
