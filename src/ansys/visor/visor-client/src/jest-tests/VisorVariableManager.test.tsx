import VisorVtkDataArray from '../state/appstate/vtkInfo/VisorVtkDataArray.tsx';
import VisorVariableState from '../state/appstate/VisorVariableState.tsx';
import { getVariableManager, VisorVariableInfo } from '../state/VisorVariableManager.tsx';

describe('getVariableManager', () => {
    describe('manager lifecycle', () => {
        test('returns a frozen manager object', () => {
            const manager = getVariableManager();

            expect(Object.isFrozen(manager)).toBe(true);
            expect(typeof manager.addDataArrayMetadata).toBe('function');
            expect(typeof manager.finishAddingDataArrayMetadata).toBe('function');
        });

        test('throws when globalVariableCollection is read before finishing', () => {
            const manager = getVariableManager();

            expect(() => manager.globalVariableCollection).toThrow(
                'finishAddingDataArrayMetadata() has not been called yet'
            );
        });

        test('creates an empty global collection when no metadata was added', () => {
            const manager = getVariableManager();

            manager.finishAddingDataArrayMetadata();

            expect(manager.globalVariableCollection.array).toEqual([]);
            expect(manager.globalVariableCollection.getVariable(null)).toBeNull();
            expect(manager.globalVariableCollection.getVariable('missing')).toBeNull();
        });

        test('throws when finishAddingDataArrayMetadata is called twice', () => {
            const manager = getVariableManager();

            manager.finishAddingDataArrayMetadata();

            expect(() => {
                manager.finishAddingDataArrayMetadata();
            }).toThrow('finishAddingDataArrayMetadata() has already been called');
        });

        test('different managers have independent state', () => {
            const firstManager = getVariableManager();
            const secondManager = getVariableManager();

            firstManager.setRecords([
                new VisorVariableState({
                    id: 'POINT::temperature::1',
                    arrayName: 'temperature',
                    type: 'POINT',
                    numComponents: 1,
                    partIds: [1],
                    defaultMagnitudeRange: [0, 10],
                    defaultRanges: [[0, 10]],
                    magnitudeRange: [0, 10],
                    ranges: [[0, 10]],
                }),
            ]);
            firstManager.finishAddingDataArrayMetadata();
            secondManager.finishAddingDataArrayMetadata();

            expect(firstManager.globalVariableCollection.array).toHaveLength(1);
            expect(secondManager.globalVariableCollection.array).toHaveLength(0);
        });
    });

    describe('addDataArrayMetadata', () => {
        test('returns an empty frozen collection for an empty array', () => {
            const manager = getVariableManager();

            const collection = manager.addDataArrayMetadata([]);

            expect(collection.array).toEqual([]);
            expect(Object.isFrozen(collection)).toBe(true);
            expect(Object.isFrozen(collection.array)).toBe(true);
        });

        test('creates scalar variable metadata', () => {
            const manager = getVariableManager();

            const collection = manager.addDataArrayMetadata([
                createDataArray({
                    type: 'POINT',
                    name: 'temperature',
                    numComponents: 1,
                    magnitudeRange: [-20, 100],
                    ranges: [[-20, 100]],
                }),
            ]);

            const variable = collection.array[0];

            expect(variable.id).toBe('POINT::temperature::1');
            expect(variable.type).toBe('POINT');
            expect(variable.name).toBe('temperature');
            expect(variable.shape).toBe('Scalar');
            expect(variable.fullName).toBe('POINT - temperature (Scalar)');
            expect(variable.numComponents).toBe(1);
            expect(variable.componentOptions).toEqual([
                {
                    id: -1,
                    name: 'Magnitude',
                },
            ]);
        });

        test('creates Vector2 component options', () => {
            const variable = addSingleVariable(
                createDataArray({
                    numComponents: 2,
                    ranges: [
                        [-1, 1],
                        [-2, 2],
                    ],
                })
            );

            expect(variable.shape).toBe('Vector2');
            expect(variable.componentOptions).toEqual([
                { id: -1, name: 'Magnitude' },
                { id: 0, name: 'X' },
                { id: 1, name: 'Y' },
            ]);
        });

        test('creates Vector3 component options', () => {
            const variable = addSingleVariable(
                createDataArray({
                    numComponents: 3,
                    ranges: [
                        [-1, 1],
                        [-2, 2],
                        [-3, 3],
                    ],
                })
            );

            expect(variable.shape).toBe('Vector3');
            expect(variable.componentOptions).toEqual([
                { id: -1, name: 'Magnitude' },
                { id: 0, name: 'X' },
                { id: 1, name: 'Y' },
                { id: 2, name: 'Z' },
            ]);
        });

        test('creates Vector4 component options', () => {
            const variable = addSingleVariable(
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

            expect(variable.shape).toBe('Vector4');
            expect(variable.componentOptions).toEqual([
                { id: -1, name: 'Magnitude' },
                { id: 0, name: 'X' },
                { id: 1, name: 'Y' },
                { id: 2, name: 'Z' },
                { id: 3, name: 'W' },
            ]);
        });

        test('creates nine-component tensor labels', () => {
            const variable = addSingleVariable(
                createDataArray({
                    numComponents: 9,
                    ranges: Array.from({ length: 9 }, (_, i) => [-i, i]),
                })
            );

            expect(variable.componentOptions).toEqual([
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
            const manager = getVariableManager();

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

        test('returns variables in input order', () => {
            const manager = getVariableManager();

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

        test('creates separate variables for different names', () => {
            const manager = getVariableManager();

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

        test('creates separate variables for different types', () => {
            const manager = getVariableManager();

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

        test('creates separate variables for different component counts', () => {
            const manager = getVariableManager();

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

    describe('local variable collections', () => {
        test('looks up a variable by ID', () => {
            const manager = getVariableManager();
            const collection = manager.addDataArrayMetadata([createDataArray()]);

            const variable = collection.array[0];

            expect(collection.getVariable(variable.id)).toBe(variable);
        });

        test('returns null for null and unknown IDs', () => {
            const manager = getVariableManager();
            const collection = manager.addDataArrayMetadata([createDataArray()]);

            expect(collection.getVariable(null)).toBeNull();
            expect(collection.getVariable('unknown')).toBeNull();
        });

        test('returns a frozen collection and array', () => {
            const manager = getVariableManager();
            const collection = manager.addDataArrayMetadata([createDataArray()]);

            expect(Object.isFrozen(collection)).toBe(true);
            expect(Object.isFrozen(collection.array)).toBe(true);
        });

        test('variable metadata objects are frozen', () => {
            const variable = addSingleVariable(createDataArray());

            expect(Object.isFrozen(variable)).toBe(true);
        });
    });

    describe('range information', () => {
        test('returns the magnitude range for component -1', () => {
            const variable = addSingleVariable(
                createDataArray({
                    magnitudeRange: [0, 10],
                })
            );

            expect(variable.getRangeInfo(-1)).toEqual({
                defaultRange: [0, 10],
                customRange: [0, 10],
            });
        });

        test('returns the range for an individual component', () => {
            const variable = addSingleVariable(
                createDataArray({
                    ranges: [
                        [-1, 1],
                        [-2, 2],
                        [-3, 3],
                    ],
                })
            );

            expect(variable.getRangeInfo(0)).toEqual({
                defaultRange: [-1, 1],
                customRange: [-1, 1],
            });

            expect(variable.getRangeInfo(2)).toEqual({
                defaultRange: [-3, 3],
                customRange: [-3, 3],
            });
        });

        test('returns null for null, undefined, and out-of-range components', () => {
            const variable = addSingleVariable(createDataArray());

            expect(variable.getRangeInfo(null)).toBeNull();
            expect(variable.getRangeInfo(undefined)).toBeNull();
            expect(variable.getRangeInfo(-2)).toBeNull();
            expect(variable.getRangeInfo(3)).toBeNull();
            expect(variable.getRangeInfo(100)).toBeNull();
        });

        test('returns cloned range arrays', () => {
            const variable = addSingleVariable(
                createDataArray({
                    magnitudeRange: [0, 10],
                })
            );

            const first = variable.getRangeInfo(-1)!;
            first.defaultRange[0] = -999;
            first.customRange[1] = 999;

            const second = variable.getRangeInfo(-1)!;

            expect(second.defaultRange).toEqual([0, 10]);
            expect(second.customRange).toEqual([0, 10]);
            expect(second.defaultRange).not.toBe(first.defaultRange);
            expect(second.customRange).not.toBe(first.customRange);
        });

        test('setCustomRange changes only the custom range', () => {
            const variable = addSingleVariable(
                createDataArray({
                    ranges: [
                        [-1, 1],
                        [-2, 2],
                        [-3, 3],
                    ],
                })
            );

            variable.setCustomRange(1, -20, 20);

            expect(variable.getRangeInfo(1)).toEqual({
                defaultRange: [-2, 2],
                customRange: [-20, 20],
            });
        });

        test('setCustomRange can change the magnitude range', () => {
            const variable = addSingleVariable(
                createDataArray({
                    magnitudeRange: [0, 10],
                })
            );

            variable.setCustomRange(-1, 2, 8);

            expect(variable.getRangeInfo(-1)).toEqual({
                defaultRange: [0, 10],
                customRange: [2, 8],
            });
        });

        test('setCustomRange ignores invalid component IDs', () => {
            const variable = addSingleVariable(createDataArray());

            variable.setCustomRange(-2, -100, 100);
            variable.setCustomRange(100, -100, 100);

            expect(variable.getRangeInfo(-1)).toEqual({
                defaultRange: [0, 10],
                customRange: [0, 10],
            });
        });
    });

    describe('duplicate variable aggregation', () => {
        test('reuses the same variable object for the same ID', () => {
            const manager = getVariableManager();

            const firstCollection = manager.addDataArrayMetadata([createDataArray()]);

            const secondCollection = manager.addDataArrayMetadata([createDataArray()]);

            expect(secondCollection.array[0]).toBe(firstCollection.array[0]);
        });

        test('expands default ranges using duplicate metadata', () => {
            const manager = getVariableManager();

            const firstVariable = manager.addDataArrayMetadata([
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

            expect(firstVariable.getRangeInfo(-1)).toEqual({
                defaultRange: [-5, 20],
                customRange: [-5, 20],
            });

            expect(firstVariable.getRangeInfo(0)).toEqual({
                defaultRange: [-10, 1],
                customRange: [-10, 1],
            });

            expect(firstVariable.getRangeInfo(1)).toEqual({
                defaultRange: [-2, 15],
                customRange: [-2, 15],
            });

            expect(firstVariable.getRangeInfo(2)).toEqual({
                defaultRange: [-30, 30],
                customRange: [-30, 30],
            });
        });

        test('resets custom ranges to the expanded defaults when duplicate metadata is added', () => {
            const manager = getVariableManager();

            const variable = manager.addDataArrayMetadata([
                createDataArray({
                    magnitudeRange: [0, 10],
                }),
            ]).array[0];

            variable.setCustomRange(-1, 2, 8);

            expect(variable.getRangeInfo(-1)?.customRange).toEqual([2, 8]);

            manager.addDataArrayMetadata([
                createDataArray({
                    magnitudeRange: [-5, 20],
                }),
            ]);

            expect(variable.getRangeInfo(-1)).toEqual({
                defaultRange: [-5, 20],
                customRange: [-5, 20],
            });
        });

        test('keeps existing bounds when duplicate ranges are narrower', () => {
            const manager = getVariableManager();

            const variable = manager.addDataArrayMetadata([
                createDataArray({
                    magnitudeRange: [-10, 20],
                }),
            ]).array[0];

            manager.addDataArrayMetadata([
                createDataArray({
                    magnitudeRange: [-5, 10],
                }),
            ]);

            expect(variable.getRangeInfo(-1)).toEqual({
                defaultRange: [-10, 20],
                customRange: [-10, 20],
            });
        });
    });

    describe('global variable collection', () => {

        test('returns null for null and unknown global IDs', () => {
            const manager = getVariableManager();

            manager.addDataArrayMetadata([createDataArray()]);
            manager.finishAddingDataArrayMetadata();

            expect(manager.globalVariableCollection.getVariable(null)).toBeNull();

            expect(manager.globalVariableCollection.getVariable('unknown')).toBeNull();
        });

        test('returns a frozen global collection', () => {
            const manager = getVariableManager();

            manager.finishAddingDataArrayMetadata();

            expect(Object.isFrozen(manager.globalVariableCollection)).toBe(true);
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

function addSingleVariable(dataArray: VisorVtkDataArray): VisorVariableInfo {
    const manager = getVariableManager();

    return manager.addDataArrayMetadata([dataArray]).array[0];
}
