import { ServerCanvas, type CanvasClick } from '../rca/ServerCanvas';

/**
 * The server canvas forwards mouse and wheel input to its area as vtk-js
 * interaction events in element pixels with y measured up from the bottom,
 * drives the same VTK button local mode does for each held combination, and
 * reports a left click at one point as a click.
 *
 * The element sits at (5, 10) and is 200 x 100, so a position that left out
 * the element's offset differs from one that kept it.  jsdom has no layout and
 * no `ResizeObserver`; both are replaced by doubles.
 *
 * Expected values are hand-written literals.
 */

const globals = globalThis as unknown as { ResizeObserver: unknown };
let originalResizeObserver: unknown;

beforeEach(() => {
    originalResizeObserver = globals.ResizeObserver;
    globals.ResizeObserver = class {
        observe() {}
        disconnect() {}
    };
});

afterEach(() => {
    globals.ResizeObserver = originalResizeObserver;
});

/** A session double that records every call. */
function makeSession() {
    return {
        call: jest.fn(async (_method: string, _args: unknown[]) => undefined),
        subscribe: () => ({ unsubscribe: () => undefined }),
    };
}

/** A canvas over a recording session whose element is 200 x 100 at (5, 10). */
function makeCanvas() {
    const session = makeSession();
    const canvas = new ServerCanvas(session, 'view');
    canvas.element.getBoundingClientRect = () =>
        ({
            left: 5,
            top: 10,
            width: 200,
            height: 100,
            right: 205,
            bottom: 110,
            x: 5,
            y: 10,
        }) as DOMRect;
    return { session, canvas };
}

/** Dispatch a mouse event of type with DOM button at client (clientX, clientY). */
function mouse(
    canvas: ServerCanvas,
    type: string,
    button: number,
    clientX: number,
    clientY: number
) {
    const event = new MouseEvent(type, {
        button,
        clientX,
        clientY,
        bubbles: true,
        cancelable: true,
    });
    canvas.element.dispatchEvent(event);
    return event;
}

/** The interaction events sent so far, in order. */
function sentEvents(session: ReturnType<typeof makeSession>): Record<string, unknown>[] {
    return session.call.mock.calls.map(([, args]) => args[2] as Record<string, unknown>);
}

/** The interaction event types sent so far, in order. */
function sentTypes(session: ReturnType<typeof makeSession>): unknown[] {
    return sentEvents(session).map((event) => event.type);
}

describe('ServerCanvas events', () => {
    test('a left press with no button held sends a MouseMove, three releases, then the press with y flipped', () => {
        const { session, canvas } = makeCanvas();

        mouse(canvas, 'mousedown', 0, 15, 30);

        const modifiers = { ctrlKey: false, altKey: false, shiftKey: false };
        expect(session.call.mock.calls).toEqual([
            [
                'trame.rca.event',
                [
                    'view',
                    'ServerCanvas',
                    { type: 'MouseMove', x: 10, y: 80, w: 200, h: 100, ...modifiers },
                ],
            ],
            [
                'trame.rca.event',
                [
                    'view',
                    'ServerCanvas',
                    { type: 'LeftButtonRelease', x: 10, y: 80, w: 200, h: 100, ...modifiers },
                ],
            ],
            [
                'trame.rca.event',
                [
                    'view',
                    'ServerCanvas',
                    { type: 'MiddleButtonRelease', x: 10, y: 80, w: 200, h: 100, ...modifiers },
                ],
            ],
            [
                'trame.rca.event',
                [
                    'view',
                    'ServerCanvas',
                    { type: 'RightButtonRelease', x: 10, y: 80, w: 200, h: 100, ...modifiers },
                ],
            ],
            [
                'trame.rca.event',
                [
                    'view',
                    'ServerCanvas',
                    { type: 'LeftButtonPress', x: 10, y: 80, w: 200, h: 100, ...modifiers },
                ],
            ],
        ]);
    });

    test('a right press while left is held sends a middle press', () => {
        const { session, canvas } = makeCanvas();
        mouse(canvas, 'mousedown', 0, 15, 30);
        session.call.mockClear();

        mouse(canvas, 'mousedown', 2, 15, 30);

        expect(sentTypes(session)).toEqual([
            'LeftButtonRelease',
            'MiddleButtonRelease',
            'RightButtonRelease',
            'MiddleButtonPress',
        ]);
    });

    test('mousemove is sent only while a button is held', () => {
        const { session, canvas } = makeCanvas();

        mouse(canvas, 'mousemove', 0, 25, 40);
        expect(session.call).not.toHaveBeenCalled();

        mouse(canvas, 'mousedown', 0, 15, 30);
        session.call.mockClear();
        mouse(canvas, 'mousemove', 0, 25, 40);

        expect(sentEvents(session)).toEqual([
            {
                type: 'MouseMove',
                x: 20,
                y: 70,
                w: 200,
                h: 100,
                ctrlKey: false,
                altKey: false,
                shiftKey: false,
            },
        ]);
    });

    test('a wheel sends one MouseWheel step and keeps the page from scrolling', () => {
        const { session, canvas } = makeCanvas();
        const wheel = new WheelEvent('wheel', {
            deltaY: 120,
            clientX: 15,
            clientY: 30,
            bubbles: true,
            cancelable: true,
        });

        canvas.element.dispatchEvent(wheel);

        expect(sentEvents(session)).toEqual([
            {
                type: 'MouseWheel',
                x: 10,
                y: 80,
                w: 200,
                h: 100,
                ctrlKey: false,
                altKey: false,
                shiftKey: false,
                spinY: 1,
            },
        ]);
        expect(wheel.defaultPrevented).toBe(true);
    });

    test('mouseout releases the button the server holds and presses none', () => {
        const { session, canvas } = makeCanvas();
        mouse(canvas, 'mousedown', 0, 15, 30);
        mouse(canvas, 'mousedown', 2, 15, 30);
        session.call.mockClear();

        mouse(canvas, 'mouseout', 0, 15, 30);
        expect(sentTypes(session)).toEqual(['MiddleButtonRelease']);

        session.call.mockClear();
        mouse(canvas, 'mousemove', 0, 25, 40);
        expect(session.call).not.toHaveBeenCalled();
    });

    test('contextmenu is prevented', () => {
        const { canvas } = makeCanvas();

        const event = mouse(canvas, 'contextmenu', 2, 15, 30);

        expect(event.defaultPrevented).toBe(true);
    });

    test('a left press and release at one point fires one click', () => {
        const { canvas } = makeCanvas();
        const clicks: CanvasClick[] = [];
        canvas.addClickListener((click) => clicks.push(click));

        mouse(canvas, 'mousedown', 0, 15, 30);
        mouse(canvas, 'mouseup', 0, 15, 30);

        expect(clicks).toEqual([{ normX: 0.05, normY: 0.8, ctrlKey: false, shiftKey: false }]);
    });

    test('a press and release at different points fires no click', () => {
        const { canvas } = makeCanvas();
        const listener = jest.fn();
        canvas.addClickListener(listener);

        mouse(canvas, 'mousedown', 0, 15, 30);
        mouse(canvas, 'mouseup', 0, 16, 30);

        expect(listener).not.toHaveBeenCalled();
    });

    test('a right press and release at one point fires no click', () => {
        const { canvas } = makeCanvas();
        const listener = jest.fn();
        canvas.addClickListener(listener);

        mouse(canvas, 'mousedown', 2, 15, 30);
        mouse(canvas, 'mouseup', 2, 15, 30);

        expect(listener).not.toHaveBeenCalled();
    });

    test('dispose stops event forwarding', () => {
        const { session, canvas } = makeCanvas();

        canvas.dispose();
        mouse(canvas, 'mousedown', 0, 15, 30);

        expect(session.call).not.toHaveBeenCalled();
    });
});
