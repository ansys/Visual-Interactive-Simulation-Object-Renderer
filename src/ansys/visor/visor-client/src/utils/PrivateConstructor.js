/**
 * Abstract base class that cannot be instantiated directly.
 *
 * @abstract
 */
class PrivateConstructor {
    /**
     * Creates an instance of {@link PrivateConstructor}.
     *
     * @throws {Error} Always throws because the constructor is private.
     * @protected
     */
    constructor() {
        throw new Error('constructor is private');
    }
}

export default PrivateConstructor;
