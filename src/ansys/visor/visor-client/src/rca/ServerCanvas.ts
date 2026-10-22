import { ClickTracker } from '../input/ClickTracker';
import { MouseButtonState } from '../input/MouseButtonState';

/** The RCA area name; must equal RCA_AREA_NAME in app/trame/server_app.py. */
export const RCA_AREA_NAME = 'view';

/** The trame-rca topic every area's frames are published on. */
const STREAM_TOPIC = 'trame.rca.topic.stream';

/** The origin this canvas reports in its size and interaction messages. */
const MESSAGE_ORIGIN = 'ServerCanvas';

/** The vtk-js event name prefix for each VTK button. */
const BUTTON_EVENT_PREFIXES = ['Left', 'Middle', 'Right'] as const;

/** The part of a wslink session the canvas uses. */
export type RcaSession = {
    subscribe(
        topic: string,
        callback: (args: unknown[]) => Promise<unknown>
    ): { unsubscribe(): unknown };
    call(method: string, args: unknown[]): Promise<unknown>;
};

/** Pixel size of the last frame drawn. */
export type FrameSize = Readonly<{ width: number; height: number }>;

/** A click on the canvas in VTK-normalised coordinates (origin bottom-left). */
export type CanvasClick = Readonly<{
    normX: number;
    normY: number;
    ctrlKey: boolean;
    shiftKey: boolean;
}>;

/** What ServerRenderer needs from the canvas. */
export interface IServerCanvas {
    readonly element: HTMLDivElement;
    readonly frameSize: FrameSize | null;
    addFrameListener(callback: (fps: number) => void): () => void;
    addClickListener(callback: (click: CanvasClick) => void): () => void;
    addResizeListener(callback: () => void): () => void;
}

/** One message on the stream topic: an encoded frame for one area. */
type StreamMessage = Readonly<{ name?: unknown; content?: unknown }>;

/** One vtk-js interaction event: element pixels, origin bottom-left. */
type InteractionEvent = {
    type: string;
    x: number;
    y: number;
    w: number;
    h: number;
    ctrlKey: boolean;
    altKey: boolean;
    shiftKey: boolean;
    spinY?: number;
};

/** Shows the frames the server streams for one RCA area, reports the area's size, and forwards mouse and wheel input to it. */
export class ServerCanvas implements IServerCanvas {
    /** Subscribe to the area's frame stream on session, draw each frame into element, and report element's size. */
    constructor(session: RcaSession, areaName: string) {
        this.#session = session;
        this.#areaName = areaName;

        const element = document.createElement('div');
        element.style.cssText = `position:relative;width:100%;height:100%;overflow:hidden;`;
        const image = document.createElement('img');
        image.style.cssText = `display:block;width:100%;height:100%;`;
        image.draggable = false;
        image.addEventListener('load', this.#onImageLoad);
        image.addEventListener('error', this.#onImageError);
        element.appendChild(image);
        this.element = element;
        this.#image = image;

        element.addEventListener('mousedown', this.#onMouseDown);
        element.addEventListener('mouseup', this.#onMouseUp);
        element.addEventListener('mousemove', this.#onMouseMove);
        element.addEventListener('mouseout', this.#onMouseOut);
        element.addEventListener('blur', this.#onBlur);
        element.addEventListener('wheel', this.#onWheel, { passive: false });
        element.addEventListener('contextmenu', this.#onContextMenu);

        this.#subscription = session.subscribe(STREAM_TOPIC, async (args) => this.#onStream(args));
        // The first non-zero observation is what starts the stream: the server
        // renders a frame for each size it is sent.
        this.#resizeObserver = new ResizeObserver(this.#onResize);
        this.#resizeObserver.observe(element);
    }

    /** The element that shows the frames. */
    readonly element: HTMLDivElement;

    /** Natural size of the last decoded frame, or null before the first. */
    get frameSize(): FrameSize | null {
        return this.#frameSize;
    }

    /** Call callback once per drawn frame with frames per second over the last second; returns its remover. */
    addFrameListener(callback: (fps: number) => void): () => void {
        const remover = () => {
            this.#frameListeners.delete(remover);
        };
        this.#frameListeners.set(remover, callback);
        return remover;
    }

    /** Call callback once per left click (press and release at one point); returns its remover. */
    addClickListener(callback: (click: CanvasClick) => void): () => void {
        const remover = () => {
            this.#clickListeners.delete(remover);
        };
        this.#clickListeners.set(remover, callback);
        return remover;
    }

    /** Call callback after each non-zero element size is sent to the area; returns its remover. */
    addResizeListener(callback: () => void): () => void {
        const remover = () => {
            this.#resizeListeners.delete(remover);
        };
        this.#resizeListeners.set(remover, callback);
        return remover;
    }

    /** Unsubscribe, stop observing the size, remove DOM listeners and revoke the current frame URL. */
    dispose(): void {
        this.#subscription.unsubscribe();
        this.#resizeObserver.disconnect();
        this.#image.removeEventListener('load', this.#onImageLoad);
        this.#image.removeEventListener('error', this.#onImageError);
        const element = this.element;
        element.removeEventListener('mousedown', this.#onMouseDown);
        element.removeEventListener('mouseup', this.#onMouseUp);
        element.removeEventListener('mousemove', this.#onMouseMove);
        element.removeEventListener('mouseout', this.#onMouseOut);
        element.removeEventListener('blur', this.#onBlur);
        element.removeEventListener('wheel', this.#onWheel);
        element.removeEventListener('contextmenu', this.#onContextMenu);
        this.#frameListeners.clear();
        this.#clickListeners.clear();
        this.#resizeListeners.clear();
        this.#revokeFrameUrl();
    }

    readonly #session: RcaSession;
    readonly #areaName: string;
    readonly #image: HTMLImageElement;
    readonly #subscription: { unsubscribe(): unknown };
    readonly #resizeObserver: ResizeObserver;
    readonly #frameListeners = new Map<() => void, (fps: number) => void>();
    readonly #frameTimes: number[] = [];
    readonly #clickListeners = new Map<() => void, (click: CanvasClick) => void>();
    readonly #resizeListeners = new Map<() => void, () => void>();
    readonly #buttons = new MouseButtonState();
    readonly #clickTracker = new ClickTracker();
    #frameSize: FrameSize | null = null;
    #frameUrl: string | null = null;

    /** Show each frame addressed to this canvas's area. */
    #onStream = (args: unknown[]): void => {
        for (const message of args as StreamMessage[]) {
            if (message == null || message.name !== this.#areaName) {
                continue;
            }
            const content = message.content;
            if (!(content instanceof Uint8Array)) {
                console.error('[VISOR] frame content is not binary');
                continue;
            }
            this.#showFrame(content as Uint8Array<ArrayBuffer>);
        }
    };

    /** Show one encoded frame from the bytes inside the view only. */
    #showFrame(content: Uint8Array<ArrayBuffer>): void {
        // A decoded message's binary field is a view into the whole message
        // buffer, so `content.buffer` would carry the framing bytes as well
        // and the image would fail to decode without an error.
        const blob = new Blob([content], { type: 'image/jpeg' });
        this.#revokeFrameUrl();
        this.#frameUrl = URL.createObjectURL(blob);
        this.#image.src = this.#frameUrl;
    }

    #revokeFrameUrl(): void {
        if (this.#frameUrl != null) {
            URL.revokeObjectURL(this.#frameUrl);
            this.#frameUrl = null;
        }
    }

    /** Record the drawn frame's size and report the frame rate over the last second. */
    #onImageLoad = (): void => {
        const image = this.#image;
        this.#frameSize = { width: image.naturalWidth, height: image.naturalHeight };
        const now = performance.now();
        const frameTimes = this.#frameTimes;
        frameTimes.push(now);
        while (frameTimes.length > 0 && frameTimes[0] < now - 1000) {
            frameTimes.shift();
        }
        const fps = frameTimes.length;
        for (const callback of this.#frameListeners.values()) {
            callback(fps);
        }
    };

    #onImageError = (): void => {
        console.error('[VISOR] frame decode failed');
    };

    /** Send each non-zero element size to the area, then tell the resize listeners; the server resizes its window and renders a frame. */
    #onResize = (entries: ResizeObserverEntry[]): void => {
        for (const entry of entries) {
            const w = Math.round(entry.contentRect.width);
            const h = Math.round(entry.contentRect.height);
            if (w === 0 || h === 0) {
                continue;
            }
            const p = window.devicePixelRatio ?? 1;
            this.#session
                .call('trame.rca.size', [this.#areaName, MESSAGE_ORIGIN, { w, h, p }])
                .catch((err) => console.error('[VISOR] trame.rca.size send failed', err));
            for (const callback of this.#resizeListeners.values()) {
                callback();
            }
        }
    };

    /** Forward the new button state; a left press may start a click. */
    #onMouseDown = (e: MouseEvent): void => {
        this.#buttons.setButton(e.button, true);
        this.#sendButtons(e);
        if (e.button === 0) {
            this.#clickTracker.press(e.clientX, e.clientY);
        }
    };

    /** Forward the new button state; a release where the press was completes a click. */
    #onMouseUp = (e: MouseEvent): void => {
        this.#buttons.setButton(e.button, false);
        this.#sendButtons(e);
        if (this.#clickTracker.release(e.clientX, e.clientY)) {
            this.#fireClick(e);
        }
    };

    /** Forward pointer motion while a button drives a gesture. */
    #onMouseMove = (e: MouseEvent): void => {
        if (this.#buttons.effectiveButton() == null) {
            return;
        }
        this.#sendInteraction(this.#interactionEvent('MouseMove', e));
    };

    /** Release the button the server holds and forget every held button, so no drag outlives the pointer. */
    #onMouseOut = (e: MouseEvent): void => {
        this.#clickTracker.reset();
        const effective = this.#buttons.effectiveButton();
        if (effective != null) {
            this.#sendInteraction(
                this.#interactionEvent(`${BUTTON_EVENT_PREFIXES[effective]}ButtonRelease`, e)
            );
        }
        for (const button of [0, 1, 2]) {
            this.#buttons.setButton(button, false);
        }
    };

    #onBlur = (): void => {
        this.#clickTracker.reset();
    };

    /** Send one wheel step per DOM wheel event and keep the page from scrolling under the view. */
    #onWheel = (e: WheelEvent): void => {
        e.preventDefault();
        this.#sendInteraction({
            ...this.#interactionEvent('MouseWheel', e),
            spinY: Math.sign(e.deltaY),
        });
    };

    #onContextMenu = (e: MouseEvent): void => {
        e.preventDefault();
    };

    /** Release all three VTK buttons, then press the one the held buttons drive, if any. */
    #sendButtons(e: MouseEvent): void {
        for (const prefix of BUTTON_EVENT_PREFIXES) {
            this.#sendInteraction(this.#interactionEvent(`${prefix}ButtonRelease`, e));
        }
        const effective = this.#buttons.effectiveButton();
        if (effective != null) {
            this.#sendInteraction(
                this.#interactionEvent(`${BUTTON_EVENT_PREFIXES[effective]}ButtonPress`, e)
            );
        }
    }

    /** An event of type at e's position in element pixels, y measured up from the element's bottom. */
    #interactionEvent(type: string, e: MouseEvent): InteractionEvent {
        const rect = this.element.getBoundingClientRect();
        return {
            type,
            x: Math.round(e.clientX - rect.left),
            y: Math.round(rect.height - (e.clientY - rect.top)),
            w: Math.round(rect.width),
            h: Math.round(rect.height),
            ctrlKey: e.ctrlKey,
            altKey: e.altKey,
            shiftKey: e.shiftKey,
        };
    }

    #sendInteraction(event: InteractionEvent): void {
        this.#session
            .call('trame.rca.event', [this.#areaName, MESSAGE_ORIGIN, event])
            .catch((err) => console.error('[VISOR] trame.rca.event send failed', err));
    }

    /** Tell every click listener where the click landed, normalised with the origin bottom-left. */
    #fireClick(e: MouseEvent): void {
        const rect = this.element.getBoundingClientRect();
        const click: CanvasClick = {
            normX: (e.clientX - rect.left) / rect.width,
            normY: 1.0 - (e.clientY - rect.top) / rect.height,
            ctrlKey: e.ctrlKey,
            shiftKey: e.shiftKey,
        };
        for (const callback of this.#clickListeners.values()) {
            callback(click);
        }
    }
}
