import { attachCameraSyncReporter, buildSyncCameraPayload } from '../CameraSyncReporter';
import type { CameraOrigin, TrameTriggerSender, VisorCameraState } from '../renderer/IRenderer';

/**
 * The `sync_camera` trigger, client side.
 *
 * Two things are pinned here and nowhere else. The first is the payload: the
 * server accepts unknown keys, so a sender that spread its whole camera
 * snapshot would pass every server-side gate while putting twelve fields on
 * the wire instead of seven. The key set is therefore asserted directly,
 * against a hand-written list.
 *
 * The second is the release. `VtkScene` survives a client rebuild, so a
 * frontend replaced without releasing its subscription leaves it live, and
 * the next gesture is reported once per surviving frontend. Every one of
 * those reports is individually valid: nothing errors, nothing renders wrong,
 * and no gate but this one can see it.
 *
 * Expected values are hand-written literals. The same seven camera values
 * appear in `tests/unit/app/test_local_app_sync_camera.py`, written out there
 * as well, so the two stacks are compared against one set of numbers rather
 * than against each other.
 */

const TRIGGER_NAME = 'sync_camera';

/**
 * A settled camera snapshot, typed as the renderer's own read-side type so
 * that the double cannot drift from what `getCameraStateAsync` really
 * returns. It carries twelve fields: the seven applied ones and five derived
 * display ones. Five of the twelve must not reach the wire.
 */
function makeCameraSnapshot(): VisorCameraState {
    return {
        // Derived display fields -- none of these belongs on the wire.
        distance: 20.0,
        orthographic: true,
        orthographicScale: 21.0,
        unitsPerPixel: 22.0,
        viewPortHeight: 23.0,
        // The seven applied fields.
        position: [11.0, 12.0, 13.0],
        focalPoint: [14.0, 15.0, 16.0],
        viewUp: [0.0, 1.0, 0.0],
        clippingRange: [17.0, 18.0],
        parallelProjection: true,
        viewAngle: 35.0,
        parallelScale: 19.0,
    };
}

/**
 * A renderer double whose `addCameraSettledListener` is a real subscription
 * with a real remover, so that releasing one subscriber is observably
 * different from releasing none. `settle` fans out to whoever is still
 * subscribed, which is exactly what `CameraGestureTracker` does at the end of
 * a settle window.
 */
function makeRendererDouble() {
    const listeners = new Map<() => void, (origin: CameraOrigin) => void>();
    const getCameraStateAsync = jest.fn(async () => makeCameraSnapshot());
    return {
        getCameraStateAsync,
        addCameraSettledListener: (callback: (origin: CameraOrigin) => void) => {
            const remover = () => {
                listeners.delete(remover);
            };
            listeners.set(remover, callback);
            return remover;
        },
        settle(origin: CameraOrigin) {
            for (const callback of listeners.values()) {
                callback(origin);
            }
        },
        subscriberCount: () => listeners.size,
    };
}

/** A sender that records its calls and resolves. */
function makeSender() {
    return jest.fn(async () => undefined) as unknown as jest.Mock & TrameTriggerSender;
}

/**
 * Let the settle callback's async body run to completion. The callback is
 * synchronous and starts a promise chain; the camera read and the send are
 * separate microtask turns.
 */
async function flush() {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
}

describe('the sync_camera report', () => {
    test('a gesture settle sends one trigger with the seven-field payload', async () => {
        const renderer = makeRendererDouble();
        const sender = makeSender();
        attachCameraSyncReporter(renderer, sender);

        renderer.settle('gesture');
        await flush();

        expect(sender).toHaveBeenCalledTimes(1);
        expect(sender).toHaveBeenCalledWith(TRIGGER_NAME, {
            origin: 'gesture',
            camera: {
                position: [11.0, 12.0, 13.0],
                focalPoint: [14.0, 15.0, 16.0],
                viewUp: [0.0, 1.0, 0.0],
                clippingRange: [17.0, 18.0],
                parallelProjection: true,
                viewAngle: 35.0,
                parallelScale: 19.0,
            },
        });
    });

    test('a programmatic settle sends the origin verbatim rather than suppressing', async () => {
        // The client does not decide what is an echo. The server drops it and
        // logs the drop, which is what makes an echo diagnosable at all.
        const renderer = makeRendererDouble();
        const sender = makeSender();
        attachCameraSyncReporter(renderer, sender);

        renderer.settle('programmatic');
        await flush();

        expect(sender).toHaveBeenCalledTimes(1);
        expect(sender.mock.calls[0][1]).toMatchObject({ origin: 'programmatic' });
    });

    test('the payload carries exactly the seven applied camera fields', () => {
        // Asserted against a written-out list, not against the snapshot the
        // builder was handed: the failure this catches is a spread, and a
        // spread agrees with any expectation derived from the source object.
        const payload = buildSyncCameraPayload('gesture', makeCameraSnapshot());

        expect(Object.keys(payload).sort()).toEqual(['camera', 'origin']);
        expect(Object.keys(payload.camera).sort()).toEqual([
            'clippingRange',
            'focalPoint',
            'parallelProjection',
            'parallelScale',
            'position',
            'viewAngle',
            'viewUp',
        ]);
    });

    test('the camera is read once per settle, not once per event', async () => {
        const renderer = makeRendererDouble();
        attachCameraSyncReporter(renderer, makeSender());

        renderer.settle('gesture');
        await flush();

        expect(renderer.getCameraStateAsync).toHaveBeenCalledTimes(1);
    });

    test('a sender that rejects does not escape the settle callback', async () => {
        const renderer = makeRendererDouble();
        const sender = jest.fn(async () => {
            throw new Error('transport down');
        }) as unknown as jest.Mock & TrameTriggerSender;
        const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
        attachCameraSyncReporter(renderer, sender);

        renderer.settle('gesture');
        await flush();

        expect(consoleError).toHaveBeenCalled();
        consoleError.mockRestore();
    });
});

describe('a replaced frontend releases its subscription', () => {
    test('two reporters over one renderer, the first released, send one trigger', async () => {
        // The rebuild sequence App.tsx performs: the replacement subscribes,
        // then the frontend being replaced releases, with no suspension point
        // in between. Without the release both subscriptions are live and the
        // next gesture is reported twice -- twice with the same camera, both
        // valid, which is why this is the only place it can be caught.
        const renderer = makeRendererDouble();
        const firstSender = makeSender();
        const secondSender = makeSender();

        const releaseFirst = attachCameraSyncReporter(renderer, firstSender);
        attachCameraSyncReporter(renderer, secondSender);
        releaseFirst();

        expect(renderer.subscriberCount()).toBe(1);

        renderer.settle('gesture');
        await flush();

        expect(firstSender).not.toHaveBeenCalled();
        expect(secondSender).toHaveBeenCalledTimes(1);
    });
});
