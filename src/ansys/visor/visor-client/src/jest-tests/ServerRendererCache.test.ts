import { ServerRenderer, type ServerStateSource } from '../renderer/ServerRenderer';
import type { IServerCanvas } from '../rca/ServerCanvas';

/**
 * The server-rendering renderer keeps a cache the server feeds: the camera
 * from the camera state key, the widget flags from its own writes.  A
 * no-argument toggle sends the value it settled on; the camera key is the
 * echo of the client's own camera writes, so receiving it sends nothing.
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

/** A trame state holding one camera key value whose watchers can be told of a new one. */
class FakeState {
    constructor(value: unknown) {
        this.#value = value;
    }

    watch(keys: string[], fn: (...values: unknown[]) => void): () => void {
        this.#watchers.push(fn);
        fn(this.#value);
        return () => {};
    }

    /** Write the camera key and notify its watchers, as a server push does. */
    push(value: unknown): void {
        this.#value = value;
        for (const fn of this.#watchers) {
            fn(value);
        }
    }

    #value: unknown;
    readonly #watchers: ((...values: unknown[]) => void)[] = [];
}

function stubCanvas(): IServerCanvas {
    return {
        element: document.createElement('div'),
        frameSize: null,
        addFrameListener: () => () => {},
        addClickListener: () => () => {},
    };
}

function makeRenderer(initial: unknown) {
    const state = new FakeState(initial);
    const sender = jest.fn(async (_name: string, _payload: unknown) => undefined);
    const renderer = new ServerRenderer(stubCanvas(), state as ServerStateSource, sender);
    return { renderer, state, sender };
}

describe('ServerRenderer toggles', () => {
    test('a no-argument bounding-box toggle sends the value it settled on', async () => {
        const { renderer, sender } = makeRenderer(undefined);

        await renderer.setBoundingBoxVisibilityAsync();

        expect(sender.mock.calls).toStrictEqual([
            ['set_bounding_box_visibility', { visible: true }],
        ]);
    });

    test('a no-argument bounding-box toggle flips the cached flag', async () => {
        const { renderer } = makeRenderer(undefined);

        await renderer.setBoundingBoxVisibilityAsync();

        expect(renderer.isBoundingBoxVisible()).toBe(true);
    });
});

describe('ServerRenderer camera cache', () => {
    test('a camera record replaces the cached camera', async () => {
        const { renderer, state } = makeRenderer(cameraRecord([0, 0, 9], [0, 0, 0]));

        state.push(cameraRecord([1, 2, 3], [4, 6, 3]));

        const camera = await renderer.getCameraStateAsync();
        expect(camera.position).toEqual([1, 2, 3]);
        expect(camera.distance).toBe(5);
    });

    test('a camera record sends nothing', async () => {
        const { state, sender } = makeRenderer(cameraRecord([0, 0, 9], [0, 0, 0]));

        state.push(cameraRecord([1, 2, 3], [4, 6, 3]));

        expect(sender).not.toHaveBeenCalled();
    });

    test('None after a record leaves the cached camera', async () => {
        const { renderer, state } = makeRenderer(cameraRecord([1, 2, 3], [4, 6, 3]));

        state.push(null);

        const camera = await renderer.getCameraStateAsync();
        expect(camera.position).toEqual([1, 2, 3]);
    });

    test('the camera read rejects before any record arrives', async () => {
        const { renderer } = makeRenderer(undefined);

        await expect(renderer.getCameraStateAsync()).rejects.toMatchObject({
            name: 'CameraStateUnavailableError',
        });
    });
});
