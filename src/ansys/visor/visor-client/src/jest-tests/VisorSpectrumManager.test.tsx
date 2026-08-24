import VisorVtkDataArray from '../state/appstate/vtkInfo/VisorVtkDataArray.tsx';
import { getSpectrumManager, VisorSpectrumInfo } from '../state/VisorSpectrumManager.tsx';

describe('getSpectrumManager', () => {
    describe('manager lifecycle', () => {
        test('returns a frozen manager object', () => {
            const manager = getSpectrumManager();

            expect(Object.isFrozen(manager)).toBe(true);
            expect(typeof manager.addDataArrayMetadata).toBe('function');
            expect(typeof manager.finishAddingDataArrayMetadata).toBe('function');
        });

        test('throws when globalSpectrumCollection is read before finishing', () => {
            const manager = getSpectrumManager();

            expect(() => manager.globalSpectrumCollection).toThrow(
                'finishAddingDataArrayMetadata() has not been called yet'
            );
        });

        test('creates an empty global collection when no metadata was added', () => {
            const manager = getSpectrumManager();

            manager.finishAddingDataArrayMetadata();

            expect(manager.globalSpectrumCollection.array).toEqual([]);
            expect(manager.globalSpectrumCollection.getSpectrum(null)).toBeNull();
            expect(manager.globalSpectrumCollection.getSpectrum('missing')).toBeNull();
        });

        test('throws when finishAddingDataArrayMetadata is called twice', () => {
            const manager = getSpectrumManager();

            manager.finishAddingDataArrayMetadata();

            expect(() => {
                manager.finishAddingDataArrayMetadata();
            }).toThrow('finishAddingDataArrayMetadata() has already been called');
        });

        test('different managers have independent state', () => {
            const firstManager = getSpectrumManager();
            const secondManager = getSpectrumManager();

            firstManager.addDataArrayMetadata([createDataArray()]);
            firstManager.finishAddingDataArrayMetadata();
            secondManager.finishAddingDataArrayMetadata();

            expect(firstManager.globalSpectrumCollection.array).toHaveLength(1);
            expect(secondManager.globalSpectrumCollection.array).toHaveLength(0);
        });
    });

    describe('addDataArrayMetadata', () => {
        test('returns an empty frozen collection for an empty array', () => {
            const manager = getSpectrumManager();

            const collection = manager.addDataArrayMetadata([]);

            expect(collection.array).toEqual([]);
            expect(Object.isFrozen(collection)).toBe(true);
            expect(Object.isFrozen(collection.array)).toBe(true);
        });

        test('creates scalar spectrum metadata', () => {
            const manager = getSpectrumManager();

            const collection = manager.addDataArrayMetadata([
                createDataArray({
                    type: 'POINT',
                    name: 'temperature',
                    numComponents: 1,
                    magnitudeRange: [-20, 100],
                    ranges: [[-20, 100]],
                }),
            ]);

            const spectrum = collection.array[0];

            expect(spectrum.id).toBe('POINT::temperature::1');
            expect(spectrum.type).toBe('POINT');
            expect(spectrum.name).toBe('temperature');
            expect(spectrum.shape).toBe('Scalar');
            expect(spectrum.fullName).toBe('POINT - temperature (Scalar)');
            expect(spectrum.numComponents).toBe(1);
            expect(spectrum.componentOptions).toEqual([
                {
                    id: -1,
                    name: 'Magnitude',
                },
            ]);
        });

        test('creates Vector2 component options', () => {
            const spectrum = addSingleSpectrum(
                createDataArray({
                    numComponents: 2,
                    ranges: [
                        [-1, 1],
                        [-2, 2],
                    ],
                })
            );

            expect(spectrum.shape).toBe('Vector2');
            expect(spectrum.componentOptions).toEqual([
                { id: -1, name: 'Magnitude' },
                { id: 0, name: 'X' },
                { id: 1, name: 'Y' },
            ]);
        });

        test('creates Vector3 component options', () => {
            const spectrum = addSingleSpectrum(
                createDataArray({
                    numComponents: 3,
                    ranges: [
                        [-1, 1],
                        [-2, 2],
                        [-3, 3],
                    ],
                })
            );

            expect(spectrum.shape).toBe('Vector3');
            expect(spectrum.componentOptions).toEqual([
                { id: -1, name: 'Magnitude' },
                { id: 0, name: 'X' },
                { id: 1, name: 'Y' },
                { id: 2, name: 'Z' },
            ]);
        });

        test('creates Vector4 component options', () => {
            const spectrum = addSingleSpectrum(
                createDataArray({
                    numComponents: 4,
                    ranges: [
                        [-1, 1],
                        [-2, 2],
                        [-3, 3],
                        [-4, 4],
                    ],
                })
            );

            expect(spectrum.shape).toBe('Vector4');
            expect(spectrum.componentOptions).toEqual([
                { id: -1, name: 'Magnitude' },
                { id: 0, name: 'X' },
                { id: 1, name: 'Y' },
                { id: 2, name: 'Z' },
                { id: 3, name: 'W' },
            ]);
        });

        test('creates nine-component tensor labels', () => {
            const spectrum = addSingleSpectrum(
                createDataArray({
                    numComponents: 9,
                    ranges: Array.from({ length: 9 }, (_, i) => [-i, i]),
                })
            );

            expect(spectrum.componentOptions).toEqual([
                { id: -1, name: 'Magnitude' },
                { id: 0, name: 'XX' },
                { id: 1, name: 'XY' },
                { id: 2, name: 'XZ' },
                { id: 3, name: 'YX' },
                { id: 4, name: 'YY' },
                { id: 5, name: 'YZ' },
                { id: 6, name: 'ZX' },
                { id: 7, name: 'ZY' },
                { id: 8, name: 'ZZ' },
            ]);
        });

        test('throws for an unsupported component count', () => {
            const manager = getSpectrumManager();

            expect(() => {
                manager.addDataArrayMetadata([
                    createDataArray({
                        numComponents: 5,
                        ranges: [
                            [0, 1],
                            [0, 1],
                            [0, 1],
                            [0, 1],
                            [0, 1],
                        ],
                    }),
                ]);
            }).toThrow('Do we support label info for data arrays with 5 component(s)?');
        });

        test('returns spectra in input order', () => {
            const manager = getSpectrumManager();

            const collection = manager.addDataArrayMetadata([
                createDataArray({
                    name: 'first',
                }),
                createDataArray({
                    name: 'second',
                }),
            ]);

            expect(collection.array.map((item) => item.name)).toEqual(['first', 'second']);
        });

        test('creates separate spectra for different names', () => {
            const manager = getSpectrumManager();

            const collection = manager.addDataArrayMetadata([
                createDataArray({
                    name: 'temperature',
                }),
                createDataArray({
                    name: 'pressure',
                }),
            ]);

            expect(collection.array).toHaveLength(2);
            expect(collection.array[0]).not.toBe(collection.array[1]);
        });

        test('creates separate spectra for different types', () => {
            const manager = getSpectrumManager();

            const collection = manager.addDataArrayMetadata([
                createDataArray({
                    type: 'POINT',
                }),
                createDataArray({
                    type: 'CELL',
                }),
            ]);

            expect(collection.array).toHaveLength(2);
            expect(collection.array[0].id).toBe('POINT::displacement::3');
            expect(collection.array[1].id).toBe('CELL::displacement::3');
        });

        test('creates separate spectra for different component counts', () => {
            const manager = getSpectrumManager();

            const collection = manager.addDataArrayMetadata([
                createDataArray({
                    numComponents: 2,
                    ranges: [
                        [-1, 1],
                        [-2, 2],
                    ],
                }),
                createDataArray({
                    numComponents: 3,
                    ranges: [
                        [-1, 1],
                        [-2, 2],
                        [-3, 3],
                    ],
                }),
            ]);

            expect(collection.array).toHaveLength(2);
            expect(collection.array[0].id).toBe('POINT::displacement::2');
            expect(collection.array[1].id).toBe('POINT::displacement::3');
        });
    });

    describe('local spectrum collections', () => {
        test('looks up a spectrum by ID', () => {
            const manager = getSpectrumManager();
            const collection = manager.addDataArrayMetadata([createDataArray()]);

            const spectrum = collection.array[0];

            expect(collection.getSpectrum(spectrum.id)).toBe(spectrum);
        });

        test('returns null for null and unknown IDs', () => {
            const manager = getSpectrumManager();
            const collection = manager.addDataArrayMetadata([createDataArray()]);

            expect(collection.getSpectrum(null)).toBeNull();
            expect(collection.getSpectrum('unknown')).toBeNull();
        });

        test('returns a frozen collection and array', () => {
            const manager = getSpectrumManager();
            const collection = manager.addDataArrayMetadata([createDataArray()]);

            expect(Object.isFrozen(collection)).toBe(true);
            expect(Object.isFrozen(collection.array)).toBe(true);
        });

        test('spectrum metadata objects are frozen', () => {
            const spectrum = addSingleSpectrum(createDataArray());

            expect(Object.isFrozen(spectrum)).toBe(true);
        });
    });

    describe('range information', () => {
        test('returns the magnitude range for component -1', () => {
            const spectrum = addSingleSpectrum(
                createDataArray({
                    magnitudeRange: [0, 10],
                })
            );

            expect(spectrum.getRangeInfo(-1)).toEqual({
                defaultRange: [0, 10],
                customRange: [0, 10],
            });
        });

        test('returns the range for an individual component', () => {
            const spectrum = addSingleSpectrum(
                createDataArray({
                    ranges: [
                        [-1, 1],
                        [-2, 2],
                        [-3, 3],
                    ],
                })
            );

            expect(spectrum.getRangeInfo(0)).toEqual({
                defaultRange: [-1, 1],
                customRange: [-1, 1],
            });

            expect(spectrum.getRangeInfo(2)).toEqual({
                defaultRange: [-3, 3],
                customRange: [-3, 3],
            });
        });

        test('returns null for null, undefined, and out-of-range components', () => {
            const spectrum = addSingleSpectrum(createDataArray());

            expect(spectrum.getRangeInfo(null)).toBeNull();
            expect(spectrum.getRangeInfo(undefined)).toBeNull();
            expect(spectrum.getRangeInfo(-2)).toBeNull();
            expect(spectrum.getRangeInfo(3)).toBeNull();
            expect(spectrum.getRangeInfo(100)).toBeNull();
        });

        test('returns cloned range arrays', () => {
            const spectrum = addSingleSpectrum(
                createDataArray({
                    magnitudeRange: [0, 10],
                })
            );

            const first = spectrum.getRangeInfo(-1)!;
            first.defaultRange[0] = -999;
            first.customRange[1] = 999;

            const second = spectrum.getRangeInfo(-1)!;

            expect(second.defaultRange).toEqual([0, 10]);
            expect(second.customRange).toEqual([0, 10]);
            expect(second.defaultRange).not.toBe(first.defaultRange);
            expect(second.customRange).not.toBe(first.customRange);
        });

        test('setCustomRange changes only the custom range', () => {
            const spectrum = addSingleSpectrum(
                createDataArray({
                    ranges: [
                        [-1, 1],
                        [-2, 2],
                        [-3, 3],
                    ],
                })
            );

            spectrum.setCustomRange(1, -20, 20);

            expect(spectrum.getRangeInfo(1)).toEqual({
                defaultRange: [-2, 2],
                customRange: [-20, 20],
            });
        });

        test('setCustomRange can change the magnitude range', () => {
            const spectrum = addSingleSpectrum(
                createDataArray({
                    magnitudeRange: [0, 10],
                })
            );

            spectrum.setCustomRange(-1, 2, 8);

            expect(spectrum.getRangeInfo(-1)).toEqual({
                defaultRange: [0, 10],
                customRange: [2, 8],
            });
        });

        test('setCustomRange ignores invalid component IDs', () => {
            const spectrum = addSingleSpectrum(createDataArray());

            spectrum.setCustomRange(-2, -100, 100);
            spectrum.setCustomRange(100, -100, 100);

            expect(spectrum.getRangeInfo(-1)).toEqual({
                defaultRange: [0, 10],
                customRange: [0, 10],
            });
        });
    });

    describe('duplicate spectrum aggregation', () => {
        test('reuses the same spectrum object for the same ID', () => {
            const manager = getSpectrumManager();

            const firstCollection = manager.addDataArrayMetadata([createDataArray()]);

            const secondCollection = manager.addDataArrayMetadata([createDataArray()]);

            expect(secondCollection.array[0]).toBe(firstCollection.array[0]);
        });

        test('expands default ranges using duplicate metadata', () => {
            const manager = getSpectrumManager();

            const firstSpectrum = manager.addDataArrayMetadata([
                createDataArray({
                    magnitudeRange: [0, 10],
                    ranges: [
                        [-1, 1],
                        [-2, 2],
                        [-3, 3],
                    ],
                }),
            ]).array[0];

            manager.addDataArrayMetadata([
                createDataArray({
                    magnitudeRange: [-5, 20],
                    ranges: [
                        [-10, 0.5],
                        [-1, 15],
                        [-30, 30],
                    ],
                }),
            ]);

            expect(firstSpectrum.getRangeInfo(-1)).toEqual({
                defaultRange: [-5, 20],
                customRange: [-5, 20],
            });

            expect(firstSpectrum.getRangeInfo(0)).toEqual({
                defaultRange: [-10, 1],
                customRange: [-10, 1],
            });

            expect(firstSpectrum.getRangeInfo(1)).toEqual({
                defaultRange: [-2, 15],
                customRange: [-2, 15],
            });

            expect(firstSpectrum.getRangeInfo(2)).toEqual({
                defaultRange: [-30, 30],
                customRange: [-30, 30],
            });
        });

        test('resets custom ranges to the expanded defaults when duplicate metadata is added', () => {
            const manager = getSpectrumManager();

            const spectrum = manager.addDataArrayMetadata([
                createDataArray({
                    magnitudeRange: [0, 10],
                }),
            ]).array[0];

            spectrum.setCustomRange(-1, 2, 8);

            expect(spectrum.getRangeInfo(-1)?.customRange).toEqual([2, 8]);

            manager.addDataArrayMetadata([
                createDataArray({
                    magnitudeRange: [-5, 20],
                }),
            ]);

            expect(spectrum.getRangeInfo(-1)).toEqual({
                defaultRange: [-5, 20],
                customRange: [-5, 20],
            });
        });

        test('keeps existing bounds when duplicate ranges are narrower', () => {
            const manager = getSpectrumManager();

            const spectrum = manager.addDataArrayMetadata([
                createDataArray({
                    magnitudeRange: [-10, 20],
                }),
            ]).array[0];

            manager.addDataArrayMetadata([
                createDataArray({
                    magnitudeRange: [-5, 10],
                }),
            ]);

            expect(spectrum.getRangeInfo(-1)).toEqual({
                defaultRange: [-10, 20],
                customRange: [-10, 20],
            });
        });
    });

    describe('global spectrum collection', () => {
        test('contains spectra added before finishing', () => {
            const manager = getSpectrumManager();

            manager.addDataArrayMetadata([
                createDataArray({
                    name: 'temperature',
                }),
                createDataArray({
                    name: 'pressure',
                }),
            ]);

            manager.finishAddingDataArrayMetadata();

            const global = manager.globalSpectrumCollection;

            expect(global.array).toHaveLength(2);
            expect(global.array.map((item) => item.name)).toEqual(['temperature', 'pressure']);
        });

        test('contains only one entry for duplicate spectrum IDs', () => {
            const manager = getSpectrumManager();

            manager.addDataArrayMetadata([
                createDataArray({
                    name: 'temperature',
                }),
            ]);

            manager.addDataArrayMetadata([
                createDataArray({
                    name: 'temperature',
                }),
            ]);

            manager.finishAddingDataArrayMetadata();

            expect(manager.globalSpectrumCollection.array).toHaveLength(1);
        });

        test('returns the same spectrum object as a local collection', () => {
            const manager = getSpectrumManager();

            const local = manager.addDataArrayMetadata([createDataArray()]);

            manager.finishAddingDataArrayMetadata();

            const id = local.array[0].id;
            const global = manager.globalSpectrumCollection;

            expect(global.getSpectrum(id)).toBe(local.array[0]);
        });

        test('returns null for null and unknown global IDs', () => {
            const manager = getSpectrumManager();

            manager.addDataArrayMetadata([createDataArray()]);
            manager.finishAddingDataArrayMetadata();

            expect(manager.globalSpectrumCollection.getSpectrum(null)).toBeNull();

            expect(manager.globalSpectrumCollection.getSpectrum('unknown')).toBeNull();
        });

        test('returns a frozen global collection', () => {
            const manager = getSpectrumManager();

            manager.finishAddingDataArrayMetadata();

            expect(Object.isFrozen(manager.globalSpectrumCollection)).toBe(true);
        });
    });
});

interface DataArrayOptions {
    indexForType?: number;
    type?: string;
    name?: string;
    numComponents?: number;
    magnitudeRange?: number[];
    ranges?: number[][];
}

function createDataArray({
    indexForType = 0,
    type = 'POINT',
    name = 'displacement',
    numComponents = 3,
    magnitudeRange = [0, 10],
    ranges = [
        [-1, 1],
        [-2, 2],
        [-3, 3],
    ],
}: DataArrayOptions = {}): VisorVtkDataArray {
    return new VisorVtkDataArray({
        indexForType,
        type,
        name,
        numComponents,
        magnitudeRange,
        ranges,
    });
}

function addSingleSpectrum(dataArray: VisorVtkDataArray): VisorSpectrumInfo {
    const manager = getSpectrumManager();

    return manager.addDataArrayMetadata([dataArray]).array[0];
}
