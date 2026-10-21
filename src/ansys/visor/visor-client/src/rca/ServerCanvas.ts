/** The RCA area name; must equal RCA_AREA_NAME in app/trame/server_app.py. */
export const RCA_AREA_NAME = 'view';

/** The trame-rca topic every area's frames are published on. */
const STREAM_TOPIC = 'trame.rca.topic.stream';

/** The origin this canvas reports in its size messages. */
const SIZE_ORIGIN = 'ServerCanvas';

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

/** What ServerRenderer needs from the canvas. */
export interface IServerCanvas {
    readonly element: HTMLDivElement;
    readonly frameSize: FrameSize | null;
    addFrameListener(callback: (fps: number) => void): () => void;
}

/** One message on the stream topic: an encoded frame for one area. */
type StreamMessage = Readonly<{ name?: unknown; content?: unknown }>;

/** Shows the frames the server streams for one RCA area, and reports the area's size to the server. */
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

    /** Unsubscribe, stop observing the size, remove DOM listeners and revoke the current frame URL. */
    dispose(): void {
        this.#subscription.unsubscribe();
        this.#resizeObserver.disconnect();
        this.#image.removeEventListener('load', this.#onImageLoad);
        this.#image.removeEventListener('error', this.#onImageError);
        this.#frameListeners.clear();
        this.#revokeFrameUrl();
    }

    readonly #session: RcaSession;
    readonly #areaName: string;
    readonly #image: HTMLImageElement;
    readonly #subscription: { unsubscribe(): unknown };
    readonly #resizeObserver: ResizeObserver;
    readonly #frameListeners = new Map<() => void, (fps: number) => void>();
    readonly #frameTimes: number[] = [];
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

    /** Send each non-zero element size to the area; the server resizes its window and renders a frame. */
    #onResize = (entries: ResizeObserverEntry[]): void => {
        for (const entry of entries) {
            const w = Math.round(entry.contentRect.width);
            const h = Math.round(entry.contentRect.height);
            if (w === 0 || h === 0) {
                continue;
            }
            const p = window.devicePixelRatio ?? 1;
            this.#session
                .call('trame.rca.size', [this.#areaName, SIZE_ORIGIN, { w, h, p }])
                .catch((err) => console.error('[VISOR] trame.rca.size send failed', err));
        }
    };
}
