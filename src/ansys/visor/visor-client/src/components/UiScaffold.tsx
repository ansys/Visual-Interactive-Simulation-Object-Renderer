import { FC, RefObject, useEffect, useRef, useState } from 'react';
import { Panel_BottomMiddle, Panel_BottomMiddle_Util } from './ui-panels/Panel_BottomMiddle.tsx';
import { Panel_BottomRight } from './ui-panels/Panel_BottomRight.tsx';
import { Panel_BottomRight_Util } from './ui-panels/Panel_BottomRight_Util.tsx';
import { Panel_TopRight } from './ui-panels/Panel_TopRight.tsx';
import { Panel_TopLeft } from './ui-panels/Panel_TopLeft.tsx';
import { ContextMenu, ContextMenuOptions, ContextMenuUtil } from './ui-panels/ContextMenu.tsx';
import { VisorFrontend, VisorCameraState } from '../VisorFrontend.tsx';
import { Panel_TopLeft_Util } from './ui-panels/Panel_TopLeft_Util.tsx';
import { Panel_TopRight_Util } from './ui-panels/Panel_TopRight_Util.tsx';
import { FpsCounter } from './FpsCounter.tsx';
import { formatNumber, randomId, randomInt, roundFloat, setScale } from '../utils/JsHelpers';

export type UiScaffoldUtil = {
    pixelDensity: number;
    setUnit: (unit: string) => void;
};

export const UiScaffold: FC<{
    visorState: VisorFrontend;
    onLoad: (util: UiScaffoldUtil) => void;
}> = ({ visorState, onLoad }) => {
    const [contextMenuOptions, setContextMenuOptions] = useState<ContextMenuOptions | null>(null!);
    let contextMenuUtil: ContextMenuUtil = null!;
    let panelTopLeftUtil: Panel_TopLeft_Util = null!;
    let panelTopRightUtil: Panel_TopRight_Util = null!;
    let panelBottomMiddleUtil: Panel_BottomMiddle_Util = null!;
    let panelBottomRightUtil: Panel_BottomRight_Util = null!;
    const showBottomLeft = false;
    const showTopMiddle = false;
    const rulerHeight = 10;
    const rulerFontSize = 12;
    const scaffoldElemId = randomId();
    const vtkCanvasContainerId = randomId();
    const rulerElemId = randomId();
    const rulerTextLeftElemId = randomId();
    const rulerTextRightElemId = randomId();
    const unitContainerElemId = randomId();
    const topLeftElemId = randomId();
    const topMiddleElemId = randomId();
    const topRightElemId = randomId();
    const bottomLeftElemId = randomId();
    const bottomRightElemId = randomId();
    const bottomMiddleElemId = randomId();

    useEffect(() => {
        const scaffoldElem = document.getElementById(scaffoldElemId)!;
        const rulerElem = document.getElementById(rulerElemId)!;
        const rulerTextLeftElem = document.getElementById(rulerTextLeftElemId)!;
        const rulerTextRightElem = document.getElementById(rulerTextRightElemId)!;
        const unitContainerElem = document.getElementById(unitContainerElemId)!;
        const topLeftElem = document.getElementById(topLeftElemId)!;
        const topMiddleElem = document.getElementById(topMiddleElemId)!;
        const topRightElem = document.getElementById(topRightElemId)!;
        const bottomLeftElem = document.getElementById(bottomLeftElemId)!;
        const bottomRightElem = document.getElementById(bottomRightElemId)!;
        const bottomMiddleElem = document.getElementById(bottomMiddleElemId)!;
        const fpsCounterManager = new FpsCounter(scaffoldElem, 'auto 0 0 auto');
        visorState.addFrameRenderedListener((fps) => {
            fpsCounterManager.setValue(formatNumber(fps, 4, true));
        });
        let pixelDensity: number = 1000;
        let lastPixelDensity: number | null = null;
        const setUiScale = () => {
            if (pixelDensity <= 0 && lastPixelDensity != null && lastPixelDensity <= 0) {
                return;
            }
            lastPixelDensity = pixelDensity;
            const scale = pixelDensity > 0 ? scaffoldElem.offsetWidth / pixelDensity : 1;
            // Apply after-scaling to some UI panels.
            // see https://github.com/ansys-internal/theia/pull/1004
            const afterScale = 0.85;
            setScale(topLeftElem, scale * afterScale);
            setScale(topMiddleElem, scale);
            setScale(topRightElem, scale * afterScale);
            setScale(bottomLeftElem, scale);
            setScale(bottomMiddleElem, scale);
            setScale(bottomRightElem, scale * afterScale);
        };
        setUiScale();

        const vtkCanvasContainer = document.getElementById(vtkCanvasContainerId)!;
        vtkCanvasContainer.appendChild(visorState.domElement);
        void visorState.resizeAsync();

        rulerElem.style.display = 'none';
        visorState.addCameraChangedListener((cameraState) => {
            if (visorState.unit != null && visorState.unit !== '') {
                updateRuler(cameraState);
            }
        });

        function updateRuler(cameraState: VisorCameraState) {
            if (cameraState.orthographic) {
                rulerElem.style.removeProperty('display');
                const val =
                    cameraState.unitsPerPixel *
                    rulerElem.getBoundingClientRect().width *
                    window.devicePixelRatio;
                rulerTextRightElem.innerHTML = roundFloat(val, 2).toString();
                return;
            }
            rulerElem.style.display = 'none';
        }

        const util: UiScaffoldUtil = {
            set pixelDensity(value) {
                pixelDensity = value;
                setUiScale();
            },
            get pixelDensity() {
                return pixelDensity;
            },
            setUnit(unit) {
                if (unit == null || unit === '') {
                    rulerElem.style.display = 'none';
                } else {
                    unit = unit.replace(/</g, '&lt;');
                    unit = unit.replace(/>/g, '&gt;');
                    unitContainerElem.innerHTML = unit;
                    visorState.getCameraStateAsync().then((cameraState) => {
                        updateRuler(cameraState);
                    });
                }
            },
        };
        visorState.setUiScaffoldUtil(util);
        onLoad(util);
        const resizeObserver = new ResizeObserver(() => {
            setUiScale();
            void visorState.resizeAsync();
        });
        resizeObserver.observe(scaffoldElem);
        return () => {
            resizeObserver.disconnect();
            fpsCounterManager.dispose();
        };
    }, []);
    return (
        <div
            id={scaffoldElemId}
            style={{
                position: 'absolute',
                zIndex: '2',
                inset: '0',
                overflow: 'hidden',
            }}
        >
            <ContextMenu
                visorState={visorState}
                onLoad={(u) => (contextMenuUtil = u)}
                options={contextMenuOptions}
            />
            <div
                id={vtkCanvasContainerId}
                className={'visor-viewer-background'}
                style={{
                    position: 'absolute',
                    inset: '0',
                    overflow: 'hidden',
                    zIndex: '1',
                }}
            ></div>
            <div
                id={topLeftElemId}
                style={{
                    position: 'absolute',
                    top: '0',
                    left: '0',
                    width: '0',
                    height: '0',
                    overflow: 'visible',
                    zIndex: '10',
                }}
            >
                <div
                    className={'theme-panel-1'}
                    style={{
                        position: 'absolute',
                        top: '10px',
                        left: '10px',
                        // minWidth: '250px',
                        // height: '300px',
                        padding: '10px',
                    }}
                >
                    <Panel_TopLeft
                        visorState={visorState}
                        onLoad={(u) => (panelTopLeftUtil = u)}
                    ></Panel_TopLeft>
                </div>
            </div>
            <div
                id={topMiddleElemId}
                style={{
                    position: 'absolute',
                    top: '0',
                    left: '50%',
                    width: '0',
                    height: '0',
                    overflow: 'visible',
                    zIndex: '5',
                }}
            >
                {showTopMiddle ? (
                    <div
                        className={'theme-panel-1'}
                        style={{
                            position: 'absolute',
                            top: '10px',
                            transform: 'translateX(-50%)',
                            minWidth: '200px',
                            height: '100px',
                            padding: '10px',
                        }}
                    >
                        Top Middle
                    </div>
                ) : null}
            </div>
            <div
                id={topRightElemId}
                style={{
                    position: 'absolute',
                    top: '0',
                    right: '0',
                    width: '0',
                    height: '0',
                    overflow: 'visible',
                    zIndex: '5',
                }}
            >
                <div
                    className={'theme-panel-1'}
                    style={{
                        position: 'absolute',
                        top: '10px',
                        right: '10px',
                        // minWidth: '200px',
                        // height: '100px',
                        padding: '0',
                        overflow: 'visible',
                    }}
                >
                    <Panel_TopRight
                        visorState={visorState}
                        onLoad={(u) => (panelTopRightUtil = u)}
                    ></Panel_TopRight>
                </div>
            </div>
            <div
                id={bottomRightElemId}
                style={{
                    position: 'absolute',
                    bottom: '0',
                    right: '0',
                    width: '0',
                    height: '0',
                    overflow: 'visible',
                    zIndex: '5',
                }}
            >
                <div
                    style={{
                        position: 'absolute',
                        bottom: '10px',
                        right: '10px',
                        overflow: 'visible',
                    }}
                >
                    <Panel_BottomRight
                        visorState={visorState}
                        onLoad={(u) => (panelBottomRightUtil = u)}
                    ></Panel_BottomRight>
                </div>
            </div>
            <div
                id={bottomMiddleElemId}
                style={{
                    position: 'absolute',
                    bottom: '0',
                    left: '50%',
                    width: '0',
                    height: '0',
                    overflow: 'visible',
                    zIndex: '5',
                }}
            >
                <div
                    className={'theme-panel-1'}
                    style={{
                        position: 'absolute',
                        bottom: '10px',
                        transform: 'translateX(-50%)',
                        padding: '10px',
                    }}
                >
                    <Panel_BottomMiddle
                        visorState={visorState}
                        onLoad={(u) => (panelBottomMiddleUtil = u)}
                    ></Panel_BottomMiddle>
                </div>
                <div
                    id={rulerElemId}
                    style={{
                        position: 'relative',
                        inset: '-140px auto auto -150px',
                        width: '300px',
                        height: `${rulerHeight}px`,
                        lineHeight: '1',
                        color: '#000000',
                        backgroundImage: `linear-gradient(90deg,
                    rgba(0, 0, 0, 1) 0%,
                    rgba(0, 0, 0, 1) 25%,
                    transparent 25%,
                    transparent 50%,
                    rgba(0, 0, 0, 1) 50%,
                    rgba(0, 0, 0, 1) 75%,
                    transparent 75%,
                    transparent 100%
                    )`,
                        borderWidth: '1px',
                        borderColor: '#000000',
                        borderRadius: '0',
                    }}
                >
                    <div
                        style={{
                            position: 'absolute',
                            inset: `${rulerHeight + 5}px 0 auto 0`,
                            textAlign: 'center',
                            fontSize: `${rulerFontSize}px`,
                            color: '#7a7a7a',
                            lineHeight: '1',
                        }}
                    >
                        Scale
                    </div>
                    <div
                        id={rulerTextLeftElemId}
                        style={{
                            position: 'absolute',
                            inset: `-${rulerFontSize + 5}px auto auto 0`,
                            fontSize: `${rulerFontSize}px`,
                            lineHeight: '1',
                        }}
                    ></div>
                    <div
                        style={{
                            position: 'absolute',
                            inset: `-${rulerFontSize + 5}px 0 auto auto`,
                            fontSize: `${rulerFontSize}px`,
                            lineHeight: '1',
                        }}
                    >
                        <div
                            id={rulerTextRightElemId}
                            style={{
                                position: 'absolute',
                                inset: `0 0 auto auto`,
                                fontSize: `${rulerFontSize}px`,
                                lineHeight: '1',
                            }}
                        ></div>
                        <div
                            style={{
                                position: 'absolute',
                                inset: '0 0 auto auto',
                                width: '0',
                                height: '0',
                            }}
                        >
                            <div
                                id={unitContainerElemId}
                                style={{
                                    position: 'absolute',
                                    paddingLeft: '8px',
                                    inset: '0 auto auto 0',
                                    fontSize: `${rulerFontSize}px`,
                                    color: '#7a7a7a',
                                    lineHeight: '1',
                                }}
                            >
                                {visorState.unit}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div
                id={bottomLeftElemId}
                style={{
                    position: 'absolute',
                    left: '0',
                    bottom: '0',
                    width: '0',
                    height: '0',
                    overflow: 'visible',
                    zIndex: '5',
                }}
            >
                {showBottomLeft ? (
                    <div
                        className={'theme-panel-1'}
                        style={{
                            position: 'absolute',
                            bottom: '10px',
                            left: '10px',
                            minWidth: '200px',
                            height: '100px',
                            padding: '10px',
                        }}
                    >
                        Bottom Left
                    </div>
                ) : null}
            </div>
        </div>
    );
};
