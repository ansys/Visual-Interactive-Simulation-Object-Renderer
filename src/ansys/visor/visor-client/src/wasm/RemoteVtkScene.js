import { VtkWASMHandler } from '@kitware/vtk-wasm/remote';
import TrameInterface from './TrameInterface.js';
import VtkScene from './VtkScene.js';
import { VtkWasmPerfCounter } from './VtkWasmPerfCounters.js';

/**
 * @typedef {string|number|boolean|null|Object|{observe:()=>number}|Record<string,FrontendVtkObject|(()=>Promise<FrontendVtkObject>)>} FrontendVtkObject
 */

/**
 * @desc `RemoteVtkScene` represents a VTK WASM scene that is synchronized with
 * another VTK scene running on a Trame server.
 */
export default class RemoteVtkScene {
    /** @type{HTMLDivElement} */
    static #invisibleDiv;
    static {
        const div = document.createElement('div');
        div.setAttribute('data-comments', 'invisible div for vtk trame connections');
        div.style.width = '0';
        div.style.height = '0';
        div.style.opacity = '0';
        div.style.overflow = 'hidden';
        div.style.position = 'absolute';
        div.style.inset = '0 auto auto 0';
        document.body.appendChild(div);
        this.#invisibleDiv = div;
    }

    /**
     * @return {HTMLDivElement}
     */
    static #getCanvasDiv = () => {
        const canvasDiv = document.createElement('div');
        canvasDiv.setAttribute('data-comments', 'vtk canvas container');
        canvasDiv.style.width = '100%';
        canvasDiv.style.height = '100%';
        canvasDiv.style.boxSizing = 'border-box';
        canvasDiv.style.margin = '0';
        canvasDiv.style.border = '0';
        canvasDiv.style.padding = '0';
        canvasDiv.style.position = 'absolute';
        canvasDiv.style.inset = 'auto';
        canvasDiv.style.overflow = 'hidden';
        this.#invisibleDiv.appendChild(canvasDiv);
        return canvasDiv;
    };

    /**
     * @param {TrameSession} trameSession
     * @param {string} wasmUrl
     * @param {boolean} perfLogging
     * @return {{
     * wasmHandler: VtkWASMHandler|any|Object|Record<string,any>,
     * vtkWasmPerfCounter: ?VtkWasmPerfCounter
     * }}
     */
    static #getWasmHandlerAsync = async (trameSession, wasmUrl, perfLogging) => {
        const wasmHandler = new VtkWASMHandler();

        /** @type {?VtkWasmPerfCounter} */
        let vtkWasmPerfCounter = null;

        if (perfLogging) {
            vtkWasmPerfCounter = new VtkWasmPerfCounter();
        }

        async function netFetchState(vtkId) {
            const res = await trameSession.call('vtklocal.get.state', [vtkId]);
            vtkWasmPerfCounter?.recordStateFetch(res);
            return res;
        }

        async function netFetchBlob(hash) {
            const t0 = perfLogging ? performance.now() : 0;
            const res = await trameSession.call('vtklocal.get.hash', [hash]);
            vtkWasmPerfCounter?.recordBlobFetch(hash, res, performance.now() - t0);
            return res;
        }

        async function netFetchStatus(vtkId) {
            const t0 = perfLogging ? performance.now() : 0;
            const res = await trameSession.call('vtklocal.get.status', [vtkId]);
            vtkWasmPerfCounter?.logStatusFetch(vtkId, performance.now() - t0);
            return res;
        }

        wasmHandler.bindNetwork(netFetchState, netFetchBlob, netFetchStatus);
        await wasmHandler.load(wasmUrl, {
            print: (msg) => {
                console.log(`Message from WebAssembly module: ${msg}`);
            },
            printErr: (msg) => {
                const prefix = `Error in WebAssembly module`;
                if (this.#wasmUpdating) {
                    console.warn(`${prefix} during VtkWASMHandler.update(): ${msg}`);
                } else if (this.#wasmGettingObject) {
                    console.warn(`${prefix} during VtkWASMHandler.getVtkObject(): ${msg}`);
                }
                console.warn(`${prefix}: ${msg}`);
            },
        });
        return { wasmHandler, vtkWasmPerfCounter };
    };

    /**
     * @param {{
     * wasmIdsStateKey:string,
     * refNameStateKey:string,
     * webSocketUrl:string,
     * wasmUrl:string,
     * }} config
     * @returns {Promise<RemoteVtkScene>}
     */
    static getInstanceAsync = async (config) => {
        if (config == null) {
            throw new Error(`config cannot be null`);
        } else if (typeof config.wasmIdsStateKey !== 'string') {
            throw new Error(`config.wasmIdsStateKey must be a string`);
        } else if (typeof config.refNameStateKey !== 'string') {
            throw new Error(`config.refNameStateKey must be a string`);
        } else if (typeof config.webSocketUrl !== 'string') {
            throw new Error(`config.webSocketUrl must be a string`);
        } else if (typeof config.wasmUrl !== 'string') {
            throw new Error(`config.wasmUrl must be a string`);
        }
        const { refNameStateKey, wasmIdsStateKey, webSocketUrl } = config;
        let wasmUrl = config.wasmUrl;
        const trameInterface = await TrameInterface.getInstanceAsync(webSocketUrl, refNameStateKey);

        // trame-vtklocal registers wasm files under a versioned path and
        // exposes it as `__trame_vtklocal_wasm_url` in Trame state.
        // We derive the absolute wasm base URL from the WebSocket origin +
        // that state value so we always fetch from the server that actually
        // has the files, regardless of which port the Dash app runs on.
        const trameWasmUrl = trameInterface.getState('__trame_vtklocal_wasm_url');
        if (trameWasmUrl && typeof trameWasmUrl === 'string') {
            // webSocketUrl is e.g. "ws://127.0.0.1:44473/ws"
            // We need "http://127.0.0.1:44473/__trame_vtklocal/wasm/9.6.1"
            const wsOrigin = webSocketUrl.replace(/^ws(s?):\/\//, 'http$1://').replace(/\/ws$/, '');
            wasmUrl = `${wsOrigin}/${trameWasmUrl}`;
        }

        const wasmIds = trameInterface.getState(wasmIdsStateKey);
        if (wasmIds == null) {
            throw new Error(`wasmIds cannot be null`);
        } else if (typeof wasmIds.rendererId !== 'number') {
            throw new Error(`wasmIds.rendererId must be a number`);
        } else if (typeof wasmIds.renderWindowId !== 'number') {
            throw new Error(`wasmIds.renderWindowId must be a number`);
        }
        const rendererId = wasmIds.rendererId;
        const renderWindowId = wasmIds.renderWindowId;
        const perfLogging = trameInterface.getState('perf_logging') === true;
        const { wasmHandler, vtkWasmPerfCounter } = await this.#getWasmHandlerAsync(
            trameInterface.session,
            wasmUrl,
            perfLogging
        );
        const canvasDiv = this.#getCanvasDiv();
        wasmHandler.bindCanvasToDOM(renderWindowId, canvasDiv);
        const canvas = canvasDiv.getElementsByTagName('canvas')[0];
        canvas.style.cssText = `position:absolute;left:0;top:0;width:100%;height:100%;`;

        ////////////////////////////////////////////////////////////////////////////////////////
        ////////////////////////////////////////////////////////////////////////////////////////
        ////////////////////////////////////////////////////////////////////////////////////////

        this.#allowConstruction = true;
        /**@type{RemoteVtkScene}*/
        let instance;
        try {
            instance = new RemoteVtkScene();
        } finally {
            this.#allowConstruction = false;
        }
        instance.#wasmHandler = wasmHandler;
        instance.#trameInterface = trameInterface;
        instance.#perfCounter = vtkWasmPerfCounter;
        instance.canvasDiv = canvasDiv;
        instance.canvas = canvas;
        instance.rendererId = rendererId;
        instance.renderWindowId = renderWindowId;
        // An initial call to updateAsync() is required for
        // cameraIds to populate, getVtkObject() to work, etc.
        await instance.updateAsync(true);
        instance.renderer = instance.getVtkObject(rendererId);
        instance.renderWindow = instance.getVtkObject(renderWindowId);

        ////////////////////////////////////////////////////////////////////////////////////////
        ////////////////////////////////////////////////////////////////////////////////////////
        ////////////////////////////////////////////////////////////////////////////////////////

        // Allow server to call method on us (update, resetCamera, evalStateExtract)
        trameInterface.addSingleCallback('checkMemory', instance.#checkMemory);
        trameInterface.addSingleCallback('evalStateExtract', instance.#evalStateExtract);
        trameInterface.addSingleCallback('startEventLoop', instance.#startEventLoop);
        trameInterface.addSingleCallback('stopEventLoop', instance.#stopEventLoop);
        trameInterface.addSingleCallback('update', instance.updateAsync);
        trameInterface.addSingleCallback('getState', (payload) => {
            for (const callback of instance.#getStateListeners.values()) {
                callback(payload);
            }
        });
        trameInterface.addSingleCallback('setState', (payload) => {
            for (const callback of instance.#setStateListeners.values()) {
                callback(payload);
            }
        });

        ////////////////////////////////////////////////////////////////////////////////////////
        ////////////////////////////////////////////////////////////////////////////////////////
        ////////////////////////////////////////////////////////////////////////////////////////

        instance.#startEventLoop();
        instance.vtkScene = await VtkScene.getInstanceAsync(null, instance);
        Object.freeze(instance);
        return instance;
    };

    /**@type{boolean}*/
    static #allowConstruction = false;
    /**@type{boolean}*/
    static #wasmUpdating = false;
    /**@type{boolean}*/
    static #wasmGettingObject = false;

    constructor() {
        if (!RemoteVtkScene.#allowConstruction) {
            const msg = `Constructor is private.`;
            throw new Error(`${msg} Use getInstanceAsync().`);
        }
    }

    /**
     * @return {void}
     */
    #checkMemory = () => {
        const cacheSize = 100000000;
        this.#wasmHandler.freeMemory(cacheSize);
    };
    /**
     * @param {Record<string,Record<string,string>>} definition
     * @return {Promise<void>}
     */
    #evalStateExtract = async (definition) => {
        this.#wasmHandler.clearStateCache();
        const promises = [];
        for (const [name, props] of Object.entries(definition)) {
            const value = {};
            for (const [propName, statePath] of Object.entries(props)) {
                value[propName] = this.#wasmHandler.getStateValue(statePath, true);
            }
            promises.push(this.#trameInterface.setStateAsync(name, value));
        }
        this.#wasmHandler.clearStateCache();
        await Promise.all(promises);
    };
    /**
     * @return {boolean}
     */
    #startEventLoop = () => {
        return this.#wasmHandler.sceneManager.startEventLoop(this.renderWindowId);
    };
    /**
     * @return {boolean}
     */
    #stopEventLoop = () => {
        return this.#wasmHandler.sceneManager.stopEventLoop(this.renderWindowId);
    };

    /**@type{any|Object|Record<string,any>}*/
    #wasmHandler;
    /**@type{TrameInterface}*/
    #trameInterface;
    /**@type{?VtkWasmPerfCounter}*/
    #perfCounter = null;
    /**@type{HTMLCanvasElement}*/
    canvas;
    /**@type{HTMLDivElement}*/
    canvasDiv;
    /**@type{number}*/
    rendererId;
    /**@type{number}*/
    renderWindowId;
    /**@type{FrontendVtkObject}*/
    renderer;
    /**@type{FrontendVtkObject}*/
    renderWindow;
    /**@type{VtkScene}*/
    vtkScene;

    /**
     * @return {boolean}
     */
    render = () => {
        return this.#wasmHandler.sceneManager.render(this.renderWindowId);
    };
    /**
     * @return {Promise<void>}
     */
    resizeAsync = async () => {
        const { width, height } = this.canvasDiv.getBoundingClientRect();
        const w = Math.floor(width * window.devicePixelRatio + 0.5);
        const h = Math.floor(height * window.devicePixelRatio + 0.5);
        await this.#wasmHandler.setSize(this.renderWindowId, w, h);
    };
    /**
     * @param {number} wasmId
     * @return {FrontendVtkObject}
     */
    getVtkObject = (wasmId) => {
        let object;
        RemoteVtkScene.#wasmGettingObject = true;
        try {
            object = this.#wasmHandler.getVtkObject(wasmId);
        } catch (e) {
            const msg = `Error getting VTK object with wasmId ${wasmId}: ${e.message}`;
            throw new Error(msg);
        } finally {
            RemoteVtkScene.#wasmGettingObject = false;
        }
        return object;
    };
    /**
     * @param {boolean} [bindCanvas=false]
     * @return {Promise<void>}
     */
    updateAsync = async (bindCanvas) => {
        if (!this.#wasmHandler.loaded) {
            return;
        }

        let t0 = 0;
        let t1 = 0;

        if (this.#perfCounter != null) {
            this.#perfCounter.reset();
            t0 = performance.now();
        }

        RemoteVtkScene.#wasmUpdating = true;
        try {
            await this.#wasmHandler.update(this.renderWindowId, bindCanvas);
        } finally {
            RemoteVtkScene.#wasmUpdating = false;
        }
        if (this.#perfCounter != null) {
            t1 = performance.now();
        }

        this.#checkMemory();
        await this.resizeAsync();

        if (this.#perfCounter != null) {
            const report = this.#perfCounter.logUpdateAsyncPerf(
                t1 - t0, // wasmMs
                performance.now() - t1 // resizeMs
            );
            this.trameTriggerAsync('perf_report_wasm', report).catch(() => {});
        }

        for (const callback of this.#serverUpdatedListeners.values()) {
            callback();
        }
    };
    /**
     * @param {string} name
     * @param {function(...any):any} f
     */
    trameAddSingleCallback = (name, f) => {
        this.#trameInterface.addSingleCallback(name, f);
    };
    /**
     * @param {string} key
     * @return {TrameStateValue}
     */
    trameGetState = (key) => {
        return this.#trameInterface.getState(key);
    };
    /**
     * @param {string} key
     * @param {any} val
     * @return {Promise<void>}
     */
    trameSetStateAsync = async (key, val) => {
        await this.#trameInterface.setStateAsync(key, val);
    };
    /**
     * @param {string} triggerName
     * @param {...any} args
     * @return {Promise<any>}
     */
    trameTriggerAsync = async (triggerName, ...args) => {
        return await this.#trameInterface.triggerAsync(triggerName, ...args);
    };

    ////////////////////////////////////////////////////////////////////////////////////////
    ////////////////////////////////////////////////////////////////////////////////////////
    ////////////////////////////////////////////////////////////////////////////////////////

    /**@type{Map<Function,()=>void>}*/
    #userObserverRemovers = new Map();
    /**@type{Map<Function,()=>void>}*/
    #serverUpdatedListeners = new Map();
    /**@type{Map<Function,(payload:any)=>void>}*/
    #getStateListeners = new Map();
    /**@type{Map<Function,(payload:any)=>void>}*/
    #setStateListeners = new Map();
    /**
     * @return {void}
     */
    clearObserversAndEventListeners = () => {
        for (const remover of this.#userObserverRemovers.values()) {
            remover();
        }
        this.#serverUpdatedListeners.clear();
        this.#getStateListeners.clear();
        this.#setStateListeners.clear();
    };
    /**
     * @param {()=>void} handler
     * @return {()=>void}
     */
    addServerUpdatedListener = (handler) => {
        const remover = () => this.#serverUpdatedListeners.delete(remover);
        this.#serverUpdatedListeners.set(remover, handler);
        return remover;
    };
    /**
     * @param {(payload:any)=>void} handler
     * @return {()=>void}
     */
    addGetStateListener = (handler) => {
        const remover = () => this.#getStateListeners.delete(remover);
        this.#getStateListeners.set(remover, handler);
        return remover;
    };
    /**
     * @param {(payload:any)=>void} handler
     * @return {()=>void}
     */
    addSetStateListener = (handler) => {
        const remover = () => this.#setStateListeners.delete(remover);
        this.#setStateListeners.set(remover, handler);
        return remover;
    };
}
