import VisorVtkDataArray from '../state/appstate/vtkInfo/VisorVtkDataArray.tsx';

describe('VisorVtkDataArray', () => {
    test('constructs an instance from an object', () => {
        const input = createValidInput();

        const result = new VisorVtkDataArray(input);

        expect(result).toBeInstanceOf(VisorVtkDataArray);
        expect(result.indexForType).toBe(2);
        expect(result.type).toBe('POINT');
        expect(result.name).toBe('displacement');
        expect(result.numComponents).toBe(3);
        expect(result.magnitudeRange).toEqual([0, 10]);
        expect(result.ranges).toEqual([
            [-1, 1],
            [-2, 2],
            [-3, 3],
        ]);
    });

    test('constructs an instance from a JSON string', () => {
        const input = createValidInput();

        const result = new VisorVtkDataArray(JSON.stringify(input));

        expect(result.indexForType).toBe(input.indexForType);
        expect(result.type).toBe(input.type);
        expect(result.name).toBe(input.name);
        expect(result.numComponents).toBe(input.numComponents);
        expect(result.magnitudeRange).toEqual(input.magnitudeRange);
        expect(result.ranges).toEqual(input.ranges);
    });

    test('uses the original array references when constructed from an object', () => {
        const input = createValidInput();

        const result = new VisorVtkDataArray(input);

        expect(result.magnitudeRange).toBe(input.magnitudeRange);
        expect(result.ranges).toBe(input.ranges);
    });

    test('creates new arrays when constructed from JSON', () => {
        const input = createValidInput();

        const result = new VisorVtkDataArray(JSON.stringify(input));

        expect(result.magnitudeRange).not.toBe(input.magnitudeRange);
        expect(result.ranges).not.toBe(input.ranges);
        expect(result.magnitudeRange).toEqual(input.magnitudeRange);
        expect(result.ranges).toEqual(input.ranges);
    });

    test('ignores additional object properties', () => {
        const input = {
            ...createValidInput(),
            unusedProperty: 'unused',
        };

        const result = new VisorVtkDataArray(input as any);

        expect(result).not.toHaveProperty('unusedProperty');
    });

    test('throws for malformed JSON', () => {
        expect(() => {
            new VisorVtkDataArray('{invalid json');
        }).toThrow(SyntaxError);
    });

    test.each([
        [
            'indexForType',
            {
                ...createValidInput(),
                indexForType: '2',
            },
        ],
        [
            'type',
            {
                ...createValidInput(),
                type: 123,
            },
        ],
        [
            'name',
            {
                ...createValidInput(),
                name: null,
            },
        ],
        [
            'numComponents',
            {
                ...createValidInput(),
                numComponents: '3',
            },
        ],
        [
            'magnitudeRange',
            {
                ...createValidInput(),
                magnitudeRange: '0,10',
            },
        ],
        [
            'ranges',
            {
                ...createValidInput(),
                ranges: {},
            },
        ],
    ])('throws when %s has an invalid type', (_propertyName, input) => {
        expect(() => {
            new VisorVtkDataArray(input as any);
        }).toThrow();
    });

    test.each(['indexForType', 'type', 'name', 'numComponents', 'magnitudeRange', 'ranges'])(
        'throws when %s is missing',
        (propertyName) => {
            const input = createValidInput();

            delete (input as any)[propertyName];

            expect(() => {
                new VisorVtkDataArray(input as any);
            }).toThrow();
        }
    );

    test('throws when constructed with null', () => {
        expect(() => {
            new VisorVtkDataArray(null);
        }).toThrow();
    });

    test('allows empty range arrays because validation only requires arrays', () => {
        const input = {
            ...createValidInput(),
            magnitudeRange: [],
            ranges: [],
        };

        const result = new VisorVtkDataArray(input);

        expect(result.magnitudeRange).toEqual([]);
        expect(result.ranges).toEqual([]);
    });
});

function createValidInput() {
    return {
        indexForType: 2,
        type: 'POINT',
        name: 'displacement',
        numComponents: 3,
        magnitudeRange: [0, 10],
        ranges: [
            [-1, 1],
            [-2, 2],
            [-3, 3],
        ],
    };
}
