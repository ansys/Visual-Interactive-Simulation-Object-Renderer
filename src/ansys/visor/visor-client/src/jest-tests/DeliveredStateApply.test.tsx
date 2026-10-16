import { VisorFrontend } from '../VisorFrontend';
import type { IRenderer } from '../renderer/IRenderer';
import type VisorVtkSceneNode from '../state/appstate/vtkInfo/VisorVtkSceneNode.tsx';
import type VisorSceneState from '../state/appstate/VisorSceneState.tsx';
import { deliveredPart, deliveredScene } from './deliveredSceneFixture.ts';

/**
 * The client applies the state it is delivered and holds no values of its
 * own: a part node is built from its delivered record, a delivered null
 * colour variable removes the colouring, a delivered colour that matches the
 * node sends nothing, and a reference to a variable the client does not hold
 * is recorded and reported rather than applied.
 *
 * Expected values are hand-written literals.
 */

const PART_A_ID = 1;
const PRESSURE_ID = 'POINT::pressure::1';
const TENSOR5_ID = 'POINT::tensor5::5';

/** A complete wire record for `pressure`, listing part A. */
function pressureRecord(): Record<string, unknown> {
    return {
        id: PRESSURE_ID,
        arrayName: 'pressure',
        type: 'POINT',
        numComponents: 1,
        partIds: [PART_A_ID],
        defaultMagnitudeRange: [0, 10],
        defaultRanges: [[0, 10]],
        magnitudeRange: [2, 8],
        ranges: [[2, 8]],
    };
}

/** A complete wire record of a width the client has no labels for, so it is not held. */
function tensor5Record(): Record<string, unknown> {
    return {
        id: TENSOR5_ID,
        arrayName: 'tensor5',
        type: 'POINT',
        numComponents: 5,
        partIds: [PART_A_ID],
        defaultMagnitudeRange: [0, 1],
        defaultRanges: [
            [0, 1],
            [0, 1],
            [0, 1],
            [0, 1],
            [0, 1],
        ],
        magnitudeRange: [0, 1],
        ranges: [
            [0, 1],
            [0, 1],
            [0, 1],
            [0, 1],
            [0, 1],
        ],
    };
}

function makeSceneGraphNode() {
    return {
        id: 0,
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
                dataArrays: [],
                name: 'part-a',
                isGroupNode: false,
                isActorNode: true,
                nodeType: 'vtkUnstructuredGrid',
                diffuseColor: [1, 1, 1],
                bounds: [],
                children: [],
            },
        ],
    };
}

/**
 * Every renderer member the constructor, the part loop, its node methods and
 * the widget toggles reach.
 */
function makeRendererDouble() {
    return {
        attachSceneGraph: jest.fn(),
        domElement: document.createElement('div'),
        addCameraSettledListener: jest.fn(() => jest.fn()),
        addViewerClickedListener: jest.fn(() => jest.fn()),
        resizeAsync: jest.fn(async () => undefined),
        setVisibilityAsync: jest.fn(async () => undefined),
        sendPartVisibilityAsync: jest.fn(async () => undefined),
        setOpacityAsync: jest.fn(async () => undefined),
        sendPartOpacityAsync: jest.fn(async () => undefined),
        setSelectedAsync: jest.fn(async () => undefined),
        sendPartSelectedAsync: jest.fn(async () => undefined),
        setDiffuseColorRgbAsync: jest.fn(async () => undefined),
        sendPartDiffuseColorAsync: jest.fn(async () => undefined),
        setColorVariableAsync: jest.fn(async () => undefined),
        sendPartColorVariableAsync: jest.fn(async () => undefined),
        clearColorVariableAsync: jest.fn(async () => undefined),
        sendClearPartColorVariableAsync: jest.fn(async () => undefined),
        setScalarRangeAsync: jest.fn(async () => undefined),
        applyCrossSectionVisibilityAsync: jest.fn(async () => undefined),
        applyEdgeVisibilityGlobalAsync: jest.fn(async () => undefined),
        applyBoundingBoxVisibilityAsync: jest.fn(async () => undefined),
        setCrossSectionVisibilityAsync: jest.fn(async () => undefined),
        setEdgeVisibilityGlobalAsync: jest.fn(async () => undefined),
        setBoundingBoxVisibilityAsync: jest.fn(async () => undefined),
    };
}

function makeFrontend(scene: VisorSceneState) {
    const renderer = makeRendererDouble();
    const frontend = new VisorFrontend(
        renderer as unknown as IRenderer,
        makeSceneGraphNode() as unknown as VisorVtkSceneNode,
        scene,
        jest.fn(async () => undefined)
    );
    const partA = frontend.sceneGraph.descendantActorNodesOrSelfDictionary[PART_A_ID];
    return { frontend, renderer, partA };
}

/** A delivery holding the given variable records and part A's record. */
function delivery(variableStates: Record<string, unknown>, partA: Record<string, unknown>) {
    return {
        scene: {
            variableStates,
            datasetStates: { '0': { id: '0', partStates: { '1': partA } } },
        },
    };
}

/** A delivery referencing the variable the client does not hold. */
function deliveryReferencingTensor5() {
    return delivery(
        { [TENSOR5_ID]: tensor5Record() },
        deliveredPart(PART_A_ID, {
            colorVariable: { variableId: TENSOR5_ID, variableComponent: -1 },
        })
    );
}

const TENSOR5_NOT_HELD_WARNING =
    "Part 1 references variable 'POINT::tensor5::5', which is not held; the part is not coloured by it";

describe('the client applies delivered state as given', () => {
    test('a delivered record with visible false, opacity 0.25 and selected false applies as given on a fresh node', () => {
        const { partA } = makeFrontend(
            deliveredScene(
                deliveredPart(PART_A_ID, { visible: false, opacity: 0.25, selected: false })
            )
        );

        expect(partA.visible).toBe(false);
        expect(partA.opacity).toBe(0.25);
        expect(partA.selected).toBe(false);
    });

    test('a delivered colorVariable null turns scalar coloring off and the delivered diffuse color shows', async () => {
        const { frontend, renderer } = makeFrontend(
            deliveredScene(
                deliveredPart(PART_A_ID, {
                    colorVariable: { variableId: PRESSURE_ID, variableComponent: -1 },
                })
            )
        );

        await frontend.setAppStateAsync(
            delivery(
                { [PRESSURE_ID]: pressureRecord() },
                deliveredPart(PART_A_ID, { colorVariable: null, diffuseRgb: [0.25, 0.5, 0.75] })
            ),
            false
        );

        expect(renderer.clearColorVariableAsync).toHaveBeenCalledWith(1);
        expect(renderer.setDiffuseColorRgbAsync).toHaveBeenCalledWith(1, 0.25, 0.5, 0.75, false);
    });

    test("setDiffuseColorRgbAsync with the node's current color sends nothing", async () => {
        const { renderer, partA } = makeFrontend(
            deliveredScene(deliveredPart(PART_A_ID, { diffuseRgb: [0.25, 0.5, 0.75] }))
        );

        await partA.setDiffuseColorRgbAsync(0.25, 0.5, 0.75);

        expect(renderer.sendPartDiffuseColorAsync).not.toHaveBeenCalled();
    });

    test('a delivered reference to a hidden variable warns once and sends nothing', async () => {
        const { frontend, renderer } = makeFrontend(deliveredScene(deliveredPart(PART_A_ID)));
        const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
        try {
            await frontend.setAppStateAsync(deliveryReferencingTensor5(), false);

            const nodeWarnings = warn.mock.calls.filter(
                ([message]) => message === TENSOR5_NOT_HELD_WARNING
            );
            expect(nodeWarnings).toHaveLength(1);
            expect(renderer.sendPartColorVariableAsync).not.toHaveBeenCalled();
            expect(renderer.setColorVariableAsync).not.toHaveBeenCalled();
        } finally {
            warn.mockRestore();
        }
    });

    test('a delivered reference to a hidden variable is recorded on the node', async () => {
        const { frontend, partA } = makeFrontend(deliveredScene(deliveredPart(PART_A_ID)));
        const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
        try {
            await frontend.setAppStateAsync(deliveryReferencingTensor5(), false);

            expect(partA.variableId).toBe('POINT::tensor5::5');
            expect(partA.variableComponent).toBe(-1);
        } finally {
            warn.mockRestore();
        }
    });
});

/** How many times each of the six per-part send members was called. */
function sendCallCounts(renderer: ReturnType<typeof makeRendererDouble>) {
    return {
        sendPartVisibilityAsync: renderer.sendPartVisibilityAsync.mock.calls.length,
        sendPartOpacityAsync: renderer.sendPartOpacityAsync.mock.calls.length,
        sendPartSelectedAsync: renderer.sendPartSelectedAsync.mock.calls.length,
        sendPartDiffuseColorAsync: renderer.sendPartDiffuseColorAsync.mock.calls.length,
        sendPartColorVariableAsync: renderer.sendPartColorVariableAsync.mock.calls.length,
        sendClearPartColorVariableAsync: renderer.sendClearPartColorVariableAsync.mock.calls.length,
    };
}

const NO_SENDS = {
    sendPartVisibilityAsync: 0,
    sendPartOpacityAsync: 0,
    sendPartSelectedAsync: 0,
    sendPartDiffuseColorAsync: 0,
    sendPartColorVariableAsync: 0,
    sendClearPartColorVariableAsync: 0,
};

/** A delivery holding `pressure` and a part A record differing from the fixture's in every field. */
function deliveryDifferingInEveryField() {
    return delivery(
        { [PRESSURE_ID]: pressureRecord() },
        deliveredPart(PART_A_ID, {
            visible: false,
            opacity: 0.25,
            selected: true,
            diffuseRgb: [0.25, 0.5, 0.75],
            colorVariable: { variableId: PRESSURE_ID, variableComponent: -1 },
        })
    );
}

describe('delivered state is applied without sending', () => {
    test('a delivered record differing in every part field sends no per-part trigger', async () => {
        const { frontend, renderer } = makeFrontend(deliveredScene(deliveredPart(PART_A_ID)));

        await frontend.setAppStateAsync(deliveryDifferingInEveryField(), false);

        expect(sendCallCounts(renderer)).toEqual(NO_SENDS);
    });

    test('a delivered record differing in every part field reaches the renderer', async () => {
        // Guards the test above: a delivery that applied nothing would also send nothing.
        const { frontend, renderer } = makeFrontend(deliveredScene(deliveredPart(PART_A_ID)));

        await frontend.setAppStateAsync(deliveryDifferingInEveryField(), false);

        expect(renderer.setVisibilityAsync.mock.calls).toEqual([[1, false]]);
        expect(renderer.setOpacityAsync.mock.calls).toEqual([[1, 0.25]]);
        expect(renderer.setDiffuseColorRgbAsync.mock.calls).toEqual([[1, 0.25, 0.5, 0.75, false]]);
        expect(renderer.setSelectedAsync.mock.calls).toEqual([[1, true, [0.25, 0.5, 0.75]]]);
        expect(renderer.setColorVariableAsync.mock.calls).toEqual([
            [
                1,
                {
                    variableId: 'POINT::pressure::1',
                    variableType: 'POINT',
                    variableName: 'pressure',
                    component: -1,
                    min: 2,
                    max: 8,
                },
            ],
        ]);
    });

    test('a delivered colorVariable null on a coloured part clears it without sending', async () => {
        const { frontend, renderer } = makeFrontend(
            deliveredScene(
                deliveredPart(PART_A_ID, {
                    colorVariable: { variableId: PRESSURE_ID, variableComponent: -1 },
                })
            )
        );

        await frontend.setAppStateAsync(
            delivery({ [PRESSURE_ID]: pressureRecord() }, deliveredPart(PART_A_ID)),
            false
        );

        expect(renderer.clearColorVariableAsync.mock.calls).toEqual([[1]]);
        expect(sendCallCounts(renderer)).toEqual(NO_SENDS);
    });

    test('the three delivered widget toggles are applied through the apply members and not the setters', async () => {
        const { frontend, renderer } = makeFrontend(deliveredScene(deliveredPart(PART_A_ID)));

        await frontend.setAppStateAsync(
            { scene: { crossSectionEnabled: true, edgesEnabled: false, boundingBoxEnabled: true } },
            false
        );

        expect(renderer.applyCrossSectionVisibilityAsync.mock.calls).toEqual([[true]]);
        expect(renderer.applyEdgeVisibilityGlobalAsync.mock.calls).toEqual([[false]]);
        expect(renderer.applyBoundingBoxVisibilityAsync.mock.calls).toEqual([[true]]);
        expect(renderer.setCrossSectionVisibilityAsync).not.toHaveBeenCalled();
        expect(renderer.setEdgeVisibilityGlobalAsync).not.toHaveBeenCalled();
        expect(renderer.setBoundingBoxVisibilityAsync).not.toHaveBeenCalled();
    });

    test('setColorVariableAsync on the slot the node holds, with a different range, applies the range and sends nothing', async () => {
        // The node is built holding pressure's magnitude slot with no range
        // applied; the delivery below holds the record and touches no part.
        const { frontend, renderer, partA } = makeFrontend(
            deliveredScene(
                deliveredPart(PART_A_ID, {
                    colorVariable: { variableId: PRESSURE_ID, variableComponent: -1 },
                })
            )
        );
        await frontend.setAppStateAsync(
            { scene: { variableStates: { [PRESSURE_ID]: pressureRecord() } } },
            false
        );

        await partA.setColorVariableAsync(PRESSURE_ID, -1);

        expect(renderer.setScalarRangeAsync.mock.calls).toEqual([[1, 2, 8]]);
        expect(sendCallCounts(renderer)).toEqual(NO_SENDS);
    });
});
