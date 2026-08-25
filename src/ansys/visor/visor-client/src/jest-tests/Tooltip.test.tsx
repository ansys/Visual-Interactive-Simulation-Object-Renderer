/** @jest-environment jsdom */

import { fireEvent } from '@testing-library/react';

let makeTooltip: (target: HTMLElement, text: string) => () => void;

beforeAll(() => {
    // Tooltip.tsx calls crypto.randomUUID() during module initialization.
    // Older jsdom versions may not provide it.
    if (globalThis.crypto == null) {
        Object.defineProperty(globalThis, 'crypto', {
            configurable: true,
            value: {},
        });
    }

    if (typeof globalThis.crypto.randomUUID !== 'function') {
        Object.defineProperty(globalThis.crypto, 'randomUUID', {
            configurable: true,
            value: () => '00000000-0000-4000-8000-000000000000',
        });
    }

    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-expect-error
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    ({ makeTooltip } = require('../utils/Tooltip'));
});

afterEach(() => {
    document.body.innerHTML = '';
    jest.restoreAllMocks();
});

describe('makeTooltip', () => {
    test('creates a tooltip and appends it to the document body', () => {
        const target = createTarget();

        makeTooltip(target, 'Example tooltip');

        const tip = getTooltip();

        expect(tip.parentElement).toBe(document.body);
        expect(tip.textContent).toBe('Example tooltip');
        expect(tip.classList.contains('visor-tooltip')).toBe(true);
        expect(tip.classList.contains('theme-background-1')).toBe(true);
    });

    test('applies the expected inline styles', () => {
        const target = createTarget();

        makeTooltip(target, 'Example tooltip');

        const style = getTooltip().style;

        expect(style.position).toBe('absolute');
        expect(style.padding).toBe('6px 8px');
        expect(style.borderWidth).toBe('1px');
        expect(style.borderRadius).toBe('4px');
        expect(style.fontSize).toBe('12px');
        expect(style.pointerEvents).toBe('none');
        expect(style.transform).toBe('translateY(-8px)');
        expect(style.transition).toBe('opacity 0.12s ease, transform 0.12s ease');
        expect(style.opacity).toBe('0');
        expect(style.zIndex).toBe('10000');
        expect(style.whiteSpace).toBe('nowrap');
    });

    test('uses textContent rather than interpreting text as HTML', () => {
        const target = createTarget();

        makeTooltip(target, '<strong>Tooltip</strong>');

        const tip = getTooltip();

        expect(tip.textContent).toBe('<strong>Tooltip</strong>');
        expect(tip.querySelector('strong')).toBeNull();
    });

    test('shows and positions the tooltip on mouseenter', () => {
        const target = createTarget();

        setTargetBounds(target, {
            left: 100,
            top: 50,
            width: 60,
            height: 30,
        });

        makeTooltip(target, 'Example tooltip');

        const tip = getTooltip();
        setTooltipDimensions(tip, 40, 20);

        fireEvent.mouseEnter(target);

        // left = 100 + 60 / 2 - 40 / 2 = 110
        // top = 50 - 20 - 8 = 22
        expect(tip.style.left).toBe('110px');
        expect(tip.style.top).toBe('22px');
        expect(tip.style.opacity).toBe('1');
        expect(tip.style.transform).toBe('translateY(0px)');
    });

    test('shows and positions the tooltip on focus', () => {
        const target = createTarget();

        setTargetBounds(target, {
            left: 200,
            top: 100,
            width: 80,
            height: 30,
        });

        makeTooltip(target, 'Example tooltip');

        const tip = getTooltip();
        setTooltipDimensions(tip, 60, 24);

        fireEvent.focus(target);

        // left = 200 + 80 / 2 - 60 / 2 = 210
        // top = 100 - 24 - 8 = 68
        expect(tip.style.left).toBe('210px');
        expect(tip.style.top).toBe('68px');
        expect(tip.style.opacity).toBe('1');
        expect(tip.style.transform).toBe('translateY(0px)');
    });

    test('rounds calculated positions to whole pixels', () => {
        const target = createTarget();

        setTargetBounds(target, {
            left: 100.4,
            top: 50.6,
            width: 51,
            height: 20,
        });

        makeTooltip(target, 'Example tooltip');

        const tip = getTooltip();
        setTooltipDimensions(tip, 20, 10);

        fireEvent.mouseEnter(target);

        // Math.round(100.4 + 25.5 - 10) = 116
        // Math.round(50.6 - 10 - 8) = 33
        expect(tip.style.left).toBe('116px');
        expect(tip.style.top).toBe('33px');
    });

    test('clamps the tooltip position to at least eight pixels', () => {
        const target = createTarget();

        setTargetBounds(target, {
            left: 0,
            top: 5,
            width: 10,
            height: 10,
        });

        makeTooltip(target, 'Example tooltip');

        const tip = getTooltip();
        setTooltipDimensions(tip, 100, 30);

        fireEvent.mouseEnter(target);

        expect(tip.style.left).toBe('8px');
        expect(tip.style.top).toBe('8px');
    });

    test('hides the tooltip on mouseleave', () => {
        const target = createTarget();

        setTargetBounds(target, {
            left: 100,
            top: 100,
            width: 50,
            height: 20,
        });

        makeTooltip(target, 'Example tooltip');

        const tip = getTooltip();
        setTooltipDimensions(tip, 40, 20);

        fireEvent.mouseEnter(target);

        expect(tip.style.opacity).toBe('1');
        expect(tip.style.transform).toBe('translateY(0px)');

        fireEvent.mouseLeave(target);

        expect(tip.style.opacity).toBe('0');
        expect(tip.style.transform).toBe('translateY(-8px)');
    });

    test('hides the tooltip on blur', () => {
        const target = createTarget();

        setTargetBounds(target, {
            left: 100,
            top: 100,
            width: 50,
            height: 20,
        });

        makeTooltip(target, 'Example tooltip');

        const tip = getTooltip();
        setTooltipDimensions(tip, 40, 20);

        fireEvent.focus(target);

        expect(tip.style.opacity).toBe('1');

        fireEvent.blur(target);

        expect(tip.style.opacity).toBe('0');
        expect(tip.style.transform).toBe('translateY(-8px)');
    });

    test('does not add a second tooltip to the same target', () => {
        const target = createTarget();

        makeTooltip(target, 'First tooltip');
        const secondCleanup = makeTooltip(target, 'Second tooltip');

        const tooltips = document.querySelectorAll<HTMLDivElement>('.visor-tooltip');

        expect(tooltips).toHaveLength(1);
        expect(tooltips[0].textContent).toBe('First tooltip');
        expect(typeof secondCleanup).toBe('function');
        expect(secondCleanup()).toBeUndefined();
    });

    test('allows different targets to have separate tooltips', () => {
        const firstTarget = createTarget();
        const secondTarget = createTarget();

        makeTooltip(firstTarget, 'First tooltip');
        makeTooltip(secondTarget, 'Second tooltip');

        const tooltips = document.querySelectorAll<HTMLDivElement>('.visor-tooltip');

        expect(tooltips).toHaveLength(2);
        expect(tooltips[0].textContent).toBe('First tooltip');
        expect(tooltips[1].textContent).toBe('Second tooltip');
    });

    test('cleanup removes the target event listeners', () => {
        const target = createTarget();

        setTargetBounds(target, {
            left: 100,
            top: 100,
            width: 50,
            height: 20,
        });

        const cleanup = makeTooltip(target, 'Example tooltip');
        const tip = getTooltip();

        setTooltipDimensions(tip, 40, 20);

        cleanup();
        fireEvent.mouseEnter(target);
        fireEvent.focus(target);

        expect(tip.style.opacity).toBe('0');
        expect(tip.style.transform).toBe('translateY(-8px)');
        expect(tip.style.left).toBe('');
        expect(tip.style.top).toBe('');
    });

    test('cleanup stops mouseleave and blur from changing the tooltip', () => {
        const target = createTarget();

        setTargetBounds(target, {
            left: 100,
            top: 100,
            width: 50,
            height: 20,
        });

        const cleanup = makeTooltip(target, 'Example tooltip');
        const tip = getTooltip();

        setTooltipDimensions(tip, 40, 20);
        fireEvent.mouseEnter(target);

        expect(tip.style.opacity).toBe('1');

        cleanup();

        fireEvent.mouseLeave(target);
        fireEvent.blur(target);

        expect(tip.style.opacity).toBe('1');
        expect(tip.style.transform).toBe('translateY(0px)');
    });

    test('cleanup leaves the tooltip element in the document', () => {
        const target = createTarget();
        const cleanup = makeTooltip(target, 'Example tooltip');
        const tip = getTooltip();

        cleanup();

        expect(document.body.contains(tip)).toBe(true);
    });
});

function createTarget(): HTMLButtonElement {
    const target = document.createElement('button');
    document.body.appendChild(target);
    return target;
}

function getTooltip(): HTMLDivElement {
    const tip = document.querySelector<HTMLDivElement>('.visor-tooltip');

    expect(tip).not.toBeNull();

    return tip!;
}

function setTooltipDimensions(tip: HTMLElement, width: number, height: number): void {
    Object.defineProperty(tip, 'offsetWidth', {
        configurable: true,
        value: width,
    });

    Object.defineProperty(tip, 'offsetHeight', {
        configurable: true,
        value: height,
    });
}

function setTargetBounds(
    target: HTMLElement,
    bounds: {
        left: number;
        top: number;
        width: number;
        height: number;
    }
): void {
    jest.spyOn(target, 'getBoundingClientRect').mockReturnValue({
        x: bounds.left,
        y: bounds.top,
        left: bounds.left,
        top: bounds.top,
        width: bounds.width,
        height: bounds.height,
        right: bounds.left + bounds.width,
        bottom: bounds.top + bounds.height,
        toJSON: () => ({}),
    } as DOMRect);
}
