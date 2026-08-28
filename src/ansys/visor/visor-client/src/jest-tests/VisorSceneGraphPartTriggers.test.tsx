import { CreateVisorSceneGraph, VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import VisorVtkDataArray from '../state/appstate/vtkInfo/VisorVtkDataArray.tsx';
import type { IRenderer } from '../renderer/IRenderer';

/**
 * The scene graph's six user actions, each of which must now do two things:
 * apply to the client's own objects, as it always did, and send the matching
 * mutation to the server.
 *
 * Every action is covered by a *pair* of tests, one per half. That is not
 * redundancy: a single test asserting "both happened" would still pass if the
 * two were fused, and the failure this pairing exists to catch is a silently
 * dropped send, which the render cannot reveal because the client is still
 * painting the same result itself.
 *
 * Expected values here are hand-written literals. In particular the
 * colour-variable descriptor is written out rather than read back from the
 * spectrum, so the test cannot agree with the code by making the same mistake.
 */

const ROOT_ID = 0;
const PART_A_ID = 1;
const PART_B_ID = 2;

const VARIABLE_ID = 'POINT::pressure::1';

function makePressureArray(): VisorVtkDataArray {
    return new VisorVtkDataArray({
        indexForType: 0,
        type: 'POINT',
        name: 'pressure',
        numComponents: 1,
        magnitudeRange: [0, 10],
        ranges: [[2, 8]],
    });
}

function makeRendererDouble() {
    return {
        // The per-part applies that already existed.
        setVisibilityAsync: jest.fn(async () => undefined),
        setSelectedAsync: jest.fn(async () => undefined),
        setOpacityAsync: jest.fn(async () => undefined),
        setDiffuseColorRgbAsync: jest.fn(async () => undefined),
        resetDiffuseColorAsync: jest.fn(async () => undefined),
        setColorVariableAsync: jest.fn(async () => undefined),
        clearColorVariableAsync: jest.fn(async () => undefined),
        setEdgeVisibilityAsync: jest.fn(async () => undefined),
        setScalarRangeAsync: jest.fn(async () => undefined),
        // The per-part sends added for the server path.
        sendPartVisibilityAsync: jest.fn(async () => undefined),
        sendPartOpacityAsync: jest.fn(async () => undefined),
        sendPartDiffuseColorAsync: jest.fn(async () => undefined),
        sendPartSelectedAsync: jest.fn(async () => undefined),
        sendPartColorVariableAsync: jest.fn(async () => undefined),
        sendClearPartColorVariableAsync: jest.fn(async () => undefined),
    };
}

type RendererDouble = ReturnType<typeof makeRendererDouble>;

function makeGraph(renderer: RendererDouble): VisorSceneNodeExtended {
    return CreateVisorSceneGraph(
        {
            id: ROOT_ID,
            dataArrays: [],
            name: '',
            isGroupNode: true,
            isActorNode: false,
            nodeType: 'root',
            diffuseColor: [1, 1, 1],
            bounds: [],
            children: [
                {
                    id: PART_A_ID,
                    dataArrays: [makePressureArray()],
                    name: 'part-a',
                    isGroupNode: false,
                    isActorNode: true,
                    nodeType: 'vtkUnstructuredGrid',
                    diffuseColor: [1, 1, 1],
                    bounds: [],
                    children: [],
                },
                {
                    id: PART_B_ID,
                    dataArrays: [makePressureArray()],
                    name: 'part-b',
                    isGroupNode: false,
                    isActorNode: true,
                    nodeType: 'vtkUnstructuredGrid',
                    diffuseColor: [1, 1, 1],
                    bounds: [],
                    children: [],
                },
            ],
        },
        undefined,
        renderer as unknown as IRenderer
    );
}

function setUp() {
    const renderer = makeRendererDouble();
    const graph = makeGraph(renderer);
    const partA = graph.descendantActorNodesOrSelfDictionary[PART_A_ID];
    return { renderer, graph, partA };
}

describe('hide / show', () => {
    test('sends set_part_visibility for the part', async () => {
        const { renderer, partA } = setUp();

        await partA.setVisibilityAsync(false);

        expect(renderer.sendPartVisibilityAsync).toHaveBeenCalledWith(PART_A_ID, false);
    });

    test('still applies visibility to the client renderer', async () => {
        const { renderer, partA } = setUp();

        await partA.setVisibilityAsync(false);

        expect(renderer.setVisibilityAsync).toHaveBeenCalledWith(PART_A_ID, false);
    });
});

describe('opacity', () => {
    test('sends set_part_opacity for the part', async () => {
        const { renderer, partA } = setUp();

        await partA.setOpacityAsync(0.25);

        expect(renderer.sendPartOpacityAsync).toHaveBeenCalledWith(PART_A_ID, 0.25);
    });

    test('still applies opacity to the client renderer', async () => {
        const { renderer, partA } = setUp();

        await partA.setOpacityAsync(0.25);

        expect(renderer.setOpacityAsync).toHaveBeenCalledWith(PART_A_ID, 0.25);
    });
});

describe('custom colour, set by rgb', () => {
    test('sends the normalised colour', async () => {
        const { renderer, partA } = setUp();

        await partA.setDiffuseColorRgbAsync(0.25, 0.5, 0.75);

        expect(renderer.sendPartDiffuseColorAsync).toHaveBeenCalledWith(
            PART_A_ID,
            [0.25, 0.5, 0.75]
        );
    });

    test('still applies the colour to the client renderer', async () => {
        const { renderer, partA } = setUp();

        await partA.setDiffuseColorRgbAsync(0.25, 0.5, 0.75);

        expect(renderer.setDiffuseColorRgbAsync).toHaveBeenCalledWith(
            PART_A_ID,
            0.25,
            0.5,
            0.75,
            false
        );
    });
});

describe('custom colour, set by hex', () => {
    test('sends the normalised colour', async () => {
        const { renderer, partA } = setUp();

        await partA.setDiffuseColorHexAsync('#ff0000');

        expect(renderer.sendPartDiffuseColorAsync).toHaveBeenCalledWith(PART_A_ID, [1, 0, 0]);
    });

    test('still applies the colour to the client renderer', async () => {
        const { renderer, partA } = setUp();

        await partA.setDiffuseColorHexAsync('#ff0000');

        expect(renderer.setDiffuseColorRgbAsync).toHaveBeenCalledWith(PART_A_ID, 1, 0, 0, false);
    });
});

describe('custom colour, reset', () => {
    test('sends a null colour, not the default colour value', async () => {
        const { renderer, partA } = setUp();

        await partA.resetDiffuseColorAsync();

        expect(renderer.sendPartDiffuseColorAsync).toHaveBeenCalledWith(PART_A_ID, null);
    });

    test('still applies the reset to the client renderer', async () => {
        const { renderer, partA } = setUp();

        await partA.resetDiffuseColorAsync();

        expect(renderer.resetDiffuseColorAsync).toHaveBeenCalledWith(PART_A_ID, [1, 1, 1], false);
    });
});

describe('colour by variable', () => {
    test('sends the descriptor for the part', async () => {
        const { renderer, partA } = setUp();

        await partA.setColorVariableAsync(VARIABLE_ID, 0);

        expect(renderer.sendPartColorVariableAsync).toHaveBeenCalledWith(PART_A_ID, {
            spectrumId: 'POINT::pressure::1',
            spectrumType: 'POINT',
            spectrumName: 'pressure',
            component: 0,
            min: 2,
            max: 8,
        });
    });

    test('still applies the colour variable to the client renderer', async () => {
        const { renderer, partA } = setUp();

        await partA.setColorVariableAsync(VARIABLE_ID, 0);

        expect(renderer.setColorVariableAsync).toHaveBeenCalledWith(PART_A_ID, {
            spectrumId: 'POINT::pressure::1',
            spectrumType: 'POINT',
            spectrumName: 'pressure',
            component: 0,
            min: 2,
            max: 8,
        });
    });
});

describe('clear colour by variable', () => {
    test('sends clear_part_color_variable for the part', async () => {
        const { renderer, partA } = setUp();

        await partA.clearColorVariableAsync();

        expect(renderer.sendClearPartColorVariableAsync).toHaveBeenCalledWith(PART_A_ID);
    });

    test('still clears the colour variable on the client renderer', async () => {
        const { renderer, partA } = setUp();

        await partA.clearColorVariableAsync();

        expect(renderer.clearColorVariableAsync).toHaveBeenCalledWith(PART_A_ID);
    });
});

describe('selection', () => {
    test('sends set_part_selected for the part, with no colour', async () => {
        const { renderer, partA } = setUp();

        await partA.setSelectedAsync(true);

        expect(renderer.sendPartSelectedAsync).toHaveBeenCalledWith(PART_A_ID, true);
    });

    test('still applies the selection to the client renderer, with its colour', async () => {
        const { renderer, partA } = setUp();

        await partA.setSelectedAsync(true);

        expect(renderer.setSelectedAsync).toHaveBeenCalledWith(PART_A_ID, true, [1, 1, 1]);
    });
});

describe('group fan-out', () => {
    test('a group action sends for exactly the actor nodes beneath it', async () => {
        // Asserted as the set of node ids the sender saw, not as a count: the
        // design is deliberately insensitive to how many messages an action
        // produces, so a count would pin the wrong property.
        const { renderer, graph } = setUp();

        await graph.setVisibilityAsync(false);

        const ids = renderer.sendPartVisibilityAsync.mock.calls.map(
            (call) => (call as unknown as [number, boolean])[0]
        );
        expect(new Set(ids)).toEqual(new Set([PART_A_ID, PART_B_ID]));
        expect(ids).not.toContain(ROOT_ID);
    });

    test('a group action still applies to exactly the actor nodes beneath it', async () => {
        const { renderer, graph } = setUp();

        await graph.setVisibilityAsync(false);

        const ids = renderer.setVisibilityAsync.mock.calls.map(
            (call) => (call as unknown as [number, boolean])[0]
        );
        expect(new Set(ids)).toEqual(new Set([PART_A_ID, PART_B_ID]));
        expect(ids).not.toContain(ROOT_ID);
    });
});
