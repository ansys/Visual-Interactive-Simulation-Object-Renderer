import { WasmRenderer } from '../renderer/WasmRenderer';
import type { WasmRendererAnnotation } from '../renderer/RendererAnnotation';
import type VtkScene from '../wasm/VtkScene';
import type { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import type { TrameTriggerSender } from '../renderer/IRenderer';

/**
 * WasmRenderer's view-level widget *send* surface: the four methods that
 * carry a scene-wide toggle to the matching server trigger, and the
 * orthographic flag seed that `createAsync` performs.
 *
 * Two things are pinned here, and they are separate on purpose.
 *
 *   1. Each of the four methods, **called with no argument**, sends its
 *      trigger once carrying the value the widget settled on -- not the
 *      argument it was passed. The toolbar calls all four with no argument,
 *      so the argument is `undefined` and only the widget knows the value.
 *      Forwarding the argument instead of reading the widget back would put
 *      `undefined` on the wire and fail nowhere a gate can see it. Every
 *      expected payload below is a hand-written literal.
 *
 *   2. `createAsync` leaves `isOrthographicEnabled()` agreeing with the wasm
 *      camera before any setter has run. Without the seed the flag is the
 *      literal `false` its field initialiser gives it, whatever the camera
 *      says, and the fault appears only in the running application -- on a
 *      rebuild, where `getAppStateAsync` reads that flag and saves it.
 *
 * Also pinned: with no sender injected the four sends are no-ops that do not
 * throw, and a failed widget send is logged under its own prefix, naming the
 * trigger and carrying no node id.
 *
 * Modelled on `WasmRendererPartTriggers.test.tsx`, which does the same for
 * the six per-part sends.
 */

const NODE_ID = 7;
const ACTOR_ID = 101;
const PROPERTY_ID = 102;
const MAPPER_ID = 103;
const ORIENTATION_WIDGET_ID = 201;
const PLANE_ID = 202;
const PLANE_WIDGET_ID = 203;
const PLANE_REPRESENTATION_ID = 204;
const BOUNDING_BOX_ALGORITHM_ID = 205;
const BOUNDING_BOX_OUTLINE_ID = 206;
const BOUNDING_BOX_AXES_ID = 207;

/** Three actor node ids for the edge fan-out. Hand-written literals. */
const FAN_OUT_ACTOR_IDS = [11, 12, 13];

/** What the wasm camera reports for `GetParallelProjection()`. */
const PARALLEL = 1;
const PERSPECTIVE = 0;

function makeAnnotation(): WasmRendererAnnotation {
    return {
        rendererKind: 'wasm',
        nodes: {
            [String(NODE_ID)]: {
                actorId: ACTOR_ID,
                propertyId: PROPERTY_ID,
                mapperId: MAPPER_ID,
            },
        },
        widgets: {
            orientationWidgetId: ORIENTATION_WIDGET_ID,
            crossSectionPlaneId: PLANE_ID,
            crossSectionPlaneWidgetId: PLANE_WIDGET_ID,
            crossSectionPlaneRepresentationId: PLANE_REPRESENTATION_ID,
            boundingBoxAlgorithmId: BOUNDING_BOX_ALGORITHM_ID,
            boundingBoxOutlineActorId: BOUNDING_BOX_OUTLINE_ID,
            boundingBoxAxesActorId: BOUNDING_BOX_AXES_ID,
        },
    };
}

function makeFakeWasmObjects() {
    const actor = {
        SetVisibility: jest.fn(async () => undefined),
    };
    const property = {
        SetEdgeColor: jest.fn(async () => undefined),
        EdgeVisibilityOn: jest.fn(async () => undefined),
        EdgeVisibilityOff: jest.fn(async () => undefined),
    };
    // Stands in for the plane, the plane representation, the plane widget,
    // the bounding-box outline and axes actors, and the box algorithm. The
    // bounding-box widget queries `GetVisibility` when toggling with no
    // argument, which is the path every test here takes.
    const widget = {
        observe: jest.fn(),
        On: jest.fn(async () => undefined),
        Off: jest.fn(async () => undefined),
        GetVisibility: jest.fn(async () => 0),
        SetVisibility: jest.fn(async () => undefined),
        SetBounds: jest.fn(async () => undefined),
        // Distinctive hand-written literals. They stand in for the
        // *representation's* origin and normal, and they are deliberately
        // nothing any default would produce, so a payload carrying them can
        // only have come from reading the representation back.
        GetOrigin: jest.fn(async () => [1.5, -2.5, 3.5]),
        GetNormal: jest.fn(async () => [0, 1, 0]),
        SetOrigin: jest.fn(async () => undefined),
        SetNormal: jest.fn(async () => undefined),
    };
    return { actor, property, widget };
}

/**
 * A scene-graph stand-in for `attachSceneGraph`.
 *
 * `EdgesWidget` enumerates `descendantActorNodesOrSelfArray` and calls the
 * renderer's own per-actor `setEdgeVisibilityAsync` for each node's `id`;
 * `BoundingBoxWidget` enumerates the same array when recomputing bounds.
 * Neither is the subject of the send tests -- what those pin is the *send*
 * that follows the local write, and they pass an empty actor list so the
 * fan-out reaches nothing.
 */
function makeSceneGraphDouble(actorIds: number[] = []) {
    return {
        descendantActorNodesOrSelfArray: actorIds.map((id) => ({ id })),
    };
}

async function makeRenderer(
    sender: TrameTriggerSender | null,
    parallelProjection: number = PERSPECTIVE,
    actorIds: number[] = []
) {
    const objects = makeFakeWasmObjects();
    const camera = {
        GetParallelProjection: jest.fn(async () => parallelProjection),
        ParallelProjectionOn: jest.fn(async () => undefined),
        ParallelProjectionOff: jest.fn(async () => undefined),
    };
    const scene = {
        canvasDiv: document.createElement('div'),
        render: jest.fn(),
        clearObserversAndEventListeners: jest.fn(),
        camera,
        getVtkObject: (wasmId: number) => {
            switch (wasmId) {
                case ACTOR_ID:
                    return objects.actor;
                case PROPERTY_ID:
                    return objects.property;
                default:
                    return objects.widget;
            }
        },
    };
    const renderer = await WasmRenderer.createAsync(
        scene as unknown as VtkScene,
        makeAnnotation(),
        sender
    );
    const sceneGraph = makeSceneGraphDouble(actorIds);
    renderer.attachSceneGraph(sceneGraph as unknown as VisorSceneNodeExtended);
    return { renderer, camera, sceneGraph, ...objects };
}

/** A sender that records its calls and resolves. */
function makeSender() {
    return jest.fn(async () => undefined) as unknown as jest.Mock & TrameTriggerSender;
}

describe('WasmRenderer widget sends: trigger name and settled value', () => {
    // Every widget starts at its constructor default of `false`, so a call
    // with no argument settles on `true`. `true` is the hand-written literal
    // expected below; nothing here asks a widget what it settled on.
    test('setCrossSectionVisibilityAsync with no argument sends set_cross_section_visibility with the settled value', async () => {
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.setCrossSectionVisibilityAsync();

        expect(sender).toHaveBeenCalledTimes(1);
        expect(sender).toHaveBeenCalledWith('set_cross_section_visibility', {
            visible: true,
        });
    });

    test('setEdgeVisibilityGlobalAsync with no argument sends set_edges_visible with the settled value', async () => {
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.setEdgeVisibilityGlobalAsync();

        expect(sender).toHaveBeenCalledTimes(1);
        expect(sender).toHaveBeenCalledWith('set_edges_visible', {
            visible: true,
        });
    });

    test('setBoundingBoxVisibilityAsync with no argument sends set_bounding_box_visibility with the settled value', async () => {
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.setBoundingBoxVisibilityAsync();

        expect(sender).toHaveBeenCalledTimes(1);
        expect(sender).toHaveBeenCalledWith('set_bounding_box_visibility', {
            visible: true,
        });
    });

    test('setOrthographicModeAsync with no argument sends set_projection with the settled value', async () => {
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.setOrthographicModeAsync();

        expect(sender).toHaveBeenCalledTimes(1);
        expect(sender).toHaveBeenCalledWith('set_projection', {
            parallel: true,
        });
    });
});

describe('WasmRenderer widget sends: no sender, and a failing sender', () => {
    test('the four widget sends are no-ops that do not throw with no sender injected', async () => {
        const { renderer } = await makeRenderer(null);

        await expect(renderer.setCrossSectionVisibilityAsync(true)).resolves.toBeUndefined();
        await expect(renderer.setEdgeVisibilityGlobalAsync(true)).resolves.toBeUndefined();
        await expect(renderer.setBoundingBoxVisibilityAsync(true)).resolves.toBeUndefined();
        await expect(renderer.setOrthographicModeAsync(true)).resolves.toBeUndefined();
    });

    test('a failed widget send is logged with the trigger name and carries no node id', async () => {
        // This log line is the only signal a failed widget send produces. It
        // is deliberately a different prefix from the per-part helper's, and
        // it names no node, because a widget trigger has none -- a sentinel
        // id here would be fiction in the one message that has to be true.
        const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
        const sender = jest.fn(async () => {
            throw new Error('socket closed');
        }) as unknown as TrameTriggerSender;
        const { renderer } = await makeRenderer(sender);

        await expect(renderer.setOrthographicModeAsync(true)).resolves.toBeUndefined();

        expect(consoleError).toHaveBeenCalledTimes(1);
        const message = String(consoleError.mock.calls[0][0]);
        expect(message).toContain('[VISOR] widget trigger send failed:');
        expect(message).toContain("trigger='set_projection'");
        expect(message).not.toContain('nodeId');

        consoleError.mockRestore();
    });
});

describe('WasmRenderer edge fan-out reaches every actor on every call', () => {
    test('setEdgeVisibilityGlobalAsync issues one per-actor call per actor on every call, not only when the value changes', async () => {
        // The per-node cache that D1 deleted lived on the scene-graph node
        // and had no invalidation, so a second toggle to the same value was
        // a no-op and three of the six pairs below were absent. This is an
        // id set with its value, not a call count: a count would not say
        // which actors were reached.
        const { renderer } = await makeRenderer(makeSender(), PERSPECTIVE, FAN_OUT_ACTOR_IDS);
        const perActor = jest.spyOn(renderer, 'setEdgeVisibilityAsync');

        await renderer.setEdgeVisibilityGlobalAsync(true);
        await renderer.setEdgeVisibilityGlobalAsync(true);

        expect(perActor.mock.calls).toEqual([
            [11, true],
            [12, true],
            [13, true],
            [11, true],
            [12, true],
            [13, true],
        ]);

        perActor.mockRestore();
    });
});

describe('WasmRenderer.createAsync seeds the orthographic flag from the wasm camera', () => {
    test('isOrthographicEnabled is true when the wasm camera reports parallel, before any setter runs', async () => {
        const { renderer } = await makeRenderer(makeSender(), PARALLEL);

        expect(renderer.isOrthographicEnabled()).toBe(true);
    });

    test('isOrthographicEnabled is false when the wasm camera reports perspective', async () => {
        // The negative half. Without it, a seed hard-written to `true` would
        // pass the test above and be wrong on every perspective camera.
        const { renderer } = await makeRenderer(makeSender(), PERSPECTIVE);

        expect(renderer.isOrthographicEnabled()).toBe(false);
    });
});

describe('WasmRenderer reports the cross-section plane on the end-of-drag event', () => {
    // The event itself does not exist under jsdom, so what is pinned here is
    // the *registration*: which event the report is bound to, and what the
    // callback bound to it sends. Whether that event ever fires is MC-5's
    // subject and no gate reaches it.
    test('the plane report is registered on EndInteractionEvent and sends the representation plane once', async () => {
        const sender = makeSender();
        const { renderer, widget } = await makeRenderer(sender);

        const endCalls = widget.observe.mock.calls.filter(
            (call) => call[0] === 'EndInteractionEvent'
        );
        expect(endCalls).toHaveLength(1);

        await endCalls[0][1]();

        expect(sender).toHaveBeenCalledTimes(1);
        expect(sender).toHaveBeenCalledWith('sync_cross_section_plane', {
            origin: [1.5, -2.5, 3.5],
            normal: [0, 1, 0],
        });
        // `renderer` is held so the construction that registered the observer
        // is not mistaken for dead code by a future reader.
        expect(renderer.isCrossSectionVisible()).toBe(false);
    });

    test('no callback registered on InteractionEvent sends anything', async () => {
        // InteractionEvent fires many times across one drag. A report bound
        // to it would satisfy every other assertion in this module and flood
        // the trigger channel, which is a fault no other gate can see.
        const sender = makeSender();
        const { widget } = await makeRenderer(sender);

        const interactionCalls = widget.observe.mock.calls.filter(
            (call) => call[0] === 'InteractionEvent'
        );
        expect(interactionCalls.length).toBeGreaterThan(0);
        for (const call of interactionCalls) {
            await call[1]();
        }

        expect(sender).not.toHaveBeenCalled();
    });
});
