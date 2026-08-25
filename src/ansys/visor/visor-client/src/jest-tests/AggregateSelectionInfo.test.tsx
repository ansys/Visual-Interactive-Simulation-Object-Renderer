import { AggregateSelectionInfo } from '../aggregate/AggregateSelectionInfo.tsx';
import type { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import type {
    VisorSpectrumComponentMetadata,
    VisorSpectrumInfo,
} from '../state/VisorSpectrumManager.tsx';

describe('AggregateSelectionInfo', () => {
    afterEach(() => {
        jest.restoreAllMocks();
    });

    test('returns empty aggregate values when there are no actor nodes', async () => {
        const result = await AggregateSelectionInfo.getInstanceAsync([]);

        expect(result.displayName).toBeNull();
        expect(result.displayOpacity).toBeNull();
        expect(result.displaySpectrumId).toBeNull();
        expect(result.displayDiffuseColor).toBeNull();
        expect(result.currentSpectrumInfo).toBeNull();
        expect(result.spectrumOptions.size).toBe(0);
    });

    test('aggregates matching values from all actor nodes', async () => {
        const spectrum = createSpectrum(10, [1]);

        const actorNodes = [
            createActorNode({
                name: 'mesh',
                opacity: 0.5,
                spectrumId: '10',
                spectrumComponent: 1,
                customDiffuseColorHex: '#123456',
                spectra: [spectrum],
            }),
            createActorNode({
                name: 'mesh',
                opacity: 0.5,
                spectrumId: '10',
                spectrumComponent: 1,
                customDiffuseColorHex: '#123456',
                spectra: [spectrum],
            }),
        ];

        const result = await AggregateSelectionInfo.getInstanceAsync(actorNodes);

        expect(result.displayName).toBe('mesh');
        expect(result.displayOpacity).toBe(0.5);
        expect(result.displaySpectrumId).toBe('10');
        expect(result.displayDiffuseColor).toBe('#123456');

        expect(result.spectrumOptions.size).toBe(1);
        expect(result.spectrumOptions.has('10')).toBe(true);
        expect(result.currentSpectrumInfo).toBe(result.spectrumOptions.get('10'));
        expect(result.currentSpectrumInfo?.id).toBe('10');
    });

    test('stores each spectrum only once when several nodes expose it', async () => {
        const spectrum = createSpectrum(10, [1]);

        const actorNodes = [
            createActorNode({
                spectra: [spectrum],
                spectrumId: '10',
                spectrumComponent: 1,
            }),
            createActorNode({
                spectra: [spectrum],
                spectrumId: '10',
                spectrumComponent: 1,
            }),
            createActorNode({
                spectra: [spectrum],
                spectrumId: '10',
                spectrumComponent: 1,
            }),
        ];

        const result = await AggregateSelectionInfo.getInstanceAsync(actorNodes);

        expect(result.spectrumOptions.size).toBe(1);
        expect([...result.spectrumOptions.keys()]).toEqual(['10']);
    });

    test('collects different spectrum options from the actor nodes', async () => {
        const spectrum10 = createSpectrum(10, [1]);
        const spectrum20 = createSpectrum(20, [1]);

        const actorNodes = [
            createActorNode({
                spectra: [spectrum10],
                spectrumId: '10',
                spectrumComponent: 1,
            }),
            createActorNode({
                spectra: [spectrum20],
                spectrumId: '10',
                spectrumComponent: 1,
            }),
        ];

        const result = await AggregateSelectionInfo.getInstanceAsync(actorNodes);

        expect([...result.spectrumOptions.keys()]).toEqual(['10', '20']);
    });

    test('uses undefined for values that differ between actor nodes', async () => {
        const spectrum10 = createSpectrum(10, [1]);
        const spectrum20 = createSpectrum(20, [1]);

        const actorNodes = [
            createActorNode({
                name: 'mesh A',
                opacity: 0.25,
                spectrumId: '10',
                spectrumComponent: 1,
                customDiffuseColorHex: '#111111',
                spectra: [spectrum10, spectrum20],
            }),
            createActorNode({
                name: 'mesh B',
                opacity: 0.75,
                spectrumId: '20',
                spectrumComponent: 1,
                customDiffuseColorHex: '#222222',
                spectra: [spectrum10, spectrum20],
            }),
        ];

        const result = await AggregateSelectionInfo.getInstanceAsync(actorNodes);

        expect(result.displayName).toBeUndefined();
        expect(result.displayOpacity).toBeUndefined();
        expect(result.displaySpectrumId).toBeUndefined();
        expect(result.displayDiffuseColor).toBeUndefined();
        expect(result.currentSpectrumInfo).toBeUndefined();
    });

    test('preserves values that match while marking only differing values undefined', async () => {
        const spectrum = createSpectrum(10, [1]);

        const actorNodes = [
            createActorNode({
                name: 'same name',
                opacity: 0.25,
                spectrumId: '10',
                spectrumComponent: 1,
                customDiffuseColorHex: '#123456',
                spectra: [spectrum],
            }),
            createActorNode({
                name: 'same name',
                opacity: 0.75,
                spectrumId: '10',
                spectrumComponent: 1,
                customDiffuseColorHex: '#123456',
                spectra: [spectrum],
            }),
        ];

        const result = await AggregateSelectionInfo.getInstanceAsync(actorNodes);

        expect(result.displayName).toBe('same name');
        expect(result.displayOpacity).toBeUndefined();
        expect(result.displaySpectrumId).toBe('10');
        expect(result.displayDiffuseColor).toBe('#123456');
    });

    test('warns when the common spectrum ID is not an available option', async () => {
        const warningSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

        const actorNode = createActorNode({
            spectrumId: '999',
            spectrumComponent: 1,
            spectra: [createSpectrum(10, [1])],
        });

        const result = await AggregateSelectionInfo.getInstanceAsync([actorNode]);

        expect(result.displaySpectrumId).toBe('999');
        expect(result.currentSpectrumInfo).toBeUndefined();
        expect(warningSpy).toHaveBeenCalledWith("invalid spectrumId: '999'");
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

    test('setDisplaySpectrumId selects an available spectrum', async () => {
        const spectrum10 = createSpectrum(10, [1]);
        const spectrum20 = createSpectrum(20, [1]);

        const result = await AggregateSelectionInfo.getInstanceAsync([
            createActorNode({
                spectrumId: '10',
                spectrumComponent: 1,
                spectra: [spectrum10, spectrum20],
            }),
        ]);

        const selected = result.setDisplaySpectrumId(20);

        expect(selected).toBe(result.spectrumOptions.get('20'));
        expect(result.currentSpectrumInfo).toBe(result.spectrumOptions.get('20'));
        expect(result.displaySpectrumId).toBe('20');
    });

    test('setDisplaySpectrumId accepts a string ID', async () => {
        const spectrum = createSpectrum(10, [1]);

        const result = await AggregateSelectionInfo.getInstanceAsync([
            createActorNode({
                spectrumId: null,
                spectrumComponent: 1,
                spectra: [spectrum],
            }),
        ]);

        const selected = result.setDisplaySpectrumId('10');

        expect(selected).toBe(result.spectrumOptions.get('10'));
        expect(result.displaySpectrumId).toBe('10');
    });

    test('setDisplaySpectrumId returns null for an unavailable spectrum', async () => {
        const spectrum = createSpectrum(10, [1]);

        const result = await AggregateSelectionInfo.getInstanceAsync([
            createActorNode({
                spectrumId: '10',
                spectrumComponent: 1,
                spectra: [spectrum],
            }),
        ]);

        const selected = result.setDisplaySpectrumId('999');

        expect(selected).toBeNull();
        expect(result.currentSpectrumInfo).toBeNull();
        expect(result.displaySpectrumId).toBeNull();
    });

    test('setDisplaySpectrumId preserves null and undefined', async () => {
        const spectrum = createSpectrum(10, [1]);

        const result = await AggregateSelectionInfo.getInstanceAsync([
            createActorNode({
                spectrumId: '10',
                spectrumComponent: 1,
                spectra: [spectrum],
            }),
        ]);

        expect(result.setDisplaySpectrumId(null)).toBeNull();
        expect(result.currentSpectrumInfo).toBeNull();
        expect(result.displaySpectrumId).toBeNull();

        expect(result.setDisplaySpectrumId(undefined)).toBeUndefined();
        expect(result.currentSpectrumInfo).toBeUndefined();
        expect(result.displaySpectrumId).toBeUndefined();
    });

    test('setDisplaySpectrumId invokes onSpectrumChange', async () => {
        const spectrum10 = createSpectrum(10, [1]);
        const spectrum20 = createSpectrum(20, [1]);

        const result = await AggregateSelectionInfo.getInstanceAsync([
            createActorNode({
                spectrumId: '10',
                spectrumComponent: 1,
                spectra: [spectrum10, spectrum20],
            }),
        ]);

        const handler = jest.fn();
        result.events.onSpectrumChange = handler;

        const selected = result.setDisplaySpectrumId(20);

        expect(handler).toHaveBeenCalledTimes(1);
        expect(handler).toHaveBeenCalledWith(selected);
    });

    test('setDisplaySpectrumId invokes the event with null for an invalid ID', async () => {
        const spectrum = createSpectrum(10, [1]);

        const result = await AggregateSelectionInfo.getInstanceAsync([
            createActorNode({
                spectrumId: '10',
                spectrumComponent: 1,
                spectra: [spectrum],
            }),
        ]);

        const handler = jest.fn();
        result.events.onSpectrumChange = handler;

        result.setDisplaySpectrumId(999);

        expect(handler).toHaveBeenCalledWith(null);
    });

    test('events initially contain null handlers', async () => {
        const result = await AggregateSelectionInfo.getInstanceAsync([]);

        expect(result.events.onSpectrumChange).toBeNull();
        expect(result.events.onSpectrumComponentChange).toBeNull();
    });
});

interface SpectrumFixture {
    metadata: VisorSpectrumInfo;
    runtime: {
        componentOptions: VisorSpectrumComponentMetadata[];
        getRangeInfo: jest.Mock;
    };
}

interface ActorNodeOptions {
    name?: string | null;
    opacity?: number | null;
    spectrumId?: string | null;
    spectrumComponent?: number;
    customDiffuseColorHex?: string | null;
    spectra?: SpectrumFixture[];
}

function createSpectrum(id: number, componentIds: number[]): SpectrumFixture {
    const componentOptions = componentIds.map((componentId) => ({
        id: componentId,
        name: `Component ${componentId}`,
    })) as VisorSpectrumComponentMetadata[];

    const validIds = new Set(componentIds);
    const idString = id.toString();

    const metadata: VisorSpectrumInfo = {
        id: idString,
        type: 'POINT',
        name: `spectrum-${idString}`,
        shape: componentIds.length === 1 ? 'Scalar' : `Vector${componentIds.length}`,
        fullName: `POINT - spectrum-${idString}`,
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
    spectrumId = null,
    spectrumComponent = 0,
    customDiffuseColorHex = '#ffffff',
    spectra = [],
}: ActorNodeOptions = {}): VisorSceneNodeExtended {
    return {
        name,
        opacity,
        spectrumId,
        spectrumComponent,
        customDiffuseColorHex,

        spectrumCollection: {
            array: spectra.map((spectrum) => spectrum.metadata),

            getSpectrum: jest.fn((id: number | string) => {
                const match = spectra.find(
                    (spectrum) => spectrum.metadata.id.toString() === id.toString()
                );

                return match?.runtime ?? null;
            }),
        },
    } as unknown as VisorSceneNodeExtended;
}
