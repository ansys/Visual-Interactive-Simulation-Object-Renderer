import { render, fireEvent, act, within } from '@testing-library/react';
import { VisorFrontend } from '../VisorFrontend';
import { Panel_TopRight } from '../components/ui-panels/Panel_TopRight';
import { Panel_TopRight_Util } from '../components/ui-panels/Panel_TopRight_Util.tsx';
import { getVariableManager } from '../state/VisorVariableManager.tsx';
import VisorAppState from '../state/appstate/VisorAppState.tsx';
import VisorVariableState from '../state/appstate/VisorVariableState.tsx';
import type { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import type { TreeViewUtil } from '../treeview/TreeView.tsx';
import type { IRenderer } from '../renderer/IRenderer';
import type VisorVtkSceneNode from '../state/appstate/vtkInfo/VisorVtkSceneNode.tsx';

/**
 * The client as a projection of server-owned variable records.
 *
 * Three subjects:
 *
 *   1. The variable manager holds the delivered records and nothing else.  A
 *      part's variables are the records that list it; a range is the record's
 *      slot, magnitude at component -1 and component i at i; nothing is
 *      widened or reset on the client; an incomplete record is refused.
 *
 *   2. `setAppStateAsync` holds a delivered variable block before the part
 *      loop, and only when the block is present: an absent block (a state the
 *      client produced itself, as a rebuild carries across) leaves the held
 *      records alone, and an empty block clears them.
 *
 *   3. The top-right panel re-reads the selection's ranges after every
 *      delivery, after the tree has synchronized, so a delivered range reaches
 *      the legend with no selection change.
 *
 *   4. The range trigger is sent once per edit, carrying the server's
 *      component convention, and never for a delivery.  A delivered range
 *      that differs from the one a part last applied reaches that part with
 *      no send at all.
 *
 * Expected values are hand-written literals.  The trigger-sender double
 * absorbs every send except in the range-trigger tests, which assert its
 * calls after clearing it and the renderer double at the end of their setup.
 *
 * jsdom has no `ResizeObserver` and jest here runs with no `setupFiles`, so
 * the stub below is this module's own.
 */

class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
}
(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub;

const PART_A_ID = 1;
const PART_B_ID = 2;
const PRESSURE_ID = 'POINT::pressure::1';
const TEMPERATURE_ID = 'POINT::temperature::1';
const VELOCITY_ID = 'POINT::velocity::2';

/** A complete wire record for `pressure`, custom range [2, 8] inside default [0, 10]. */
function pressureRecord(overrides: Record<string, unknown> = {}): Record<string, unknown> {
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
        ...overrides,
    };
}

/** A complete wire record for `temperature`, listing part B only. */
function temperatureRecord(): Record<string, unknown> {
    return {
        id: TEMPERATURE_ID,
        arrayName: 'temperature',
        type: 'POINT',
        numComponents: 1,
        partIds: [PART_B_ID],
        defaultMagnitudeRange: [-20, 100],
        defaultRanges: [[-20, 100]],
        magnitudeRange: [-20, 100],
        ranges: [[-20, 100]],
    };
}

/** A complete wire record for two-component `velocity`, listing part A. */
function velocityRecord(): Record<string, unknown> {
    return {
        id: VELOCITY_ID,
        arrayName: 'velocity',
        type: 'POINT',
        numComponents: 2,
        partIds: [PART_A_ID],
        defaultMagnitudeRange: [0, 10],
        defaultRanges: [
            [-1, 1],
            [-2, 2],
        ],
        magnitudeRange: [0, 10],
        ranges: [
            [-1, 1],
            [-2, 2],
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
 * Every renderer member the frontend's constructor, `getAppStateAsync`,
 * `setAppStateAsync`, the part's own methods and the mounted panel reach.
 */
function makeRendererDouble() {
    return {
        attachSceneGraph: jest.fn(),
        domElement: document.createElement('div'),
        addCameraSettledListener: jest.fn(() => jest.fn()),
        addViewerClickedListener: jest.fn(() => jest.fn()),
        renderAsync: jest.fn(async () => undefined),
        resizeAsync: jest.fn(async () => undefined),
        // Read by getAppStateAsync.
        isOrthographicEnabled: jest.fn(() => false),
        isCrossSectionVisible: jest.fn(() => false),
        areEdgesVisibleGlobally: jest.fn(() => true),
        isBoundingBoxVisible: jest.fn(() => false),
        getCameraStateAsync: jest.fn(async () => ({
            position: [0, 0, 1],
            focalPoint: [0, 0, 0],
            viewUp: [0, 1, 0],
            clippingRange: [0.1, 10],
            parallelProjection: false,
            viewAngle: 30,
            parallelScale: 1,
        })),
        getCrossSectionOriginAsync: jest.fn(async () => [0, 0, 0]),
        getCrossSectionNormalAsync: jest.fn(async () => [1, 0, 0]),
        // Written by setAppStateAsync.
        setOrthographicModeAsync: jest.fn(async () => undefined),
        setCrossSectionVisibilityAsync: jest.fn(async () => undefined),
        setEdgeVisibilityGlobalAsync: jest.fn(async () => undefined),
        setBoundingBoxVisibilityAsync: jest.fn(async () => undefined),
        setCameraPositionAsync: jest.fn(async () => undefined),
        setCameraFocalPointAsync: jest.fn(async () => undefined),
        setCameraViewUpAsync: jest.fn(async () => undefined),
        setCameraClippingRangeAsync: jest.fn(async () => undefined),
        setCameraViewAngleAsync: jest.fn(async () => undefined),
        setCameraParallelScaleAsync: jest.fn(async () => undefined),
        setCrossSectionOriginAsync: jest.fn(async () => undefined),
        setCrossSectionNormalAsync: jest.fn(async () => undefined),
        // Reached through the part's own methods.
        setColorVariableAsync: jest.fn(async () => undefined),
        sendPartColorVariableAsync: jest.fn(async () => undefined),
        clearColorVariableAsync: jest.fn(async () => undefined),
        sendClearPartColorVariableAsync: jest.fn(async () => undefined),
        setScalarRangeAsync: jest.fn(async () => undefined),
        setDiffuseColorRgbAsync: jest.fn(async () => undefined),
        sendPartDiffuseColorAsync: jest.fn(async () => undefined),
        setSelectedAsync: jest.fn(async () => undefined),
        sendPartSelectedAsync: jest.fn(async () => undefined),
        setOpacityAsync: jest.fn(async () => undefined),
        sendPartOpacityAsync: jest.fn(async () => undefined),
        setVisibilityAsync: jest.fn(async () => undefined),
        sendPartVisibilityAsync: jest.fn(async () => undefined),
    };
}

type RendererDouble = ReturnType<typeof makeRendererDouble>;

type TriggerSenderDouble = jest.Mock<Promise<unknown>, [string, unknown]>;

function makeFrontend(): {
    frontend: VisorFrontend;
    renderer: RendererDouble;
    triggerSender: TriggerSenderDouble;
} {
    const renderer = makeRendererDouble();
    const triggerSender = jest.fn(async () => undefined) as unknown as TriggerSenderDouble;
    const frontend = new VisorFrontend(
        renderer as unknown as IRenderer,
        makeSceneGraphNode() as unknown as VisorVtkSceneNode,
        triggerSender
    );
    return { frontend, renderer, triggerSender };
}

/** The tree-view util members the frontend and the mounted panel reach. */
function makeTreeViewUtilDouble(
    selectedNodes: VisorSceneNodeExtended[],
    synchronize: () => void = () => {}
): TreeViewUtil<VisorSceneNodeExtended> {
    return {
        addSelectionChangeListener: jest.fn(() => jest.fn()),
        rows: [],
        rowUtilsMap: new Map(),
        selectedNodes,
        updateSelectedNodesArray: jest.fn(),
        synchronize,
    } as unknown as TreeViewUtil<VisorSceneNodeExtended>;
}

describe('the variable manager holds the delivered records', () => {
    test('a part collection lists exactly the held variables whose record lists the part', () => {
        const manager = getVariableManager();
        // Taken before the delivery: a frozen node keeps the collection it
        // was built with, so the collection has to be a live view.
        const partA = manager.getPartVariableCollection(PART_A_ID);
        const partB = manager.getPartVariableCollection(PART_B_ID);
        const partC = manager.getPartVariableCollection(3);

        manager.setRecords([
            new VisorVariableState(pressureRecord({ partIds: [PART_A_ID, PART_B_ID] })),
            new VisorVariableState(temperatureRecord()),
        ]);

        expect(partA.array.map((v) => v.id)).toEqual(['POINT::pressure::1']);
        expect(partB.array.map((v) => v.id)).toEqual([
            'POINT::pressure::1',
            'POINT::temperature::1',
        ]);
        expect(partC.array).toEqual([]);
        expect(partA.getVariable('POINT::temperature::1')).toBeNull();
        expect(partB.getVariable('POINT::temperature::1')?.name).toBe('temperature');
    });

    test('a second delivery replaces the default range rather than widening it', () => {
        const manager = getVariableManager();
        manager.setRecords([new VisorVariableState(pressureRecord())]);

        manager.setRecords([
            new VisorVariableState(
                pressureRecord({
                    defaultMagnitudeRange: [1, 5],
                    magnitudeRange: [1, 5],
                })
            ),
        ]);

        const variable = manager.getPartVariableCollection(PART_A_ID).getVariable(PRESSURE_ID)!;
        expect(variable.getRangeInfo(-1)).toEqual({ defaultRange: [1, 5], customRange: [1, 5] });
    });

    test('component -1 reads the magnitude slot and component i reads range i, default and custom apart', () => {
        const manager = getVariableManager();
        manager.setRecords([
            new VisorVariableState({
                id: 'POINT::velocity::2',
                arrayName: 'velocity',
                type: 'POINT',
                numComponents: 2,
                partIds: [PART_A_ID],
                defaultMagnitudeRange: [0, 10],
                defaultRanges: [
                    [-1, 1],
                    [-2, 2],
                ],
                magnitudeRange: [0, 5],
                ranges: [
                    [-0.5, 0.5],
                    [-1.5, 1.5],
                ],
            }),
        ]);

        const variable = manager
            .getPartVariableCollection(PART_A_ID)
            .getVariable('POINT::velocity::2')!;
        expect(variable.getRangeInfo(-1)).toEqual({ defaultRange: [0, 10], customRange: [0, 5] });
        expect(variable.getRangeInfo(0)).toEqual({
            defaultRange: [-1, 1],
            customRange: [-0.5, 0.5],
        });
        expect(variable.getRangeInfo(1)).toEqual({
            defaultRange: [-2, 2],
            customRange: [-1.5, 1.5],
        });
        expect(variable.getRangeInfo(2)).toBeNull();
        expect(variable.getRangeInfo(-2)).toBeNull();
    });

    test('a custom range written through one collection is read through every other', () => {
        const manager = getVariableManager();
        manager.finishAddingDataArrayMetadata();
        manager.setRecords([
            new VisorVariableState(pressureRecord({ partIds: [PART_A_ID, PART_B_ID] })),
        ]);

        manager
            .getPartVariableCollection(PART_A_ID)
            .getVariable(PRESSURE_ID)!
            .setCustomRange(-1, 3, 7);

        expect(manager.globalVariableCollection.getVariable(PRESSURE_ID)!.getRangeInfo(-1)).toEqual(
            { defaultRange: [0, 10], customRange: [3, 7] }
        );
        expect(
            manager.getPartVariableCollection(PART_B_ID).getVariable(PRESSURE_ID)!.getRangeInfo(-1)
        ).toEqual({ defaultRange: [0, 10], customRange: [3, 7] });
    });

    test('an incomplete record is refused, naming the field, and the held records are kept', () => {
        const manager = getVariableManager();
        manager.setRecords([new VisorVariableState(pressureRecord())]);
        const fields = [
            'id',
            'arrayName',
            'type',
            'numComponents',
            'partIds',
            'defaultMagnitudeRange',
            'defaultRanges',
            'magnitudeRange',
            'ranges',
        ];

        for (const field of fields) {
            const record = pressureRecord();
            delete record[field];
            expect(() => manager.setRecords([new VisorVariableState(record)])).toThrow(
                `'${field}'`
            );
        }
        expect(() =>
            manager.setRecords([
                new VisorVariableState(
                    pressureRecord({
                        numComponents: 2,
                        defaultRanges: [
                            [0, 10],
                            [0, 10],
                        ],
                        ranges: [[2, 8]],
                    })
                ),
            ])
        ).toThrow(`'ranges'`);

        const variable = manager.getPartVariableCollection(PART_A_ID).getVariable(PRESSURE_ID)!;
        expect(variable.getRangeInfo(-1)).toEqual({ defaultRange: [0, 10], customRange: [2, 8] });
    });
});

describe('setAppStateAsync holds a delivered variable block', () => {
    test('a part is coloured at the delivered custom range, not the default', async () => {
        const { frontend, renderer } = makeFrontend();

        // Delivered as an instance: the block has to survive the copy
        // `setAppStateAsync` makes of it.
        await frontend.setAppStateAsync(
            new VisorAppState({
                scene: {
                    variableStates: { [PRESSURE_ID]: pressureRecord() },
                    datasetStates: {
                        '0': {
                            id: '0',
                            partStates: {
                                '1': { id: '1', variableId: PRESSURE_ID, variableComponent: -1 },
                            },
                        },
                    },
                },
            }),
            false
        );

        expect(renderer.setColorVariableAsync).toHaveBeenCalledWith(PART_A_ID, {
            variableId: 'POINT::pressure::1',
            variableType: 'POINT',
            variableName: 'pressure',
            component: -1,
            min: 2,
            max: 8,
        });
    });

    test("the client's own state carried back leaves the held records untouched", async () => {
        // The client's own state carries `ui.darkTheme`, whose branch fetches
        // the two theme stylesheets; jsdom has no `fetch`.
        const globals = globalThis as unknown as { fetch: unknown };
        const originalFetch = globals.fetch;
        globals.fetch = jest.fn(async () => ({ text: async () => '' }));
        try {
            const { frontend } = makeFrontend();
            await frontend.setAppStateAsync(
                { scene: { variableStates: { [PRESSURE_ID]: pressureRecord() } } },
                false
            );

            await frontend.setAppStateAsync(await frontend.getAppStateAsync(), false);

            expect(
                frontend.globalVariableCollection.getVariable(PRESSURE_ID)?.getRangeInfo(-1)
            ).toEqual({
                defaultRange: [0, 10],
                customRange: [2, 8],
            });
        } finally {
            globals.fetch = originalFetch;
        }
    });

    test('a delivered empty block clears the held records', async () => {
        const { frontend } = makeFrontend();
        await frontend.setAppStateAsync(
            { scene: { variableStates: { [PRESSURE_ID]: pressureRecord() } } },
            false
        );

        await frontend.setAppStateAsync({ scene: { variableStates: {} } }, false);

        expect(frontend.globalVariableCollection.array).toEqual([]);
        expect(frontend.globalVariableCollection.getVariable(PRESSURE_ID)).toBeNull();
    });

    test('the top-right panel is refreshed after the tree synchronizes', async () => {
        const { frontend } = makeFrontend();
        const order: string[] = [];
        frontend.setTreeViewUtil(makeTreeViewUtilDouble([], () => order.push('synchronize')));
        const noop = () => {};
        frontend.setPanelTopRightUtil(
            new Panel_TopRight_Util(
                noop,
                noop,
                noop,
                noop,
                () => false,
                () => false,
                noop,
                () => 0,
                async () => {
                    order.push('refresh');
                }
            )
        );

        await frontend.setAppStateAsync({ scene: { variableStates: {} } }, true);

        expect(order).toEqual(['synchronize', 'refresh']);
    });
});

/**
 * A real frontend holding one delivered record, with part A coloured by the
 * given slot and selected in the tree, and the top-right panel mounted on it.
 */
async function mountOnDeliveredRecord(
    record: Record<string, unknown>,
    variableId: string,
    component: number
): Promise<{
    frontend: VisorFrontend;
    container: HTMLElement;
    triggerSender: TriggerSenderDouble;
}> {
    const { frontend, triggerSender } = makeFrontend();
    const part = frontend.sceneGraph.descendantActorNodesOrSelfDictionary[PART_A_ID];
    frontend.setTreeViewUtil(makeTreeViewUtilDouble([part]));
    await frontend.setAppStateAsync({ scene: { variableStates: { [variableId]: record } } }, false);
    await part.setColorVariableAsync(variableId, component);

    let container: HTMLElement = null!;
    await act(async () => {
        container = render(<Panel_TopRight visorState={frontend} onLoad={() => {}} />).container;
    });
    await frontend.panelTopRightUtilPromise;
    return { frontend, container, triggerSender };
}

/**
 * The legend's min or max row, located by its heading: the ids in this
 * component are `randomId()`-generated.
 */
function legendRow(container: HTMLElement, heading: 'Min' | 'Max') {
    const label = within(container).getByText(heading, { selector: 'div' }).closest('label')!;
    return {
        input: label.querySelector('input') as HTMLInputElement,
        reset: label.querySelector('a') as HTMLAnchorElement,
    };
}

/** Types a range into the legend and clicks Apply, then lets its handler settle. */
async function applyRange(container: HTMLElement, min: string, max: string): Promise<void> {
    legendRow(container, 'Min').input.value = min;
    legendRow(container, 'Max').input.value = max;
    const apply = within(container).getByText('Apply', { selector: 'button' });
    await act(async () => {
        fireEvent.click(apply);
        await new Promise((resolve) => setTimeout(resolve, 0));
    });
}

/** The `set_variable_range` sends among a trigger-sender double's calls. */
function rangeSends(triggerSender: TriggerSenderDouble): unknown[][] {
    return triggerSender.mock.calls.filter(([name]) => name === 'set_variable_range');
}

/** A delivery holding one `pressure` record and colouring part A by its magnitude. */
function deliveryColouringPartA(record: Record<string, unknown>) {
    return {
        scene: {
            variableStates: { [PRESSURE_ID]: record },
            datasetStates: {
                '0': {
                    id: '0',
                    partStates: {
                        '1': { id: '1', variableId: PRESSURE_ID, variableComponent: -1 },
                    },
                },
            },
        },
    };
}

describe('the legend follows a delivery with no selection change', () => {
    test('a delivered custom range is shown in the legend', async () => {
        const { frontend, container } = await mountOnDeliveredRecord(
            pressureRecord(),
            PRESSURE_ID,
            -1
        );
        expect(legendRow(container, 'Min').input.value).toBe('2');
        expect(legendRow(container, 'Max').input.value).toBe('8');

        await act(async () => {
            await frontend.setAppStateAsync(
                {
                    scene: {
                        variableStates: {
                            [PRESSURE_ID]: pressureRecord({ magnitudeRange: [3, 7] }),
                        },
                    },
                },
                true
            );
        });

        expect(legendRow(container, 'Min').input.value).toBe('3');
        expect(legendRow(container, 'Max').input.value).toBe('7');
    });

    test('reset shows the delivered default range', async () => {
        const { frontend, container } = await mountOnDeliveredRecord(
            pressureRecord(),
            PRESSURE_ID,
            -1
        );

        await act(async () => {
            await frontend.setAppStateAsync(
                {
                    scene: {
                        variableStates: {
                            [PRESSURE_ID]: pressureRecord({ defaultMagnitudeRange: [-1, 12] }),
                        },
                    },
                },
                true
            );
        });
        const minRow = legendRow(container, 'Min');
        await act(async () => {
            fireEvent.click(minRow.reset);
        });

        expect(minRow.input.value).toBe('-1');
    });
});

describe('the range trigger is sent for an edit and never for a delivery', () => {
    test('an apply click on the magnitude sends one set_variable_range with component -1', async () => {
        const { container, triggerSender } = await mountOnDeliveredRecord(
            pressureRecord(),
            PRESSURE_ID,
            -1
        );
        triggerSender.mockClear();

        await applyRange(container, '3', '7');

        expect(triggerSender.mock.calls).toEqual([
            [
                'set_variable_range',
                { variableId: 'POINT::pressure::1', component: -1, min: 3, max: 7 },
            ],
        ]);
    });

    test('an apply click on component 1 sends component 1', async () => {
        const { container, triggerSender } = await mountOnDeliveredRecord(
            velocityRecord(),
            VELOCITY_ID,
            1
        );
        triggerSender.mockClear();

        await applyRange(container, '-1', '1');

        expect(triggerSender.mock.calls).toEqual([
            [
                'set_variable_range',
                { variableId: 'POINT::velocity::2', component: 1, min: -1, max: 1 },
            ],
        ]);
    });

    test('a delivered push sends no set_variable_range', async () => {
        const { frontend, triggerSender } = makeFrontend();

        await frontend.setAppStateAsync(deliveryColouringPartA(pressureRecord()), false);

        expect(rangeSends(triggerSender)).toEqual([]);
    });

    test('a changed delivered range reaches a part already coloured by that slot, sending nothing', async () => {
        const { frontend, renderer, triggerSender } = makeFrontend();
        await frontend.setAppStateAsync(deliveryColouringPartA(pressureRecord()), false);
        renderer.setScalarRangeAsync.mockClear();
        renderer.sendPartColorVariableAsync.mockClear();
        triggerSender.mockClear();

        // Magnitude moves to [3, 7]; component 0 stays at [2, 8].
        await frontend.setAppStateAsync(
            deliveryColouringPartA(pressureRecord({ magnitudeRange: [3, 7] })),
            false
        );

        expect(renderer.setScalarRangeAsync.mock.calls).toEqual([[1, 3, 7]]);
        expect(renderer.sendPartColorVariableAsync).not.toHaveBeenCalled();
        expect(rangeSends(triggerSender)).toEqual([]);
    });

    test('a delivered range differing from the last edit reaches a part already coloured by that slot', async () => {
        const { frontend, renderer, triggerSender } = makeFrontend();
        await frontend.setAppStateAsync(deliveryColouringPartA(pressureRecord()), false);
        await frontend.setVariableRangeAsync(PRESSURE_ID, -1, 3, 7);
        renderer.setScalarRangeAsync.mockClear();
        renderer.sendPartColorVariableAsync.mockClear();
        triggerSender.mockClear();

        await frontend.setAppStateAsync(deliveryColouringPartA(pressureRecord()), false);

        expect(renderer.setScalarRangeAsync.mock.calls).toEqual([[1, 2, 8]]);
        expect(renderer.sendPartColorVariableAsync).not.toHaveBeenCalled();
        expect(rangeSends(triggerSender)).toEqual([]);
    });
});

/** Sets a panel `<select>` to a value and lets its change handler settle. */
async function chooseOption(select: HTMLSelectElement, value: string): Promise<void> {
    select.value = value;
    await act(async () => {
        fireEvent.change(select);
        await new Promise((resolve) => setTimeout(resolve, 0));
    });
}

/** The panel `<select>` holding an option with the given value. */
function selectHolding(container: HTMLElement, value: string): HTMLSelectElement {
    return container.querySelector(`select option[value="${value}"]`)!
        .parentElement as HTMLSelectElement;
}

describe('re-selection carries the node component only where it names an option', () => {
    test('a scalar is applied after re-selecting a part coloured by a vector component X', async () => {
        const { frontend, renderer } = makeFrontend();
        const part = frontend.sceneGraph.descendantActorNodesOrSelfDictionary[PART_A_ID];
        frontend.setTreeViewUtil(makeTreeViewUtilDouble([part]));
        await frontend.setAppStateAsync(
            {
                scene: {
                    variableStates: {
                        [VELOCITY_ID]: velocityRecord(),
                        [PRESSURE_ID]: pressureRecord(),
                    },
                },
            },
            false
        );
        await part.setColorVariableAsync(VELOCITY_ID, -1);

        let container: HTMLElement = null!;
        await act(async () => {
            container = render(<Panel_TopRight visorState={frontend} onLoad={() => {}} />).container;
        });
        const util = await frontend.panelTopRightUtilPromise;
        const warningSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
        try {
            await chooseOption(selectHolding(container, '0'), '0');
            await act(async () => {
                await util.refreshSelectionAsync();
            });
            renderer.sendPartColorVariableAsync.mockClear();

            await chooseOption(selectHolding(container, PRESSURE_ID), PRESSURE_ID);

            expect(renderer.sendPartColorVariableAsync.mock.calls).toEqual([
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
            expect(warningSpy).not.toHaveBeenCalledWith("invalid componentId: '0'");
        } finally {
            warningSpy.mockRestore();
        }
    });
});
