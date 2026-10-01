import VisorVariableState from '../state/appstate/VisorVariableState.tsx';
import { getVariableManager, VisorVariableInfo } from '../state/VisorVariableManager.tsx';

describe('getVariableManager', () => {
    describe('manager lifecycle', () => {
        test('returns a frozen manager object', () => {
            const manager = getVariableManager();

            expect(Object.isFrozen(manager)).toBe(true);
            expect(typeof manager.setRecords).toBe('function');
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

    describe('setRecords', () => {
        test('creates scalar variable metadata', () => {
            const variable = heldVariable({
                id: 'POINT::temperature::1',
                arrayName: 'temperature',
                numComponents: 1,
                defaultMagnitudeRange: [-20, 100],
                defaultRanges: [[-20, 100]],
                magnitudeRange: [-20, 100],
                ranges: [[-20, 100]],
            });

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
            const ranges = [
                [-1, 1],
                [-2, 2],
            ];
            const variable = heldVariable({
                id: 'POINT::displacement::2',
                numComponents: 2,
                defaultRanges: ranges,
                ranges,
            });

            expect(variable.shape).toBe('Vector2');
            expect(variable.componentOptions).toEqual([
                { id: -1, name: 'Magnitude' },
                { id: 0, name: 'X' },
                { id: 1, name: 'Y' },
            ]);
        });

        test('creates Vector3 component options', () => {
            const variable = heldVariable();

            expect(variable.shape).toBe('Vector3');
            expect(variable.componentOptions).toEqual([
                { id: -1, name: 'Magnitude' },
                { id: 0, name: 'X' },
                { id: 1, name: 'Y' },
                { id: 2, name: 'Z' },
            ]);
        });

        test('creates Vector4 component options', () => {
            const ranges = [
                [-1, 1],
                [-2, 2],
                [-3, 3],
                [-4, 4],
            ];
            const variable = heldVariable({
                id: 'POINT::displacement::4',
                numComponents: 4,
                defaultRanges: ranges,
                ranges,
            });

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
            const ranges = Array.from({ length: 9 }, (_, i) => [-i, i]);
            const variable = heldVariable({
                id: 'POINT::stress::9',
                arrayName: 'stress',
                numComponents: 9,
                defaultRanges: ranges,
                ranges,
            });

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
            const ranges = [
                [0, 1],
                [0, 1],
                [0, 1],
                [0, 1],
                [0, 1],
            ];

            expect(() => {
                manager.setRecords([
                    record({
                        id: 'POINT::displacement::5',
                        numComponents: 5,
                        defaultRanges: ranges,
                        ranges,
                    }),
                ]);
            }).toThrow('Do we support label info for variables with 5 component(s)?');
        });

        test('returns variables in input order', () => {
            const manager = getVariableManager();

            manager.setRecords([
                record({ id: 'POINT::first::3', arrayName: 'first' }),
                record({ id: 'POINT::second::3', arrayName: 'second' }),
            ]);
            manager.finishAddingDataArrayMetadata();

            expect(manager.globalVariableCollection.array.map((item) => item.name)).toEqual([
                'first',
                'second',
            ]);
        });

        test('reuses the same variable object for the same ID', () => {
            const manager = getVariableManager();
            manager.finishAddingDataArrayMetadata();

            manager.setRecords([record()]);
            const first = manager.globalVariableCollection.getVariable('POINT::displacement::3');
            manager.setRecords([record({ magnitudeRange: [1, 9] })]);

            expect(first).not.toBeNull();
            expect(manager.globalVariableCollection.getVariable('POINT::displacement::3')).toBe(
                first
            );
        });
    });

    describe('local variable collections', () => {
        test('looks up a variable by ID', () => {
            const manager = getVariableManager();
            const collection = manager.getPartVariableCollection(1);
            manager.setRecords([record()]);

            const variable = collection.array[0];

            expect(collection.getVariable(variable.id)).toBe(variable);
        });

        test('returns null for null and unknown IDs', () => {
            const manager = getVariableManager();
            const collection = manager.getPartVariableCollection(1);
            manager.setRecords([record()]);

            expect(collection.getVariable(null)).toBeNull();
            expect(collection.getVariable('unknown')).toBeNull();
        });

        test('variable metadata objects are frozen', () => {
            const variable = heldVariable();

            expect(Object.isFrozen(variable)).toBe(true);
        });
    });

    describe('range information', () => {
        test('returns null for null, undefined, and out-of-range components', () => {
            const variable = heldVariable();

            expect(variable.getRangeInfo(null)).toBeNull();
            expect(variable.getRangeInfo(undefined)).toBeNull();
            expect(variable.getRangeInfo(-2)).toBeNull();
            expect(variable.getRangeInfo(3)).toBeNull();
            expect(variable.getRangeInfo(100)).toBeNull();
        });

        test('returns cloned range arrays', () => {
            const variable = heldVariable();

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
            const variable = heldVariable();

            variable.setCustomRange(1, -20, 20);

            expect(variable.getRangeInfo(1)).toEqual({
                defaultRange: [-2, 2],
                customRange: [-20, 20],
            });
        });

        test('setCustomRange can change the magnitude range', () => {
            const variable = heldVariable();

            variable.setCustomRange(-1, 2, 8);

            expect(variable.getRangeInfo(-1)).toEqual({
                defaultRange: [0, 10],
                customRange: [2, 8],
            });
        });

        test('setCustomRange ignores invalid component IDs', () => {
            const variable = heldVariable();

            variable.setCustomRange(-2, -100, 100);
            variable.setCustomRange(100, -100, 100);

            expect(variable.getRangeInfo(-1)).toEqual({
                defaultRange: [0, 10],
                customRange: [0, 10],
            });
        });
    });

    describe('global variable collection', () => {
        test('returns null for null and unknown global IDs', () => {
            const manager = getVariableManager();

            manager.setRecords([record()]);
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

/**
 * A complete record, by default `POINT::displacement::3` on part 1 with
 * magnitude [0, 10] and components [-1, 1], [-2, 2], [-3, 3], custom equal to
 * default.
 */
function record(overrides: Record<string, unknown> = {}): VisorVariableState {
    return new VisorVariableState({
        id: 'POINT::displacement::3',
        arrayName: 'displacement',
        type: 'POINT',
        numComponents: 3,
        partIds: [1],
        defaultMagnitudeRange: [0, 10],
        defaultRanges: [
            [-1, 1],
            [-2, 2],
            [-3, 3],
        ],
        magnitudeRange: [0, 10],
        ranges: [
            [-1, 1],
            [-2, 2],
            [-3, 3],
        ],
        ...overrides,
    });
}

/** The one variable a fresh manager holds after delivering a single record. */
function heldVariable(overrides: Record<string, unknown> = {}): VisorVariableInfo {
    const manager = getVariableManager();
    manager.setRecords([record(overrides)]);
    manager.finishAddingDataArrayMetadata();

    return manager.globalVariableCollection.array[0];
}
