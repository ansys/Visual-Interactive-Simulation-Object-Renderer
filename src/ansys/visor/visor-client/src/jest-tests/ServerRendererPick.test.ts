import { ServerRenderer, type ServerStateSource } from '../renderer/ServerRenderer';
import type { CanvasClick, IServerCanvas } from '../rca/ServerCanvas';

/**
 * A click on the server-drawn view asks the server which part lies under it,
 * in render-window device pixels measured on the last frame, origin bottom
 * left.  One click makes one pick, however many listeners there are, and each
 * listener hears its result once.  A click while a pick is running is dropped.
 *
 * The page is 300 x 200 CSS px at device pixel ratio 2, so the frame is
 * 600 x 400.  Expected values are hand-written literals.
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

describe('ServerRenderer pick', () => {
    test('a click sends one pick_part_at in render-window pixels from the frame', async () => {
        const { canvas, click } = stubCanvas();
        const sender = jest.fn(async (_name: string, _payload: unknown) => 7 as unknown);
        const renderer = new ServerRenderer(canvas, emptyState, sender);
        renderer.addViewerClickedListener(jest.fn());
        renderer.addViewerClickedListener(jest.fn());

        click(CLICK);
        await settle();

        expect(sender.mock.calls).toStrictEqual([['pick_part_at', { x: 300, y: 100 }]]);
    });

    test('every viewer-clicked listener gets the picked node once', async () => {
        const { canvas, click } = stubCanvas();
        const sender = jest.fn(async (_name: string, _payload: unknown) => 7 as unknown);
        const renderer = new ServerRenderer(canvas, emptyState, sender);
        const first = jest.fn();
        const second = jest.fn();
        renderer.addViewerClickedListener(first);
        renderer.addViewerClickedListener(second);

        click(CLICK);
        await settle();

        expect(first.mock.calls).toEqual([[7, false, false, 0.5, 0.25]]);
        expect(second.mock.calls).toEqual([[7, false, false, 0.5, 0.25]]);
    });

    test('a click while a pick is pending sends nothing', async () => {
        const { canvas, click } = stubCanvas();
        const sender = jest.fn(
            (_name: string, _payload: unknown) => new Promise<unknown>(() => {})
        );
        new ServerRenderer(canvas, emptyState, sender);

        click(CLICK);
        click(CLICK);
        await settle();

        expect(sender).toHaveBeenCalledTimes(1);
    });
});
