/** @jest-environment jsdom */

import { FpsCounter } from '../components/FpsCounter';

describe('FpsCounter', () => {
    beforeEach(() => {
        jest.useFakeTimers();
    });

    afterEach(() => {
        jest.runOnlyPendingTimers();
        jest.useRealTimers();
        document.body.innerHTML = '';
        jest.restoreAllMocks();
    });

    describe('constructor', () => {
        test('appends the FPS display to the supplied container', () => {
            const container = createContainer();

            new FpsCounter(container, '10px');

            expect(container.children).toHaveLength(1);
            expect(container.firstElementChild).toBeInstanceOf(HTMLDivElement);
        });

        test('applies the supplied inset', () => {
            const container = createContainer();

            new FpsCounter(container, '10px 20px 30px 40px');

            const display = getDisplay(container);

            expect(display.style.inset).toBe('10px 20px 30px 40px');
        });

        test('applies the expected display styles', () => {
            const container = createContainer();

            new FpsCounter(container, '5px');

            const style = getDisplay(container).style;

            expect(style.position).toBe('absolute');
            expect(style.inset).toBe('5px');
            expect(style.backgroundColor).toBe('rgba(0, 0, 0, 0.75)');
            expect(style.color).toBe('rgb(255, 255, 255)');
            expect(style.padding).toBe('10px');
            expect(style.zIndex).toBe('999');
            expect(style.minWidth).toBe('16ch');
            expect(style.display).toBe('none');
        });

        test('creates the expected FPS table', () => {
            const container = createContainer();

            new FpsCounter(container, '0');

            const display = getDisplay(container);
            const table = display.querySelector('table');
            const cells = display.querySelectorAll('td');

            expect(table).not.toBeNull();
            expect(cells).toHaveLength(2);
            expect(cells[0].textContent).toBe('FPS:');
            expect(cells[0].classList.contains('text-left')).toBe(true);
            expect(cells[1].classList.contains('text-right')).toBe(true);
            expect(cells[1].textContent).toBe('');
        });

        test('is hidden initially', () => {
            const container = createContainer();

            new FpsCounter(container, '0');

            expect(getDisplay(container).style.display).toBe('none');
        });
    });

    describe('setValue', () => {
        test('displays a numeric value', () => {
            const container = createContainer();
            const counter = new FpsCounter(container, '0');

            counter.setValue(60);

            expect(getValueCell(container).textContent).toBe('60');
        });

        test('displays a string value', () => {
            const container = createContainer();
            const counter = new FpsCounter(container, '0');

            counter.setValue('59.8');

            expect(getValueCell(container).textContent).toBe('59.8');
        });

        test('replaces the previous value', () => {
            const container = createContainer();
            const counter = new FpsCounter(container, '0');

            counter.setValue(30);
            counter.setValue(60);

            expect(getValueCell(container).textContent).toBe('60');
        });

        test('writes string values as HTML', () => {
            const container = createContainer();
            const counter = new FpsCounter(container, '0');

            counter.setValue('<strong>60</strong>');

            const valueCell = getValueCell(container);

            expect(valueCell.querySelector('strong')?.textContent).toBe('60');
        });
    });

    describe('keyboard shortcut', () => {
        test('shows the display when Ctrl+F10 is pressed', () => {
            const container = createContainer();

            new FpsCounter(container, '0');

            dispatchKeyDown({
                key: 'F10',
                ctrlKey: true,
            });

            expect(getDisplay(container).style.display).toBe('');
        });

        test('hides the display when Ctrl+F10 is pressed again after the debounce period', () => {
            const container = createContainer();

            new FpsCounter(container, '0');

            dispatchKeyDown({
                key: 'F10',
                ctrlKey: true,
            });

            expect(getDisplay(container).style.display).toBe('');

            jest.advanceTimersByTime(250);

            dispatchKeyDown({
                key: 'F10',
                ctrlKey: true,
            });

            expect(getDisplay(container).style.display).toBe('none');
        });

        test('ignores repeated Ctrl+F10 presses during the debounce period', () => {
            const container = createContainer();

            new FpsCounter(container, '0');

            dispatchKeyDown({
                key: 'F10',
                ctrlKey: true,
            });

            expect(getDisplay(container).style.display).toBe('');

            dispatchKeyDown({
                key: 'F10',
                ctrlKey: true,
            });

            expect(getDisplay(container).style.display).toBe('');
        });

        test('allows toggling again after 250 milliseconds', () => {
            const container = createContainer();

            new FpsCounter(container, '0');

            dispatchKeyDown({
                key: 'F10',
                ctrlKey: true,
            });

            jest.advanceTimersByTime(249);

            dispatchKeyDown({
                key: 'F10',
                ctrlKey: true,
            });

            expect(getDisplay(container).style.display).toBe('');

            jest.advanceTimersByTime(1);

            dispatchKeyDown({
                key: 'F10',
                ctrlKey: true,
            });

            expect(getDisplay(container).style.display).toBe('none');
        });

        test('does nothing when F10 is pressed without Ctrl', () => {
            const container = createContainer();

            new FpsCounter(container, '0');

            dispatchKeyDown({
                key: 'F10',
                ctrlKey: false,
            });

            expect(getDisplay(container).style.display).toBe('none');
        });

        test('does nothing when Ctrl is pressed with another key', () => {
            const container = createContainer();

            new FpsCounter(container, '0');

            dispatchKeyDown({
                key: 'F9',
                ctrlKey: true,
            });

            expect(getDisplay(container).style.display).toBe('none');
        });

        test('matches the F10 key case-sensitively', () => {
            const container = createContainer();

            new FpsCounter(container, '0');

            dispatchKeyDown({
                key: 'f10',
                ctrlKey: true,
            });

            expect(getDisplay(container).style.display).toBe('none');
        });
    });

    describe('dispose', () => {
        test('removes the FPS display from the DOM', () => {
            const container = createContainer();
            const counter = new FpsCounter(container, '0');

            expect(container.children).toHaveLength(1);

            counter.dispose();

            expect(container.children).toHaveLength(0);
        });

        test('removes the keyboard event listener', () => {
            const container = createContainer();
            const counter = new FpsCounter(container, '0');
            const display = getDisplay(container);

            counter.dispose();

            dispatchKeyDown({
                key: 'F10',
                ctrlKey: true,
            });

            expect(display.style.display).toBe('none');
        });

        test('can be called more than once', () => {
            const container = createContainer();
            const counter = new FpsCounter(container, '0');

            expect(() => {
                counter.dispose();
                counter.dispose();
            }).not.toThrow();

            expect(container.children).toHaveLength(0);
        });

        test('setValue can still update the detached display', () => {
            const container = createContainer();
            const counter = new FpsCounter(container, '0');
            const valueCell = getValueCell(container);

            counter.dispose();
            counter.setValue(120);

            expect(valueCell.textContent).toBe('120');
            expect(valueCell.isConnected).toBe(false);
        });
    });

    describe('multiple counters', () => {
        test('creates an independent display for each counter', () => {
            const firstContainer = createContainer();
            const secondContainer = createContainer();

            const firstCounter = new FpsCounter(firstContainer, '5px');
            const secondCounter = new FpsCounter(secondContainer, '10px');

            firstCounter.setValue(30);
            secondCounter.setValue(60);

            expect(getValueCell(firstContainer).textContent).toBe('30');
            expect(getValueCell(secondContainer).textContent).toBe('60');
            expect(getDisplay(firstContainer).style.inset).toBe('5px');
            expect(getDisplay(secondContainer).style.inset).toBe('10px');
        });

        test('Ctrl+F10 toggles all active counters', () => {
            const firstContainer = createContainer();
            const secondContainer = createContainer();

            new FpsCounter(firstContainer, '0');
            new FpsCounter(secondContainer, '0');

            dispatchKeyDown({
                key: 'F10',
                ctrlKey: true,
            });

            expect(getDisplay(firstContainer).style.display).toBe('');
            expect(getDisplay(secondContainer).style.display).toBe('');
        });

        test('disposing one counter leaves the other counter active', () => {
            const firstContainer = createContainer();
            const secondContainer = createContainer();

            const firstCounter = new FpsCounter(firstContainer, '0');
            new FpsCounter(secondContainer, '0');

            firstCounter.dispose();

            dispatchKeyDown({
                key: 'F10',
                ctrlKey: true,
            });

            expect(firstContainer.children).toHaveLength(0);
            expect(getDisplay(secondContainer).style.display).toBe('');
        });
    });
});

function createContainer(): HTMLDivElement {
    const container = document.createElement('div');
    document.body.appendChild(container);
    return container;
}

function getDisplay(container: HTMLElement): HTMLDivElement {
    const display = container.firstElementChild;

    expect(display).toBeInstanceOf(HTMLDivElement);

    return display as HTMLDivElement;
}

function getValueCell(container: HTMLElement): HTMLTableCellElement {
    const cells = container.querySelectorAll<HTMLTableCellElement>('td');

    expect(cells).toHaveLength(2);

    return cells[1];
}

function dispatchKeyDown({ key, ctrlKey }: { key: string; ctrlKey: boolean }): void {
    window.dispatchEvent(
        new KeyboardEvent('keydown', {
            key,
            ctrlKey,
            bubbles: true,
        })
    );
}
