import { AggregateSelectionInfo } from '../aggregate/AggregateSelectionInfo.tsx';
import type { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import type {
    VisorVariableComponentMetadata,
    VisorVariableInfo,
} from '../state/VisorVariableManager.tsx';

describe('AggregateSelectionInfo', () => {
    afterEach(() => {
        jest.restoreAllMocks();
    });

    test('returns empty aggregate values when there are no actor nodes', async () => {
        const result = await AggregateSelectionInfo.getInstanceAsync([]);

        expect(result.displayName).toBeNull();
        expect(result.displayOpacity).toBeNull();
        expect(result.displayVariableId).toBeNull();
        expect(result.displayDiffuseColor).toBeNull();
        expect(result.currentVariableInfo).toBeNull();
        expect(result.variableOptions.size).toBe(0);
    });

    test('aggregates matching values from all actor nodes', async () => {
        const variable = createVariable(10, [1]);

        const actorNodes = [
            createActorNode({
                name: 'mesh',
                opacity: 0.5,
                variableId: '10',
                variableComponent: 1,
                customDiffuseColorHex: '#123456',
                variables: [variable],
            }),
            createActorNode({
                name: 'mesh',
                opacity: 0.5,
                variableId: '10',
                variableComponent: 1,
                customDiffuseColorHex: '#123456',
                variables: [variable],
            }),
        ];

        const result = await AggregateSelectionInfo.getInstanceAsync(actorNodes);

        expect(result.displayName).toBe('mesh');
        expect(result.displayOpacity).toBe(0.5);
        expect(result.displayVariableId).toBe('10');
        expect(result.displayDiffuseColor).toBe('#123456');

        expect(result.variableOptions.size).toBe(1);
        expect(result.variableOptions.has('10')).toBe(true);
        expect(result.currentVariableInfo).toBe(result.variableOptions.get('10'));
        expect(result.currentVariableInfo?.id).toBe('10');
    });

    test('stores each variable only once when several nodes expose it', async () => {
        const variable = createVariable(10, [1]);

        const actorNodes = [
            createActorNode({
                variables: [variable],
                variableId: '10',
                variableComponent: 1,
            }),
            createActorNode({
                variables: [variable],
                variableId: '10',
                variableComponent: 1,
            }),
            createActorNode({
                variables: [variable],
                variableId: '10',
                variableComponent: 1,
            }),
        ];

        const result = await AggregateSelectionInfo.getInstanceAsync(actorNodes);

        expect(result.variableOptions.size).toBe(1);
        expect([...result.variableOptions.keys()]).toEqual(['10']);
    });

    test('collects different variable options from the actor nodes', async () => {
        const variable10 = createVariable(10, [1]);
        const variable20 = createVariable(20, [1]);

        const actorNodes = [
            createActorNode({
                variables: [variable10],
                variableId: '10',
                variableComponent: 1,
            }),
            createActorNode({
                variables: [variable20],
                variableId: '10',
                variableComponent: 1,
            }),
        ];

        const result = await AggregateSelectionInfo.getInstanceAsync(actorNodes);

        expect([...result.variableOptions.keys()]).toEqual(['10', '20']);
    });

    test('uses undefined for values that differ between actor nodes', async () => {
        const variable10 = createVariable(10, [1]);
        const variable20 = createVariable(20, [1]);

        const actorNodes = [
            createActorNode({
                name: 'mesh A',
                opacity: 0.25,
                variableId: '10',
                variableComponent: 1,
                customDiffuseColorHex: '#111111',
                variables: [variable10, variable20],
            }),
            createActorNode({
                name: 'mesh B',
                opacity: 0.75,
                variableId: '20',
                variableComponent: 1,
                customDiffuseColorHex: '#222222',
                variables: [variable10, variable20],
            }),
        ];

        const result = await AggregateSelectionInfo.getInstanceAsync(actorNodes);

        expect(result.displayName).toBeUndefined();
        expect(result.displayOpacity).toBeUndefined();
        expect(result.displayVariableId).toBeUndefined();
        expect(result.displayDiffuseColor).toBeUndefined();
        expect(result.currentVariableInfo).toBeUndefined();
    });

    test('preserves values that match while marking only differing values undefined', async () => {
        const variable = createVariable(10, [1]);

        const actorNodes = [
            createActorNode({
                name: 'same name',
                opacity: 0.25,
                variableId: '10',
                variableComponent: 1,
                customDiffuseColorHex: '#123456',
                variables: [variable],
            }),
            createActorNode({
                name: 'same name',
                opacity: 0.75,
                variableId: '10',
                variableComponent: 1,
                customDiffuseColorHex: '#123456',
                variables: [variable],
            }),
        ];

        const result = await AggregateSelectionInfo.getInstanceAsync(actorNodes);

        expect(result.displayName).toBe('same name');
        expect(result.displayOpacity).toBeUndefined();
        expect(result.displayVariableId).toBe('10');
        expect(result.displayDiffuseColor).toBe('#123456');
    });

    test('warns when the common variable ID is not an available option', async () => {
        const warningSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

        const actorNode = createActorNode({
            variableId: '999',
            variableComponent: 1,
            variables: [createVariable(10, [1])],
        });

        const result = await AggregateSelectionInfo.getInstanceAsync([actorNode]);

        expect(result.displayVariableId).toBe('999');
        expect(result.currentVariableInfo).toBeUndefined();
        expect(warningSpy).toHaveBeenCalledWith("invalid variableId: '999'");
    });

    test('setDisplayName updates the displayed name', async () => {
        const result = await AggregateSelectionInfo.getInstanceAsync([]);

        result.setDisplayName('updated name');

        expect(result.displayName).toBe('updated name');

        result.setDisplayName(null);
        expect(result.displayName).toBeNull();

        result.setDisplayName(undefined);
        expect(result.displayName).toBeUndefined();
    });

    test('setDisplayOpacity parses numeric strings', async () => {
        const result = await AggregateSelectionInfo.getInstanceAsync([]);

        result.setDisplayOpacity('0.75');

        expect(result.displayOpacity).toBe(0.75);
    });

    test('setDisplayOpacity accepts numbers, null, and undefined', async () => {
        const result = await AggregateSelectionInfo.getInstanceAsync([]);

        result.setDisplayOpacity(0.25);
        expect(result.displayOpacity).toBe(0.25);

        result.setDisplayOpacity(null);
        expect(result.displayOpacity).toBeNull();

        result.setDisplayOpacity(undefined);
        expect(result.displayOpacity).toBeUndefined();
    });

    test('setDisplayOpacity converts an invalid string to null', async () => {
        const result = await AggregateSelectionInfo.getInstanceAsync([]);

        result.setDisplayOpacity('not numeric');

        expect(result.displayOpacity).toBeNull();
    });

    test('setDisplayVariableId selects an available variable', async () => {
        const variable10 = createVariable(10, [1]);
        const variable20 = createVariable(20, [1]);

        const result = await AggregateSelectionInfo.getInstanceAsync([
            createActorNode({
                variableId: '10',
                variableComponent: 1,
                variables: [variable10, variable20],
            }),
        ]);

        const selected = result.setDisplayVariableId(20);

        expect(selected).toBe(result.variableOptions.get('20'));
        expect(result.currentVariableInfo).toBe(result.variableOptions.get('20'));
        expect(result.displayVariableId).toBe('20');
    });

    test('setDisplayVariableId accepts a string ID', async () => {
        const variable = createVariable(10, [1]);

        const result = await AggregateSelectionInfo.getInstanceAsync([
            createActorNode({
                variableId: null,
                variableComponent: 1,
                variables: [variable],
            }),
        ]);

        const selected = result.setDisplayVariableId('10');

        expect(selected).toBe(result.variableOptions.get('10'));
        expect(result.displayVariableId).toBe('10');
    });

    test('setDisplayVariableId returns null for an unavailable variable', async () => {
        const variable = createVariable(10, [1]);

        const result = await AggregateSelectionInfo.getInstanceAsync([
            createActorNode({
                variableId: '10',
                variableComponent: 1,
                variables: [variable],
            }),
        ]);

        const selected = result.setDisplayVariableId('999');

        expect(selected).toBeNull();
        expect(result.currentVariableInfo).toBeNull();
        expect(result.displayVariableId).toBeNull();
    });

    test('setDisplayVariableId preserves null and undefined', async () => {
        const variable = createVariable(10, [1]);

        const result = await AggregateSelectionInfo.getInstanceAsync([
            createActorNode({
                variableId: '10',
                variableComponent: 1,
                variables: [variable],
            }),
        ]);

        expect(result.setDisplayVariableId(null)).toBeNull();
        expect(result.currentVariableInfo).toBeNull();
        expect(result.displayVariableId).toBeNull();

        expect(result.setDisplayVariableId(undefined)).toBeUndefined();
        expect(result.currentVariableInfo).toBeUndefined();
        expect(result.displayVariableId).toBeUndefined();
    });

    test('setDisplayVariableId invokes onVariableChange', async () => {
        const variable10 = createVariable(10, [1]);
        const variable20 = createVariable(20, [1]);

        const result = await AggregateSelectionInfo.getInstanceAsync([
            createActorNode({
                variableId: '10',
                variableComponent: 1,
                variables: [variable10, variable20],
            }),
        ]);

        const handler = jest.fn();
        result.events.onVariableChange = handler;

        const selected = result.setDisplayVariableId(20);

        expect(handler).toHaveBeenCalledTimes(1);
        expect(handler).toHaveBeenCalledWith(selected);
    });

    test('setDisplayVariableId invokes the event with null for an invalid ID', async () => {
        const variable = createVariable(10, [1]);

        const result = await AggregateSelectionInfo.getInstanceAsync([
            createActorNode({
                variableId: '10',
                variableComponent: 1,
                variables: [variable],
            }),
        ]);

        const handler = jest.fn();
        result.events.onVariableChange = handler;

        result.setDisplayVariableId(999);

        expect(handler).toHaveBeenCalledWith(null);
    });

    test('events initially contain null handlers', async () => {
        const result = await AggregateSelectionInfo.getInstanceAsync([]);

        expect(result.events.onVariableChange).toBeNull();
        expect(result.events.onVariableComponentChange).toBeNull();
    });
});

interface VariableFixture {
    metadata: VisorVariableInfo;
    runtime: {
        componentOptions: VisorVariableComponentMetadata[];
        getRangeInfo: jest.Mock;
    };
}

interface ActorNodeOptions {
    name?: string | null;
    opacity?: number | null;
    variableId?: string | null;
    variableComponent?: number;
    customDiffuseColorHex?: string | null;
    variables?: VariableFixture[];
}

function createVariable(id: number, componentIds: number[]): VariableFixture {
    const componentOptions = componentIds.map((componentId) => ({
        id: componentId,
        name: `Component ${componentId}`,
    })) as VisorVariableComponentMetadata[];

    const validIds = new Set(componentIds);
    const idString = id.toString();

    const metadata: VisorVariableInfo = {
        id: idString,
        type: 'POINT',
        name: `variable-${idString}`,
        shape: componentIds.length === 1 ? 'Scalar' : `Vector${componentIds.length}`,
        fullName: `POINT - variable-${idString}`,
        numComponents: componentIds.length,
        componentOptions,
        getRangeInfo: (componentId) => {
            if (componentId == null || !validIds.has(componentId)) {
                return null;
            }

            return {
                defaultRange: [0, 1],
                customRange: [0, 1],
            };
        },
        setCustomRange: jest.fn(),
    };

    return {
        metadata,
        runtime: {
            componentOptions,
            getRangeInfo: jest.fn((componentId: number) => {
                if (!validIds.has(componentId)) {
                    return null;
                }

                return {
                    defaultRange: [0, 1],
                    customRange: [0, 1],
                };
            }),
        },
    };
}

function createActorNode({
    name = 'mesh',
    opacity = 1,
    variableId = null,
    variableComponent = 0,
    customDiffuseColorHex = '#ffffff',
    variables = [],
}: ActorNodeOptions = {}): VisorSceneNodeExtended {
    return {
        name,
        opacity,
        variableId,
        variableComponent,
        customDiffuseColorHex,

        variableCollection: {
            array: variables.map((variable) => variable.metadata),

            getVariable: jest.fn((id: number | string) => {
                const match = variables.find(
                    (variable) => variable.metadata.id.toString() === id.toString()
                );

                return match?.runtime ?? null;
            }),
        },
    } as unknown as VisorSceneNodeExtended;
}
