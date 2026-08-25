import React, { useEffect, useRef } from 'react';
import PropTypes from 'prop-types';

/**
 * @typedef VisorRemoteReactInterface
 * @property {()=>void} attachOnSelectListener
 */

const Visordash = (props) => {
  const { id, host, port, aspectRatio, pixelDensity, darkMode, basePath, fireSnapshot, setProps } =
    props;

  // Normalise basePath: strip trailing slash, default to empty string.
  const bp = (basePath || '').replace(/\/$/, '');

  // Store setProps in a ref to avoid stale closure
  const setPropsRef = useRef(setProps);
  useEffect(() => {
    setPropsRef.current = setProps;
  }, [setProps]);

  useEffect(() => {
    // The "window.__visorArgs" object is
    // passed to the main Visor React app.
    const visorArgs = (window.__visorArgs ??= {});
    visorArgs.host = host;
    visorArgs.port = port;
    visorArgs.aspectRatio = aspectRatio;
    visorArgs.pixelDensity = pixelDensity;
    visorArgs.darkMode = darkMode;
    visorArgs.basePath = bp;
    loadAssetsAsync().then();

    async function loadAssetsAsync() {
      console.log(`loading assets...`);
      const styleElem = document.createElement('link');
      const stylePromise = new Promise((resolve, reject) => {
        styleElem.onload = () => {
          resolve();
        };
        styleElem.onerror = () => reject(null);
        styleElem.rel = 'stylesheet';
        styleElem.href = `${bp}/visordash/css.css?i=` + crypto.randomUUID();
        document.head.appendChild(styleElem);
      });
      try {
        await stylePromise;
      } catch (err) {
        if (err === null) {
          // If error is null, then either the style or
          // script failed to download. Therefore, retry.
          styleElem.remove();
          console.log(`style failed to load. retrying...`);
          // eslint-disable-next-line no-magic-numbers
          setTimeout(loadAssetsAsync, 3000);
          return;
        }
        throw err;
      }
      console.log(`style loaded. loading script...`);
      /** @type{HTMLScriptElement}*/
      let script;
      const scriptPromise = new Promise((resolve, reject) => {
        script = document.createElement('script');
        script.src = `${bp}/visordash/js.js?i=` + crypto.randomUUID();
        script.type = 'module';
        script.async = false;
        script.onload = () => {
          document.head.appendChild(script);
          resolve();
        };
        script.onerror = () => reject(null);
        document.head.appendChild(script);
      });
      await scriptPromise;
      console.log('script loaded.');
    }
  }, []);

  // Passive, on-demand snapshot
  useEffect(() => {
    if (fireSnapshot) {
      (async () => {
        const snapFn = window.__visorState?.getAppStateAsync;
        if (typeof snapFn === 'function' && typeof setPropsRef.current === 'function') {
          const appState = await snapFn(/*pass 'true' to key by name*/ true);
          setPropsRef.current({
            parts: appState.toDict(),
            fireSnapshot: false,
          });
        } else if (typeof setPropsRef.current === 'function') {
          setPropsRef.current({ parts: null, fireSnapshot: false });
        }
      })();
    }
  }, [fireSnapshot]);

  return (
    <div id={id} style={{ width: '100%', height: '100%' }}>
      <div id="VisorContainer" style={{ width: '100%', height: '100%' }} />
    </div>
  );
};

Visordash.propTypes = {
  /**
   * The ID used to identify this component in Dash callbacks.
   */
  id: PropTypes.string,
  /**
   * The host for the websocket connection
   */
  host: PropTypes.string,
  /**
   * The port for the websocket connection
   */
  port: PropTypes.number,
  /**
   * The aspect ratio of the viewer.
   * Set to -1 to make the Visor component always fit its container.
   */
  aspectRatio: PropTypes.number,
  /**
   * The pixel density of the viewer.
   * Think of it like the "DPI" of the Visor component: the higher the pixel density,
   * the smaller the UI panels and text. The lower the pixel density, the larger the UI panels and text.
   * Default is 1,000. Set to -1 to disable.
   */
  pixelDensity: PropTypes.number,
  /**
   * Enable/disable dark CSS theme.
   */
  darkMode: PropTypes.bool,
  /**
   * URL prefix for all internal viewer assets (JS, CSS, WASM, fonts).
   * Set this when deploying behind a reverse proxy with a path prefix,
   * e.g. "/my-solution-prefix".  Must start with "/" when non-empty and
   * must NOT end with "/".  Default is "" (no prefix).
   */
  basePath: PropTypes.string,
  /**
   * When set to true, triggers the frontend to take a snapshot of the current parts state.
   * The snapshot is returned via the `parts` prop and `fireSnapshot` is reset to false.
   */
  fireSnapshot: PropTypes.bool,
  /**
   * Contains the latest snapshot of the parts state, returned from the frontend when `fireSnapshot` is triggered.
   */
  parts: PropTypes.any,
  /**
   * Dash-injected function used to update component props from the frontend.
   */
  setProps: PropTypes.func,
};

export default Visordash;
