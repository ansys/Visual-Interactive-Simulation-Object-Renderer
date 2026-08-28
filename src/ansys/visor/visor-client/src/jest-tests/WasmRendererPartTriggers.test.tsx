import { WasmRenderer } from '../renderer/WasmRenderer';
import type { WasmRendererAnnotation } from '../renderer/RendererAnnotation';
import type VtkScene from '../wasm/VtkScene';
import type { TrameTriggerSender } from '../renderer/IRenderer';

/**
 * WasmRenderer's per-part *send* surface: the six methods that carry a
 * per-part mutation to the matching server trigger.
 *
 * Two things are pinned here, and they are pinned by separate tests on
 * purpose:
 *
 *   1. Each send calls the injected sender with the trigger name and the
 *      exact payload the server's model expects. Every expected payload is a
 *      hand-written literal; nothing here rebuilds a payload the way the code
 *      under test builds it.
 *
 *   2. Each existing per-part apply still mutates the wasm object it always
 *      mutated. A test that only checked the render would still pass if the
 *      send were dropped, and a test that only checked the send would still
 *      pass if the apply were broken, so neither is allowed to stand in for
 *      the other.
 *
 * Also pinned: with no sender injected the sends are no-ops that do not
 * throw, and a sender that rejects does not propagate out of a send.
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
    const lut = {
        SetHueRange: jest.fn(async () => undefined),
        SetVectorModeToMagnitude: jest.fn(async () => undefined),
    };
    const actor = {
        SetVisibility: jest.fn(async () => undefined),
    };
    const property = {
        SetAmbientColor: jest.fn(async () => undefined),
        SetAmbient: jest.fn(async () => undefined),
        SetDiffuse: jest.fn(async () => undefined),
        SetDiffuseColor: jest.fn(async () => undefined),
        SetOpacity: jest.fn(async () => undefined),
        SetEdgeColor: jest.fn(async () => undefined),
        EdgeVisibilityOn: jest.fn(async () => undefined),
        EdgeVisibilityOff: jest.fn(async () => undefined),
    };
    const mapper = {
        SetScalarModeToUsePointFieldData: jest.fn(async () => undefined),
        SetScalarModeToUseCellFieldData: jest.fn(async () => undefined),
        SetScalarRange: jest.fn(async () => undefined),
        SetColorModeToMapScalars: jest.fn(async () => undefined),
        ColorByArrayComponent: jest.fn(async () => undefined),
        SetScalarVisibility: jest.fn(async () => undefined),
        CreateDefaultLookupTable: jest.fn(async () => undefined),
        GetLookupTable: jest.fn(async () => lut),
    };
    const widget = {
        observe: jest.fn(),
        On: jest.fn(async () => undefined),
        Off: jest.fn(async () => undefined),
        GetOrigin: jest.fn(async () => [0, 0, 0]),
        GetNormal: jest.fn(async () => [0, 0, 1]),
        SetOrigin: jest.fn(async () => undefined),
        SetNormal: jest.fn(async () => undefined),
    };
    return { lut, actor, property, mapper, widget };
}

async function makeRenderer(sender: TrameTriggerSender | null) {
    const objects = makeFakeWasmObjects();
    const scene = {
        canvasDiv: document.createElement('div'),
        render: jest.fn(),
        clearObserversAndEventListeners: jest.fn(),
        getVtkObject: (wasmId: number) => {
            switch (wasmId) {
                case ACTOR_ID:
                    return objects.actor;
                case PROPERTY_ID:
                    return objects.property;
                case MAPPER_ID:
                    return objects.mapper;
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
    return { renderer, ...objects };
}

/** A sender that records its calls and resolves. */
function makeSender() {
    return jest.fn(async () => undefined) as unknown as jest.Mock &
        TrameTriggerSender;
}

describe('WasmRenderer per-part sends: trigger name and payload', () => {
    test('sendPartVisibilityAsync sends set_part_visibility with nodeId and visible', async () => {
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.sendPartVisibilityAsync(7, false);

        expect(sender).toHaveBeenCalledWith('set_part_visibility', {
            nodeId: 7,
            visible: false,
        });
    });

    test('sendPartOpacityAsync sends set_part_opacity with nodeId and opacity', async () => {
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.sendPartOpacityAsync(7, 0.25);

        expect(sender).toHaveBeenCalledWith('set_part_opacity', {
            nodeId: 7,
            opacity: 0.25,
        });
    });

    test('sendPartDiffuseColorAsync sends set_part_diffuse_color with the colour', async () => {
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.sendPartDiffuseColorAsync(7, [0.25, 0.5, 0.75]);

        expect(sender).toHaveBeenCalledWith('set_part_diffuse_color', {
            nodeId: 7,
            diffuseRgb: [0.25, 0.5, 0.75],
        });
    });

    test('sendPartDiffuseColorAsync sends an explicit null diffuseRgb key for a reset', async () => {
        // The key must be present and null. The server model gives diffuseRgb
        // no default, so an omitted key is a rejected message, not a clear.
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.sendPartDiffuseColorAsync(7, null);

        expect(sender).toHaveBeenCalledWith('set_part_diffuse_color', {
            nodeId: 7,
            diffuseRgb: null,
        });
        const payload = sender.mock.calls[0][1] as Record<string, unknown>;
        expect(Object.prototype.hasOwnProperty.call(payload, 'diffuseRgb')).toBe(true);
    });

    test('sendPartSelectedAsync sends set_part_selected with nodeId and selected', async () => {
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.sendPartSelectedAsync(7, true);

        expect(sender).toHaveBeenCalledWith('set_part_selected', {
            nodeId: 7,
            selected: true,
        });
    });

    test('sendPartSelectedAsync carries no colour', async () => {
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.sendPartSelectedAsync(7, true);

        const payload = sender.mock.calls[0][1] as Record<string, unknown>;
        expect(Object.keys(payload).sort()).toEqual(['nodeId', 'selected']);
    });

    test('sendPartColorVariableAsync maps the descriptor onto the wire keys', async () => {
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.sendPartColorVariableAsync(7, {
            spectrumId: 'POINT::pressure::1',
            spectrumType: 'POINT',
            spectrumName: 'pressure',
            component: 0,
            min: 2,
            max: 8,
        });

        expect(sender).toHaveBeenCalledWith('set_part_color_variable', {
            nodeId: 7,
            variableId: 'POINT::pressure::1',
            association: 'POINT',
            arrayName: 'pressure',
            component: 0,
            min: 2,
            max: 8,
        });
    });

    test('sendPartColorVariableAsync sends CELL as the association for a cell array', async () => {
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.sendPartColorVariableAsync(7, {
            spectrumId: 'CELL::temperature::3',
            spectrumType: 'CELL',
            spectrumName: 'temperature',
            component: -1,
            min: -1.5,
            max: 4.5,
        });

        expect(sender).toHaveBeenCalledWith('set_part_color_variable', {
            nodeId: 7,
            variableId: 'CELL::temperature::3',
            association: 'CELL',
            arrayName: 'temperature',
            component: -1,
            min: -1.5,
            max: 4.5,
        });
    });

    test('sendPartColorVariableAsync forwards variableId verbatim without parsing it', async () => {
        // An id that would not survive being split and rebuilt: it is carried
        // as an opaque token, and the association and array name travel in
        // their own fields precisely so that nothing has to decompose it.
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.sendPartColorVariableAsync(7, {
            spectrumId: 'not::a::parseable::id::at::all',
            spectrumType: 'POINT',
            spectrumName: 'pressure',
            component: 0,
            min: 0,
            max: 1,
        });

        const payload = sender.mock.calls[0][1] as Record<string, unknown>;
        expect(payload.variableId).toBe('not::a::parseable::id::at::all');
        expect(payload.association).toBe('POINT');
        expect(payload.arrayName).toBe('pressure');
    });

    test('sendClearPartColorVariableAsync sends clear_part_color_variable with only nodeId', async () => {
        const sender = makeSender();
        const { renderer } = await makeRenderer(sender);

        await renderer.sendClearPartColorVariableAsync(7);

        expect(sender).toHaveBeenCalledWith('clear_part_color_variable', {
            nodeId: 7,
        });
    });
});

describe('WasmRenderer per-part applies still mutate their wasm objects', () => {
    test('setVisibilityAsync still sets visibility on the actor', async () => {
        const { renderer, actor } = await makeRenderer(makeSender());

        await renderer.setVisibilityAsync(NODE_ID, false);

        expect(actor.SetVisibility).toHaveBeenCalledWith(0);
    });

    test('setOpacityAsync still sets opacity on the property', async () => {
        const { renderer, property } = await makeRenderer(makeSender());

        await renderer.setOpacityAsync(NODE_ID, 0.25);

        expect(property.SetOpacity).toHaveBeenCalledWith(0.25);
    });

    test('setDiffuseColorRgbAsync still sets the diffuse colour on the property', async () => {
        const { renderer, property } = await makeRenderer(makeSender());

        await renderer.setDiffuseColorRgbAsync(NODE_ID, 0.25, 0.5, 0.75, false);

        expect(property.SetDiffuseColor).toHaveBeenCalledWith(0.25, 0.5, 0.75);
    });

    test('setSelectedAsync still applies the selection tint and lighting', async () => {
        const { renderer, property } = await makeRenderer(makeSender());

        await renderer.setSelectedAsync(NODE_ID, true, [1, 0, 0]);

        expect(property.SetAmbientColor).toHaveBeenCalledWith([0 / 255, 62 / 255, 111 / 255]);
        expect(property.SetDiffuse).toHaveBeenCalledWith(0.5);
        expect(property.SetAmbient).toHaveBeenCalledWith(0.5);
        expect(property.SetDiffuseColor).toHaveBeenCalledWith(1, 0, 0);
    });

    test('setColorVariableAsync still configures the mapper and the default table', async () => {
        const { renderer, mapper, lut } = await makeRenderer(makeSender());

        await renderer.setColorVariableAsync(NODE_ID, {
            spectrumId: 'POINT::pressure::1',
            spectrumType: 'POINT',
            spectrumName: 'pressure',
            component: 0,
            min: 2,
            max: 8,
        });

        expect(mapper.SetScalarModeToUsePointFieldData).toHaveBeenCalled();
        expect(mapper.SetScalarRange).toHaveBeenCalledWith(2, 8);
        expect(mapper.SetColorModeToMapScalars).toHaveBeenCalled();
        expect(mapper.ColorByArrayComponent).toHaveBeenCalledWith('pressure', 0);
        expect(mapper.SetScalarVisibility).toHaveBeenCalledWith(1);
        expect(mapper.CreateDefaultLookupTable).toHaveBeenCalled();
        expect(lut.SetHueRange).toHaveBeenCalledWith(0.667, 0.0);
        expect(lut.SetVectorModeToMagnitude).toHaveBeenCalled();
    });

    test('clearColorVariableAsync still turns scalar visibility off', async () => {
        const { renderer, mapper } = await makeRenderer(makeSender());

        await renderer.clearColorVariableAsync(NODE_ID);

        expect(mapper.SetScalarVisibility).toHaveBeenCalledWith(0);
    });
});

describe('WasmRenderer sends when no sender is injected', () => {
    test('all six sends are no-ops that do not throw', async () => {
        const { renderer } = await makeRenderer(null);

        await expect(renderer.sendPartVisibilityAsync(7, true)).resolves.toBeUndefined();
        await expect(renderer.sendPartOpacityAsync(7, 0.5)).resolves.toBeUndefined();
        await expect(
            renderer.sendPartDiffuseColorAsync(7, [1, 0, 0])
        ).resolves.toBeUndefined();
        await expect(renderer.sendPartSelectedAsync(7, true)).resolves.toBeUndefined();
        await expect(
            renderer.sendPartColorVariableAsync(7, {
                spectrumId: 'POINT::pressure::1',
                spectrumType: 'POINT',
                spectrumName: 'pressure',
                component: 0,
                min: 2,
                max: 8,
            })
        ).resolves.toBeUndefined();
        await expect(renderer.sendClearPartColorVariableAsync(7)).resolves.toBeUndefined();
    });

    test('a send touches no wasm object', async () => {
        const { renderer, actor, property, mapper } = await makeRenderer(null);

        await renderer.sendPartVisibilityAsync(NODE_ID, false);
        await renderer.sendPartOpacityAsync(NODE_ID, 0.25);
        await renderer.sendPartSelectedAsync(NODE_ID, true);

        expect(actor.SetVisibility).not.toHaveBeenCalled();
        expect(property.SetOpacity).not.toHaveBeenCalled();
        expect(property.SetAmbientColor).not.toHaveBeenCalled();
        expect(mapper.SetScalarVisibility).not.toHaveBeenCalled();
    });
});

describe('WasmRenderer sends when the sender rejects', () => {
    test('the rejection does not propagate out of the send', async () => {
        const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
        const sender = jest.fn(async () => {
            throw new Error('socket closed');
        }) as unknown as TrameTriggerSender;
        const { renderer } = await makeRenderer(sender);

        await expect(renderer.sendPartOpacityAsync(7, 0.25)).resolves.toBeUndefined();

        consoleError.mockRestore();
    });

    test('the failure is logged with the trigger name and the node id', async () => {
        // This log line is the only signal a failed send produces: the render
        // looks identical either way, so the message must name what failed and
        // for which part, under a fixed prefix that can be grepped.
        const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
        const sender = jest.fn(async () => {
            throw new Error('socket closed');
        }) as unknown as TrameTriggerSender;
        const { renderer } = await makeRenderer(sender);

        await renderer.sendPartOpacityAsync(7, 0.25);

        expect(consoleError).toHaveBeenCalledTimes(1);
        const message = String(consoleError.mock.calls[0][0]);
        expect(message).toContain('[VISOR] per-part trigger send failed:');
        expect(message).toContain("trigger='set_part_opacity'");
        expect(message).toContain('nodeId=7');

        consoleError.mockRestore();
    });

    test('a non-Error rejection is caught too', async () => {
        // The catch is unnarrowed on purpose: any rejection, of any shape, is
        // a failed send.
        const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
        const sender = jest.fn(async () => {
            throw 'not an Error';
        }) as unknown as TrameTriggerSender;
        const { renderer } = await makeRenderer(sender);

        await expect(renderer.sendPartVisibilityAsync(7, true)).resolves.toBeUndefined();
        expect(consoleError).toHaveBeenCalledTimes(1);

        consoleError.mockRestore();
    });
});

