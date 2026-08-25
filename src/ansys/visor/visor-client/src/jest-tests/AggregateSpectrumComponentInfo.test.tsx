import { AggregateSelectionInfo } from '../aggregate/AggregateSelectionInfo.tsx';
import { AggregateSpectrumComponentInfo } from '../aggregate/AggregateSpectrumComponentInfo.tsx';
import type { AggregateSpectrumInfo } from '../aggregate/AggregateSpectrumInfo.tsx';
import type { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import type {
    VisorSpectrumCollection,
    VisorSpectrumComponentMetadata,
    VisorSpectrumInfo,
} from '../state/VisorSpectrumManager.tsx';
import type { FieldAssociation } from '../state/appstate/vtkInfo/VisorVtkDataArray.tsx';

describe('AggregateSpectrumComponentInfo', () => {
    afterEach(() => {
        jest.restoreAllMocks();
    });

    test('exposes its component ID, metadata, and parent spectrum', async () => {
        const parentSpectrum = await createParentSpectrum();
        const metadata = getComponentMetadata(parentSpectrum, 0);

        const result = await AggregateSpectrumComponentInfo.getInstanceAsync(
            [
                createActorNode({
                    spectrumId: parentSpectrum.id,
                    spectrumComponent: 0,
                    spectra: [
                        createSpectrum({
                            id: parentSpectrum.id,
                            componentIds: [-1, 0, 1, 2],
                        }),
                    ],
                }),
            ],
            parentSpectrum,
            metadata
        );

        expect(result).toBeInstanceOf(AggregateSpectrumComponentInfo);
        expect(result.id).toBe(0);
        expect(result.metadata).toBe(metadata);
        expect(result.spectrumInfo).toBe(parentSpectrum);
    });

    test('returns null aggregate values when there are no actor nodes', async () => {
        const parentSpectrum = await createParentSpectrum();
        const metadata = getComponentMetadata(parentSpectrum, 0);

        const result = await AggregateSpectrumComponentInfo.getInstanceAsync(
            [],
            parentSpectrum,
            metadata
        );

        expect(result.displaySpectrumDefaultMin).toBeNull();
        expect(result.displaySpectrumDefaultMax).toBeNull();
        expect(result.displaySpectrumMin).toBeNull();
        expect(result.displaySpectrumMax).toBeNull();
    });

    test('aggregates matching range values from all actor nodes', async () => {
        const parentSpectrum = await createParentSpectrum();
        const metadata = getComponentMetadata(parentSpectrum, 0);

        const firstSpectrum = createSpectrum({
            id: parentSpectrum.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-10, 10, -5, 5)]]),
        });

        const secondSpectrum = createSpectrum({
            id: parentSpectrum.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-10, 10, -5, 5)]]),
        });

        const result = await AggregateSpectrumComponentInfo.getInstanceAsync(
            [
                createActorNode({
                    spectrumId: parentSpectrum.id,
                    spectrumComponent: 0,
                    spectra: [firstSpectrum],
                }),
                createActorNode({
                    spectrumId: parentSpectrum.id,
                    spectrumComponent: 0,
                    spectra: [secondSpectrum],
                }),
            ],
            parentSpectrum,
            metadata
        );

        expect(result.displaySpectrumDefaultMin).toBe(-10);
        expect(result.displaySpectrumDefaultMax).toBe(10);
        expect(result.displaySpectrumMin).toBe(-5);
        expect(result.displaySpectrumMax).toBe(5);
    });

    test('marks only differing range fields as undefined', async () => {
        const parentSpectrum = await createParentSpectrum();
        const metadata = getComponentMetadata(parentSpectrum, 0);

        const firstSpectrum = createSpectrum({
            id: parentSpectrum.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-10, 10, -5, 5)]]),
        });

        const secondSpectrum = createSpectrum({
            id: parentSpectrum.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-20, 10, -15, 5)]]),
        });

        const result = await AggregateSpectrumComponentInfo.getInstanceAsync(
            [
                createActorNode({
                    spectrumId: parentSpectrum.id,
                    spectrumComponent: 0,
                    spectra: [firstSpectrum],
                }),
                createActorNode({
                    spectrumId: parentSpectrum.id,
                    spectrumComponent: 0,
                    spectra: [secondSpectrum],
                }),
            ],
            parentSpectrum,
            metadata
        );

        expect(result.displaySpectrumDefaultMin).toBeUndefined();
        expect(result.displaySpectrumDefaultMax).toBe(10);
        expect(result.displaySpectrumMin).toBeUndefined();
        expect(result.displaySpectrumMax).toBe(5);
    });

    test('sets all range values to undefined when a node has no matching spectrum', async () => {
        const parentSpectrum = await createParentSpectrum();
        const metadata = getComponentMetadata(parentSpectrum, 0);

        const matchingSpectrum = createSpectrum({
            id: parentSpectrum.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-10, 10, -5, 5)]]),
        });

        const unrelatedSpectrum = createSpectrum({
            id: 'POINT::temperature::1',
            name: 'temperature',
            shape: 'Scalar',
            componentIds: [-1],
        });

        const result = await AggregateSpectrumComponentInfo.getInstanceAsync(
            [
                createActorNode({
                    spectrumId: parentSpectrum.id,
                    spectrumComponent: 0,
                    spectra: [matchingSpectrum],
                }),
                createActorNode({
                    spectrumId: unrelatedSpectrum.id,
                    spectrumComponent: -1,
                    spectra: [unrelatedSpectrum],
                }),
            ],
            parentSpectrum,
            metadata
        );

        expect(result.displaySpectrumDefaultMin).toBeUndefined();
        expect(result.displaySpectrumDefaultMax).toBeUndefined();
        expect(result.displaySpectrumMin).toBeUndefined();
        expect(result.displaySpectrumMax).toBeUndefined();
    });

    test('sets all range values to undefined when a component range is missing', async () => {
        const parentSpectrum = await createParentSpectrum();
        const metadata = getComponentMetadata(parentSpectrum, 0);

        const spectrumWithRange = createSpectrum({
            id: parentSpectrum.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-10, 10, -5, 5)]]),
        });

        const spectrumWithoutRange = createSpectrum({
            id: parentSpectrum.id,
            componentIds: [-1, 0, 1, 2],
            omittedRangeIds: [0],
        });

        const result = await AggregateSpectrumComponentInfo.getInstanceAsync(
            [
                createActorNode({
                    spectrumId: parentSpectrum.id,
                    spectrumComponent: 0,
                    spectra: [spectrumWithRange],
                }),
                createActorNode({
                    spectrumId: parentSpectrum.id,
                    spectrumComponent: 0,
                    spectra: [spectrumWithoutRange],
                }),
            ],
            parentSpectrum,
            metadata
        );

        expect(result.displaySpectrumDefaultMin).toBeUndefined();
        expect(result.displaySpectrumDefaultMax).toBeUndefined();
        expect(result.displaySpectrumMin).toBeUndefined();
        expect(result.displaySpectrumMax).toBeUndefined();
    });

    test('stops aggregation after encountering a missing range', async () => {
        const parentSpectrum = await createParentSpectrum();
        const metadata = getComponentMetadata(parentSpectrum, 0);

        const missingRangeSpectrum = createSpectrum({
            id: parentSpectrum.id,
            componentIds: [-1, 0, 1, 2],
            omittedRangeIds: [0],
        });

        const laterSpectrum = createSpectrum({
            id: parentSpectrum.id,
            componentIds: [-1, 0, 1, 2],
            ranges: new Map([[0, createRange(-100, 100, -50, 50)]]),
        });

        const laterGetRangeInfoSpy = jest.spyOn(laterSpectrum, 'getRangeInfo');

        const result = await AggregateSpectrumComponentInfo.getInstanceAsync(
            [
                createActorNode({
                    spectrumId: parentSpectrum.id,
                    spectrumComponent: 0,
                    spectra: [missingRangeSpectrum],
                }),
                createActorNode({
                    spectrumId: parentSpectrum.id,
                    spectrumComponent: 0,
                    spectra: [laterSpectrum],
                }),
            ],
            parentSpectrum,
            metadata
        );

        expect(result.displaySpectrumDefaultMin).toBeUndefined();
        expect(result.displaySpectrumDefaultMax).toBeUndefined();
        expect(result.displaySpectrumMin).toBeUndefined();
        expect(result.displaySpectrumMax).toBeUndefined();

        expect(laterGetRangeInfoSpy).not.toHaveBeenCalled();
    });

    describe('setDisplaySpectrumMin', () => {
        test('accepts a number', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplaySpectrumMin(12.5);

            expect(success).toBe(true);
            expect(result.displaySpectrumMin).toBe(12.5);
        });

        test('parses a numeric string', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplaySpectrumMin('12.5');

            expect(success).toBe(true);
            expect(result.displaySpectrumMin).toBe(12.5);
        });

        test('uses parseFloat behavior for partially numeric strings', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplaySpectrumMin('12.5px');

            expect(success).toBe(true);
            expect(result.displaySpectrumMin).toBe(12.5);
        });

        test('converts a nonnumeric string to null', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplaySpectrumMin('not numeric');

            expect(success).toBe(false);
            expect(result.displaySpectrumMin).toBeNull();
        });

        test('preserves null', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplaySpectrumMin(null);

            expect(success).toBe(false);
            expect(result.displaySpectrumMin).toBeNull();
        });

        test('preserves undefined', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplaySpectrumMin(undefined);

            expect(success).toBe(false);
            expect(result.displaySpectrumMin).toBeUndefined();
        });

        test('invokes onMinChange with the parsed value', async () => {
            const result = await createComponentInfo();
            const handler = jest.fn();

            result.events.onMinChange = handler;

            result.setDisplaySpectrumMin('25.5');

            expect(handler).toHaveBeenCalledTimes(1);
            expect(handler).toHaveBeenCalledWith(25.5);
        });

        test('invokes onMinChange with null for invalid input', async () => {
            const result = await createComponentInfo();
            const handler = jest.fn();

            result.events.onMinChange = handler;

            result.setDisplaySpectrumMin('invalid');

            expect(handler).toHaveBeenCalledTimes(1);
            expect(handler).toHaveBeenCalledWith(null);
        });
    });

    describe('setDisplaySpectrumMax', () => {
        test('accepts a number', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplaySpectrumMax(87.5);

            expect(success).toBe(true);
            expect(result.displaySpectrumMax).toBe(87.5);
        });

        test('parses a numeric string', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplaySpectrumMax('87.5');

            expect(success).toBe(true);
            expect(result.displaySpectrumMax).toBe(87.5);
        });

        test('uses parseFloat behavior for partially numeric strings', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplaySpectrumMax('87.5px');

            expect(success).toBe(true);
            expect(result.displaySpectrumMax).toBe(87.5);
        });

        test('converts a nonnumeric string to null', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplaySpectrumMax('not numeric');

            expect(success).toBe(false);
            expect(result.displaySpectrumMax).toBeNull();
        });

        test('preserves null', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplaySpectrumMax(null);

            expect(success).toBe(false);
            expect(result.displaySpectrumMax).toBeNull();
        });

        test('preserves undefined', async () => {
            const result = await createComponentInfo();

            const success = result.setDisplaySpectrumMax(undefined);

            expect(success).toBe(false);
            expect(result.displaySpectrumMax).toBeUndefined();
        });

        test('invokes onMaxChange with the parsed value', async () => {
            const result = await createComponentInfo();
            const handler = jest.fn();

            result.events.onMaxChange = handler;

            result.setDisplaySpectrumMax('75.5');

            expect(handler).toHaveBeenCalledTimes(1);
            expect(handler).toHaveBeenCalledWith(75.5);
        });

        test('invokes onMaxChange with null for invalid input', async () => {
            const result = await createComponentInfo();
            const handler = jest.fn();

            result.events.onMaxChange = handler;

            result.setDisplaySpectrumMax('invalid');

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

        expect(result.displaySpectrumDefaultMin).toBe(-10);
        expect(result.displaySpectrumDefaultMax).toBe(10);
        expect(result.displaySpectrumMin).toBe(-5);
        expect(result.displaySpectrumMax).toBe(5);

        result.setDisplaySpectrumMin(-2);
        result.setDisplaySpectrumMax(2);

        expect(result.displaySpectrumMin).toBe(-2);
        expect(result.displaySpectrumMax).toBe(2);
        expect(result.displaySpectrumDefaultMin).toBe(-10);
        expect(result.displaySpectrumDefaultMax).toBe(10);
    });
});

interface RangeInfo {
    defaultRange: [number, number];
    customRange: [number, number];
}

interface CreateSpectrumOptions {
    id: string;
    componentIds: number[];
    name?: string;
    type?: FieldAssociation;
    shape?: string;
    ranges?: Map<number, RangeInfo>;
    omittedRangeIds?: number[];
}

interface CreateActorNodeOptions {
    spectrumId: string | null;
    spectrumComponent: number;
    spectra: VisorSpectrumInfo[];
}

async function createParentSpectrum(): Promise<AggregateSpectrumInfo> {
    const spectrum = createSpectrum({
        id: 'POINT::velocity::3',
        name: 'velocity',
        shape: 'Vector3',
        componentIds: [-1, 0, 1, 2],
    });

    const actorNode = createActorNode({
        spectrumId: spectrum.id,
        spectrumComponent: 0,
        spectra: [spectrum],
    });

    const selection = await AggregateSelectionInfo.getInstanceAsync([actorNode]);

    expect(selection.currentSpectrumInfo).not.toBeNull();
    expect(selection.currentSpectrumInfo).not.toBeUndefined();

    return selection.currentSpectrumInfo!;
}

async function createComponentInfo(): Promise<AggregateSpectrumComponentInfo> {
    const parentSpectrum = await createParentSpectrum();

    const metadata = getComponentMetadata(parentSpectrum, 0);

    const actorSpectrum = createSpectrum({
        id: parentSpectrum.id,
        name: 'velocity',
        shape: 'Vector3',
        componentIds: [-1, 0, 1, 2],
        ranges: new Map([[0, createRange(-10, 10, -5, 5)]]),
    });

    return AggregateSpectrumComponentInfo.getInstanceAsync(
        [
            createActorNode({
                spectrumId: parentSpectrum.id,
                spectrumComponent: 0,
                spectra: [actorSpectrum],
            }),
        ],
        parentSpectrum,
        metadata
    );
}

function getComponentMetadata(
    spectrumInfo: AggregateSpectrumInfo,
    componentId: number
): VisorSpectrumComponentMetadata {
    const metadata = spectrumInfo.metadata.componentOptions.find((item) => item.id === componentId);

    if (metadata == null) {
        throw new Error(`component metadata not found: ${componentId}`);
    }

    return metadata;
}

function createSpectrum({
    id,
    componentIds,
    name = 'velocity',
    type = 'POINT',
    shape = 'Vector3',
    ranges = new Map(),
    omittedRangeIds = [],
}: CreateSpectrumOptions): VisorSpectrumInfo {
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

function createSpectrumCollection(spectra: VisorSpectrumInfo[]): VisorSpectrumCollection {
    const array = [...spectra];

    const map = new Map<string, VisorSpectrumInfo>(
        array.map((spectrum) => [spectrum.id, spectrum])
    );

    return {
        array,

        getSpectrum(id: string | null) {
            if (id == null) {
                return null;
            }

            return map.get(id) ?? null;
        },
    };
}

function createActorNode({
    spectrumId,
    spectrumComponent,
    spectra,
}: CreateActorNodeOptions): VisorSceneNodeExtended {
    return {
        name: 'mesh',
        opacity: 1,
        spectrumId,
        spectrumComponent,
        customDiffuseColorHex: '#ffffff',
        spectrumCollection: createSpectrumCollection(spectra),
    } as unknown as VisorSceneNodeExtended;
}

function createComponentOptions(componentIds: number[]): VisorSpectrumComponentMetadata[] {
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
