import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { copyFile, mkdir } from 'fs/promises';
import fs from 'fs';
import path from 'path';
import * as zlib from 'zlib';

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [
        react(),
        {
            name: 'modify-text-file',
            async closeBundle() {
                // copy client bundle files from /visor-client/modules/wasm to /viewer/client_bundle/wasm
                const outDir = this.environment.config.build.outDir;
                const vtkAssetDir = path.resolve(outDir, 'wasm');
                await mkdir(vtkAssetDir, { recursive: true });
                {
                    await copyAsset('vtkWebAssembly.wasm');
                    await copyAsset('vtkWebAssembly.mjs');
                    await copyAsset('vtkWebAssemblyAsync.wasm');
                    await copyAsset('vtkWebAssemblyAsync.mjs');

                    async function copyAsset(fileName: string) {
                        const src = path.resolve(__dirname, `modules/wasm/${fileName}`);
                        const dest = path.resolve(vtkAssetDir, fileName);
                        await copyFile(src, dest);
                    }
                }
                ///////////////////////////////////////////////////////////////////////////////////////
                ///////////////////////////////////////////////////////////////////////////////////////
                ///////////////////////////////////////////////////////////////////////////////////////
                let reactJsPath: string | null = null;
                let reactCssPath: string | null = null;
                const reactAssetDir = path.resolve(outDir, 'assets');
                const reactAssetPaths = await fs.promises.readdir(reactAssetDir);
                if (reactAssetPaths.length != 2) {
                    const msg = `There should be exactly 2 files in the React asset directory (js and`;
                    throw new Error(`${msg} css). Directory searched: '${reactAssetPaths}'`);
                }
                reactAssetPaths.forEach((filename) => {
                    if (/\.js$/i.test(filename)) {
                        reactJsPath = path.join(reactAssetDir, filename);
                    } else if (/\.css$/i.test(filename)) {
                        reactCssPath = path.join(reactAssetDir, filename);
                    }
                });
                if (reactJsPath == null) {
                    const msg = `No JS file was found in React asset`;
                    throw new Error(`${msg} directory '${reactAssetDir}'`);
                }
                if (reactCssPath == null) {
                    const msg = `No CSS file was found in React asset`;
                    throw new Error(`${msg} directory '${reactAssetDir}'`);
                }
                console.log(`React JS path: '${reactJsPath}'`);
                console.log(`React CSS path: '${reactCssPath}'`);
                // Rewrite legacy names before reading JS/CSS so generated Python helpers
                // will contain the rewritten content.
                try {
                    rewriteLegacyNames(outDir);
                } catch (e) {
                    console.warn('rewriteLegacyNames failed:', e);
                }
                const reactJs = await fs.promises.readFile(reactJsPath, 'utf-8');
                const reactCss = await fs.promises.readFile(reactCssPath, 'utf-8');
                ///////////////////////////////////////////////////////////////////////////////////////
                ///////////////////////////////////////////////////////////////////////////////////////
                ///////////////////////////////////////////////////////////////////////////////////////
                const vtkMjsPath = path.join(vtkAssetDir, 'vtkWebAssembly.mjs');
                const vtkWasmPath = path.join(vtkAssetDir, 'vtkWebAssembly.wasm');
                const vtkAsyncMjsPath = path.join(vtkAssetDir, 'vtkWebAssemblyAsync.mjs');
                const vtkAsyncWasmPath = path.join(vtkAssetDir, 'vtkWebAssemblyAsync.wasm');
                console.log(`VTK MJS path: '${vtkMjsPath}'`);
                console.log(`VTK WASM path: '${vtkWasmPath}'`);
                console.log(`VTK ASYNC MJS path: '${vtkAsyncMjsPath}'`);
                console.log(`VTK ASYNC WASM path: '${vtkAsyncWasmPath}'`);
                const vtkWasmZipped = zlib.gzipSync(await fs.promises.readFile(vtkWasmPath), {
                    level: zlib.constants.Z_BEST_COMPRESSION,
                });
                const vtkAsyncWasmZipped = zlib.gzipSync(
                    await fs.promises.readFile(vtkAsyncWasmPath),
                    {
                        level: zlib.constants.Z_BEST_COMPRESSION,
                    }
                );
                const vtkMjs = await fs.promises.readFile(vtkMjsPath, 'utf-8');
                const vtkWasmBase64 = vtkWasmZipped.toString('base64');
                const vtkAsyncMjs = await fs.promises.readFile(vtkAsyncMjsPath, 'utf-8');
                const vtkAsyncWasmBase64 = vtkAsyncWasmZipped.toString('base64');
                ///////////////////////////////////////////////////////////////////////////////////////
                ///////////////////////////////////////////////////////////////////////////////////////
                ///////////////////////////////////////////////////////////////////////////////////////
                const cssDir = path.resolve(outDir, 'css');
                const darkThemePath = path.join(cssDir, 'theme-dark.css');
                console.log(`Dark theme path: '${darkThemePath}'`);
                const lightThemePath = path.join(cssDir, 'theme-light.css');
                console.log(`Light theme path: '${lightThemePath}'`);
                const darkThemeCss = await fs.promises.readFile(darkThemePath, 'utf-8');
                const lightThemeCss = await fs.promises.readFile(lightThemePath, 'utf-8');
                ///////////////////////////////////////////////////////////////////////////////////////
                ///////////////////////////////////////////////////////////////////////////////////////
                ///////////////////////////////////////////////////////////////////////////////////////
                const fontDir = path.resolve(outDir, 'fonts');
                const fontPath = path.join(fontDir, 'source-sans-3.woff2');
                console.log(`Font path: '${fontPath}'`);
                const fontZipped = zlib.gzipSync(await fs.promises.readFile(fontPath));
                const fontBase64 = fontZipped.toString('base64');
                ///////////////////////////////////////////////////////////////////////////////////////
                ///////////////////////////////////////////////////////////////////////////////////////
                ///////////////////////////////////////////////////////////////////////////////////////

                function stringToFunction(funcName: string, str: string) {
                    let python = `def ${funcName}():\n`;
                    python += `\tparts: [str] = [\n`;
                    for (const match of str.matchAll(/.{1,100}/gs)) {
                        python += `\t\t"${escape(match[0])}",\n`;
                    }
                    python += '\t]\n';
                    python += '\treturn "".join(parts)\n';
                    return python;

                    function escape(str: string) {
                        str = str.replace(/\\/g, '\\\\');
                        str = str.replace(/"/g, '\\"');
                        str = str.replace(/'/g, "\\'");
                        str = str.replace(/\n/g, '\\n');
                        str = str.replace(/\r/g, '\\r');
                        str = str.replace(/\t/g, '\\t');
                        str = str.replace(/\f/g, '\\f');
                        // eslint-disable-next-line no-control-regex
                        str = str.replace(/\x08/g, '\\b');
                        return str;
                    }
                }

                let reactAssetsPython = stringToFunction('getJs', reactJs);
                reactAssetsPython += stringToFunction('getCss', reactCss);
                let vtkAssetsPython = stringToFunction('getVtkMjs', vtkMjs);
                vtkAssetsPython += stringToFunction('getVtkWasmBase64', vtkWasmBase64);
                let vtkAsyncAssetsPython = stringToFunction('getVtkAsyncMjs', vtkAsyncMjs);
                vtkAsyncAssetsPython += stringToFunction(
                    'getVtkAsyncWasmBase64',
                    vtkAsyncWasmBase64
                );
                let cssPython = stringToFunction('getDarkThemeCss', darkThemeCss);
                cssPython += stringToFunction('getLightThemeCss', lightThemeCss);
                const fontPython = stringToFunction('getFontBase64', fontBase64);
                ///////////////////////////////////////////////////////////////////////////////////////
                const dashProjectDir = path.resolve(outDir, '..', '..');
                console.log(`Dash project directory: '${dashProjectDir}'`);
                const dashPackageDir = path.join(dashProjectDir, 'dash', 'visordash');
                console.log(`Dash package directory: '${dashPackageDir}'`);
                await fs.promises.mkdir(dashPackageDir, { recursive: true });
                ///////////////////////////////////////////////////////////////////////////////////////
                const reactAssetsPythonPath = path.join(
                    dashPackageDir,
                    '__GITIGNORE_visor_react_assets.py'
                );
                await fs.promises.writeFile(reactAssetsPythonPath, reactAssetsPython, 'utf-8');
                console.log(`Created file: '${reactAssetsPythonPath}'`);
                ///////////////////////////////////////////////////////////////////////////////////////
                const vtkAssetsPythonPath = path.join(
                    dashPackageDir,
                    '__GITIGNORE_visor_vtk_assets.py'
                );
                await fs.promises.writeFile(vtkAssetsPythonPath, vtkAssetsPython, 'utf-8');
                console.log(`Created file: '${vtkAssetsPythonPath}'`);
                ///////////////////////////////////////////////////////////////////////////////////////
                const vtkAsyncAssetsPythonPath = path.join(
                    dashPackageDir,
                    '__GITIGNORE_visor_vtk_async_assets.py'
                );
                await fs.promises.writeFile(
                    vtkAsyncAssetsPythonPath,
                    vtkAsyncAssetsPython,
                    'utf-8'
                );
                console.log(`Created file: '${vtkAsyncAssetsPythonPath}'`);
                ///////////////////////////////////////////////////////////////////////////////////////
                const cssPythonPath = path.join(dashPackageDir, '__GITIGNORE_visor_css.py');
                await fs.promises.writeFile(cssPythonPath, cssPython, 'utf-8');
                console.log(`Created file: '${cssPythonPath}'`);
                ///////////////////////////////////////////////////////////////////////////////////////
                const fontPythonPath = path.join(dashPackageDir, '__GITIGNORE_visor_font.py');
                await fs.promises.writeFile(fontPythonPath, fontPython, 'utf-8');
                console.log(`Created file: '${fontPythonPath}'`);
            },
        },
    ],
    build: {
        minify: false,
        outDir: '../viewer/client_bundle',
        emptyOutDir: true,
    },
});

// Post-build: ensure any legacy vtkWasmSceneManager identifiers emitted
// inside bundled assets are rewritten to vtkWebAssembly to avoid runtime
// fallback probing. This is a lightweight deterministic text-replacement
// that keeps the bundle clean without editing dependency sources.
function rewriteLegacyNames(outDir: string) {
    const assetsDir = path.resolve(outDir, 'assets');
    if (!fs.existsSync(assetsDir)) return;
    for (const file of fs.readdirSync(assetsDir)) {
        const full = path.join(assetsDir, file);
        if (!/\.js$/.test(file)) continue;
        let txt = fs.readFileSync(full, 'utf-8');
        const before = txt;
        // Replace the legacy bundle name with the modern one
        txt = txt.replace(/vtkWasmSceneManager/g, 'vtkWebAssembly');
        if (txt !== before) {
            fs.writeFileSync(full, txt, 'utf-8');
            console.log(`Rewrote legacy wasm name in ${full}`);
        }
    }
}

// Export helper for manual invocation after build if needed.
export { rewriteLegacyNames };
