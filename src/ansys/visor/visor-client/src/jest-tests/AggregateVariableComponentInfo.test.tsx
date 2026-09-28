import { AggregateSelectionInfo } from '../aggregate/AggregateSelectionInfo.tsx';
import { AggregateVariableComponentInfo } from '../aggregate/AggregateVariableComponentInfo.tsx';
import type { AggregateVariableInfo } from '../aggregate/AggregateVariableInfo.tsx';
import type { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import type {
    VisorVariableCollection,
    VisorVariableComponentMetadata,
    VisorVariableInfo,
} from '../state/VisorVariableManager.tsx';
import type { FieldAssociation } from '../state/appstate/vtkInfo/VisorVtkDataArray.tsx';

describe('AggregateVariableComponentInfo', () => {
    afterEach(() => {
        jest.restoreAllMocks();
    });

    test('exposes its component ID, metadata, and parent variable', async () => {
        const parentVariable = await createParentVariable();
        const metadata = getComponentMetadata(parentVariable, 0);

        const result = await AggregateVariableComponentInfo.getInstanceAsync(
            [
                createActorNode({
                    variableId: parentVariable.id,
                    variableComponent: 0,
                    variables: [
                        createVariable({
                            id: parentVariable.id,
                            componentIds: [-1, 0, 1, 2],
                        }),
                    ],
                }),
            ],
            parentVariable,
            metadata
        );

        expect(result).toBeInstanceOf(AggregateVariableComponentInfo);
        expect(result.id).toBe(0);
        expect(result.metadata).toBe(metadata);
        expect(result.variableInfo).toBe(parentVariable);
    });

    test('returns null aggregate values when there are no actor nodes', async () => {
        const parentVariable = await createParentVariable();
        const metadata = getComponentMetadata(parentVariable, 0);

        const result = await AggregateVariableComponentInfo.getInstanceAsync(
            [],
            parentVariable,
            metadata
        );

        expect(result.displayVariableDefaultMin).toBeNull();
        expect(result.displayVariableDefaultMax).toBeNull();
        expect(result.displayVariableMin).toBeNull();
        expect(result.displayVariableMax).toBeNull();
    });

    test('aggregates matching range values from all actor nodes', async () => {
        const parentVariable = await createParentVariable();
        const metadata = getComponentMetadata(parentVariable, 0);

        const firstVariable = createVariable({
            id: parentVariable.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-10, 10, -5, 5)]]),
        });

        const secondVariable = createVariable({
            id: parentVariable.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-10, 10, -5, 5)]]),
        });

        const result = await AggregateVariableComponentInfo.getInstanceAsync(
            [
                createActorNode({
                    variableId: parentVariable.id,
                    variableComponent: 0,
                    variables: [firstVariable],
                }),
                createActorNode({
                    variableId: parentVariable.id,
                    variableComponent: 0,
                    variables: [secondVariable],
                }),
            ],
            parentVariable,
            metadata
        );

        expect(result.displayVariableDefaultMin).toBe(-10);
        expect(result.displayVariableDefaultMax).toBe(10);
        expect(result.displayVariableMin).toBe(-5);
        expect(result.displayVariableMax).toBe(5);
    });

    test('marks only differing range fields as undefined', async () => {
        const parentVariable = await createParentVariable();
        const metadata = getComponentMetadata(parentVariable, 0);

        const firstVariable = createVariable({
            id: parentVariable.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-10, 10, -5, 5)]]),
        });

        const secondVariable = createVariable({
            id: parentVariable.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-20, 10, -15, 5)]]),
        });

        const result = await AggregateVariableComponentInfo.getInstanceAsync(
            [
                createActorNode({
                    variableId: parentVariable.id,
                    variableComponent: 0,
                    variables: [firstVariable],
                }),
                createActorNode({
                    variableId: parentVariable.id,
                    variableComponent: 0,
                    variables: [secondVariable],
                }),
            ],
            parentVariable,
            metadata
        );

        expect(result.displayVariableDefaultMin).toBeUndefined();
        expect(result.displayVariableDefaultMax).toBe(10);
        expect(result.displayVariableMin).toBeUndefined();
        expect(result.displayVariableMax).toBe(5);
    });

    test('sets all range values to undefined when a node has no matching variable', async () => {
        const parentVariable = await createParentVariable();
        const metadata = getComponentMetadata(parentVariable, 0);

        const matchingVariable = createVariable({
            id: parentVariable.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-10, 10, -5, 5)]]),
        });

        const unrelatedVariable = createVariable({
            id: 'POINT::temperature::1',
            name: 'temperature',
            shape: 'Scalar',
            componentIds: [-1],
        });

        const result = await AggregateVariableComponentInfo.getInstanceAsync(
            [
                createActorNode({
                    variableId: parentVariable.id,
                    variableComponent: 0,
                    variables: [matchingVariable],
                }),
                createActorNode({
                    variableId: unrelatedVariable.id,
                    variableComponent: -1,
                    variables: [unrelatedVariable],
                }),
            ],
            parentVariable,
            metadata
        );

        expect(result.displayVariableDefaultMin).toBeUndefined();
        expect(result.displayVariableDefaultMax).toBeUndefined();
        expect(result.displayVariableMin).toBeUndefined();
        expect(result.displayVariableMax).toBeUndefined();
    });

    test('sets all range values to undefined when a component range is missing', async () => {
        const parentVariable = await createParentVariable();
        const metadata = getComponentMetadata(parentVariable, 0);

        const variableWithRange = createVariable({
            id: parentVariable.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-10, 10, -5, 5)]]),
        });

        const variableWithoutRange = createVariable({
            id: parentVariable.id,
            componentIds: [-1, 0, 1, 2],
            omittedRangeIds: [0],
        });

        const result = await AggregateVariableComponentInfo.getInstanceAsync(
            [
                createActorNode({
                    variableId: parentVariable.id,
                    variableComponent: 0,
                    variables: [variableWithRange],
                }),
                createActorNode({
                    variableId: parentVariable.id,
                    variableComponent: 0,
                    variables: [variableWithoutRange],
                }),
            ],
            parentVariable,
            metadata
        );

        expect(result.displayVariableDefaultMin).toBeUndefined();
        expect(result.displayVariableDefaultMax).toBeUndefined();
        expect(result.displayVariableMin).toBeUndefined();
        expect(result.displayVariableMax).toBeUndefined();
    });

    test('stops aggregation after encountering a missing range', async () => {
        const parentVariable = await createParentVariable();
        const metadata = getComponentMetadata(parentVariable, 0);

        const missingRangeVariable = createVariable({
            id: parentVariable.id,
            componentIds: [-1, 0, 1, 2],
            omittedRangeIds: [0],
        });

        const laterVariable = createVariable({
            id: parentVariable.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-100, 100, -50, 50)]]),
        });

        const laterGetRangeInfoSpy = jest.spyOn(laterVariable, 'getRangeInfo');

        const result = await AggregateVariableComponentInfo.getInstanceAsync(
            [
                createActorNode({
                    variableId: parentVariable.id,
                    variableComponent: 0,
                    variables: [missingRangeVariable],
                }),
                createActorNode({
                    variableId: parentVariable.id,
                    variableComponent: 0,
                    variables: [laterVariable],
                }),
            ],
            parentVariable,
            metadata
        );

        expect(result.displayVariableDefaultMin).toBeUndefined();
        expect(result.displayVariableDefaultMax).toBeUndefined();
        expect(result.displayVariableMin).toBeUndefined();
        expect(result.displayVariableMax).toBeUndefined();

        expect(laterGetRangeInfoSpy).not.toHaveBeenCalled();
    });

    describe('setDisplayVariableMin', () => {
        test('accepts a number', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplayVariableMin(12.5);

            expect(success).toBe(true);
            expect(result.displayVariableMin).toBe(12.5);
        });

        test('parses a numeric string', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplayVariableMin('12.5');

            expect(success).toBe(true);
            expect(result.displayVariableMin).toBe(12.5);
        });

        test('uses parseFloat behavior for partially numeric strings', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplayVariableMin('12.5px');

            expect(success).toBe(true);
            expect(result.displayVariableMin).toBe(12.5);
        });

        test('converts a nonnumeric string to null', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplayVariableMin('not numeric');

            expect(success).toBe(false);
            expect(result.displayVariableMin).toBeNull();
        });

        test('preserves null', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplayVariableMin(null);

            expect(success).toBe(false);
            expect(result.displayVariableMin).toBeNull();
        });

        test('preserves undefined', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplayVariableMin(undefined);

            expect(success).toBe(false);
            expect(result.displayVariableMin).toBeUndefined();
        });

        test('invokes onMinChange with the parsed value', async () => {
            const result = await createComponentInfo();
            const handler = jest.fn();

            result.events.onMinChange = handler;

            result.setDisplayVariableMin('25.5');

            expect(handler).toHaveBeenCalledTimes(1);
            expect(handler).toHaveBeenCalledWith(25.5);
        });

        test('invokes onMinChange with null for invalid input', async () => {
            const result = await createComponentInfo();
            const handler = jest.fn();

            result.events.onMinChange = handler;

            result.setDisplayVariableMin('invalid');

            expect(handler).toHaveBeenCalledTimes(1);
            expect(handler).toHaveBeenCalledWith(null);
        });
    });

    describe('setDisplayVariableMax', () => {
        test('accepts a number', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplayVariableMax(87.5);

            expect(success).toBe(true);
            expect(result.displayVariableMax).toBe(87.5);
        });

        test('parses a numeric string', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplayVariableMax('87.5');

            expect(success).toBe(true);
            expect(result.displayVariableMax).toBe(87.5);
        });

        test('uses parseFloat behavior for partially numeric strings', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplayVariableMax('87.5px');

            expect(success).toBe(true);
            expect(result.displayVariableMax).toBe(87.5);
        });

        test('converts a nonnumeric string to null', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplayVariableMax('not numeric');

            expect(success).toBe(false);
            expect(result.displayVariableMax).toBeNull();
        });

        test('preserves null', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplayVariableMax(null);

            expect(success).toBe(false);
            expect(result.displayVariableMax).toBeNull();
        });

        test('preserves undefined', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplayVariableMax(undefined);

            expect(success).toBe(false);
            expect(result.displayVariableMax).toBeUndefined();
        });

        test('invokes onMaxChange with the parsed value', async () => {
            const result = await createComponentInfo();
            const handler = jest.fn();

            result.events.onMaxChange = handler;

            result.setDisplayVariableMax('75.5');

            expect(handler).toHaveBeenCalledTimes(1);
            expect(handler).toHaveBeenCalledWith(75.5);
        });

        test('invokes onMaxChange with null for invalid input', async () => {
            const result = await createComponentInfo();
            const handler = jest.fn();

            result.events.onMaxChange = handler;

            result.setDisplayVariableMax('invalid');

            expect(handler).toHaveBeenCalledTimes(1);
            expect(handler).toHaveBeenCalledWith(null);
        });
    });

    test('events initially contain null handlers', async () => {
        const result = await createComponentInfo();

        expect(result.events.onMinChange).toBeNull();
        expect(result.events.onMaxChange).toBeNull();
    });

    test('setters replace custom aggregate values without changing defaults', async () => {
        const result = await createComponentInfo();

        expect(result.displayVariableDefaultMin).toBe(-10);
        expect(result.displayVariableDefaultMax).toBe(10);
        expect(result.displayVariableMin).toBe(-5);
        expect(result.displayVariableMax).toBe(5);

        result.setDisplayVariableMin(-2);
        result.setDisplayVariableMax(2);

        expect(result.displayVariableMin).toBe(-2);
        expect(result.displayVariableMax).toBe(2);
        expect(result.displayVariableDefaultMin).toBe(-10);
        expect(result.displayVariableDefaultMax).toBe(10);
    });
});

interface RangeInfo {
    defaultRange: [number, number];
    customRange: [number, number];
}

interface CreateVariableOptions {
    id: string;
    componentIds: number[];
    name?: string;
    type?: FieldAssociation;
    shape?: string;
    ranges?: Map<number, RangeInfo>;
    omittedRangeIds?: number[];
}

interface CreateActorNodeOptions {
    variableId: string | null;
    variableComponent: number;
    variables: VisorVariableInfo[];
}

async function createParentVariable(): Promise<AggregateVariableInfo> {
    const variable = createVariable({
        id: 'POINT::velocity::3',
        name: 'velocity',
        shape: 'Vector3',
        componentIds: [-1, 0, 1, 2],
    });

    const actorNode = createActorNode({
        variableId: variable.id,
        variableComponent: 0,
        variables: [variable],
    });

    const selection = await AggregateSelectionInfo.getInstanceAsync([actorNode]);

    expect(selection.currentVariableInfo).not.toBeNull();
    expect(selection.currentVariableInfo).not.toBeUndefined();

    return selection.currentVariableInfo!;
}

async function createComponentInfo(): Promise<AggregateVariableComponentInfo> {
    const parentVariable = await createParentVariable();

    const metadata = getComponentMetadata(parentVariable, 0);

    const actorVariable = createVariable({
        id: parentVariable.id,
        name: 'velocity',
        shape: 'Vector3',
        componentIds: [-1, 0, 1, 2],
        ranges: new Map([[0, createRange(-10, 10, -5, 5)]]),
    });

    return AggregateVariableComponentInfo.getInstanceAsync(
        [
            createActorNode({
                variableId: parentVariable.id,
                variableComponent: 0,
                variables: [actorVariable],
            }),
        ],
        parentVariable,
        metadata
    );
}

function getComponentMetadata(
    variableInfo: AggregateVariableInfo,
    componentId: number
): VisorVariableComponentMetadata {
    const metadata = variableInfo.metadata.componentOptions.find((item) => item.id === componentId);

    if (metadata == null) {
        throw new Error(`component metadata not found: ${componentId}`);
    }

    return metadata;
}

function createVariable({
    id,
    componentIds,
    name = 'velocity',
    type = 'POINT',
    shape = 'Vector3',
    ranges = new Map(),
    omittedRangeIds = [],
}: CreateVariableOptions): VisorVariableInfo {
    const componentOptions = createComponentOptions(componentIds);

    const rangeState = new Map<number, RangeInfo>();
    const omitted = new Set(omittedRangeIds);

    for (const componentId of componentIds) {
        if (omitted.has(componentId)) {
            continue;
        }

        const suppliedRange = ranges.get(componentId);

        rangeState.set(
            componentId,
            suppliedRange != null ? cloneRangeInfo(suppliedRange) : createRange(0, 1, 0, 1)
        );
    }

    for (const [componentId, range] of ranges) {
        if (!omitted.has(componentId)) {
            rangeState.set(componentId, cloneRangeInfo(range));
        }
    }

    const numComponents = componentIds.filter((componentId) => componentId >= 0).length;

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

function createVariableCollection(variables: VisorVariableInfo[]): VisorVariableCollection {
    const array = [...variables];

    const map = new Map<string, VisorVariableInfo>(
        array.map((variable) => [variable.id, variable])
    );

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
    variables,
}: CreateActorNodeOptions): VisorSceneNodeExtended {
    return {
        name: 'mesh',
        opacity: 1,
        variableId,
        variableComponent,
        customDiffuseColorHex: '#ffffff',
        variableCollection: createVariableCollection(variables),
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
