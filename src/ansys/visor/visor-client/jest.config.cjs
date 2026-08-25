/** @type {import('jest').Config} */
const config = {
    // 'jsdom' ensures that Jest recognizes
    // the JavaScript "document" object
    // see https://stackoverflow.com/a/67845294
    testEnvironment: 'jsdom',
    verbose: true,
    moduleNameMapper: {
        // This solves the SyntaxError: Unexpected token ':' error
        // when Jest tests try to import CSS.
        // see https://stackoverflow.com/a/39434579
        '\\.(css|less|sass|scss)$': '<rootDir>/css-stub-for-jest.js',
    },
};

module.exports = config;
