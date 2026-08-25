import PrivateConstructor from '../utils/PrivateConstructor.js';

describe('PrivateConstructor', () => {
    test('exports a class', () => {
        expect(typeof PrivateConstructor).toBe('function');
    });

    test('throws when instantiated directly', () => {
        expect(() => new PrivateConstructor()).toThrow('constructor is private');
    });

    test('throws an Error instance when instantiated', () => {
        expect(() => new PrivateConstructor()).toThrow(Error);
    });

    test('prevents subclasses from being instantiated', () => {
        class DerivedClass extends PrivateConstructor {}

        expect(() => new DerivedClass()).toThrow('constructor is private');
    });
});
