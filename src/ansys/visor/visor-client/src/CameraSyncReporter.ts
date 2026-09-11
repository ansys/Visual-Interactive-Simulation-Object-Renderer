import type {
    CameraOrigin,
    IRenderer,
    TrameTriggerSender,
    VisorCameraState,
} from './renderer/IRenderer';

/**
 * The `sync_camera` trigger: the client's half of the server-tracked camera.
 *
 * This module exists apart from `VisorFrontend` so that it can be tested. A
 * `VisorFrontend` cannot be constructed under jest -- it needs a real scene
 * graph node, the module-global spectrum manager and a renderer that accepts
 * `attachSceneGraph`, and it ends in `Object.freeze` -- so a listener body
 * written inline there would be pinned by nothing, and the payload shape is
 * precisely the part no server-side gate can check. `CameraGestureTracker`
 * was split out for the same reason in the previous increment.
 *
 * What reaches here is already debounced: `addCameraSettledListener` fires
 * once per settle window, never once per camera event, and it carries that
 * window's origin. The camera is therefore read exactly once per settle --
 * the read is a multi-await round trip to the wasm camera, and paying it per
 * event is what the debounce exists to avoid.
 */

/** The payload of the `sync_camera` trigger. Mirrors the server's model. */
export type SyncCameraPayload = Readonly<{
    origin: CameraOrigin;
    camera: Readonly<{
        position: readonly number[];
        focalPoint: readonly number[];
        viewUp: readonly number[];
        clippingRange: readonly number[];
        parallelProjection: boolean;
        viewAngle: number;
        parallelScale: number;
    }>;
}>;

/**
 * The part of a renderer this module uses. Narrower than `IRenderer` so the
 * unit test can supply exactly these two members without a cast that would
 * defeat the type check it is here to get.
 */
export type CameraSyncSource = Pick<IRenderer, 'addCameraSettledListener' | 'getCameraStateAsync'>;

/**
 * Build the trigger payload from a settled camera snapshot.
 *
 * The seven applied fields are named one by one, deliberately, rather than
 * spread from the snapshot. `VisorCameraState` carries five further derived
 * display fields -- `distance`, `orthographic`, `orthographicScale`,
 * `unitsPerPixel`, `viewPortHeight` -- which are meaningless to the server's
 * record. Spreading would put all twelve on the wire, and the server would
 * accept it silently: pydantic ignores unknown keys, so every server-side
 * gate would stay green while the wire contract quietly became "whatever the
 * client's snapshot type happens to hold today". Naming the seven is the only
 * place that shape is decided, which is why the test asserts the key set.
 *
 * `parallelProjection` is carried verbatim. `getCameraStateAsync` has already
 * narrowed the wasm camera's raw value to a boolean; this module does not
 * re-derive it.
 *
 * `origin` is carried verbatim too, for both values. The client never
 * suppresses a report it believes is an echo -- the server decides, and logs
 * what it dropped.
 */
export function buildSyncCameraPayload(
    origin: CameraOrigin,
    camera: VisorCameraState
): SyncCameraPayload {
    return {
        origin,
        camera: {
            position: camera.position,
            focalPoint: camera.focalPoint,
            viewUp: camera.viewUp,
            clippingRange: camera.clippingRange,
            parallelProjection: camera.parallelProjection,
            viewAngle: camera.viewAngle,
            parallelScale: camera.parallelScale,
        },
    };
}

/**
 * Subscribe to settled camera windows and report each one to the server.
 *
 * Returns the remover from `addCameraSettledListener`, **verbatim**. The
 * caller owns it and must call it when the frontend holding it is replaced:
 * the `VtkScene` survives a client rebuild, so a frontend that is discarded
 * without releasing leaves its subscription live and every later gesture is
 * reported once per rebuild that has ever happened. Each of those reports is
 * individually valid, which is why no gate can see the fault.
 *
 * The sender is required. A frontend with no transport is not a state this
 * path supports: it would subscribe, read the camera on every settle, build a
 * payload and drop it, which is indistinguishable at runtime from a working
 * wire that the server is ignoring.
 *
 * A failed send is logged and swallowed, never rethrown. The settle callback
 * returns `void` and is invoked from a timer, so a rejection escaping it has
 * no caller to receive it and would surface as an unhandled rejection. The
 * log prefix is fixed and greppable because it is the only signal that a
 * report was lost -- the view looks identical either way.
 */
export function attachCameraSyncReporter(
    renderer: CameraSyncSource,
    send: TrameTriggerSender
): () => void {
    return renderer.addCameraSettledListener((origin: CameraOrigin) => {
        void (async () => {
            try {
                const camera = await renderer.getCameraStateAsync();
                await send('sync_camera', buildSyncCameraPayload(origin, camera));
            } catch (err) {
                console.error(`[VISOR] sync_camera trigger send failed: origin='${origin}'`, err);
            }
        })();
    });
}
