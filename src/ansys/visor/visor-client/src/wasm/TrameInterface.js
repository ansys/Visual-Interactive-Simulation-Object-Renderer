import { Trame } from '@kitware/trame/src/trame.js';

/**
 * @typedef {string|number|boolean|null|Object|Record<string,TrameStateValue>} TrameStateValue
 */

/**
 * @name Trame#client
 * @type {{getConnection:()=>TrameConnection}}
 */

/**
 * @typedef {{
 * connect:function():void,
 * destroy:function(e):void,
 * fireConnectionClose:function(u):void,
 * fireConnectionError:function(u):void,
 * fireConnectionReady:function(u):void,
 * getSession:function():TrameSession,
 * getUrl:function():string,
 * isA:function(n):boolean,
 * onConnectionClose:function(u):void,
 * onConnectionError:function(u):void,
 * onConnectionReady:function(u):void
 * }} TrameConnection
 */

/**
 * @typedef {{
 * addAttachment:function(h:any):void,
 * call:function(h:any,l:any,p2:any):Promise<any>,
 * close:function():void,
 * destroy:function():void,
 * isA:function(n:any):void,
 * onconnect:function(h:any):void,
 * onmessage:function(h:any):Promise<void>,
 * subscribe:function(h:any,l:any):void,
 * unsubscribe:function(h:any):void
 * }} TrameSession
 */

/**
 * @desc `TrameInterface` represents a connection to a Trame server.
 * This class is simply a wrapper around a `Trame` object with the
 * goal of simplifying communication with `Trame`.
 */
export default class TrameInterface {
    static #allowConstruction = false;
    /**@type{Trame}*/
    #trame;
    /**@type{Object}*/
    #callbacksObject = {};

    /**
     * @param {string} s
     * @return {boolean}
     */
    static #stringIsInvalid(s) {
        return typeof s !== 'string' || s.length === 0;
    }

    constructor() {
        if (!TrameInterface.#allowConstruction) {
            const msg = `Constructor is private.`;
            throw new Error(`${msg} Use getInstanceAsync().`);
        }
    }

    /**
     * @param {string} webSocketUrl
     * @param {string} refNameStateKey
     * @return {Promise<TrameInterface>}
     */
    static async getInstanceAsync(webSocketUrl, refNameStateKey) {
        if (TrameInterface.#stringIsInvalid(refNameStateKey)) {
            throw new Error(`refNameStateKey must be a non-empty string`);
        }
        const trame = new Trame();
        await trame.connect({
            application: 'trame',
            sessionURL: webSocketUrl,
        });
        const connection = trame.client.getConnection();

        /**@type{TrameInterface}*/
        let instance;
        this.#allowConstruction = true;
        try {
            instance = new TrameInterface();
        } finally {
            this.#allowConstruction = false;
        }

        instance.#trame = trame;
        instance.session = connection.getSession();
        const refName = instance.getState(refNameStateKey);
        if (TrameInterface.#stringIsInvalid(refName)) {
            const msg = `The Trame state value obtained for '${refNameStateKey}' is invalid.`;
            throw new Error(`${msg} '${refNameStateKey}' must be a non-empty string.`);
        }
        trame.refs[refName] = instance.#callbacksObject;

        return Object.freeze(instance);
    }

    /**@type{TrameSession}*/
    session;
    /**
     * @param {Object} obj
     */
    addCallbacks = (obj) => {
        if (typeof obj !== 'object') {
            throw new Error(`obj must be a non-function object`);
        }
        for (const [key, val] of Object.entries(obj)) {
            if (typeof val === 'function') {
                this.addSingleCallback(key, val);
            }
        }
    };
    /**
     * @param {string} name
     * @param {function(...any):any} f
     */
    addSingleCallback = (name, f) => {
        if (typeof name !== 'string') {
            throw new Error(`name must be a string`);
        } else if (typeof f !== 'function') {
            throw new Error(`f must be a function`);
        }
        const callbacksObject = this.#callbacksObject;
        if (name in callbacksObject) {
            throw new Error(`the property with name '${name}' has already been added`);
        }
        callbacksObject[name] = f;
    };
    /**
     * @param {string} key
     * @return {TrameStateValue}
     */
    getState = (key) => {
        return this.#trame.state.get(key);
    };
    /**
     * @param {string} key
     * @param {any} val
     * @return {Promise<void>}
     */
    setStateAsync = async (key, val) => {
        await this.#trame.state.set(key, val);
    };
    /**
     * @param {string} triggerName
     * @param {...any} args
     * @return {Promise<any>}
     */
    triggerAsync = async (triggerName, ...args) => {
        return await this.#trame.trigger(triggerName, [...args]);
    };
}
