import { FC, useEffect } from 'react';
import { VisorFrontend } from '../../VisorFrontend.tsx';
import { Panel_BottomRight_Util } from './Panel_BottomRight_Util.tsx';
import { formatNumber, randomId } from '../../utils/JsHelpers';

const FMT_PLACES = 6;
const FMT_PAD = false;

function fmtCoord(v: number): string {
    return formatNumber(v, FMT_PLACES, FMT_PAD);
}

export const Panel_BottomRight: FC<{
    visorState: VisorFrontend;
    onLoad: (util: Panel_BottomRight_Util) => void;
}> = ({ visorState, onLoad }) => {
    const containerId = randomId();
    const contentId = randomId();
    const copyButtonId = randomId();

    useEffect(() => {
        const container = document.getElementById(containerId) as HTMLDivElement;
        const content = document.getElementById(contentId) as HTMLDivElement;
        const copyButton = document.getElementById(copyButtonId) as HTMLButtonElement;

        // Initially hidden
        container.style.display = 'none';

        let currentResult: any = null;

        function buildContent(result: any): { html: string; text: string } {
            if (!result || !result.found) {
                return { html: '', text: '' };
            }
            if (result.mode === 'vertex') {
                const [x, y, z] = result.position as number[];
                const text = `X: ${fmtCoord(x)}  Y: ${fmtCoord(y)}  Z: ${fmtCoord(z)}`;
                const html = `<table style="border-spacing:4px 2px">
                    <tr><td style="opacity:0.6">X</td><td>${fmtCoord(x)}</td></tr>
                    <tr><td style="opacity:0.6">Y</td><td>${fmtCoord(y)}</td></tr>
                    <tr><td style="opacity:0.6">Z</td><td>${fmtCoord(z)}</td></tr>
                </table>`;
                return { html, text };
            } else if (result.mode === 'edge') {
                const [ax, ay, az] = result.pointA as number[];
                const [bx, by, bz] = result.pointB as number[];
                const len: number = result.length;
                const text =
                    `Point A: (${fmtCoord(ax)}, ${fmtCoord(ay)}, ${fmtCoord(az)})  ` +
                    `Point B: (${fmtCoord(bx)}, ${fmtCoord(by)}, ${fmtCoord(bz)})  ` +
                    `Length: ${fmtCoord(len)}`;
                const html = `<table style="border-spacing:4px 2px">
                    <tr><td style="opacity:0.6" colspan="4">Point A</td></tr>
                    <tr>
                        <td style="opacity:0.6">X</td><td>${fmtCoord(ax)}</td>
                        <td style="opacity:0.6">Y</td><td>${fmtCoord(ay)}</td>
                    </tr>
                    <tr>
                        <td style="opacity:0.6">Z</td><td>${fmtCoord(az)}</td>
                    </tr>
                    <tr><td style="opacity:0.6" colspan="4">Point B</td></tr>
                    <tr>
                        <td style="opacity:0.6">X</td><td>${fmtCoord(bx)}</td>
                        <td style="opacity:0.6">Y</td><td>${fmtCoord(by)}</td>
                    </tr>
                    <tr>
                        <td style="opacity:0.6">Z</td><td>${fmtCoord(bz)}</td>
                    </tr>
                    <tr>
                        <td style="opacity:0.6">Length</td>
                        <td colspan="3">${fmtCoord(len)}</td>
                    </tr>
                </table>`;
                return { html, text };
            } else if (result.mode === 'face') {
                const area: number = result.area;
                const text = `Area: ${fmtCoord(area)}`;
                const html = `<table style="border-spacing:4px 2px">
                    <tr><td style="opacity:0.6">Area</td><td>${fmtCoord(area)}</td></tr>
                </table>`;
                return { html, text };
            }
            return { html: '', text: '' };
        }

        function showResult(result: any) {
            currentResult = result;
            if (!result || !result.found) {
                container.style.display = 'none';
                return;
            }
            const { html, text } = buildContent(result);
            if (!html) {
                container.style.display = 'none';
                return;
            }
            content.innerHTML = html;
            copyButton.onclick = () => {
                navigator.clipboard.writeText(text).catch(() => {
                    // fallback: do nothing if clipboard API not available
                });
            };
            container.style.display = 'block';
        }

        function clearResult() {
            currentResult = null;
            container.style.display = 'none';
            content.innerHTML = '';
        }

        // Listen for geometry pick results
        const removeGeometryListener = visorState.addGeometryPickedListener(showResult);

        // Hide panel when switching back to 'part' mode; reset on any mode change
        const removeModeListener = visorState.addSelectionModeChangedListener((mode) => {
            clearResult();
            if (mode === 'part') {
                container.style.display = 'none';
            }
        });

        const util = new Panel_BottomRight_Util(showResult, clearResult);
        onLoad(util);

        return () => {
            removeGeometryListener();
            removeModeListener();
        };
    }, []);

    return (
        <div
            id={containerId}
            className={'theme-panel-1'}
            style={{
                padding: '10px',
                minWidth: '160px',
                fontSize: '12px',
            }}
        >
            <div id={contentId}></div>
            <div style={{ marginTop: '8px', textAlign: 'right' }}>
                <button
                    id={copyButtonId}
                    className={'theme-hover-background-3'}
                    style={{
                        padding: '3px 8px',
                        fontSize: '11px',
                        cursor: 'pointer',
                        borderRadius: '3px',
                        border: 'none',
                        background: 'transparent',
                        color: 'inherit',
                    }}
                >
                    Copy to clipboard
                </button>
            </div>
        </div>
    );
};
