# ADR 12: VISOR Metadata per Part Support

## Status
Proposed

## Context

VISOR currently uses a separate `Metadata` class to store visualization-related attributes (e.g., name, unit),
since not all Ansys flagships can yet embed such data directly in their VTK outputs.
A new requirement introduces per-part opacity control.

Following discussions with Kitware and input from @ahernsean, it was confirmed that VTK `FieldData` can
reliably persist small per-part JSON
metadata on leaf datasets (e.g., .vtp pieces under a .vtm).
In parallel, work is underway across flagships to define a shared data standard,
including support for embedded visualization metadata.

## Discussion Summary

* **Recommendation from review**:
Store per-part opacity directly in VTK `FieldData` on each leaf dataset (as a JSON string), for example `{"opacity": 0.5}`
stored under a `vtkStringArray` named `visor_state`
Reserve the external sidecar/Metadata concept for future session-level state.
This ensures defaults travel with geometry, avoids multiblock writer issues, and aligns with emerging VTK conventions.
* **Current team direction**:
Continue using the existing external `Metadata` class in the near term to support early adoption across flagships
and maintain flexibility before the shared format is finalized and adopted.
The `Metadata` object will continue to store per-part visualization settings (e.g., opacity) keyed by part name.

## Decision
For this ADR:
* Short term:
Implement per-part opacity via the external Metadata class, using part names for association
* Long term:
Migrate to embedded per-leaf `FieldData`, likely once the flagship-standard VTK schema for
visualization metadata is available and adopted.

## Notes
* Do not use `vtkInformation` for persistence; it is unsuitable for serialized metadata.
* XML-based VTK formats are the recommended path for preserving any per-leaf state.
* The external `Metadata` mechanism remains supported for early adopters and backward compatibility
until a unified data model is in place.