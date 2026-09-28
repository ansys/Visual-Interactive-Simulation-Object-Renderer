import { AggregateSelectionInfo } from '../aggregate/AggregateSelectionInfo.tsx';
import { AggregateVariableInfo } from '../aggregate/AggregateVariableInfo.tsx';
import type { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import type {
    VisorVariableCollection,
    VisorVariableComponentMetadata,
    VisorVariableInfo,
} from '../state/VisorVariableManager.tsx';
import type { FieldAssociation } from '../state/appstate/vtkInfo/VisorVtkDataArray.tsx';

describe('AggregateVariableInfo', () => {
    afterEach(() => {
        jest.restoreAllMocks();
    });

    test('exposes its variable ID and metadata', async () => {
        const variable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: variable.id,
                variableComponent: 0,
                spectra: [variable],
            }),
        ]);

        const result = selection.currentVariableInfo;

        expect(result).toBeInstanceOf(AggregateVariableInfo);
        expect(result?.id).toBe('POINT::velocity::3');
        expect(result?.metadata).toBe(variable);
    });

    test('creates one aggregate component option for each metadata component', async () => {
        const variable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: variable.id,
                variableComponent: 0,
                spectra: [variable],
            }),
        ]);

        const result = selection.currentVariableInfo!;

        expect([...result.componentOptions.keys()]).toEqual(['-1', '0', '1', '2']);

        expect(result.componentOptions.get('-1')?.id).toBe(-1);
        expect(result.componentOptions.get('0')?.id).toBe(0);
        expect(result.componentOptions.get('1')?.id).toBe(1);
        expect(result.componentOptions.get('2')?.id).toBe(2);
    });

    test('associates aggregate components with their metadata', async () => {
        const variable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: variable.id,
                variableComponent: 1,
                spectra: [variable],
            }),
        ]);

        const result = selection.currentVariableInfo!;
        const component = result.componentOptions.get('1')!;

        expect(component.metadata).toBe(variable.componentOptions[2]);
        expect(component.variableInfo).toBe(result);
    });

    test('selects the common component used by all actor nodes', async () => {
        const firstVariable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
        });

        const secondVariable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: firstVariable.id,
                variableComponent: 1,
                spectra: [firstVariable],
            }),
            createActorNode({
                variableId: secondVariable.id,
                variableComponent: 1,
                spectra: [secondVariable],
            }),
        ]);

        const result = selection.currentVariableInfo!;

        expect(result.displayComponentId).toBe(1);
        expect(result.currentComponentInfo).toBe(result.componentOptions.get('1'));
    });

    test('uses undefined when actor nodes have different components', async () => {
        const firstVariable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
        });

        const secondVariable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: firstVariable.id,
                variableComponent: 0,
                spectra: [firstVariable],
            }),
            createActorNode({
                variableId: secondVariable.id,
                variableComponent: 1,
                spectra: [secondVariable],
            }),
        ]);

        const result = selection.currentVariableInfo!;

        expect(result.displayComponentId).toBeUndefined();
        expect(result.currentComponentInfo).toBeUndefined();
    });

    test('defaults to the first component option when the selected component has no range', async () => {
        const variable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: variable.id,
                variableComponent: 999,
                spectra: [variable],
            }),
        ]);

        const result = selection.currentVariableInfo!;

        expect(result.displayComponentId).toBe(-1);
        expect(result.currentComponentInfo).toBe(result.componentOptions.get('-1'));
    });

    test("aggregates component ranges from each actor node's variable collection", async () => {
        const firstVariable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([
                [-1, createRange(0, 100, 10, 90)],
                [0, createRange(-10, 10, -5, 5)],
                [1, createRange(-20, 20, -15, 15)],
                [2, createRange(-30, 30, -25, 25)],
            ]),
        });

        const secondVariable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([
                [-1, createRange(0, 100, 10, 90)],
                [0, createRange(-10, 10, -5, 5)],
                [1, createRange(-20, 20, -15, 15)],
                [2, createRange(-30, 30, -25, 25)],
            ]),
        });

        const selection = await createSelection([
            createActorNode({
                variableId: firstVariable.id,
                variableComponent: 1,
                spectra: [firstVariable],
            }),
            createActorNode({
                variableId: secondVariable.id,
                variableComponent: 1,
                spectra: [secondVariable],
            }),
        ]);

        const component = selection.currentVariableInfo!.currentComponentInfo!;

        expect(component.displayVariableDefaultMin).toBe(-20);
        expect(component.displayVariableDefaultMax).toBe(20);
        expect(component.displayVariableMin).toBe(-15);
        expect(component.displayVariableMax).toBe(15);
    });

    test('marks differing component ranges as undefined', async () => {
        const firstVariable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0],
            ranges: new Map([
                [-1, createRange(0, 100, 10, 90)],
                [0, createRange(-10, 10, -5, 5)],
            ]),
        });

        const secondVariable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0],
            ranges: new Map([
                [-1, createRange(0, 100, 10, 90)],
                [0, createRange(-20, 20, -15, 5)],
            ]),
        });

        const selection = await createSelection([
            createActorNode({
                variableId: firstVariable.id,
                variableComponent: 0,
                spectra: [firstVariable],
            }),
            createActorNode({
                variableId: secondVariable.id,
                variableComponent: 0,
                spectra: [secondVariable],
            }),
        ]);

        const component = selection.currentVariableInfo!.currentComponentInfo!;

        expect(component.displayVariableDefaultMin).toBeUndefined();
        expect(component.displayVariableDefaultMax).toBeUndefined();
        expect(component.displayVariableMin).toBeUndefined();
        expect(component.displayVariableMax).toBe(5);
    });

    test('warns when a displayed component has range data but no component option', async () => {
        const warningSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

        const variable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1],
            ranges: new Map([
                [-1, createRange(0, 100, 0, 100)],
                [0, createRange(-10, 10, -10, 10)],
                [1, createRange(-20, 20, -20, 20)],
                [999, createRange(-1, 1, -1, 1)],
            ]),
        });

        const selection = await createSelection([
            createActorNode({
                variableId: variable.id,
                variableComponent: 999,
                spectra: [variable],
            }),
        ]);

        const result = selection.currentVariableInfo!;

        expect(result.displayComponentId).toBe(999);
        expect(result.currentComponentInfo).toBeUndefined();
        expect(warningSpy).toHaveBeenCalledWith("invalid componentId: '999'");
    });

    test('setDisplayComponentId selects a component by number', async () => {
        const variable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: variable.id,
                variableComponent: 0,
                spectra: [variable],
            }),
        ]);

        const result = selection.currentVariableInfo!;
        const selected = result.setDisplayComponentId(2);

        expect(selected).toBe(result.componentOptions.get('2'));
        expect(result.currentComponentInfo).toBe(selected);
        expect(result.displayComponentId).toBe(2);
    });

    test('setDisplayComponentId accepts a string ID', async () => {
        const variable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: variable.id,
                variableComponent: 0,
                spectra: [variable],
            }),
        ]);

        const result = selection.currentVariableInfo!;
        const selected = result.setDisplayComponentId('1');

        expect(selected).toBe(result.componentOptions.get('1'));
        expect(result.displayComponentId).toBe(1);
    });

    test('setDisplayComponentId returns null for an unavailable component', async () => {
        const variable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: variable.id,
                variableComponent: 0,
                spectra: [variable],
            }),
        ]);

        const result = selection.currentVariableInfo!;
        const selected = result.setDisplayComponentId(999);

        expect(selected).toBeNull();
        expect(result.currentComponentInfo).toBeNull();
        expect(result.displayComponentId).toBeNull();
    });

    test('setDisplayComponentId preserves null', async () => {
        const variable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: variable.id,
                variableComponent: 0,
                spectra: [variable],
            }),
        ]);

        const result = selection.currentVariableInfo!;

        expect(result.setDisplayComponentId(null)).toBeNull();
        expect(result.currentComponentInfo).toBeNull();
        expect(result.displayComponentId).toBeNull();
    });

    test('setDisplayComponentId preserves undefined', async () => {
        const variable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: variable.id,
                variableComponent: 0,
                spectra: [variable],
            }),
        ]);

        const result = selection.currentVariableInfo!;

        expect(result.setDisplayComponentId(undefined)).toBeUndefined();
        expect(result.currentComponentInfo).toBeUndefined();
        expect(result.displayComponentId).toBeUndefined();
    });

    test('setDisplayComponentId invokes onVariableComponentChange', async () => {
        const variable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: variable.id,
                variableComponent: 0,
                spectra: [variable],
            }),
        ]);

        const result = selection.currentVariableInfo!;
        const handler = jest.fn();

        selection.events.onVariableComponentChange = handler;

        result.setDisplayComponentId(1);

        expect(handler).toHaveBeenCalledTimes(1);
        expect(handler).toHaveBeenCalledWith(result);
    });

    test('throws when changing a component while the current variable is null', async () => {
        const variable = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: variable.id,
                variableComponent: 0,
                spectra: [variable],
            }),
        ]);

        const result = selection.currentVariableInfo!;

        selection.setDisplayVariableId(null);

        expect(() => {
            result.setDisplayComponentId(1);
        }).toThrow('component should not be changed when the current variable is null');
    });

    test('throws when changing a component on a variable that is not current', async () => {
        const velocity = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
        });

        const acceleration = createVariable({
            id: 'POINT::acceleration::3',
            name: 'acceleration',
            componentIds: [-1, 0, 1, 2],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: velocity.id,
                variableComponent: 0,
                spectra: [velocity, acceleration],
            }),
        ]);

        const nonCurrentVariable = selection.variableOptions.get(acceleration.id)!;

        expect(() => {
            nonCurrentVariable.setDisplayComponentId(1);
        }).toThrow('component should not be changed on a variable that is not current');
    });

    test('allows component changes after a different variable becomes current', async () => {
        const velocity = createVariable({
            id: 'POINT::velocity::3',
            name: 'velocity',
            componentIds: [-1, 0, 1, 2],
        });

        const acceleration = createVariable({
            id: 'POINT::acceleration::3',
            name: 'acceleration',
            componentIds: [-1, 0, 1, 2],
        });

        const selection = await createSelection([
            createActorNode({
                variableId: velocity.id,
                variableComponent: 0,
                spectra: [velocity, acceleration],
            }),
        ]);

        const accelerationInfo = selection.setDisplayVariableId(acceleration.id)!;

        expect(() => {
            accelerationInfo.setDisplayComponentId(2);
        }).not.toThrow();

        expect(accelerationInfo.displayComponentId).toBe(2);
        expect(accelerationInfo.currentComponentInfo).toBe(
            accelerationInfo.componentOptions.get('2')
        );
    });
});

interface RangeInfo {
    defaultRange: number[];
    customRange: number[];
}

interface CreateVariableOptions {
    id: string;
    name: string;
    componentIds: number[];
    type?: FieldAssociation;
    shape?: string;
    ranges?: Map<number, RangeInfo>;
}

interface CreateActorNodeOptions {
    variableId: string | null;
    variableComponent: number;
    spectra: VisorVariableInfo[];
}

async function createSelection(
    actorNodes: VisorSceneNodeExtended[]
): Promise<AggregateSelectionInfo> {
    return AggregateSelectionInfo.getInstanceAsync(actorNodes);
}

function createVariable({
    id,
    name,
    componentIds,
    type = 'POINT',
    shape = 'Vector3',
    ranges,
}: CreateVariableOptions): VisorVariableInfo {
    const componentOptions = createComponentOptions(componentIds);

    const rangeState = new Map<number, RangeInfo>();

    for (const componentId of componentIds) {
        const suppliedRange = ranges?.get(componentId);

        rangeState.set(
            componentId,
            suppliedRange != null ? cloneRangeInfo(suppliedRange) : createRange(0, 1, 0, 1)
        );
    }

    // Allow tests to provide range data for a component that is not
    // present in componentOptions.
    if (ranges != null) {
        for (const [componentId, range] of ranges) {
            if (!rangeState.has(componentId)) {
                rangeState.set(componentId, cloneRangeInfo(range));
            }
        }
    }

    const numComponents = componentIds.filter((id) => id >= 0).length;

    return {
        id,
        type,
        name,
        shape,
        fullName: `${type} - ${name} (${shape})`,
        numComponents,
        componentOptions,

        getRangeInfo(component) {
            if (component == null) {
                return null;
            }

            const range = rangeState.get(component);

            if (range == null) {
                return null;
            }

            return cloneRangeInfo(range);
        },

        setCustomRange(component, min, max) {
            const range = rangeState.get(component);

            if (range != null) {
                range.customRange[0] = min;
                range.customRange[1] = max;
            }
        },
    };
}

function createVariableCollection(spectra: VisorVariableInfo[]): VisorVariableCollection {
    const array = [...spectra];
    const map = new Map(array.map((variable) => [variable.id, variable]));

    return {
        array,

        getVariable(id: string | null) {
            if (id == null) {
                return null;
            }

            return map.get(id) ?? null;
        },
    };
}

function createActorNode({
    variableId,
    variableComponent,
    spectra,
}: CreateActorNodeOptions): VisorSceneNodeExtended {
    return {
        name: 'mesh',
        opacity: 1,
        variableId,
        variableComponent,
        customDiffuseColorHex: '#ffffff',
        variableCollection: createVariableCollection(spectra),
    } as unknown as VisorSceneNodeExtended;
}

function createComponentOptions(componentIds: number[]): VisorVariableComponentMetadata[] {
    return componentIds.map((id) => ({
        id,
        name: getComponentName(id),
    }));
}

function getComponentName(id: number): string {
    switch (id) {
        case -1:
            return 'Magnitude';
        case 0:
            return 'X';
        case 1:
            return 'Y';
        case 2:
            return 'Z';
        case 3:
            return 'W';
        default:
            return `Component ${id}`;
    }
}

function createRange(
    defaultMin: number,
    defaultMax: number,
    customMin: number,
    customMax: number
): RangeInfo {
    return {
        defaultRange: [defaultMin, defaultMax],
        customRange: [customMin, customMax],
    };
}

function cloneRangeInfo(range: RangeInfo): RangeInfo {
    return {
        defaultRange: [...range.defaultRange],
        customRange: [...range.customRange],
    };
}
