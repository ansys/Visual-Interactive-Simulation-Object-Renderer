import { ServerRenderer, type ServerStateSource } from '../renderer/ServerRenderer';
import type { IServerCanvas } from '../rca/ServerCanvas';

/**
 * The server-rendering renderer keeps a cache the server feeds: the camera
 * and the cross-section plane from their state keys, the widget flags from
 * its own writes.  A no-argument toggle sends the value it settled on; the
 * camera key is the echo of the client's own camera writes, so receiving it
 * sends nothing.
 *
 * Expected values are hand-written literals.
 */

/** A camera record as the server publishes it, at the given position and focal point. */
function cameraRecord(position: number[], focalPoint: number[]) {
    return {
        position,
        focalPoint,
        viewUp: [0, 1, 0],
        clippingRange: [0.1, 100],
        parallelProjection: false,
        viewAngle: 30,
        parallelScale: 1,
    };
}

/** A trame state holding one value per key whose watchers can be told of a new one. */
class FakeState {
    constructor(values: Record<string, unknown>) {
        this.#values = new Map(Object.entries(values));
    }

    watch(keys: string[], fn: (...values: unknown[]) => void): () => void {
        const key = keys[0];
        this.#watchers.push({ key, fn });
        fn(this.#values.get(key));
        return () => {};
    }

    /** Write one key and notify that key's watchers, as a server push does. */
    push(key: string, value: unknown): void {
        this.#values.set(key, value);
        for (const watcher of this.#watchers) {
            if (watcher.key === key) {
                watcher.fn(value);
            }
        }
    }

    readonly #values: Map<string, unknown>;
    readonly #watchers: { key: string; fn: (...values: unknown[]) => void }[] = [];
}

function stubCanvas(): IServerCanvas {
    return {
        element: document.createElement('div'),
        frameSize: null,
        addFrameListener: () => () => {},
        addClickListener: () => () => {},
        addResizeListener: () => () => {},
    };
}

function makeRenderer(initial: Record<string, unknown>) {
    const state = new FakeState(initial);
    const sender = jest.fn(async (_name: string, _payload: unknown) => undefined);
    const renderer = new ServerRenderer(stubCanvas(), state as ServerStateSource, sender);
    return { renderer, state, sender };
}

describe('ServerRenderer toggles', () => {
    test('a no-argument bounding-box toggle sends the value it settled on', async () => {
        const { renderer, sender } = makeRenderer({});

        await renderer.setBoundingBoxVisibilityAsync();

        expect(sender.mock.calls).toStrictEqual([
            ['set_bounding_box_visibility', { visible: true }],
        ]);
    });

    test('a no-argument bounding-box toggle flips the cached flag', async () => {
        const { renderer } = makeRenderer({});

        await renderer.setBoundingBoxVisibilityAsync();

        expect(renderer.isBoundingBoxVisible()).toBe(true);
    });
});

describe('ServerRenderer camera cache', () => {
    test('a camera record replaces the cached camera', async () => {
        const { renderer, state } = makeRenderer({
            server_camera_state: cameraRecord([0, 0, 9], [0, 0, 0]),
        });

        state.push('server_camera_state', cameraRecord([1, 2, 3], [4, 6, 3]));

        const camera = await renderer.getCameraStateAsync();
        expect(camera.position).toEqual([1, 2, 3]);
        expect(camera.distance).toBe(5);
    });

    test('a camera record sends nothing', async () => {
        const { state, sender } = makeRenderer({
            server_camera_state: cameraRecord([0, 0, 9], [0, 0, 0]),
        });

        state.push('server_camera_state', cameraRecord([1, 2, 3], [4, 6, 3]));

        expect(sender).not.toHaveBeenCalled();
    });

    test('None after a record leaves the cached camera', async () => {
        const { renderer, state } = makeRenderer({
            server_camera_state: cameraRecord([1, 2, 3], [4, 6, 3]),
        });

        state.push('server_camera_state', null);

        const camera = await renderer.getCameraStateAsync();
        expect(camera.position).toEqual([1, 2, 3]);
    });

    test('the camera read rejects before any record arrives', async () => {
        const { renderer } = makeRenderer({});

        await expect(renderer.getCameraStateAsync()).rejects.toMatchObject({
            name: 'CameraStateUnavailableError',
        });
    });
});

describe('ServerRenderer cross-section cache', () => {
    test('a cross-section record fills the plane reads', async () => {
        const { renderer, state } = makeRenderer({});

        state.push('server_cross_section_state', { origin: [1, 2, 3], normal: [0, 0, 1] });

        expect(await renderer.getCrossSectionOriginAsync()).toEqual([1, 2, 3]);
        expect(await renderer.getCrossSectionNormalAsync()).toEqual([0, 0, 1]);
    });

    test('None after a cross-section record leaves the cached plane', async () => {
        const { renderer, state } = makeRenderer({
            server_cross_section_state: { origin: [1, 2, 3], normal: [0, 0, 1] },
        });

        state.push('server_cross_section_state', null);

        expect(await renderer.getCrossSectionOriginAsync()).toEqual([1, 2, 3]);
        expect(await renderer.getCrossSectionNormalAsync()).toEqual([0, 0, 1]);
    });
});

describe('ServerRenderer canvas resize', () => {
    let originalDevicePixelRatio: number;

    beforeEach(() => {
        originalDevicePixelRatio = window.devicePixelRatio;
        Object.defineProperty(window, 'devicePixelRatio', { configurable: true, value: 1.5 });
    });

    afterEach(() => {
        Object.defineProperty(window, 'devicePixelRatio', {
            configurable: true,
            value: originalDevicePixelRatio,
        });
    });

    test('a canvas resize gives camera listeners the snapshot at the truncated device-pixel height', () => {
        const element = document.createElement('div');
        Object.defineProperty(element, 'clientHeight', { configurable: true, value: 100 });
        const resizeListeners: (() => void)[] = [];
        const canvas: IServerCanvas = {
            element,
            frameSize: null,
            addFrameListener: () => () => {},
            addClickListener: () => () => {},
            addResizeListener: (callback) => {
                resizeListeners.push(callback);
                return () => {};
            },
        };
        const state = new FakeState({ server_camera_state: cameraRecord([0, 0, 9], [0, 0, 0]) });
        const renderer = new ServerRenderer(canvas, state as ServerStateSource, jest.fn());
        const listener = jest.fn();
        renderer.addCameraChangedListener(listener);
        Object.defineProperty(element, 'clientHeight', { configurable: true, value: 301 });

        resizeListeners.forEach((callback) => callback());

        expect(listener).toHaveBeenCalledTimes(1);
        expect(listener.mock.calls[0][0].viewPortHeight).toBe(451);
        expect(listener.mock.calls[0][0].unitsPerPixel).toBeCloseTo(0.004434589800443459, 12);
    });
});
