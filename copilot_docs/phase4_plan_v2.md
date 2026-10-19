# Phase 4 plan v1 — REMOTE rendering mode (trame-rca)

Status: v1. Sections 1–6 keep v0's facts unchanged. Lines marked **v1 —** record where a Section 8 ruling settles,
reopens or supersedes a v0 recommendation, and three rows of 6.F are rewritten. Section 7 is rewritten to apply
the rulings, with S1 split into a PR stack and the cleanup candidates and open questions for ruling in 7.2.
Section 8 keeps the rulings verbatim and adds their bindings (8.1). This file replaces `phase4_plan_v0.md`; later sessions read this file only.

Tags: **[src]** = read from source (path cited). **[inf]** = inferred, not read.
**cannot determine** = not read; no claim is made.
Tree (Sections 1–6): commit "remove unused client renderer members" on `chore/renderer-interface-cleanup`.
Tree (Section 7 reads): commit "add rulings" on `feat/4.0-plan`; difference from the above in 7.0.
Spike: `_spike_reference/theia`, commit "fix LUT sync issue" (`junk/poc-remote-with-round-trips`).
Paths: server = `src/ansys/visor/viewer/`, client = `src/ansys/visor/visor-client/src/`,
spike = `_spike_reference/theia/src/ansys/theia/viewer/`, spike client =
`_spike_reference/theia/src/ansys/theia/theia-client/src/`. `client_bundle/` was never searched.
Searches are single-pattern, literal (`git grep -n -F` or `Select-String -SimpleMatch`); pattern text is given
at each use.

---

## Section 1 — Stories (verbatim)

S1 Server: RemoteRenderer(IRenderer), off-screen OpenGL2, build_renderer_annotation() -> None;  per-part applies through
           VtkNodePipeline; widget and toggle applies with bounds injected; camera methods, the camera sent to the browser
           by its own trigger; set_viewport_size.  RemoteApp registers every LocalApp trigger and renders once per
           event-loop tick.  VisorVTKRemote overrides the lifecycle hooks.  VisorRemoteScene implements the runtime-state
           hooks against this renderer, with no browser dependency.  The spike's wslink StreamManager patch: drop it if its
           failure no longer reproduces, otherwise, annotate it with the upstream issue and make it fail loudly.
           TS RendererAnnotation becomes a discriminated union.  
S2 REMOTE and HEADLESS in RenderingMode (the backend may already select REMOTE, wired to a stub; check).
           App.tsx probes rendering_mode and is the only mode branch; remote reuses teh probe's session and never loads
           the wasm module.  Both modes serve one bundle. 
S3 src/rca/RemoteCanvas.tsx draws frames and forwards mouse and wheel (y flipped).  src/renderer/RemoteRenderer.ts
           sends through TrameTriggerSender; camera from a remote-only cache.
S4 Server-originated changes (add, remove, update, clear, update_variables, load_state) bump scene_version; the client
           rebuilds and releases what the replaced frontend registered.
S5 Camera interaction through the server-side interactor.
S6 The server render window follows a canvas resize.

**v1 —** The stories stay verbatim. Two story lines are overridden by rulings: S1's "TS RendererAnnotation
becomes a discriminated union" (ruling 7: no union; the probe gives the mode) and S2's "REMOTE and HEADLESS in
RenderingMode" (ruling 8: HEADLESS is out of this phase). S1's "VisorVTKRemote overrides the lifecycle hooks"
is still open (C-8).

---

## Section 2 — Q1: client camera read and the four synchronous toggle getters, with no wasm

### 2.1 Facts

**2.1.1 Client camera read type — `VisorCameraState` in `client/renderer/IRenderer.ts`** [src], and where
`WasmRenderer.getCameraStateAsync` (`client/renderer/WasmRenderer.ts`) gets each field [src]:

| Field | Source in WasmRenderer | Kind |
|---|---|---|
| `distance` | wasm camera `GetDistance` | derived |
| `orthographic` | `!!GetParallelProjection` | derived (duplicates `parallelProjection`) |
| `orthographicScale` | parallel scale | derived (duplicates `parallelScale`) |
| `unitsPerPixel` | `parallelScale / (0.5 * viewPortHeight)` | derived, needs viewport |
| `viewPortHeight` | `vtkScene.getViewPortHeightAsync()` (`renderWindow.GetSize` × viewport) | viewport, not camera |
| `position` | camera getter | record |
| `focalPoint` | camera getter | record |
| `viewUp` | camera getter | record |
| `clippingRange` | camera getter | record |
| `parallelProjection` | raw value `=== 1` | record |
| `viewAngle` | camera getter | record |
| `parallelScale` | camera getter | record |

All twelve come from the wasm camera or wasm viewport. With no wasm, none has a source on the client [inf from
the table].

**2.1.2 Callers of `getCameraStateAsync`** (search `getCameraStateAsync` in client `src/`) [src]:

| Call site | Uses |
|---|---|
| `CameraSyncReporter.ts:114` | builds the 7-field `sync_camera` payload (record fields only), origin `gesture` |
| `VisorFrontend.tsx:86` | exposes it on the frontend object |
| `VisorFrontend.tsx:292` | `getAppStateAsync` → camera saved into app state (record fields) |
| `UiScaffold.tsx:120` | ruler: `setUnit` path, reads `orthographic`, `unitsPerPixel` |
| `WasmRenderer.ts:224` | camera-changed listener payload |
| tests | `CameraSyncReporter.test.ts`, `VariableRecordProjection.test.tsx:153` |

`addCameraChangedListener` caller: `UiScaffold.tsx:86` (`updateRuler` uses `orthographic`, `unitsPerPixel`) [src].
The derived fields are consumed only by the ruler; the record fields only by sync and save [src, rows above].
`CameraSyncReporter` is attached per frontend at `VisorFrontend.tsx:99`
(`attachCameraSyncReporter(renderer, triggerSender)`), released through `releaseCameraSettledListener`
(`VisorFrontend.tsx:100`, called at `App.tsx:154`) [src; search `releaseCameraSettledListener`].

**2.1.3 Callers of the four toggle getters** `isCrossSectionVisible`, `isBoundingBoxVisible`,
`isOrthographicEnabled`, `areEdgesVisibleGlobally` (search: each name separately in client `src/`) [src]:
- `VisorFrontend.tsx:288–291` — `getAppStateAsync` copies the four into the saved app state.
- `WasmRenderer` internal: each toggle setter writes locally, then reads its own getter back to build the send.
- tests: `WasmRendererWidgetTriggers.test.tsx`, `VariableRecordProjection.test.tsx`.
- `getAppStateAsync` external caller: dash `src/ansys/visor/dash/src/lib/components/Visordash.react.js:84`
  (`window.__visorState?.getAppStateAsync(true)` → `appState.toDict()`).
IRenderer contract on the getters: "last server-delivered or last local set" [src, `IRenderer.ts`].

**2.1.4 Toolbar starting values** [src]. `Panel_BottomMiddle.tsx` lines 56–74 call
`setOrthographicModeAsync()` / `setCrossSectionVisibilityAsync()` / `setEdgeVisibilityGlobalAsync()` /
`setBoundingBoxVisibilityAsync()` with **no argument** (toggle), then `visorState.render()`. The value toggled from:
- Orthographic: `OrthographicWidget.#enabled` starts `false`, seeded from the wasm camera in `createAsync`;
  toggle reads the camera.
- Bounding box: toggle queries the outline actor `GetVisibility`.
- Cross section: `!#enabled` (widget field).
- Edges: `!#enabled` (widget field).
Two of four start values come from wasm objects (camera, outline actor) [src]; with no wasm they have no source [inf].

**2.1.5 Every camera-type declaration, field by field** [src]:

| Declaration | Fields |
|---|---|
| server `models/common/visor_camera_state.py` `VisorCameraState` (filled by `_read_pipeline_camera`) | position, focal_point (`focalPoint`), view_up (`viewUp`), clipping_range (`clippingRange`), parallel_projection (`parallelProjection`), view_angle (`viewAngle`), parallel_scale (`parallelScale`) — 7 |
| server `models/runtime/requests/sync_camera_payload.py` `SyncCameraPayload` | origin `gesture`/`programmatic`, camera: `VisorCameraState` |
| client `renderer/IRenderer.ts` `VisorCameraState` | 12 fields, table 2.1.1 |
| client `state/appstate/VisorCameraState.tsx` | the same 7 record fields as the server model |
| spike server `RemoteRenderer.get_camera_state` → `TheiaCameraState`, sent as `model_dump()` (camelCase) in state `rca_camera_state` | position, focalPoint, viewUp, clippingRange, parallelProjection, viewAngle, parallelScale — the same 7 |
| spike client `renderer/IRenderer.ts` `TheiaCameraState` | the 7 above plus derived `distance`, `orthographic`, `orthographicScale`, `unitsPerPixel`, `viewPortHeight` — the same 12 as VISOR's client type |
| spike client `vtk_to_camera_state` (in `RemoteRenderer.ts`) | `distance` from position/focalPoint; `unitsPerPixel = parallelScale*2/viewPortHeight`; `viewPortHeight` kept from the previous value, default 600, **never updated** |

**2.1.6 What the server delivers** [src]:
- `RuntimeViewState`: `camera` (`VisorCameraState`, nullable), `cross_section` (nullable).
- `RuntimeSceneState`: `unit`, `orthographic_enabled` (nullable), `cross_section_enabled`, `edges_enabled`,
  `bounding_box_enabled`, `dataset_states`, `variable_states`.
- `VisorSceneDetails` (schema 4): `ui`, `scene`, `vtk_info`; docstring: "Never carries the view records".
  Client `VisorSceneDetails` builds app state from `{ui, scene}` only.
- The view (camera, cross section) reaches the client only through `_push_runtime_state` →
  `VisorFrontendBridge.set_state` (`js_call(ref, "setState", VisorLoadStateRequest)`, fire-and-forget) in local mode.
- Server `_current_runtime_state` derives `orthographic_enabled` from the camera record [src, `vtk/scene/base.py`].
Consequence: the four toggles are delivered in scene details on every rebuild; the camera is not [inf].
None of the five derived fields is delivered by any server model [src, 2.1.5].

**2.1.7 How the spike toggled** [src, spike client `renderer/RemoteRenderer.ts`]:
- Cross section and bounding box: local fields `#crossSectionOn`, `#bboxOn`, seeded from
  `WidgetAnnotation.cross_section_visible` / `bbox_visible`; flipped locally, value sent by trigger.
- Camera and projection: optimistic local patch, then fire-and-forget triggers `set_camera_position`,
  `set_camera_focal_point`, `set_camera_view_up`, `set_camera_clipping_range`, `set_orthographic_mode {enable}`,
  `set_camera_view_angle`, `set_camera_parallel_scale`.
- `getCameraStateAsync`: round trip, trigger `get_camera_state`.
- Server→client camera: subscription to wslink topic `"trame.state.update"`, reading `rca_camera_state`.
- `render()` and `resizeAsync()` are no-ops.
- Payload keys snake_case (`node_id`); VISOR uses camelCase (`nodeId`) validated by pydantic aliases.

**2.1.8 trame transport facts that bound the options** [src]:
- `trame.state.get` RPC returns the full server state (initial connect); `push_state_change` publishes
  `"trame.state.topic"` with only the changed keys; `js_call` → `push_actions` (`"trame.actions.topic"`);
  `trame.trigger` RPC runs the handler inside `with server.state` (`.venv/.../trame_server/protocol.py` L130–256,
  `core.py` L230–269).
- Client `@kitware/trame` 1.0.0: `state.js` has `onChange(fn)` and `watch(keys, fn)`; `Trame.js` subscribes to
  `"trame.state.topic"`.
- `"trame.state.update"` is an RPC name, not a topic [src]. So the spike's `rca_camera_state` subscription most
  likely never fired [inf]. **Silent failure** in the spike: stale camera with no error.
- In trame, a "trigger" is client→server. The server can reach the client only by state or `js_call` [inf from
  the rows above]. S1's "the camera sent to the browser by its own trigger" therefore needs a state key or a
  js_call; see 6.S1 contradictions.

### 2.2 Options

| # | Option | Cost to callers |
|---|---|---|
| A | `RemoteRenderer` keeps a remote-only cache. Camera: the 7 record fields from a server push (state key, watched with `state.watch`); derived fields computed client-side (`distance` from position/focalPoint, `orthographic`/`orthographicScale` copied, `viewPortHeight` from the `RemoteCanvas` CSS height, `unitsPerPixel` from those). Toggles: seeded from `RuntimeSceneState` on each rebuild, updated on local set; no-arg setters flip the cache and send the explicit value. | None: signatures unchanged; getters stay synchronous. Ruler, sync, save, dash unchanged. |
| B | `getCameraStateAsync` round-trips a server trigger (spike's `get_camera_state`). Toggles as A. | Signatures unchanged (already async). One round trip per ruler update and per save; camera-changed listener still needs a push. |
| C | Shrink the IRenderer camera type to the 7 record fields; callers compute derived values. | Changes `UiScaffold` ruler, `WasmRenderer`, tests; edits local-mode code paths. |
| D | Getters return `undefined` in remote. | `getAppStateAsync`, dash `getAppStateAsync(true)`, widget toggles must handle absence; saved state loses toggles. |
| E | Spike model: optimistic local patch on each camera setter plus fire-and-forget sends, cache never confirmed by the server. | None to signatures; cache diverges from the server after any server-side gesture (S5), since the spike's push never arrived (2.1.8). |

### 2.3 Recommendation

**A.** Rejects B (a round trip per ruler update while S5 already needs a push), C (edits local-mode code; local mode
runs no new code), D (breaks the getter contract and the dash save path), E (unconfirmed cache; the spike's version
was silently stale).
`viewPortHeight` comes from the client canvas, not a server default (the spike's 600 default is the bug to avoid).
Fact that would change it: if a state-key camera push from the server is not delivered at interaction end
(threading of state writes from the render loop, see 5.4) → B.

**v1 — Ruled: A (ruling 1).** No-arg setters flip the cache and send the explicit value. Bound to S1.7, S3.3
and S6.
**v1 — Reopened under ruling 13: C.** C was rejected only because it edits local-mode code. On its merits it
overlaps ruling 2's open question, whether per-part methods leave the interface, which is decided after S1. C is
carried to that decision and not ruled here.

---

## Section 3 — Q2: color and selection applies

### 3.1 Facts — what each implementation writes

| Apply | VISOR client `WasmRenderer` [src] | VISOR server `VtkNodePipeline` [src] | Spike `RemoteRenderer` [src] |
|---|---|---|---|
| diffuse color | `#applyDiffuseColorAsync(nodeId, rgb, selected)`: coefficients per `selected` (below), then `SetDiffuseColor(rgb)` | `set_diffuse_color`: `SetDiffuseColor` only | `SetDiffuseColor(rgb)` |
| selected = true | `SetAmbientColor(SELECTION_TINT_RGB = 0, 62/255, 111/255)`, `Diffuse 0.5`, `Ambient 0.5`, then `SetDiffuseColor(rgb)` | `set_selected(node, True, rgb)`: `AmbientColor(0,62/255,111/255)`, `Diffuse 0.5`, `Ambient 0.5`, then `SetDiffuseColor(*rgb)` | `SetDiffuseColor(DefaultSelectionColor)`, `Ambient 0.3` — replaces the part colour |
| selected = false | `Diffuse 1`, `Ambient 0`, then `SetDiffuseColor(rgb)` | `Diffuse 1.0`, `Ambient 0.0`, then `SetDiffuseColor(*rgb)` | `SetDiffuseColor(rgb)`, `Ambient 0`, `Diffuse 1` |
| color variable | scalar mode, `SetScalarRange`, `SetColorModeToMapScalars`, `ColorByArrayComponent(name, comp)`, `SetScalarVisibility(1)` | checks variable type and array presence; scalar mode point/cell, `SelectColorArray(name)`, `SetArrayComponent`, `SetScalarRange`, `SetColorModeToMapScalars`, `SetScalarVisibility(True)`, `SetUseLookupTableScalarRange(0)`; LUT built once | `ColorByArrayComponent(index)`, reconfigures LUT |
| clear color variable | `SetScalarVisibility(0)` | `SetScalarVisibility(False)` only | `SetScalarVisibility` off **and** `SetDiffuseColor(DefaultMeshColor)` |

**Call order relied on:**
- Server `_apply_part_state` (`vtk/scene/base.py`, ~L1137): `apply_visibility`, `apply_opacity`,
  `apply_diffuse_color`, `apply_selected(part_id, selected, rgb)`, `_apply_part_color_variable` (clear or apply)
  [src]. `set_selected` takes `diffuse_rgb` and rewrites `DiffuseColor`, so the result does not depend on whether
  diffuse ran first, given the registry rgb [inf from the rows above].
- Client `VisorFrontend.setAppStateAsync` (L471–491): diffuse then selected **sequenced** per node (comment: both
  write the same ambient/diffuse properties), then opacity/visibility/colorVariable in parallel [src]. The
  sequencing guards interleaving of async writes; each call writes the full set from its own arguments [inf].
- Spike [src]: `apply_part_state` applies opacity, visible, diffuse, color_by, edge — never selection.
  `_restore_part_states_from_runtime` calls `apply_part_state`, then `clear_color_variable` when color_by is
  None, which overwrote the restored diffuse with `DefaultMeshColor`. So the spike's callers did **not** enforce
  a safe order; a restore lost the part colour [inf from the two src facts].

### 3.2 Per-method contract

All VISOR implementations meet this today; a RemoteRenderer that delegates to `VtkNodePipeline` (S1) meets it by
construction; the spike does not (two rows).

- `apply_diffuse_color(node, rgb)`: writes `DiffuseColor = rgb` only.
- `apply_selected(node, selected, diffuse_rgb)`: writes `AmbientColor` (tint), `Ambient`, `Diffuse` as a function
  of `selected` only, and `DiffuseColor = diffuse_rgb`. Selection never replaces the part colour.
- `apply_color_variable(...)`: writes scalar mode, array, component, range, color mode, LUT, `ScalarVisibility on`;
  never touches `DiffuseColor`/`Ambient*`/`Diffuse`.
- `clear_color_variable(node)`: writes `ScalarVisibility off` only.
- Result: the four calls commute given consistent arguments (`diffuse_rgb` in `apply_selected` equals the part's
  current diffuse colour). The caller owns that consistency (server: registry; client: part state).

### 3.3 Recommendation

Adopt 3.2 as the IRenderer docstring on both stacks; RemoteRenderer delegates to `VtkNodePipeline`.
Rejects: the spike's selection-as-colour-replacement and clear-resets-diffuse (order-dependent; shown to lose the
colour on restore; differs from local mode's look); documenting a required call order instead of a contract
(callers on two stacks would each have to honour it).
Fact that would change it: if the ambient tint is not visible in the server's off-screen render (lighting differs
from wasm) — **cannot determine** without a remote render; checked manually in S1 (Section 7).

**v1 — Ruled: contract 3.2 adopted as the docstring on both stacks; RemoteRenderer delegates to VtkNodePipeline
(ruling 2).** Bound to S1.2 and S1.3. The tint check is the second manual check in S1.6. Whether the per-part
methods leave the interface is decided after S1.

---

## Section 4 — Picking

### 4.1 Facts — today (local) [src unless marked]

- **Part select by click.**
  1. `VtkScene.#setupPicker`: on mouseup, wasm `picker.Pick`; click listeners receive `actor.id` and normalised
     coordinates (`client/wasm/VtkScene.js`).
  2. `WasmRenderer` maps actor id → nodeId through `#actorIdToNodeId`.
  3. `Panel_TopRight.tsx` L427–453 (listener on `visorState.addViewerClickedListener`), part mode only: without
     ctrl/shift deselect every row (`node.setSelectedAsync(false)`), toggle the clicked node,
     `updateSelectedNodesArray`, `onSelectionChangeAsync`.
  4. `node.setSelectedAsync` (`state/VisorSceneGraph.tsx` L389) → `applySelectedAsync` →
     `renderer.setSelectedAsync(nodeId, selected, customDiffuseColor)`; if that changed anything →
     `renderer.sendPartSelectedAsync` → trigger `set_part_selected {nodeId, selected}`.
  Conclusion: part picking is client-side wasm; selection reaches the server as one `set_part_selected` per part.
- **Geometry picker.** A second listener, `renderer.addViewerClickedListener` (`VisorFrontend.tsx:190`, remover
  discarded), runs in non-part modes → `renderer.pickGeometryAsync(normX, normY, mode)` →
  `VtkScene.pickGeometryAsync`, which picks in wasm and sends trigger
  `pick_geometry(actorWasmId, cellId, mode, x, y, z)`. Server `LocalApp.pick_geometry` → scene → 
  `VisorLocalRenderer.pick_geometry` iterates actors matching the object-manager (wasm) id.
- **Highlight**: drawn on a client Canvas2D overlay by `setGeometryHighlightAsync`; removed by
  `clearGeometryHighlight` (`VtkScene.js`).
- `IRenderer.addViewerClickedListener(nodeId, ctrl, shift, normX, normY)`.

### 4.2 Facts — spike remote [src]

- Click detection in `RemoteCanvas`: left-button release within 5 CSS px of the press;
  `xVtk = (clientX-left)*dpr`, `yVtk = (height-(clientY-top))*dpr`.
- Spike `App` → `session.call("trame.trigger", ["pick_at_position", [{x,y}], {}])` → server `pick_node_id`
  (`vtkPropPicker.Pick(x, y, 0, renderer)`) → on hit `scene.set_part_selected(node_id, True)`; on empty space
  deselect all; deferred render; returns `node_id`.
- Client then `rendererRef.notifyClick(nodeId, ctrl, shift)` → click listeners → the panel flow, which selects
  again and sends `set_part_selected` again. Two owners of selection; ctrl/shift ignored server-side.
- Geometry picker: absent in the spike tree.
- No story S1–S6 names picking.

### 4.3 Options

| # | Option | Effect |
|---|---|---|
| P1 | Server-side pick returns a node id only (new trigger, coordinates from `RemoteCanvas`, `vtkPropPicker`), **no server-side selection**. `RemoteRenderer` raises the same `viewerClicked(nodeId, ctrl, shift, normX, normY)` event; `Panel_TopRight` selection flow unchanged. Geometry picker disabled in remote this phase; `RemoteRenderer.pickGeometryAsync` throws a named error. | Part-select parity; one owner of selection; no server highlight. |
| P2 | P1 plus geometry picking server-side: cell picker gives actor/cell/world position, feeds `pick_geometry`; highlight drawn as server actors. | `pick_geometry` keys on wasm actor ids (4.1) — needs a remote id scheme and a server highlight renderer; no story covers it. |
| P3 | Spike's model: server selects/deselects itself, then client re-selects. | Two owners of selection; bypasses `getSelectionMode()` and ctrl/shift. |
| P4 | No picking in remote this phase. | Click does nothing; smallest scope. |

### 4.4 Recommendation

**P1**, as an S3 increment, server trigger in S1. Rejects P2 (wasm-id keyed server path and client-side highlight
both need redesign; no story), P3 (two owners of selection, shown in 4.2), P4 (loses a working local feature for a
small saving).
Fact that would change it: a ruling that the phase excludes picking → P4; a ruling that geometry picking must work
in remote → P2 with its own story.

**v1 — Ruled: P1 (ruling 3).** Part select only; geometry picking in remote is a later story. The named error
conflicts with the tree: the click listener in `VisorFrontend` swallows it with `.catch(() => {})` (7.0, 7.1).
The resolution is C-5. Bound to S1.5 (`pick_part_at`, Q-3) and S3.4.

---

## Section 5 — Rebuild signal

### 5.1 Facts — local mode today [src]

- `VisorLocalRenderer.render()` = `RenderWindow.Render()` + `LocalView.update()` (`renderer/local_renderer.py`
  L677–684); `render_window_only()` = `Render()` only (L690); `flush_wasm_state()` = `LocalView.update()` only
  (L694). `LocalView` built with `throttle_rate=4, eager_sync=True`.
- `LocalView.update()` = `api.update(...)` then `server.js_call(ref, "update", options)`
  (`.venv/Lib/site-packages/trame_vtklocal/widgets/vtklocal.py` ~L285–304). Whether `throttle_rate` coalesces
  `update` calls: **cannot determine**. No `update_throttle` is used (search `update_throttle` in `src`: no match).
- Client: `RemoteVtkScene.updateAsync` is the `'update'` callback (`client/wasm/RemoteVtkScene.js` L215); after the
  wasm update it runs `#checkMemory`, `resizeAsync`, then every `#serverUpdatedListeners` entry. One
  `LocalView.update` → one rebuild.
- `App.onServerUpdateAsync` (`client/App.tsx`), in order:
  1. `clearObserversAndEventListeners` on `RemoteVtkScene` (clears `serverUpdated` and `setState` listeners only);
  2. trigger `get_visor_scene_details_json` → `new VisorSceneDetails`;
  3. `WasmRenderer.createAsync(vtkScene, requireWasmAnnotation(...), trameTriggerAsync)`;
  4. `new VisorFrontend(...)` (App.tsx L140);
  5. `oldFrontend.releaseCameraSettledListener()` (L154);
  6. `setAppStateAsync(appState, false)`, `__visorState = newFrontend`, `setVisorFrontend` (UiScaffold remounts via
     `key={randomInt()}`);
  7. `finally`: re-add the `serverUpdated` and `setState` listeners;
  8. `setTimeout` resize after 100 ms.
- Consequence of steps 1 and 7: an `update` arriving during a rebuild finds no listener and is dropped [inf].
  **Silent failure** today on a burst: the client can show a scene older than the server's, with no error.
  **v1 — Ruled: recorded, not fixed in this phase (ruling 11).** Carried in 7.6. The remote latest-wins rebuild
  stays remote-only so that local behaviour does not change (C-6).
- `RemoteVtkScene.getInstanceAsync` is called only at `App.tsx:83` (always loads wasm).

### 5.2 Facts — per S4 operation (all `app/visor_vtk.py`) [src]

| Operation | Call sites | Local signal |
|---|---|---|
| `start` | L222 `_scene.clear()` if input; L225 `_prepare_and_render_scene`; L228 `_server_manager.start` | `update` via `finalize_scene` → `render()` (before the server starts) |
| `update` | L252 clear; L255 `_prepare_and_render_scene` | `update` |
| `add_dataset` | L278 `_prepare_and_render_scene` (L496–523: `_register_dataset`, `finalize_scene` L521) | `update` |
| `remove_dataset` | L293 `_scene.remove_dataset`; `self.clear()` if count 0, else L298 `update_widgets`, L299 `_scene.render()` | `update` |
| `clear` | L318 `_scene.clear`; L319 `finalize_scene` | `update` |
| `update_variables` | L361 `update_variables_for_dataset` → `self.render()` (`vtk/scene/base.py` L577–578) | `update` |
| `load_state` | L416 `apply_state` | `update` only if `dataset_count > 0` (`finalize_scene(skip_reset_camera=True)`), then always `setState` via `_push_runtime_state` |

- `apply_state` order (under `_vtk_lock`, an RLock): `persisted_to_runtime`, `_load_variable_records`,
  `_restore_part_states`, `_restore_scene_state`, `_restore_ui_state`, `_restore_view_state`,
  `finalize_scene(skip_reset_camera=True)` if datasets, `_push_runtime_state`.
- `VisorLocalScene._push_runtime_state` = `render_window_only()` + `VisorFrontendBridge.set_state`
  (`js_call(ref, "setState", ...)`).
- `scene.add_dataset`, `scene.remove_dataset`, `scene.clear` do not render; the per-part, widget and panel
  coordinator methods write the store and apply under the lock and never push.
- `save_state` is async, calls `scene.get_state`, no render. `get_scene_details` runs without `_vtk_lock`.

### 5.3 Facts — spike `scene_version` [src]

- `RemoteApp.__init__` sets state `rendering_mode="remote"`, `rca_ready=False`, `scene_version=0`;
  `on_client_connected` → `schedule_render()` only (`remote_app.py` L59–61).
- `notify_scene_changed()` bumps `scene_version` (`remote_app.py` L184–194). Callers (search
  `notify_scene_changed` in spike `src`): only `theia_vtk_remote.py:110` (`_post_add_dataset_hook`, then
  `schedule_render`) and `:115` (`_post_remove_dataset_hook`). No bump on update, clear, update_variables,
  load_state.
- `_defer_render`: one `asyncio.ensure_future(_flush_render)` per loop tick, `await asyncio.sleep(0)` then
  `schedule_render` (L229–244).
- Spike client `useRemoteVtk` rebuilds the frontend on `scene_version`, reusing the same `RemoteRenderer`, and
  subscribed through `"trame.state.update"` — an RPC name, not the state topic (2.1.8). The spike's rebuild on
  `scene_version` most likely never fired [inf]; `App.tsx` `UiScaffold key={remoteVersion}`.

### 5.4 Facts — burst and reconnect mechanics [src]

- `trame.state.get` returns the full state at connect (`trame_server/protocol.py` L216–222): a reconnecting client
  sees the current value of any state key.
- `push_state_change` publishes only changed keys; actions (`js_call`) are events and are not replayed.
- The thread a VisorVTK operation runs on: the caller's thread; the trame server runs on
  `TrameServerManager._async_runner.thread` (`exec_mode="coroutine"`). Whether state writes from the caller thread
  are flushed safely: **cannot determine** (not read). Local mode already calls `js_call` from the caller thread
  through `LocalView.update` [src].

### 5.5 Options — one signal both modes use

| # | Option | Burst | Reconnect |
|---|---|---|---|
| R1 | Server: one VisorVTK hook (`_post_scene_change_hook`) at each S4 site. Local: hook is a no-op (local already signals through `render()` → `update`). Remote: bump state `scene_version` and schedule a frame. Client remote: `state.watch(['scene_version'])`; rebuild latest-wins (after a rebuild, compare the version seen with the current one and rebuild again if newer). | At most one extra rebuild after the burst; no version lost, since the value persists in state. | Full state on connect; the first build reads the current version. |
| R2 | `scene_version` in both modes; local rebuild moves from the wasm `update` callback to the state watch. | As R1. | As R1. Local risk: the version can arrive before the wasm objects it refers to; ordering of `"trame.state.topic"` vs `"trame.actions.topic"` is **cannot determine** → `requireWasmAnnotation`/actor lookups fail. Edits local-mode code. |
| R3 | Remote emits an event: `js_call(ref, "sceneChanged")`. | One event per op; the current App removes its listener during a rebuild (5.1), so events in a burst are dropped. | Not replayed; client must also build on connect. Needs a client handler for `"trame.actions.topic"` outside wasm — **cannot determine** whether `@kitware/trame` dispatches it without a ref component. |
| R4 | Client polls or re-fetches scene details on each frame. | Rebuild per frame. | Implicit. Cost per frame. |

### 5.6 Recommendation

**R1.** Rejects R2 (edits local mode; unproven topic ordering), R3 (inherits the drop-during-rebuild defect and
needs an unverified client path), R4 (cost per frame).
The hook is called once per operation at the call sites in 5.2, not from `render()`: in remote, `render()` is also
reached by trigger-driven changes that need a frame but no rebuild [inf from 5.2 and S1's "renders once per
event-loop tick"]. `load_state` bumps unconditionally (it can change toggles and parts with no datasets).
Fact that would change it: if a state write from the caller thread is not delivered (5.4) → keep R1 but marshal the
bump onto the loop thread via the async runner; if a ruling requires one client path for both modes → R2 with an
ordering proof first.
Separate defect, not this phase's choice: the local drop-during-rebuild in 5.1 (flag; candidate ruling).

**v1 — Ruled: R1 (ruling 4).** The bump is marshalled onto the loop thread unless shown safe, and every
`Render()` holds `_vtk_lock`. Two consequences (7.1):
- The marshalling must not block. Use `AsyncRunner.run_coroutine`, not `run_coroutine_block`. Otherwise a caller
  thread holding `_vtk_lock` waits on a loop that is waiting on the same lock in the RCA window.
- Whether the loop blocks on the lock or retries is Q-1.
The "fact that would change it" above is superseded: marshalling is now the default. S1.0 item 2 decides
whether direct writes are safe.
**v1 — R2 under ruling 13:** the local-edit reason no longer counts. R2 stays rejected on the remaining reason,
that the ordering of `trame.state.topic` and `trame.actions.topic` is unproven.
**v1 — Separate defect:** ruled by ruling 11 (see 5.1).

---

## Section 6 — Per story

### 6.S1 Server

**Exists in the tree [src]:**
- Server `IRenderer` (`renderer/base.py`): abstract `build_renderer_annotation`, `register_node(node, dataset)`,
  `deregister_node`, `deregister_all`, `apply_visibility`, `apply_opacity`, `apply_diffuse_color`,
  `apply_selected(node_id, selected, diffuse_rgb)`, `apply_color_variable(node_id, array_type, array_name,
  component, min, max)`, `clear_color_variable`, `reset_camera(bounds)`, `set_edges_visible`,
  `set_cross_section_visibility`, `set_bounding_box_visibility`, `update_bounds`, `update_actor_count`,
  `pick_geometry(actor_wasm_id, cell_id, mode, world_pos)`, `render`. Concrete: `get_camera_state`,
  `sync_camera` (record, no copy), `set_projection` (in place; no record → no write), `sync_cross_section_plane`,
  `get_cross_section_plane`. Holds `_last_camera_state`, `_last_cross_section_state`. Apply docstrings: "On
  return, the state this renderer serves to the client reflects the write, and the client is not notified."
- No `set_viewport_size` (absent from the list above).
- Implementers (search `(IRenderer)` in `tests` and server `src`): `local_renderer.py:52 VisorLocalRenderer`,
  `null_renderer.py:29 NullRenderer`. Conformance test: `tests/unit/renderer/test_local_renderer.py` L314–323
  asserts `not NullRenderer.__abstractmethods__`.
- `NullRenderer`: annotation `None`; `reset_camera` does not write the record.
- `VisorLocalRenderer`: `set_cross_section_visibility` and `set_bounding_box_visibility` no-ops ("driven
  client-side"); `update_bounds` seeds the plane record if `None`, else writes it back after the widget update.
- `VisorSceneBase` (`vtk/scene/base.py`): one abstract hook `_push_runtime_state`; docstring already names "RCA
  path: push camera onto vtkCamera + render_window_only(); Headless path: no-op". Toggles in
  `_cross_section_enabled`, `_edges_enabled`, `_bounding_box_enabled` (default `False`). `set_part_visibility` also
  updates widget bounds and actor count. Test `tests/unit/vtk/scene/test_base.py` L72 asserts
  `VisorSceneBase.__abstractmethods__ == {...}` exactly.
- `VisorVTK` (`app/visor_vtk.py`): `__new__` `mode_map` (L134–136) only `{LOCAL: VisorVTKLocal}`, else
  `ValueError("Unsupported rendering mode for VTK ...")`; `__init__` → `_file_io`, `_initialize_server`, abstract
  `_initialize_rendering(standalone, trame_log_dir)`. No lifecycle hooks (search `_hook` in
  `src/ansys/visor/viewer`: only `_register_lifecycle_hooks`, `local_app.py:255,259`).
- `VisorVTKLocal._initialize_rendering` builds `VisorLocalScene(server, dark_mode)` and `LocalApp(server,
  scene-details lambda, standalone, trame_logger, pick_geometry lambda, scene_mutation_api=scene)`.
- `LocalApp` (`app/trame/local_app.py`, `@TrameApp()`, `@trigger` + `@parse_payload`): triggers
  `get_visor_scene_details_json`, `pick_geometry`, `perf_report_wasm`, `perf_report_server_update`,
  `set_part_visibility`, `set_part_opacity`, `set_part_diffuse_color`, `set_part_selected`,
  `set_part_color_variable`, `clear_part_color_variable`, `set_variable_range`, `sync_camera` (drops
  `origin != "gesture"`), `set_cross_section_visibility`, `set_edges_visible`, `set_bounding_box_visibility`,
  `set_projection`, `sync_cross_section_plane`, `set_panel_top_left_panel_collapsed`,
  `set_panel_top_right_panel_collapsed`, `set_panel_top_right_legend_collapsed`, `set_panel_top_right_tab_index`.
  Lifecycle via `controller.add` (`on_server_start`, `on_server_ready`, `on_client_connected`, `on_client_exited`,
  `on_server_exited`). `SceneMutationApi` Protocol.
- `LocalApp(` is constructed in 18 places in 7 test files (search `LocalApp(` in `tests`): `test_local_app.py`
  107,118; `test_local_app_set_projection.py` 81,92; `test_local_app_sync_camera.py` 100,111;
  `test_local_app_sync_cross_section_plane.py` 77; `test_local_app_ui_panel_triggers.py` 82;
  `test_local_app_widget_triggers.py` 77,88; `test_visor_trame_app.py` 53,68,80,101,113,131,148,165.
- `TrameServerManager` keeps `_async_runner` private; `start` → `run_coroutine_block(_start_core)` →
  `server.start(thread=async_runner.thread, exec_mode="coroutine")`, waits for `server.ready`. No post-start hook.
- `RendererAnnotation` (server `models/runtime/vtk/renderer_annotation.py`): base field `renderer_kind`
  (`rendererKind`); `WasmRendererAnnotation` kind `"wasm"`, `nodes: dict[str, WasmNodeHandles(actor_id,
  property_id, mapper_id)]`, `widgets: WasmWidgetHandles` (7 ids). Client `renderer/RendererAnnotation.ts`:
  `WasmRendererAnnotation {rendererKind:'wasm', nodes, widgets}`, `RendererAnnotation = WasmRendererAnnotation`;
  `parseRendererAnnotation` → `null` on absence, throws on any other kind; `requireWasmAnnotation` throws on null.
  `rendererKind` in client tests: `SchemaVersion.test.tsx` L73/89, `WasmRendererPartTriggers.test.tsx` L42,
  `WasmRendererWidgetTriggers.test.tsx` L65.

**Spike did [src]; keep / drop [inf, per story text]:**

| Spike | Story keeps / drops |
|---|---|
| `RemoteRenderer`: off-screen `vtkRenderWindow` (`SetOffScreenRendering(1)`, fixed `SetSize(800,600)`), `vtkRenderingOpenGL2`, interactor not initialised (Render only on the loop thread), background from `dark_mode` | keeps off-screen OpenGL2; drops fixed size (S6) |
| `render()` / `render_window_only()` = `rca_app.schedule_render()` (frame rendered by `VtkWindow.img_cols_rows` on the loop thread) | keeps ("renders once per event-loop tick") |
| Own per-part writes (selection as colour, clear resets diffuse) | drops (S1 "per-part applies through VtkNodePipeline"; Section 3) |
| Server widgets: `vtkCameraOrientationWidget`, `vtkOutlineSource` bbox actor, lazy `vtkImplicitPlaneWidget2` (`InteractionEvent` → `schedule_render`); `update_bounds`, `update_actor_count` no-ops | keeps server widgets; drops no-op bounds ("with bounds injected") |
| `get_camera_state` / `apply_camera`; camera to browser via state `rca_camera_state` on a wrong topic | keeps camera methods; transport must change (2.1.8) |
| `RemoteApp`: own trigger names (snake_case, `reset_part_diffuse_color`, `set_part_edge_visibility`, `set_part_scalar_range`, `set_orthographic_mode`, `get_camera_state`, `pick_at_position`) | drops; story: "registers every LocalApp trigger" |
| `_defer_render` coalescing | keeps |
| `setup_rca_stream` (main thread, `RemoteControlledArea(name="view")` before `server.start()`) via `_setup_render_stream_hook` (`theia_vtk_remote.py:98–100`); `wire_rca_stream_async` via `_post_start_hook` → `async_runner.run_coroutine_block(..., False)` (`:102–106`): `create_view_handler(render_window, target_fps=30, interactive_quality=60, still_quality=90)`, push patch, interaction patch, `rca_ready=True`, `schedule_render`, `_register_scene_triggers` | keeps the two-phase wiring as lifecycle hooks |
| `TheiaRemoteScene._apply_runtime_state_to_render` = `apply_camera` + `render_window_only()` | keeps (matches `_push_runtime_state` docstring) |
| `TheiaVTKRemote` holds no VTK lock (`theia_vtk_remote.py:92`) | **cannot determine** whether VISOR's `_vtk_lock` suffices for loop-thread renders; decision in Section 7 |

**v1 —** Rows above superseded or settled:
- Lock row: ruling 4. Every `Render()` holds `_vtk_lock`. In remote, `Render()` runs in trame-rca's
  `img_cols_rows` on the loop thread (7.0), so the lock is taken in a VISOR-owned RCA window (C-2, S1.4).
  Blocking or retry is Q-1.
- "keeps the two-phase wiring as lifecycle hooks": C-8 recommends wiring the stream in `RemoteApp` (constructor
  plus `on_server_ready`) instead of new `VisorVTK` hooks.
- Push and interaction patches: both are replaced by the VISOR window (C-2), not carried.
- Spike trigger names: dropped. The shared trigger base (ruling 5, S1.5) carries VISOR's names, minus the
  local-only ones if C-3 is ruled in.

**wslink StreamManager patch [src]:**
- What it replaces: instance method `StreamManager.push_content` on `view_adapter.streamer`, only when
  `streamer.coreServer is None` (spike `remote_app.py` L134–155). Replacement body: `self.publish(
  "trame.rca.topic.stream", dict(name=area_name, meta=metadata, content=self.addAttachment(content)))`. Comment:
  "wslink no longer sets LinkProtocol.coreServer, so StreamManager.push_content crashes with AttributeError on the
  very first frame, silently killing the _push async task."
- Installed spike trame-rca 2.4.0 `push_content` (`_spike_reference/theia/.venv/Lib/site-packages/trame_rca/
  protocol.py` L106–111) is **the same body** as the replacement; it references neither `coreServer` nor
  `network_monitor`. Search `coreServer` over the spike venv `wslink` and `trame_rca` packages: matches only in
  `wslink/websocket.py` L38 (`self.coreServer = None` in `LinkProtocol.__init__`), L46–47 (`getSharedObject`),
  L185 (`registerLinkProtocol` sets it), L193 (`unregisterLinkProtocol` clears it). Search `network_monitor`: wslink
  only (`protocol.py`, `publish.py` L30/39, `websocket.py` L151); none in `trame_rca`.
- VISOR venv `wslink/protocol.py`: search `coreServer` — no match (same as the spike's `protocol.py`).
- Versions:

  | Package | VISOR venv | VISOR `pyproject.toml` | VISOR `poetry.lock` | Spike `pyproject.toml` | Spike `poetry.lock` | Spike `.venv` |
  |---|---|---|---|---|---|---|
  | wslink | 2.5.7 | ^2.5.0 | 2.5.7 | ^2.5.0 | 2.5.6 | 2.5.7 |
  | trame-rca | not installed | absent | absent | not recorded | no entry | 2.4.0 |
  | trame | 3.12.0 | "3.12.0" | not recorded | not recorded | not recorded | not recorded |
  | trame-server | 3.15.0 | ^3.6.0 | not recorded | not recorded | not recorded | not recorded |
  | trame-client | 3.13.6 | not recorded | not recorded | not recorded | not recorded | not recorded |
  | trame-vtklocal | 1.6.2 | 1.6.2 | not recorded | 0.16.4 | not recorded | not recorded |
  | vtk | 9.7.0 | 9.7.0 | not recorded | 9.6.1 | 9.6.1 | not recorded |

- Consequence [inf]: with trame-rca 2.4.0 the crash the comment describes cannot happen in `push_content`; the
  patch is behaviour-neutral where it applies. The comment most likely refers to an earlier trame-rca. Story rule
  "drop it if its failure no longer reproduces" → drop, confirmed by a manual first-frame check once trame-rca is
  installed in the VISOR venv (Section 7).
- **Silent failures in trame-rca 2.4.0** [src, `protocol.py`]: an unknown area name in `trame.rca.size` or
  `trame.rca.event` only `print`s ("No area ... available for size" L104, "... for event" L119) and drops the call.
  The second spike patch (`_patch_interaction_handler`, comment L157–164: `vtkRemoteInteractionAdapter.ProcessEvent`
  did not recognise the spike canvas's JSON) is a separate patch, kept or dropped under S5.

**Contradictions the tree or sources show:**
- "the camera sent to the browser by its own trigger": trame triggers are client→server (2.1.8); the server push
  must be a state key or js_call [inf].
- "build_renderer_annotation() -> None" vs "TS RendererAnnotation becomes a discriminated union": with `None`
  the client receives no `rendererKind` to discriminate; `parseRendererAnnotation` already returns `null` for
  absence. The mode comes from the S2 probe, not the annotation [inf].
- "set_viewport_size": trame-rca already carries resize (`trame.rca.size` → `RcaViewAdapter.update_size` →
  `window.process_resize_event(w*p*scale, h*p*scale)` → `schedule_render`, spike `trame_rca/utils.py` L327–346).
  If `set_viewport_size` is added to `IRenderer` as abstract, both existing implementers and the conformance test
  must change.
- "VisorVTKRemote overrides the lifecycle hooks": none exist in `VisorVTK`.

**v1 —** Contradictions settled or carried:
- Camera "by its own trigger": ruling 1, a state key (Q-2, S1.7).
- `-> None` vs union: ruling 7, no union. `build_renderer_annotation() -> None` stays.
- `set_viewport_size`: ruling 6, on `RemoteRenderer` only, driven by the trame-rca resize path. `IRenderer`, its
  two implementers and the conformance test are unchanged.
- Lifecycle hooks: still open, C-8.

### 6.S2 Modes, probe, one bundle

**Exists [src]:**
- `RenderingMode` (`core/visor_enums.py` L41–68): only `LOCAL = "local"`; `from_string` case-insensitive by name.
  No REMOTE, no HEADLESS, no stub. **Contradicts** "the backend may already select REMOTE, wired to a stub".
- Enum exposure (search `RenderingMode` in server `src`): CLI `cli/parse_args.py` L48
  `choices=[e.name for e in RenderingMode]`; API `api/models.py` L31–43 (description says "(LOCAL)");
  `api/server.py` L208, L419; `api/visor_cache.py` L20/55/92; `app/visor.py` L40/56; `app/visor_vtk.py`
  L123–151. Adding a member exposes it in CLI and API at once [inf]; a member not in `mode_map` raises `ValueError`
  at construction (loud).
- Tests using `RenderingMode` (search in `tests`): `unit/api/test_visor_cache.py`, `unit/app/test_visor_vtk.py`
  (`MODE_TO_CLASS` L22–24 parametrises dispatch; L79–88 unrecognised-mode test), `unit/cli/test_apis.py`,
  `unit/cli/test_parse_args.py`, `unit/cli/test_visor_cli.py`.
- Local server state: `wasm_ids`, `wasm_ref_name`, `perf_logging` (seeded by `VisorLocalRenderer`, popped by
  `VisorLocalScene.cleanup_state`).
- Bundle: `LocalApp._set_headers` / `_set_www_path` use `settings.get_client_bundle(standalone)` → default bundle or
  `None` (`config.py` L63). The spike `RemoteApp` used the same call. One bundle is already the mechanism [inf].
- `App.tsx` has no mode branch; always `RemoteVtkScene.getInstanceAsync` (L83).
- `TrameInterface.getInstanceAsync(webSocketUrl, refNameStateKey)` requires state `wasm_ref_name` non-empty and
  throws otherwise; it cannot serve a remote probe as is [inf].

**Spike did [src]:** `useRenderingMode` opens a probe `new Trame().connect` to `ws://host:port/ws` (always `ws`,
ignores https), reads `rendering_mode`; keeps the session for `"remote"`, disconnects otherwise; `App.tsx` branches
to `RemoteCanvas` + `UiScaffold key={remoteVersion}` or the local path `key={local.topologyVersion}`.
Story keeps the probe and session reuse; drops the hard-coded `ws` scheme [inf: https deployments would fail].

**Options (probe and local session):**
- O1: probe session reused in remote only; local disconnects it and `RemoteVtkScene` connects as today (spike).
  Local code unchanged beyond the branch.
- O2: probe session reused in both modes; `TrameInterface` accepts an existing session. Edits local-mode code.
- HEADLESS: H1 enum member mapped to nothing (constructing raises `ValueError`; still listed in CLI choices);
  H2 mapped to a `VisorVTK` subclass with `NullRenderer` and no app; H3 member added but filtered from CLI/API
  choices. What HEADLESS means is not stated by any story — needs a ruling.

**v1 — Ruled:**
- HEADLESS is out of this phase (ruling 8). H1–H3 are not pursued.
- The client follows the spike's App structure (ruling 9). `useRenderingMode` probes on the page's scheme;
  `useLocalVtk` and `useRemoteVtk` hold the mode wiring. Ruling 9 spells the hooks `userRenderingMode` and
  `useVtkLocal`; the plan uses `useRenderingMode` and `useLocalVtk` (8.1).
- O1 vs O2: O2 was rejected for editing local code and is reopened under ruling 13 as C-10. O1 is recommended
  for this phase.
- `REMOTE` without a stub: C-9.

### 6.S3 RemoteCanvas, RemoteRenderer

**Exists [src]:**
- Client `IRenderer.ts`: full interface — `send*`, setters with optional argument (toggle when omitted), `apply*`,
  widget getters (Section 2), `dispose`, `addCameraSettledListener`, `addViewerClickedListener(nodeId, ctrl,
  shift, normX, normY)`, `pickGeometryAsync`, `setGeometryHighlightAsync`, `clearGeometryHighlight`.
  `TrameTriggerSender = (name, payload) => Promise<unknown>`.
- Implementers: `NullRenderer.ts` L29 (all no-op test double), `WasmRenderer.ts` L26.
- `new VisorFrontend` sites: `App.tsx` L140, `AppStateProjectionLoad.test.ts` L102, `DeliveredStateApply.test.tsx`
  L123, `UiPanelStateSends.test.tsx` L111, `VariableRecordProjection.test.tsx` L209.
- `EdgesWidget` fans out over `nodeIds` (`SetEdgeColor` black, `EdgeVisibilityOn/Off`) (`widgets/edgesWidget.ts`).

**Spike did [src]:** `RemoteCanvas` subscribes to `trame.rca.topic.stream`, decodes JPEG into a canvas; a
ResizeObserver sends `trame.rca.size [area, "RemoteCanvas", {w, h, p: dpr}]`; mouse and wheel to `trame.rca.event`;
buttons mapped directly (0 left, 1 middle, 2 right), without VISOR's T3 remap; click detection and y flip as 4.2.
`RemoteRenderer.ts` as 2.1.7. Story keeps canvas, frames, events, y flip; drops the spike's trigger names
(`TrameTriggerSender` with VISOR names) and its unconfirmed camera patch.

**Options:** renderer lifetime per rebuild — (a) new `RemoteRenderer` per rebuild, cache re-seeded from scene details
and the camera state key; (b) one `RemoteRenderer` reused across rebuilds (spike). (a) matches `WasmRenderer`
(created per rebuild, `App.tsx` step 3) [inf].

**v1 — Ruled: (a), a new `RemoteRenderer` per rebuild (ruling 10).** This departs from the spike's
`useRemoteVtk`, which reuses one renderer; ruling 10 governs over ruling 9 on this point. Bound to S3.3.

### 6.S4 scene_version

Facts and options: Section 5. Release facts [src]:
- `WasmRenderer.dispose()` → `vtkScene.clearObserversAndEventListeners()` (clears VtkScene camera, click, frame
  listeners; disposes the gesture tracker). Nothing in `src` calls `renderer.dispose()` (search `.dispose()`:
  UiScaffold fpsCounter, tests, `VtkScene.js` L130).
- Registered per frontend and never released: `VisorFrontend.tsx:190` click listener (remover discarded); wasm
  `.observe` in the `WasmRenderer` constructor — planeWidget `InteractionEvent` L63, `EndInteractionEvent` L92,
  orientationWidget `EndInteractionEvent` L111. They accumulate per rebuild [inf]. **Silent** (each fires validly).
- Also registered: `Panel_TopRight.tsx:427` (`visorState.addViewerClickedListener`), `UiScaffold` L59 (frame), L86
  (camera); `VtkScene.#setupHighlightOverlay` camera listener L244; VtkScene `window keydown` never removed (TODO
  L509). Whether UiScaffold/Panel listeners are removed on unmount: **cannot determine** (unmount code not read).
- Released today: only `releaseCameraSettledListener` (`App.tsx:154`).

### 6.S5 Server-side interactor

**Spike did [src]:** `_patch_interaction_handler` replaces `VtkWindow.process_interaction_event` with direct
`iren.InvokeEvent` using an `_EVENT_MAP` (mouse, wheel, key), flat `{x,y}` or nested `{position:{x,y}}`; on
`EndInteractionEvent` → `_push_camera_state` → `state.rca_camera_state = cam.model_dump()`. trame-rca
`RcaViewAdapter.on_interaction` → `window.process_interaction_event(event)` → `schedule_render`. Base
`AreaAdapter.on_interaction` reads keys `t`, `p`, `shift`, `ctrl`, `alt`, `cmd`, `fn` (`protocol.py` L67–82).
Whether trame-rca's unpatched `VtkWindow` accepts that format: **cannot determine** (`vtk_utils.py` not read).
**Tree [src]:** `LocalApp.sync_camera` drops `origin != "gesture"`; `CameraSyncReporter` (attached at
`VisorFrontend.tsx:99`) sends gesture syncs from the client camera.
**Options:** CameraSyncReporter in remote — (a) `RemoteRenderer.addCameraSettledListener` never fires (reporter stays
attached, inert); (b) VisorFrontend skips attaching in remote; (c) it fires on server camera pushes (sends back
what the server already has: loop). Camera record update in remote — server writes `_last_camera_state` at
interaction end, then pushes the state key.

**v1 — Ruled through ruling 9: (b) in effect.** `CameraSyncReporter` is attached by `useLocalVtk` only
(S2c.1); `useRemoteVtk` never attaches it. (a), the inert reporter, is dropped. Whether
`addCameraSettledListener` then leaves client `IRenderer` is C-7. The camera record at gesture end is written by
the VISOR RCA window (C-2, S5).

### 6.S6 Resize

**Spike [src]:** fixed 800x600; resize only through trame-rca `trame.rca.size` (6.S1); spike client
`viewPortHeight` never updated. **Tree [src]:** no `set_viewport_size`; client `viewPortHeight` from wasm.
**Options:** (a) trame-rca resize path calls `RemoteRenderer.set_viewport_size` (one owner of window size);
(b) separate VISOR trigger `set_viewport_size` from `RemoteCanvas`; two paths to one window size.

**v1 — Ruled: (a) (ruling 6).** Path: `trame.rca.size` → `RcaViewAdapter.update_size` →
`VisorRcaWindow.process_resize_event` → `RemoteRenderer.set_viewport_size` (C-2, S1.4, S6).

### 6.F VisorFrontend responsibilities — which move out under these stories

| Responsibility | Location [src] | Under REMOTE |
|---|---|---|
| Exposes `getCameraStateAsync` | L86 | stays; served by RemoteRenderer cache (2.3) |
| Attaches `CameraSyncReporter` | L99–106 | **v1:** moves out of `VisorFrontend` into `useLocalVtk` (ruling 9, S2c.1); `useRemoteVtk` never attaches it |
| Geometry-pick listener on `renderer.addViewerClickedListener` | L190 | stays (mode-independent); `RemoteRenderer.pickGeometryAsync` throws a named error (ruling 3), surfaced per C-5; **v1:** remover kept and released by `release()` (C-4) |
| Maps click nodeId → scene node for `Panel_TopRight.tsx:427` | `addViewerClickedListener` | stays |
| `getAppStateAsync`: four toggles + camera | L288–292 | stays |
| `setAppStateAsync`: toggles via `apply*`, camera via `setCamera*Async`, projection via `applyOrthographicModeAsync`, parts (diffuse→selected sequenced, others parallel) | L471–491 | stays |
| `releaseCameraSettledListener` | L100 | **v1:** replaced by `VisorFrontend.release()` for what the frontend itself registers (C-4); the camera-sync remover is held by `useLocalVtk` (ruling 9) |
| Rebuild trigger (wasm `update` callback) | `App.tsx onServerUpdateAsync` (not VisorFrontend) | **v1:** local, moved unchanged into `useLocalVtk` (S2c.0); remote, `scene_version` watch with latest-wins in `useRemoteVtk` (ruling 9, S4.2); shared build sequence per C-6 |

---

## Section 7 — Phase outline (rulings 1–13 applied)

Sections 1–6 are carried from v0 unchanged except for the header. Section 7 is rewritten. Section 8 is carried
verbatim. Each increment below names the rulings it applies. Where an increment would add a duplicate, an inert
stand-in or a mode check, it says so and proposes where that belongs (ruling 12).
Items marked **C-n** are cleanup candidates waiting for a ruling (ruling 13). Items marked **Q-n** are questions
the rulings leave open. Both are collected in 7.2.

### 7.0 Reads behind v1 (this pass)

Tree for this pass: commit "add rulings" on `feat/4.0-plan`. Sections 1–6 were read at commit "remove unused client
renderer members" on `chore/renderer-interface-cleanup`. Between the two (`git diff --stat`), the code changes are
the VTKHDF long-array normalizer (`vtk/io/client_dataset_normalizer.py`, `vtk/io/file_to_dataset.py`, their tests)
and changes to `VisorSceneGraph.tsx` / `VisorSceneState.tsx` [src]. I read the diffs of the last two: they are
whitespace only. None of the changed files is cited in Sections 1–6 [src, file list].
Searches are literal, run with `git grep -n -F` unless stated otherwise.

**Server, locking and Render() [src]:**
- `_vtk_lock` (server viewer): created as `threading.RLock()` in `VisorSceneBase.__init__`. `VisorSceneBase.render`
  holds it around `self._renderer.render()`. The comment block above the pipeline camera helpers in
  `local_renderer.py` states the convention: the caller holds the lock and the renderer takes none.
- `.Render()` (server viewer): two matches, `VisorLocalRenderer.render` and `VisorLocalRenderer.render_window_only`.
- `render_window_only(`: the definition, the docstrings in `vtk/scene/base.py` (`_push_runtime_state`), and one
  call in `VisorLocalScene._push_runtime_state` (`local_scene.py`).
- `_renderer.render(`: one match, inside `VisorSceneBase.render`, under the lock.
- Consequence [inf]: in local mode every `Render()` that VISOR issues is under `_vtk_lock`, provided every caller of
  `_push_runtime_state` holds the lock. Only `apply_state` was read as a caller (Section 5.2). The full caller list
  was not searched → carried to S1.0.
- `AsyncRunner` (`app/trame/async_runner.py`) offers `run_coroutine_block` (blocks), `run_coroutine` (returns a
  `concurrent.futures.Future` without blocking) and `run_coroutine_async`. `TrameServerManager` holds the runner
  as `_async_runner` and exposes a `state` property.

**trame-rca 2.4.0, read in the spike venv (not installed in VISOR's) [src]:**
- `vtk_utils.VtkWindow.img_cols_rows` calls `self._vtk_render_window.Render()`. `utils.RcaRenderScheduler._render` is
  a coroutine that calls `self._window.img_cols_rows` synchronously. **Render() runs on the event-loop thread.**
- `protocol.AbstractWindow` is a `runtime_checkable` Protocol with `img_cols_rows`, `process_resize_event(width,
  height)` and `process_interaction_event(event)`. Its docstring says: "Any class matching this interface can be
  used as a remote window". `RcaViewAdapter.__init__(window: AbstractWindow | vtkRenderWindow, name, ...)` wraps
  the window through `window_wrapper`.
- `RcaViewAdapter.update_size` clamps to a 10 px minimum and scales by `p` (pixel ratio) and `scale`. If
  `max_pixel_count` is set, it caps the size. It then calls `self._window.process_resize_event(width, height)` and
  `schedule_render()`.
- `RcaViewAdapter.on_interaction` drops releases that had no press, then calls
  `self._window.process_interaction_event(event)` and `schedule_render()`.
- `VtkWindow.process_interaction_event` returns early on `StartInteractionEvent` / `EndInteractionEvent` and
  otherwise calls `vtkRemoteInteractionAdapter.ProcessEvent(iren, json.dumps(event))`.
- `RcaRenderScheduler.schedule_render` = `asynchronous.create_task(self.async_schedule_render())`.
- `RemoteControlledArea.add_view_handler` registers the handler at once if the server is running. Otherwise it
  queues the handler, and `_on_ready` drains the queue (`widgets/rca.py`).

**trame class decorator [src, `trame_common/decorators/klass.py`]:**
- `TrameApp.__call__` wraps `klass.__init__`. The wrapper scans `inspect.getmembers(instance.__class__, ...)`, so
  `@trigger`, `@change` and `@controller` methods inherited from a base are registered.
- If both a base and its subclass carry `@TrameApp()`, the subclass wrapper calls the base wrapper. Every
  decorated method is then registered twice [inf from `wrapped_init` calling `self.klass_init`].

**Server renderer shape [src, `renderer/local_renderer.py`]:**
- Every `apply_*` has the same shape: `self._pipelines.get(node_id)`; `None` → debug log and return; then
  `pipe.set_*(...)`; then `_serialize_vtk_object(...)` or `_serialize_part_state(node_id)`.
- `register_node`: `VtkNodePipeline.from_dataset`, `set_clipping_plane(cross-section plane)`,
  `mapper.SetScalarVisibility(False)`, `AddActor`.
- `reset_camera`, `sync_camera` and `set_projection` each end in `_serialize_camera_state`.
- The three widgets are constructed without the `LocalView`. Registration is a separate call,
  `register_with_local_view(self._local_view)`, in each `_initialize_*_widget`.
- `_initialize_render_window` creates no off-screen setting (`ShowWindowOff`, `SetMultiSamples(0)`). No test in
  `tests/` calls `Render()` (searches `Render()` and `SetOffScreenRendering`: no match in `tests`).
- `pick_geometry` (search `def pick_geometry`): `renderer/base.py` (abstract), `local_renderer.py`,
  `null_renderer.py`, `VisorSceneBase.pick_geometry`, and the `LocalApp.pick_geometry` trigger.
  `update_actor_count`: `base.py`, `local_renderer.py`, `null_renderer.py`. What the local implementation does was
  not read → S1.0.
- Wasm-path triggers on `LocalApp`: `perf_report_wasm` and `perf_report_server_update` (search `def perf_report`).
- `test_local_renderer.py` patches `"ansys.visor.viewer.renderer.local_renderer.VtkNodePipeline.from_dataset"` at
  seven sites (search `VtkNodePipeline`). The patch target is a module path.

**Client [src, searches run from `src/ansys/visor/visor-client`]:**
- `attachCameraSyncReporter`: one production call, in the `VisorFrontend` constructor
  (`this.#cameraSettledRemover = attachCameraSyncReporter(renderer, triggerSender)`). The other matches are in
  `CameraSyncReporter.test.ts`.
- `releaseCameraSettledListener`: defined in `VisorFrontend` and called once, in `App.onServerUpdateAsync`. The
  comment there requires that no `await` separates the new frontend's subscription (in its constructor) from the
  old frontend's release.
- The `VisorFrontend` constructor registers `renderer.addViewerClickedListener(...)` and discards the remover. In
  non-part modes the listener calls `this.pickGeometryAsync(normX, normY).catch(() => {})`.
- `VisorFrontend.setSelectionMode` calls `renderer.clearGeometryHighlight()` unconditionally.
- `App.tsx` already builds `ws`/`wss` and `http`/`https` from `window.location.protocol`.
- Spike `App.tsx`: `useRenderingMode(host, port)` → `{mode, session}`. `useRemoteVtk(session, darkMode)` and
  `useLocalVtk(host, port, darkMode, active)` are both called unconditionally, and each returns `null` when
  inactive. The render branches on `remoteSession != null`.
- The spike's `useLocalVtk` adds features the tree does not have: a data-only fast path, generation stamping, a
  dirty map and replay. Ruling 9 asks for today's wiring to be moved unchanged, so the spike hook is a shape
  reference only.

### 7.1 Rulings checked against the tree and the stories

| Ruling | Tree | Story text | Note |
|---|---|---|---|
| 1 (Q1 = A) | consistent | consistent | `viewPortHeight` must be in render-window pixels, as wasm reads it (`renderWindow.GetSize` × viewport, 2.1.1). See S6. |
| 2 (per-part contract) | consistent: local apply = lookup + `VtkNodePipeline` + serialize (7.0) | consistent | Makes candidate C-1 natural. |
| 3 (P1; geometry pick throws a named error) | **conflicts**: the click listener in `VisorFrontend` ends with `.catch(() => {})`, so the named error is swallowed and nothing is reported. `setSelectionMode` calls `clearGeometryHighlight()` on every mode change, so that method cannot be the one that throws. | none | Without a change the throw is **silent**. Resolution: C-5. |
| 4 (R1; bump on the loop thread; every Render() holds `_vtk_lock`) | local: consistent (7.0, with one caller list carried). Remote: `Render()` is called by trame-rca's `VtkWindow`, which VISOR does not own. The ruling can be met only by VISOR supplying its own `AbstractWindow` (C-2). | none | **Tension inside the ruling.** (a) If the loop thread blocks on `_vtk_lock` while a caller thread holds it (`add_dataset`, `apply_state`), all websocket I/O stops for that time. (b) If the bump is marshalled with `run_coroutine_block` from inside a locked region while the loop waits on the lock in `img_cols_rows`, the two threads deadlock. The bump must use the non-blocking `run_coroutine` (Q-1). |
| 5 (shared trigger base; `LocalApp` constructor unchanged) | consistent: inherited `@trigger`s register (7.0) | S1: "RemoteApp registers every LocalApp trigger" — see C-3 | Constraint: exactly one class in the chain carries `@TrameApp()`, or every trigger registers twice. |
| 6 (`set_viewport_size` on RemoteRenderer, via the trame-rca resize path) | consistent: `update_size` calls `window.process_resize_event` (7.0) | S1 lists `set_viewport_size` without saying where it lives — consistent | Needs C-2's window to reach the renderer. |
| 7 (no annotation union) | consistent: `requireWasmAnnotation` is called only on the local path (`App.onServerUpdateAsync`) | **conflicts** with S1: "TS RendererAnnotation becomes a discriminated union." | The ruling overrides the story. `build_renderer_annotation() -> None` in remote stays as S1 states. |
| 8 (HEADLESS out) | consistent: no HEADLESS member exists | **conflicts** with S2: "REMOTE and HEADLESS in RenderingMode" | The ruling overrides the story. |
| 9 (spike App structure; hooks hold mode wiring; VisorFrontend mode-independent) | **conflicts**: `CameraSyncReporter` is attached inside the `VisorFrontend` constructor and released through a `VisorFrontend` member. Moving it out is a local code edit, allowed by ruling 13, and must keep the no-`await` invariant (7.0). The "page's ws/wss" part is already true in `App.tsx`. | S2: "App.tsx probes rendering_mode and is the only mode branch" — the hooks hold the wiring and App branches only on render | The probe is new. `TrameInterface.getInstanceAsync` cannot serve as the probe (6.S2). |
| 10 (new RemoteRenderer per rebuild) | consistent: `WasmRenderer` is created per rebuild | none | **Tension with 9**: the spike's `useRemoteVtk` reuses one renderer (`rendererRef`). Ruling 10 governs. |
| 11 (local drop-during-rebuild recorded, not fixed) | consistent | none | Constraint: the remote latest-wins rebuild must not be shared with local in this phase. Sharing it would change local behaviour (C-6). |
| 12 | applied per increment below | — | — |
| 13 | applied; candidates in 7.2 | — | — |

### 7.2 Cleanup candidates and open questions (for ruling)

Each candidate states what changes in local-mode code, the test net, the alternative it replaces, and what it
removes (a duplicate, an inert stand-in or a mode check).

- **C-1 Shared server base for VTK-pipeline renderers.** Today only `VisorLocalRenderer` owns `_pipelines`, the
  lookup-then-delegate `apply_*`, `register_node`, the camera writes, and the window/interactor/widget setup.
  Proposal: a base class owns all of these and calls one of three post-write methods. Local implements them as
  today's serialize calls; remote implements them as a frame request. Signatures (proposal):
  - `class VtkPipelineRenderer(IRenderer)` — "Owns the VTK renderer, window, widgets and per-node pipelines; applies part state through VtkNodePipeline."
  - `def _publish_object(self, vtk_object: vtkObject) -> None` — "Make one written VTK object visible to the client."
  - `def _publish_part_mapper(self, node_id: int) -> None` — "Make one part's written mapper visible to the client."
  - `def _publish_camera(self) -> None` — "Make the written pipeline camera visible to the client."
  Effect: "remote differs from local only after the write" (S1 acceptance) holds by construction, and nothing
  per part is duplicated. Local impact: methods move to the base; the serialize helpers become the three
  overrides. Tests that break: the seven `VtkNodePipeline.from_dataset` patches in `test_local_renderer.py`,
  because their module-path target moves with `register_node`. They are re-pointed, not rewritten. The
  conformance test (`not NullRenderer.__abstractmethods__`) is unaffected unless `NullRenderer` inherits the base.
  Alternative: `RemoteRenderer` copies the lookup-then-delegate bodies. That duplicates every `apply_*` (ruling 12)
  and leaves parity resting on a test alone. Recommendation: adopt. Binds S1.2.
- **C-2 VISOR-owned RCA window (`AbstractWindow`).** Proposal: a VISOR class implements the trame-rca Protocol.
  `img_cols_rows` takes `_vtk_lock` around `Render()` and the image read. `process_resize_event` calls
  `RemoteRenderer.set_viewport_size`. `process_interaction_event` dispatches to the interactor and handles
  `EndInteractionEvent`, which trame-rca's `VtkWindow` drops (7.0).
  This one class replaces both spike monkey-patches: the stream push patch, which is already behaviour-neutral
  (6.S1), and `_patch_interaction_handler`. It is also the only place where ruling 4 can hold for remote renders.
  Local impact: none. Alternative: subclass or patch trame-rca's `VtkWindow`, which keeps a dependency on its
  private members. Recommendation: adopt. Binds S1.4 and S5.
- **C-3 Local-only server members stay local.** `pick_geometry` (keyed on wasm actor ids) is on server
  `IRenderer`, and the `pick_geometry`, `perf_report_wasm` and `perf_report_server_update` triggers are on
  `LocalApp`. Proposal: move `pick_geometry` off `IRenderer` onto `VisorLocalRenderer`; this follows the tree's
  earlier commit "move local-only members off server IRenderer". Keep the three triggers on `LocalApp` and out of
  the shared trigger base.
  This conflicts with S1's "RemoteApp registers every LocalApp trigger"; the ruling has to say which wins.
  Alternative: register them in remote and have `RemoteRenderer.pick_geometry` raise. That is an inert stand-in,
  and the client never calls it in remote (ruling 3).
  Local impact: `VisorSceneBase.pick_geometry` must reach the method on the local renderer type. Who calls it and
  how was not read → S1.0.
  Whether `update_actor_count` belongs in the same group: **cannot determine** (body not read) → S1.0.
  Binds S1.2 and S1.5.
- **C-4 One release for everything a frontend registered.** Today `VisorFrontend` holds only the camera-settled
  remover and discards the geometry-click remover. Proposal: `VisorFrontend.release()` — "Remove every listener
  this frontend registered on its renderer." It is mode-independent, and both hooks call it on rebuild. Under
  ruling 9 the camera-sync remover moves to the local hook (S2c.1), so `release()` covers the click listener plus
  whatever S4 finds. Local impact: the click listener is released on rebuild. That is a behaviour change only in
  that stale listeners stop firing. Each stale one ran `pickGeometryAsync` against a renderer already replaced
  [inf] → **needs a ruling under 13**. Alternative: keep accumulating listeners locally and release only in
  remote, which is a mode check. Binds S2c.1 and S4.3.
- **C-5 Surfacing the named geometry-pick error (ruling 3 conflict).** Options:
  (a) `VisorFrontend` logs the caught error instead of swallowing it. This is mode-independent; the only local
  change is console output when a wasm pick fails.
  (b) `useRemoteVtk` offers only part mode in the selection-mode UI. That is a mode check in UI code. Where the
  selection-mode UI lives was not searched → **cannot determine**.
  (c) Accept that it is swallowed. That contradicts the purpose of ruling 3.
  Recommendation: (a). Under 13 it needs a ruling because it changes local console output.
  `RemoteRenderer.clearGeometryHighlight` is a true no-op in remote, because no highlight exists. It is not a
  stand-in. Binds S3.4.
- **C-6 Shared client frontend build.** Today `App.onServerUpdateAsync` does, in order: fetch scene details;
  parse with the `SchemaVersionMismatchError` branch; build the renderer; build `VisorFrontend`; release the old
  frontend; apply the dark-mode override; `setAppStateAsync(..., false)`; set `__visorState`;
  `setVisorFrontend`. Everything except the renderer construction and the trigger transport is the same in remote.
  Proposal: one function, `buildFrontendAsync(sceneDetailsJson, createRenderer, triggerSender, darkMode)`, which
  the local and remote hooks both call. Without it, `useRemoteVtk` duplicates the sequence (ruling 12).
  The latest-wins runner stays remote-only (ruling 11). Local impact: S2c.0 moves the code and S2c.2 extracts the
  function; existing tests are the net. Binds S2c.2.
- **C-7 `addCameraSettledListener` leaves client `IRenderer`.** After S2c.1 only `useLocalVtk` attaches the
  `CameraSyncReporter`, so `RemoteRenderer.addCameraSettledListener` would be an inert stand-in. Proposal: move
  `addCameraSettledListener` to `WasmRenderer` and type `CameraSyncSource` against `WasmRenderer`. The same
  question applies to `setGeometryHighlightAsync`, which has a local caller only.
  Tests: four modules list `addCameraSettledListener` in a renderer double (`AppStateProjectionLoad.test.ts`,
  `DeliveredStateApply.test.tsx`, `UiPanelStateSends.test.tsx`, `VariableRecordProjection.test.tsx`). Whether those
  doubles are typed object literals, which would turn the extra key into an excess-property error: **cannot
  determine** → read in S3.3. Alternative: keep the method on the interface and let remote return a no-op remover.
  Binds S3.3.
- **C-8 Where the remote stream is wired.** S1 says "VisorVTKRemote overrides the lifecycle hooks", but `VisorVTK`
  has none (6.S1). Option (a): add abstract hooks to `VisorVTK`; `VisorVTKLocal` then implements each one as an
  explicit no-op, which is an inert stand-in. Option (b): wire the stream in `RemoteApp`. Create the
  `RemoteControlledArea` in its constructor, which runs before `server.start()` (`_initialize_rendering` is called
  from `VisorVTK.__init__`, 6.S1). Create the view handler in an `on_server_ready` handler, which runs on the loop
  thread; trame-rca's `add_view_handler` also queues until ready (7.0).
  Recommendation: (b). It adds no local stand-in and needs no public accessor for `_async_runner`. Binds S1.6.
- **C-9 Fold the S2-server stub into S1.6.** v0 put `REMOTE` in the enum first, mapped to a stub that raises
  `NotImplementedError`. The CLI and API would list `remote` while it can only raise (an inert stand-in visible to
  users). Proposal: add `REMOTE` in the same PR that adds `VisorVTKRemote` (S1.6). Alternative: v0's stub-first
  order. Binds S1.6.
- **C-10 Probe session reused in local (O2, reopened under 13).** For this phase the plan uses O1: local
  disconnects the probe and `RemoteVtkScene` connects as today. O2 would make `TrameInterface` accept an existing
  session, which saves one connection per page load but changes the local connection lifecycle. Recommendation:
  O1 now, O2 as a later candidate. Binds S2c.3.
- **C-11 One mouse-button mapping for both modes.** The wasm path remaps buttons (session trap T3). The spike's
  `RemoteCanvas` did not. For local-parity gestures (middle drag rotates, chord pans), `RemoteCanvas` needs the same
  mapping. Proposal: extract the mapping into one shared function used by both paths. Where the mapping lives
  today was not searched → **cannot determine** → read in S3.2. Alternative: copy it into `RemoteCanvas` (a
  duplicate). Binds S3.2.
- **C-12 `rendering_mode` is set by both apps.** The probe reads `rendering_mode`. Proposal: the shared trigger
  base requires each app to declare its mode and seeds the state key. `LocalApp` then publishes `"local"`, which
  adds one state key and changes no behaviour. Alternative: treat a missing key as local. That is a mode check by
  absence: a remote server that failed to set the key would load wasm and fail later, at `wasm_ref_name`.
  Binds S1.5.

**Open questions:**
- **Q-1 (ruling 4).** Must `img_cols_rows` block on `_vtk_lock`, or try to acquire it and re-schedule the frame when
  it is held? Blocking stalls the loop for the length of any locked operation (7.1). Try-and-reschedule never
  stalls the loop, but a long operation delays the frame. In both cases the bump uses non-blocking `run_coroutine`.
  Recommendation: try-and-reschedule. Binds S1.4 and S4.1.
- **Q-2.** The name of the camera state key. Proposal: `remote_camera_state`, carrying the seven record fields in
  camelCase (the `VisorCameraState` aliases). Binds S1.7 and S3.3.
- **Q-3.** The name of the P1 pick trigger. Proposal: `pick_part_at`, payload `{x, y}` in render-window pixels with
  y flipped, returns `nodeId` or `null`. Binds S1.5 and S3.4.

### 7.3 Story order and dependencies

1. **S1 stack** (7.4). S1.0 comes first. S1.6 adds `REMOTE` (C-9; if C-9 is rejected, an S2-server stub PR goes
   before S1.1).
2. **S2c.0 `useLocalVtk` move**, the first client increment. It touches only local code, so it may land any time
   in parallel with S1.
3. **S2c.1–S2c.2** (camera-sync move, shared build). These need S2c.0.
4. **S2c.3 + S3.1** (probe, branch, `RemoteCanvas` frames). These need S1.6 (`rendering_mode`, frames) and S2c.2.
   They land together so that the remote branch never renders an empty stand-in.
5. **S3.2–S3.4** (events, `RemoteRenderer.ts`, picking). These need S1.5 and S1.7.
6. **S6** (resize). Needs S3.1 and S1.4.
7. **S5** (interactor, camera push at gesture end). Needs S3.3, S6 and S1.4.
8. **S4** (`scene_version`, release). Needs S3.3 and S1.6.

### 7.4 S1 — server, as a PR stack

The stack applies to every PR: rulings 2, 4, 5, 6, 7 and 13. Each PR leaves all four gates runnable.

**How RemoteRenderer is tested without a GPU.**
- VTK property, mapper, camera and widget writes need no OpenGL context. The context is created only on
  `Render()` or window initialisation [inf; supported by `test_local_renderer.py`, which builds real pipelines and
  a `vtkRenderWindowInteractor` and never renders, 7.0].
- Unit tests of `RemoteRenderer` therefore construct it and call every `apply_*`, camera method and
  `set_viewport_size`, and assert on VTK object state. They never call `Render()`. Expected values are hand-written
  literals (session rule 10).
- The post-write step is a required injected frame requester (no default; planning rule). The tests pass a
  recording double and assert that it was called.
- The C-2 window takes the lock and the render step by injection, so a test can hold `_vtk_lock` on a second
  thread and assert that `img_cols_rows` does not render while the lock is held. That test uses a recording
  stand-in for `Render()`, not a GL render.
- Anything that produces a real frame (pixels, selection tint, first frame) gets a new pytest marker, proposed as
  `gpu`. It is excluded from the gate commands and covered by the manual checks below.
- Whether off-screen OpenGL2 can run on CI or on a Windows host without a GPU is carried to S1.0. Rejected
  alternatives: OSMesa/EGL VTK wheels (they change the VTK dependency) and xvfb (Linux only).

**S1.0 — Read (no code).** It resolves the "cannot determine" items S1 rests on and writes the findings as a log
entry. Each item names the source to read and what changes if the answer is no.
1. **Threads.** The thread each `VisorVTK` operation runs on (start, update, add/remove dataset, clear,
   update_variables, load_state) and the thread trigger handlers run on. Read the `trame_server` `trigger` RPC path
   and `TrameServerManager._start_core`.
2. **State writes.** Is a `server.state[...]` write plus flush from a non-loop thread delivered to the client, and
   in which order relative to `js_call`? Read `trame_server/state.py` and the `push_state_change` path. If not
   delivered: every state write in S1.6, S1.7 and S4.1 goes through `run_coroutine`.
3. **Where Render() runs.** Repeat the 7.0 trame-rca read against the version installed in VISOR's venv after
   S1.1. Find every caller of `_push_runtime_state` and every path to `VisorSceneBase.render`, and confirm that
   each one holds `_vtk_lock`.
4. **`asynchronous.create_task` from a non-loop thread** (`trame_server/utils/asynchronous.py`). This decides
   whether `RemoteRenderer`'s frame requester may call trame-rca's `schedule_render` directly or must marshal.
5. **Interaction event format.** Read `vtkRemoteInteractionAdapter.ProcessEvent` and the format `RemoteCanvas` will
   send. This decides C-2's `process_interaction_event`.
6. **Encode buffer lifetime.** Does `RcaRenderScheduler` encode, on a pool thread, a numpy view that the next
   `Render()` overwrites?
7. **Off-screen OpenGL2** on the developer host and on CI.
8. **Local-only members.** The `update_actor_count` body, and the callers of `VisorSceneBase.pick_geometry` (C-3).

- Model: the strongest reasoning model, because the answers reorder the stack. No gates (no code).
- Closes: none. Must not share a session with code PRs (session rule 7).

**S1.1 — trame-rca dependency.**
- Intent: add `trame-rca` to `pyproject.toml` and `poetry.lock`, pinned to the version S1.0 read.
- Files: `pyproject.toml`, `poetry.lock`.
- Ruling 12: nothing added.
- Tests: none break (no import yet).
- Manual check (belongs to S1.6, whose subject is the stream): first frame with no push-content patch (6.S1).
- May share a session with S1.2 (both are small and have independent subjects).

**S1.2 — Shared pipeline-renderer base (C-1, C-3; local, behaviour-preserving).**
- Built only if C-1 is ruled in. Moves `VisorLocalRenderer`'s pipeline, widget, camera-write and `apply_*` bodies
  into `VtkPipelineRenderer`. The local overrides of `_publish_*` are today's serialize calls. If C-3 is ruled in,
  `pick_geometry` moves off `IRenderer`.
- Files: `renderer/base.py` (or a new `renderer/pipeline_renderer.py`), `renderer/local_renderer.py`,
  `renderer/null_renderer.py` (C-3), `vtk/scene/base.py` (C-3, `pick_geometry` call), and
  `tests/unit/renderer/test_local_renderer.py` (seven patch targets re-pointed).
- Tests that break: the seven patches above (target path). Under C-3, any test that calls
  `NullRenderer.pick_geometry` (search in the prompt).
- Pin: none; this is a behaviour-preserving move and the existing suite is the net.
- Ruling 12: removes a duplicate before it exists.
- Model: a strong coding model (provenance tracing). Must not share a session with S1.3: S1.3 depends on the
  base's final signatures.

**S1.3 — `RemoteRenderer(IRenderer)`.**
- Off-screen `vtkRenderWindow` with OpenGL2. No fixed size: the initial size comes from the first
  `set_viewport_size`; until then, the 300×300 that trame-rca uses as its default image size (`image_size`)
  [src 7.0].
- Background from `dark_mode`.
- Per-part applies through `VtkNodePipeline` (via S1.2, or directly if C-1 is rejected). `_publish_*` overrides
  each call the injected frame requester.
- Widgets: `VisorOrientationWidget`, `VisorCrossSectionWidget` and `VisorBoundingBox`, constructed as local does,
  without `register_with_local_view`. `set_cross_section_visibility` and `set_bounding_box_visibility` act on the
  widgets (local leaves them as no-ops). `update_bounds` and `update_actor_count` act as local does.
- Camera methods as on `IRenderer`.
- `set_viewport_size(width, height)` — "Resize the off-screen render window to the client canvas in device
  pixels." Remote only (ruling 6).
- `build_renderer_annotation() -> None`.
- The 3.2 contract is written as the docstring on server `IRenderer`, and in the same PR on client `IRenderer.ts`
  (ruling 2: both stacks; doc-only on the client).
- Signatures (proposal):
  - `RemoteRenderer.__init__(self, dark_mode: bool, request_frame: Callable[[], None])` — "Build the off-screen
    pipeline; request_frame is called after every write."
  - `RemoteRenderer.render_window -> vtkRenderWindow` — "The window the RCA view streams."
  - `RemoteRenderer.set_viewport_size(width: int, height: int) -> None`
- Files: `renderer/remote_renderer.py` (new), `renderer/base.py` (docstrings),
  `visor-client/src/renderer/IRenderer.ts` (docstrings), `tests/unit/renderer/test_remote_renderer.py` (new),
  `tests/unit/renderer/test_per_part_parity.py` (new; see acceptance).
- Ruling 12: if C-3 is rejected, `pick_geometry` raises a named error here (an inert stand-in). The proposed home
  is C-3.
- `request_frame` has no default, so a renderer built without one fails at construction.
- Pin: the `apply_selected` test asserting `AmbientColor (0, 62/255, 111/255)` and `DiffuseColor` equal to the
  given rgb on a `RemoteRenderer`. Reverting the delegation (the spike's colour replacement) fails it.
- Model: a strong coding model.

**S1.4 — VISOR RCA window (C-2; Q-1).**
- Implements `AbstractWindow`:
  - `img_cols_rows`: under `_vtk_lock`, per Q-1. Render, then read the image.
  - `process_resize_event` → `RemoteRenderer.set_viewport_size`.
  - `process_interaction_event`: in this PR it forwards to the interactor exactly as trame-rca's `VtkWindow` does;
    S5 completes it.
- Takes the lock, the renderer and the render window by required injection.
- Signatures (proposal):
  - `class VisorRcaWindow` — "trame-rca window over a RemoteRenderer; renders under the scene lock."
  - `__init__(self, renderer: RemoteRenderer, vtk_lock: threading.RLock)`
  - `img_cols_rows -> tuple[NDArray, int, int]`
  - `process_resize_event(width: int, height: int) -> None`
  - `process_interaction_event(event: dict) -> None`
- Files: `renderer/remote_window.py` (new) and its test.
- Ruling 12: this removes the spike's two monkey-patches; nothing inert is added.
- Pin: the test that holds `_vtk_lock` on a second thread and asserts no render happens.
  **Silent failure if wrong:** a render racing a dataset load on another thread. No gate catches that today.
- Must not share a session with S1.3: they have different subjects, and this one has a lock test.

**S1.5 — Shared trigger base (ruling 5; C-3, C-12, Q-3).**
- Extracts the per-part, widget, camera, panel and scene-details triggers from `LocalApp` into a base class.
  `LocalApp`'s constructor signature and its 18 test constructions stay unchanged. Exactly one class in each chain
  carries `@TrameApp()` (7.0).
- `LocalApp` keeps `pick_geometry`, `perf_report_wasm` and `perf_report_server_update` (C-3).
- The base seeds `rendering_mode` from a required abstract property (C-12).
- `RemoteApp` adds `pick_part_at` (Q-3; P1, no server-side selection).
- `sync_camera` keeps dropping `origin != "gesture"`. No remote client sends it (S5).
- Files: `app/trame/local_app.py`, `app/trame/` (new base module, `remote_app.py`), and tests for the base and
  for `pick_part_at`. The `LocalApp` test modules listed in 6.S1 must pass unchanged.
- Pin: a test that the set of triggers registered by `LocalApp` equals a hand-written list of today's names. A
  missing `@TrameApp()` or a doubled one fails it.
- Ruling 12: the `sync_camera` origin check is a gesture/programmatic check, not a mode check; it stays.
- Model: a strong coding model.

**S1.6 — `VisorRemoteScene`, `VisorVTKRemote`, `RemoteApp` stream wiring, `REMOTE` (C-8, C-9).**
- `RenderingMode.REMOTE`, plus a `mode_map` entry.
- `VisorVTKRemote._initialize_rendering` builds `VisorRemoteScene` (a `RemoteRenderer` whose `request_frame` is
  coalesced once per loop tick) and `RemoteApp`.
- `RemoteApp`: `RemoteControlledArea` in the constructor; the view handler over `VisorRcaWindow` in
  `on_server_ready`; `rendering_mode="remote"`.
- `VisorRemoteScene._push_runtime_state` writes the camera onto the `vtkCamera` and requests a frame, as the
  `VisorSceneBase` docstring already names.
- No push-content patch.
- Tests that break: `tests/unit/app/test_visor_vtk.py` `MODE_TO_CLASS` is extended; the unrecognised-mode test
  stays. `tests/unit/cli/test_parse_args.py` and `test_apis.py` if they enumerate the choices (search in the
  prompt). `test_base.py`'s abstract-set assertion is unchanged, because no scene hook is added.
- Ruling 12: frame coalescing lives in `RemoteApp`, as one owner.
- Model: a strong coding model.
- Manual check:
  - Procedure: start with `--rendering-mode remote` (the exact CLI spelling is taken from `parse_args.py` in the
    prompt), open the page, and watch the websocket in the browser network panel.
  - Pass: binary messages on `trame.rca.topic.stream` within 5 s.
  - Fail: no stream messages and no server error. That is the spike comment's failure (6.S1), and it is
    **silent**.
- Second manual check: select a part through a trigger, then read the frame. Pass: a blue ambient tint, with the
  part colour kept (3.3).

**S1.7 — Camera state key (ruling 1 server side; Q-2).**
- `RemoteRenderer` writes `remote_camera_state` (camelCase, seven fields) after `reset_camera`, `sync_camera`,
  `set_projection` and `load_state`'s `_push_runtime_state`. S5 adds the write at gesture end.
- The write runs on the thread S1.0 item 2 decides.
- Files: `renderer/remote_renderer.py`, `vtk/scene/remote_scene.py`, tests.
- Pin: after `reset_camera`, the state key equals a hand-written seven-field dict.
- Ruling 12: none.
- **Silent failure:** a write from the wrong thread that is never flushed leaves the client ruler stale, with no
  error (2.1.8 spike precedent). The client-side check is in S3.3.

**S1 acceptance.**
- Every `LocalApp` trigger name except those C-3 keeps local is callable in remote. Verified by a gate (S1.5).
- Contract 3.2 holds for `RemoteRenderer`. Gate (S1.3).
- **Remote per-part applies differ from local only after the write.** For each `apply_*` and the same inputs,
  the vtkProperty and mapper fields of `VisorLocalRenderer` and `RemoteRenderer` equal the same hand-written
  literals. This is one parametrised module over both renderers, with store and object state in separate test
  functions (session rule 10b). The post-write step is pinned per renderer: serialize for local, frame request
  for remote. With C-1 this also holds by construction; without C-1 it rests on the test alone. Gate (S1.3).
  Constructing `VisorLocalRenderer` needs a trame `Server`; how existing tests supply one is read in the prompt.
- A burst of N triggers in one loop tick produces one frame. Gate (S1.6, a recording frame requester).
- No `Render()` runs without `_vtk_lock`. Gate (S1.4).
- First frame without the patch, and the selection tint. Manual checks (S1.6).

### 7.5 Client work

All client work applies rulings 9, 10, 11, 12 and 13. The jest baseline is captured before the first client edit
(session rules, Gates).

**S2c.0 — Move today's local wiring into `useLocalVtk` (first client increment; ruling 9).**
- Intent: move `wasmView`, the bootstrap effect, `onServerUpdateAsync` and `onSetStateAsync` out of `App.tsx`
  into `hooks/useLocalVtk.ts`, unchanged, including the listener clear/re-add and the 100 ms resize. `App` renders
  the `UiScaffold` from the hook's frontend. `useVisorArgs` is extracted from `App` as it stands.
- Files: `App.tsx`, `hooks/useLocalVtk.ts` (new), `hooks/useVisorArgs.ts` (new).
- Tests that break: none expected. Whether a jest test renders `App`: search `App` imports in `jest-tests` in the
  prompt.
- Pin: none. This is a move, and the existing tests plus the manual check are the net.
- Ruling 12: none.
- Manual check:
  - Procedure: local mode; load a dataset; `add_dataset` a second one from Python.
  - Pass: the scene shows both datasets and the UI remounts.
  - Fail: the scene stays on the first dataset.

**S2c.1 — `CameraSyncReporter` attach and release move to `useLocalVtk` (ruling 9; C-4).**
- `VisorFrontend` no longer calls `attachCameraSyncReporter`. `useLocalVtk` attaches the reporter right after
  constructing the new frontend and releases the old one, with no `await` in between (the invariant in 7.0).
- If C-4 is ruled in, `VisorFrontend.release()` also removes the geometry-click listener.
- Files: `VisorFrontend.tsx`, `hooks/useLocalVtk.ts`, plus a test of the hook's attach/release.
- Tests: the four `VisorFrontend` construction modules keep passing; the double's key becomes unused.
  `CameraSyncReporter.test.ts` is unaffected.
- Pin: after two rebuilds, one settled-camera event produces one `sync_camera` send.
- **Silent failure:** a double report, where every send is valid and nothing fails.
- Manual check: rebuild twice, orbit once, and count `sync_camera` arrivals on the server. The prompt cites the
  log line that `LocalApp.sync_camera` writes and its level. If no such line exists, there is no manual check and
  the jest pin is the check.

**S2c.2 — Shared `buildFrontendAsync` (C-6).**
- Extracts the build sequence (C-6) from `useLocalVtk`. Local behaviour is unchanged.
- Signature (proposal): `buildFrontendAsync(sceneDetailsJson: unknown, createRenderer: (d: VisorSceneDetails) =>
  Promise<IRenderer>, triggerSender: TrameTriggerSender, darkMode: boolean | undefined): Promise<VisorFrontend |
  SchemaVersionMismatchError>` — "Build and seed a frontend from delivered scene details."
- Ruling 12: removes the duplicate that `useRemoteVtk` would otherwise carry.

**S2c.3 + S3.1 — Probe, branch, `RemoteCanvas` frames (S2, S3; C-10, C-12).**
- `useRenderingMode(host, port)` connects with `@kitware/trame` on the page's scheme and reads `rendering_mode`.
  For local it disconnects (O1, C-10). For remote it keeps the session.
- `App` calls both hooks unconditionally and branches only on render.
- `rca/RemoteCanvas.tsx` subscribes to `trame.rca.topic.stream` and draws JPEG frames. Area name `"view"`, the
  same literal as `RemoteApp`.
- A missing or unknown `rendering_mode` raises a named error on the page instead of falling back to local.
- Ruling 12: the branch is App's only mode check; it is what ruling 9 asks for.
- Acceptance:
  - The remote page loads no wasm module. Manual: network panel; fail = a `/wasm` request.
  - Local is unchanged. Gate: the jest suite.
- One bundle: `settings.get_client_bundle(standalone)` is already shared (6.S2), so nothing is added.

**S3.2 — Mouse and wheel to `trame.rca.event`, y flipped (C-11).**
- Uses the shared button mapping if C-11 is ruled in.
- Click detection as in the spike (4.2), raising `viewerClicked` through `RemoteRenderer` (S3.4).
- An unknown area name only prints on the server (6.S1). Proposal: `RemoteCanvas` takes the area name from the
  same constant as `useRemoteVtk`, so the two cannot diverge. The silent server print stays as found-not-fixed.

**S3.3 — `RemoteRenderer.ts` (rulings 1, 10; C-7, Q-2).**
- One renderer per rebuild.
- Sends through a required `TrameTriggerSender` built over the probe session, with VISOR trigger names. The
  payload shape matches what `RemoteVtkScene.trameTriggerAsync` sends today; read in the prompt.
- Cache:
  - The seven camera record fields come from `remote_camera_state`, read through `state.watch`.
  - The derived fields are computed on the client.
  - `viewPortHeight` comes from S6.
  - The toggles are seeded from `RuntimeSceneState` per rebuild. No-arg setters flip the cache and send the
    explicit value.
- `render()` and `resizeAsync()` are no-ops: the server renders every write, and S6 owns resize. These are true
  no-ops, not stand-ins.
- Ruling 12: `addCameraSettledListener` is an inert stand-in unless C-7 is ruled in.
- Pin: a toggle with no argument sends the flipped explicit value.
- **Silent failure:** a stale camera cache. Manual: after `reset_camera` from Python, the ruler changes.

**S3.4 — Picking P1 (ruling 3; C-5, Q-3).**
- A click calls `pick_part_at` and raises `viewerClicked(nodeId, ctrl, shift, normX, normY)`. The
  `Panel_TopRight` flow is unchanged, so selection has one owner.
- `pickGeometryAsync` throws `GeometryPickingUnavailableError` (name proposed). It is surfaced per C-5.
- Pin: a click on a part sends exactly one `set_part_selected`.

**S6 — Resize (ruling 6).**
- A `RemoteCanvas` ResizeObserver sends `trame.rca.size {w, h, p}`. The server path is `update_size` →
  `VisorRcaWindow.process_resize_event` → `set_viewport_size`.
- The client cache's `viewPortHeight` = CSS height × dpr, which is the device-pixel height the server window gets
  with `scale` 1 and no pixel cap.
- **Silent failure:** if `max_pixel_count` or `scale` is ever set, the server height differs and the ruler's
  `unitsPerPixel` is wrong with no error. Proposal: `RemoteApp` leaves both at their defaults, and a test pins that.
- Acceptance: after a resize, the server window size equals the canvas CSS size × dpr. Gate on the server side
  through a recording renderer. Manual: the ruler matches local for the same scene.

**S5 — Server-side interactor (ruling 9; C-2).**
- `VisorRcaWindow.process_interaction_event` handles `EndInteractionEvent`: under `_vtk_lock`, it writes
  `_last_camera_state` from the pipeline camera, then writes `remote_camera_state` (S1.7).
- `useRemoteVtk` never attaches `CameraSyncReporter`, so no stand-in is needed.
- Acceptance:
  - Orbit, pan and zoom render on the server. Manual.
  - After a gesture, the client cache equals the server's `get_camera_state`. Gate on the server; manual on the
    client.
  - No `sync_camera` is sent in remote. Gate: a `useRemoteVtk` test.

**S4 — `scene_version` and release (ruling 4, R1; rulings 10, 11; C-4).**
- **S4.1** `_post_scene_change_hook` is called at the seven sites in 5.2. In remote it bumps `scene_version` through
  non-blocking `run_coroutine` (Q-1) and requests a frame. In local it is a documented no-op.
- Ruling 12: the local no-op is an inert stand-in. Its proposed home is the mode hook itself, because local
  already signals through `LocalView.update`. The alternative, calling it from `render()`, is rejected in 5.6.
- **S4.2** `useRemoteVtk` watches `scene_version` and rebuilds latest-wins, remote only (ruling 11).
- **S4.3** The replaced frontend's `release()` (C-4) and `renderer.dispose()` run on each rebuild.
- Acceptance:
  - Each of add, remove, update, clear, update_variables and load_state produces one rebuild. Gate (server hook
    count) and manual.
  - A burst ends on the latest scene. Gate: a hook test with a held build promise.
  - A reconnect shows the current scene. Manual.
  - Replaced frontends leave no live listener. Gate.

### 7.6 Found, not fixed (carried)

- Local drop-during-rebuild (5.1). Ruling 11.
- trame-rca prints on an unknown area name and drops the call (6.S1).
- `VtkScene` `window keydown` listener never removed (6.S4).


---

## Section 8 — Rulings
1. Q1: Client camera read and the four synchronous toggle getters: option A (remote-only cache, record pushed by a state
   key, derived fields on the client, viewPortHeight from the canvas).  No-arg setters flip the cache
   and send the explicit value.
2. Q2: color and selection applies: per-part contract: adopt it as the docstring on both stacks; RemoteRenderer delegates
   to VtkNodePipeline.  Whether the per-part methods then leave the interface is decided after S1, not now.
3. Picking: P1, part select only; geometry picking in remote mode throws a named error this phase and is its own
   later story (not covered here: "Geometry picking in remote mode").
4. Rebuild signal: R1.  The bump is marshalled onto the loop thread unless shown safe.  Every Render() holds _vtk_lock.
5. Triggers: extract a shared base for LocalApp and RemoteApp that keeps LocalApp's constructor unchanged.
6. set_viewport_size on RemoteRenderer only, driven by trame-rca resize path (option a); not on IRenderer.
7. No RendererAnnotation union; the mode comes from the probe.
8. HEADLESS is out of this phase.
9. Client modes: follow the spike's App structure (see _spike_reference\theia\src\ansys\theia\theia-client\src\App.tsx).
   (it can use something like classes if that's more appropriate than the spike's function component; the naming does
   not need to match exaclty; there is room to propose other names if mor appropriate).
   userRenderingMode probes (page's ws/wss schema); useVtkLocal and useRemoteVtk hold all mode-specific wiring
   (rebuild trigger, CameraSyncReporter, release); VisorFrontend stays mode-independent.  First client increment:
   move today's local wiring into useLocalVtk (or equivalent naming) unchanged.  
10. New RemoteRenderer per rebuild (6.S3).
11. The local drop-during-rebuild defect is recorded, not fixed in this phase.  
12. Each increment plan names any duplicate, inert stand-in or mode check it would add, and propose where it belongs
    instead (a mode hook, a shared function, or a later story).
13. Local mode's behaviour does not change in this phase; its code may.  Behaviour-preserving moves, extractions and
    shared functions in local-mode code are allowed, with the existing tests as the net.  Options rejected only because
    they edit local-mode code are reopened on their merits.
14. C-1, C-2, C-3, C-4, C-5, C-7, C-8, C-9, C-10, C-11, and C-12 adopted as recommended.
15. C-6 adopted; buildFrontendAsync throws SchemaVersionMismatchError instead of returning it, and returns
    Promise<VisorFrontend>.
16. Q-1: try-and-reschedule.  Q2: remote_camera_state.  Q3: pick_part_at.
17. Ruling 14 overrides 13 for C-4 (stale click listeners stop firing on rebuild) and C-5 (a failed wasm geometry pick
    is logged).
18. C-3 overrides S1's "RemoteApp registers every LocalApp trigger" for pick_geometry, perf_report_wasm and
    perf_report_server_update.
19. Rendering modes are CLIENT, SERVER and PARAVIEW>  LOCAL is renamed CLIENT where SERVER is added.  Every new name the
    plan spells Remote is spelled Server (RemoteRenderer -> ServerRenderer, remote_camera_state -> server_camera_state,
    and so on); trame-rca names are unchanged.  Existing Local names stay in Phase 4 (it is only the enum exposed under
    `RenderingMode` that changes).

### 8.1 Bindings (v1)

The rulings above are verbatim. Each line below names the increments of Section 7 that a ruling binds.

1. → S1.7 (camera state key), S3.3 (cache), S6 (`viewPortHeight`).
2. → S1.2 (shared base, if C-1), S1.3 (delegation; docstrings on server `IRenderer` and client `IRenderer.ts`).
3. → S1.5 (`pick_part_at`, Q-3), S3.4; C-5 (the named error is swallowed today).
4. → S1.0 (threads, state writes), S1.4 (lock in the RCA window, Q-1), S1.6 (frame coalescing), S1.7, S4.1
   (non-blocking bump).
5. → S1.5 (exactly one `@TrameApp()` per chain; 18 `LocalApp(` test constructions unchanged).
6. → S1.3 (`set_viewport_size`), S1.4 (`process_resize_event`), S6.
7. → S1.3 (`build_renderer_annotation() -> None`), S2c.3 (mode from the probe).
8. → S1.6 (`REMOTE` only).
9. → S2c.0 (move), S2c.1 (`CameraSyncReporter`), S2c.3 (probe, branch), S4.2 (remote rebuild). Name mapping:
   `userRenderingMode` = `useRenderingMode`; `useVtkLocal` = `useLocalVtk`.
10. → S3.3.
11. → S4.2 (latest-wins stays remote-only); 7.6.
12. → every increment; each one states its additions in Section 7.
13. → S1.2, S1.5, S2c.0–S2c.2 (local moves and extractions); candidates C-1 to C-12 await rulings.


