# ADR 17: Server-Authoritative State and Remote Rendering for VISOR

## Status
Accepted (2026-07-21 by VISOR team)

## Context
VISOR is a browser-based 3D scientific visualization platform built on Trame, with rendering currently performed
client-side via VTK.wasm (`trame-vtklocal`).  This works well for datasets that fit comfortably in browser memory,
but the geometry must be serialized to the client and client hardware bounds performance.

Remote rendering, in which the server owns the VTK pipeline and rendering and streams rendered frames to the browser,
is a product requirement.  The local wasm mode still serves the case where no server GPU is available, and
where the dataset is small enough to fit in browser memory.  The Trame framework supports both modes,
with `trame-vtklocal` and `trame-rca` as its packages for the local and remote paths respectively.

Remote rendering needs the scene to live on the server.  In VISOR today it does not: per-part visual state lives
in the browser and is never synced back, so the server's copy is stale by design after startup.  Host solutions
drive VISOR through its Python service API, so those calls operate on that stale copy.  Wasm-specific code is also
coupled through code on both frontend and backend, leaving no clean seam for a second rendering mode to attach.

This ADR covers two coupled pieces of work: what the current application needs before a remote path can be added,
and the remote path itself.

## Requirements
* **Server-authoritative state**: the scene lives on the server; a rendering mode with no client-side scene cannot
depend on client-owned state
* **Server-side rendering**: with pixel streaming to the browser, the existing UI overlaid, and camera and
interaction events forwarded to the server
* **One shared codebase for both modes**, minimizing divergence so that features and fixes apply to both paths
where possible
* **State behaviour identical across both modes**: Save/load state behaves the same regardless of rendering mode
* **API behaviour identical across both modes**: API-driven changes (`add_dataset`, `update_variables`, etc) behave
the same regardless of rendering mode
* **Support for datasets beyond client-side limits**: Rendering mode is selected when the application instance is
created, with the local wasm mode retained for no-server-GPU deployments; switching modes within a running
session is not a requirement.

## Out of scope

* Pre-existing issues that are not prerequisites for remote rendering.  Performance and threading work is in scope
only where parity requires it.
* Multi-user and multi-tenancy
* In-session rendering mode switching
* Product-level performance targets (this work targets partiy)
* Production hardening of the remote path: session management, reconnect, encoder and quality controls.  These
land under the performance epic, not in this ADR.
   * A unified graceful auto-connect is deferred to the performance epic.
* Detailed design of the round-trip mechanism.  We commit to round trips here, but it is designed separately;
see below.

## Options Considered

### Question 1: State ownership and stack

**Option 1.1 Keep the current hybrid client-owned state model.**  Cannot support a rendering mode with no client scene.
Also carries today's known costs: state changes push stale server state on `local_view.update()` before
reapplying state on the client, producing an inherent visible flicker.  Not chosen.

**Option 1.2 Move state fully client-side, off Trame.**  A pure JS/VTK.wasm application with a
purpose-built service layer.  This maximizes client-side simplicity, but is structurally incompatible with remote
rendering.  To support the Python-driven APIs, it means building and owning transport, session, and sync layers
that Trame already provides.  Not chosen.

**Option 1.2 Server-authoritative state within Trame (chosen).** The server owns scene state; Trame remains the session
and delivery layer.  This is the only option compatible with remote rendering, it resolves the state reconstruction
limitations noted above independent of rendering mode, and it keeps VISOR on infrastructure maintained upstream.
One cost is that the wasm path's end state requires round trips for state changes, which is the risk the second spike
was run to evaluate (see Spike Summary below).  Chosen.

### Question 2: How the two modes coexist

**Option 2.1 Single stack with two renderers behind a shared `IRenderer` abstraction (chosen).** Python abstract class and
TypeScript interface; shared code programs against it, each mode implements it. The same React bundle serves both.

**Option 2.2 Parallel remote path inside the existing app, no shared abstractions.**
The fastest to a first demo, but the current state model and a remote path's state model do not align, so
mode-specific branching spreads through backend and frontend and every feature is effectively built and maintained
twice in one codebase (not clean, difficult to maintain).  Not chosen.

**Option 2.3 Separate frontend for remote mode.** Maximal isolation between the modes, at the cost of two UIs to build
and maintain, a split user experience, and giving up the shared-codebase requirement.  Not chosen.

### Question 3: Remote transport within Trame
The trame-native options are the older image streaming widgets (`VtkRemoteView` / `VtkRemoteLocalView`, trame-vtk) and
`trame-rca` (Remote Controlled Area, Kitware's current purpose-built streaming layer).  `trame-rca` was selected as
the current-generation tool, recommended by Kitware.

### Question 4: Structure of the Trame application layer

Rendering mode selection at startup is a requirement (see Requirements).  The remaining structural question is whether
one Trame application class serves both modes, or each mode has its own.

**Option 4.1 A single Trame application class serving both modes.**  On its face, less total code.  In practice the
two modes expose the same trigger contract but complete the triggers differently (apply and sync the WASM scene vs
apply and schedule a server-side render), so a merged class would branch on mode inside nearly every handler.
It also could not deliver in-session mode-switching alone, since a session's mode is decided when its scene, renderer,
and client objects are constructed, and switching is also not a requirement.  Not chosen.

**Option 4.2 One thin Trame application per mode (chosen).** `LocalApp` and `RemoteApp` are separate classes,
each decorated with `@TrameApp`, owning only their mode's web configuration.  The frontend trigger contract is
common to both, and the shared Python logic lives in the scene layer beneath them (the scene base and the per-part
pipeline), so the application classes themselves stay thin.  A session is unambiguously on one code path from
startup, which is more robust for the SAF integration path.  Chosen.



## Decision

Adopt server-authoritative state within Trame, with dual rendering modes behind an `IRenderer` abstraction.

* **`IRenderer` on both sides.**  Python: scene coordination (dataset registry, state mapping, user-facing API)
no longer owns VTK pipeline objects; a renderer implementation owns the pipeline, render window, and frame delivery.
TypeScript: wasm-specific calls move behind the interface, and an RCA canvas component handles stream display
interaction forwarding in remote mode, with no wasm binary downloaded when running remote.
* **State model.** The server owns the VTK pipeline.  Its objects are the authoritative record of scene state.
In local mode the client holds a wasm copy of the scene, so a change originating in the browser has to travel to the
server, be applied to the server's pipeline, and come back as the state the client renders.  That round trip is
required by this model.  In remote mode the client holds no scene and forwards events.  On the wasm path,
local optimizations are preserved where latency demands them (cross-section drag applies locally and syncs on release,
for example).  Service API calls, save/load, and refresh all act on the server's objects and behave identically
in both modes.
* **Shared per-part pipeline.** The per-part VTK pipeline (actor, mapper, geometry filter, clipping plane) is identical
in both modes.
* **Remote transport and rendering backends.** `trame-rca` only transports the pixels.  The remote path is first built
and de-risked against a VTK off-screen render window with the OpenGL backend (Phase 4 below), which is enough to prove
the architecture.  The Paraview `pvserver` is the production backend for large models, and is added as
the last step (Phase 5).
* **Rendering mode selected at startup.** Mode is fixed at instance creation, exposed on the entry point, and plumbed
through the service and CLI. Each mode has its own thin `@TrameApp` class (`LocalApp`, `RemoteApp`) owning only
that mode's web configuration.  One unambiguous code path per session is a robust fit for the SAF integration path.

### Round trips on the wasm path: committed, designed separately

Committing to server-authoritative state commits us to round trips on the local path; that is a decision confirmed
in this ADR.  What that mechanism looks like in detail is a question left out of the scope in this ADR.
Some open design questions include whether the client applies a change optimistically while its round trip is in
flight, whether changes need tracking and acknowledgement and what that would look like, and how camera interaction
behaves on the local path.
The design for the round-trip feature is left for its own ADR under the performance epic (see Implementation Plan
below), informed by the round-trip spike findings.

## Implementation Plan
Below is the proposed implementation plan, broken into phases.  The full user story breakdown is not tracked here.

```
Phase 1 (backend refactor)---
                             |                              --> Phase 4 (remote rendering) --> Phase 5 (pveserver)
                             |--> Phase 3 (state inversion) |
                             |                              --> Phase 6 (round trips)
                             |                                  (under performance epic, separate ADR)
Phase 2 (frontend refactor) --
```

Each user story as part of the implementation plan is expected to leave VISOR in a working state, so that
parallel development work can continue while we incrementally move toward the final architecture.  The phases are:

* Phase 1: backend refactor extracting the renderer abstraction from the scene layer
* Phase 2: frontend refactor extracting wasm-specific code behind the renderer interface (parallel with Phase 1)
* Phase 3: state authority inversion: Incrementally move state from client to server, keeping VISOR functional
at each step.  In this phase, the client interactions are still applied locally, but the state is synced back
to the server, and the server's VTK pipeline is updated accordingly. Some parts of the VTK pipeline will need to
be added on the server side.  Note that this phase does not yet include the round-trip mechanism itself.
* Phase 4: remote path (RCA canvas, remote renderer, mode selection at VISOR startup).  Includes moving geometry
picking server-side with highlights as actors in the server scene, which also adds occlusion.
* Phase 5: Add `pvserver`.  Start with a timeboxed spike, followed by an implementation story based on the spike.
* Phase 6 (in parallel after Phase 3): the round trip mechanism.  Will be a separate feature under the performance epic.
Requires an ADR for the design of the round-trip mechanism. Due to an upstream issue encountered on the round-trip
spike (see below under Accepted Costs), this phase needs to start with a user story to bump the versions of
`trame-vtklocal` and `vtk-wasm` to the latest versions.


## Consequences

### Positive
* One codebase, two modes, no forked UI or state logic
* Server-authoritative state fixes save/load state and the inherent visible flicker on `local_view.update()`
* Local wasm mode retained for no-server-GPU deployments and small datasets
* Idiomatic to Trame, so maintenance stays aligned with upstream

### Accepted Costs
* Session-thread affinity is the largest unresolved risk. The spikes surfaced (rather than introduced) a
threading issue.  The framework expects VTK operations on the session's thread, and VISOR's API entry points arrive
from the host on other threads.  Serializing state applies did not change crash frequency, so the root cause is
open.  It affects API correctness after the server-owned model, so it is a parity prerequisite.
* The wasm path runs an interim model after Phase 3 (client-local application, one-way sync back) until the round-trip
feature lands.  The end state arrives in two steps, the second under its own ADR.
* An upstream color table issue blocks round trips on the wasm path, with no viable local workaround.  The spike branch
investigation found that the issue sits in the framework's state application layer (as opposed to VISOR's code).  The
`trame-vtklocal` and `vtk-wasm` dependency bumps at the start of Phase 6 may resolve the issue.  If the retest on
the latest versions fails, an upstream ticket would need to be filed to resolve it. (Note that this would leave the wasm
path on the interim model mentioned above - with the remote path being unaffected.)
* `pvserver` introduces a VTK version-pinning consideration (ParaView ships its own VTK), tracked in Phase 5.  Pinning
is the initial approach, but we will also explore building a custom `pvserver` against our VTK version.

## References
* Dual-mode architecture + remote rendering spike user story and spike findings document:
  * https://github.com/ansys-internal/theia/issues/1051
* Round-trip and optimization spike user story:
  * https://github.com/ansys-internal/theia/issues/1128
* User story breakdown for the phased implementation
  * https://github.com/ansys-internal/theia/issues/1049
* User story brekadown for performance epic (round trips, optimizations, and remote rendering production hardening)
  * https://github.com/ansys-internal/theia/issues/1168