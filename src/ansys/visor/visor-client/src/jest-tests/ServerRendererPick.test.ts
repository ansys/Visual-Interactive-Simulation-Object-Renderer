import { ServerRenderer, type ServerStateSource } from '../renderer/ServerRenderer';
import type { CanvasClick, IServerCanvas } from '../rca/ServerCanvas';

/**
 * A part pick asks the server which part lies under a point, in render-window
 * device pixels measured on the last frame, origin bottom left.  A click on
 * the canvas reaches every canvas-click listener once and asks the server
 * nothing: the frontend decides what a click picks.
 *
 * The page is 300 x 200 CSS px at device pixel ratio 2, so the frame is
 * 600 x 400.  Expected values are hand-written literals.
 *
 * A geometry pick asks the server in the same pixels, and a highlight or a
 * clear asks the server to draw or drop it.
 */

let originalDevicePixelRatio: number;

beforeEach(() => {
    originalDevicePixelRatio = window.devicePixelRatio;
    Object.defineProperty(window, 'devicePixelRatio', { configurable: true, value: 2 });
});

afterEach(() => {
    Object.defineProperty(window, 'devicePixelRatio', {
        configurable: true,
        value: originalDevicePixelRatio,
    });
});

/** A state that never holds a camera record. */
const emptyState: ServerStateSource = {
    watch: (_keys, fn) => {
        fn(undefined);
        return () => {};
    },
};

/** A canvas of 300 x 200 CSS px whose last frame is 600 x 400, and the click callback the renderer registered. */
function stubCanvas() {
    const element = document.createElement('div');
    Object.defineProperty(element, 'clientWidth', { value: 300 });
    Object.defineProperty(element, 'clientHeight', { value: 200 });
    element.getBoundingClientRect = () =>
        ({
            left: 0,
            top: 0,
            width: 300,
            height: 200,
            right: 300,
            bottom: 200,
            x: 0,
            y: 0,
        }) as DOMRect;
    const clicks: ((click: CanvasClick) => void)[] = [];
    const canvas: IServerCanvas = {
        element,
        frameSize: { width: 600, height: 400 },
        addFrameListener: () => () => {},
        addClickListener: (callback) => {
            clicks.push(callback);
            return () => {};
        },
        addResizeListener: () => () => {},
    };
    return { canvas, click: (c: CanvasClick) => clicks.forEach((callback) => callback(c)) };
}

const CLICK: CanvasClick = { normX: 0.5, normY: 0.25, ctrlKey: false, shiftKey: false };

/** Let the pick's promise chain finish. */
async function settle() {
    await new Promise((resolve) => setTimeout(resolve, 0));
}

describe('ServerRenderer part pick', () => {
    test('pickPartAsync sends one pick_part_at in render-window pixels from the frame and returns the node', async () => {
        const { canvas } = stubCanvas();
        const sender = jest.fn(async (_name: string, _payload: unknown) => 7 as unknown);
        const renderer = new ServerRenderer(canvas, emptyState, sender);

        const nodeId = await renderer.pickPartAsync(0.5, 0.25);

        expect(nodeId).toBe(7);
        expect(sender.mock.calls).toStrictEqual([['pick_part_at', { x: 300, y: 100 }]]);
    });

    test('a pick_part_at result that is not a node id rejects with a TypeError', async () => {
        const { canvas } = stubCanvas();
        const sender = jest.fn(async (_name: string, _payload: unknown) => 'seven' as unknown);
        const renderer = new ServerRenderer(canvas, emptyState, sender);

        await expect(renderer.pickPartAsync(0.5, 0.25)).rejects.toThrow(
            new TypeError('pick_part_at result is not a node id or null: seven')
        );
    });

    test('a click reaches every canvas-click listener once and sends nothing', async () => {
        const { canvas, click } = stubCanvas();
        const sender = jest.fn(async (_name: string, _payload: unknown) => 7 as unknown);
        const renderer = new ServerRenderer(canvas, emptyState, sender);
        const first = jest.fn();
        const second = jest.fn();
        renderer.addCanvasClickListener(first);
        renderer.addCanvasClickListener(second);

        click(CLICK);
        await settle();

        expect(first.mock.calls).toEqual([
            [{ normX: 0.5, normY: 0.25, ctrlKey: false, shiftKey: false }],
        ]);
        expect(second.mock.calls).toEqual([
            [{ normX: 0.5, normY: 0.25, ctrlKey: false, shiftKey: false }],
        ]);
        expect(sender).not.toHaveBeenCalled();
    });
});

describe('ServerRenderer geometry pick', () => {
    test('pickGeometryAsync sends one pick_geometry_at in render-window pixels from the frame', async () => {
        const { canvas } = stubCanvas();
        const sender = jest.fn(
            async (_name: string, _payload: unknown) => ({ found: false }) as unknown
        );
        const renderer = new ServerRenderer(canvas, emptyState, sender);

        await renderer.pickGeometryAsync(0.25, 0.25, 'vertex');

        expect(sender.mock.calls).toStrictEqual([
            ['pick_geometry_at', { x: 150, y: 100, mode: 'vertex' }],
        ]);
    });

    test('a highlight then a clear each send set_geometry_highlight with the pick', async () => {
        const { canvas } = stubCanvas();
        const sender = jest.fn(async (_name: string, _payload: unknown) => undefined as unknown);
        const renderer = new ServerRenderer(canvas, emptyState, sender);

        await renderer.setGeometryHighlightAsync({
            found: true,
            mode: 'vertex',
            position: [1, 2, 3],
        });
        renderer.clearGeometryHighlight();
        await settle();

        expect(sender.mock.calls).toStrictEqual([
            [
                'set_geometry_highlight',
                { pick: { found: true, mode: 'vertex', position: [1, 2, 3] } },
            ],
            ['set_geometry_highlight', { pick: { found: false } }],
        ]);
    });
});
