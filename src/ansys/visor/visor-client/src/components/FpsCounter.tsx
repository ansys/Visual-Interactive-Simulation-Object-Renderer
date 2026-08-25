/**
 * Displays a toggleable frames-per-second counter inside a specified container.
 *
 * The counter can be shown or hidden by pressing Ctrl+F10.
 */
export class FpsCounter {
    /**
     * Creates an FPS counter and attaches it to the provided container.
     *
     * @param container - The HTML element that will contain the FPS display.
     * @param inset - A valid CSS `inset` value used to position the display.
     */
    constructor(container: HTMLElement, inset: string) {
        const fpsDisplay = document.createElement('div');
        fpsDisplay.style.position = 'absolute';
        fpsDisplay.style.inset = inset;
        fpsDisplay.style.backgroundColor = 'rgba(0,0,0,0.75)';
        fpsDisplay.style.color = '#ffffff';
        fpsDisplay.style.padding = '10px';
        fpsDisplay.style.zIndex = '999';
        fpsDisplay.style.minWidth = '16ch';
        fpsDisplay.style.display = 'none';

        fpsDisplay.innerHTML = `
            <table class="">
                <tr>
                    <td class="text-left">FPS:</td>
                    <td class="text-right"></td>
                </tr>
            </table>
        `;

        this.#valueContainer = fpsDisplay.getElementsByTagName('td')[1];
        container.appendChild(fpsDisplay);

        let timeoutId: number | null = null;

        this.#fpsDisplay = fpsDisplay;

        this.#handler = (e: KeyboardEvent) => {
            if (e.ctrlKey && e.key === 'F10') {
                const allow = timeoutId == null;

                if (allow) {
                    timeoutId = setTimeout(() => {
                        clearTimeout(timeoutId!);
                        timeoutId = null;
                    }, 250);
                } else {
                    return;
                }

                if (fpsDisplay.style.display === 'none') {
                    fpsDisplay.style.removeProperty('display');
                } else {
                    fpsDisplay.style.display = 'none';
                }
            }
        };

        window.addEventListener('keydown', this.#handler);
    }

    /**
     * The element in which the current FPS value is displayed.
     */
    readonly #valueContainer: HTMLElement;

    /**
     * The root element of the FPS display.
     */
    readonly #fpsDisplay: HTMLElement;

    /**
     * Handles keyboard events used to toggle the FPS display.
     *
     * @param e - The keyboard event dispatched by the window.
     */
    readonly #handler: (e: KeyboardEvent) => void;

    /**
     * Updates the value shown by the FPS counter.
     *
     * @param val - The FPS value to display.
     */
    setValue = (val: string | number): void => {
        this.#valueContainer.innerHTML = val.toString();
    };

    /**
     * Removes the FPS display and unregisters its keyboard event listener.
     */
    dispose = (): void => {
        this.#fpsDisplay.remove();
        window.removeEventListener('keydown', this.#handler);
    };
}
