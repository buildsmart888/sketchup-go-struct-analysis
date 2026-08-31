# Architecture

## Current boundaries

`src/go_struct_core` owns validated input models and numerical analysis only. It must not import
PySide, SketchUp, reporting, or file-dialog APIs. The public boundary for the current phase is:

```text
legacy GOFrame JSON -> FrameModel -> frame solver -> JSON-compatible result
```

The PySide workspace is a separate consumer of that boundary:

```text
FrameInputPanel -> FrameModel -> frame solver -> FrameResultsPanel
```

Before results reach the UI, `build_frame_postprocess()` samples each member for N/V/M and FE
deflection, records extrema, and creates governing-combination envelope data. This keeps diagram
math, sign conventions, and diagnostics independent from PySide.

The UI owns editable tables, file dialogs, canvas authoring, rendering, and presentation units. A
project selects legacy kg-m, kN-m, N-mm, or tf-m; UI boundaries convert to/from the core's canonical
legacy kg/m fields. The core owns validation, source units, stiffness calculations, and result semantics.

Canvas authoring emits a complete JSON-compatible model change to the main window. The main window
updates `FrameInputPanel`, which remains the model source of truth and sends the refreshed model
back to the canvas and results panel. The main window records compatible model snapshots for
undo/redo. This keeps mouse authoring and table editing synchronized.

`CanvasSpatialIndex` is a UI-only model-space cache rebuilt when the model changes. It indexes nodes,
member bounds, load anchors, member midpoints, and non-endpoint member intersections for local cursor
queries. `FrameCanvas` throttles interaction repaint to 60 fps and diagram hover to 30 fps; its
interaction detail mode suppresses expensive overlays while the pointer moves and restores them after
a short idle delay. This cache and level-of-detail policy does not alter solver data or project files,
and leaves a future `QOpenGLWidget` renderer free to replace only the drawing backend.

`DisplaySettings` belongs to the UI layer. Its graph-side orientation controls can change where a
diagram is drawn, but never reverse a solver value, change solver input, stored result values, or units.
Legacy projects that selected the old opposite sign display migrate to a flipped graph side. FBD receives a
single case/combo result plus matching load factors; envelopes are intentionally excluded because
they do not represent one equilibrated load state.

The data contract mirrors `go_struct_analysis/goframe.rb` and the `collectData()` function in
`go_struct_analysis/templates/goframe_dialog.html`.

## Current and planned consumers

- Phase 3.1: the Beam workspace uses `BeamModel` and a standalone 1D Euler-Bernoulli solver while
  retaining the shared JSON field names and result/post-processing contract. It deliberately accepts
  horizontal members with transverse loads only; axial beam actions and non-horizontal geometry are
  rejected rather than silently analysed as a frame. `BeamCanvas` and the Beam workspace table-change
  boundary preserve one horizontal node baseline before data reaches the solver.
- Phase 3.2: the Truss workspace uses `TrussModel` and a planar pin-jointed solver with only `Ux`
  and `Uy` per node. It shares the editor, units, results, and validation contract, but rejects
  member loads, nodal moments, self weight, and frame end releases. `I` remains an internal frame-schema
  compatibility field only; Truss files and UI need only material `E` and area `A`.
- Hybrid Frame-Truss projects stay on the shared `FrameModel` and 3-DOF-per-node direct-stiffness
  path. `FrameElement.member_type` selects the local stiffness: Frame members retain the full 6x6
  N/V/M matrix while Truss members contribute axial translation stiffness only. This permits bracing
  to meet Frame columns/beams at the same node without creating a second project or result contract.
  The schema rejects member loads and released ends on Truss members; unstiffened rotational load DOFs
  are rejected by the solver before a displacement is reported.
- The shared profile-truss generator carries profile, web pattern, `dimension`, support placement, and
  joint-model metadata. Current values describe 2D pin-jointed templates; the fields reserve a stable
  upgrade path for 3D truss geometry and member grouping without changing the existing solver contract.
- Phase 3 authoring helpers remain at the workspace boundary: `BeamCanvas` resizes/splits horizontal
  spans, while `TrussCanvas` handles section grouping, roof geometry, and selected-member operations.
  `truss_tools.distribute_vertical_line_load()` is intentionally a pure transform that converts a
  selected-chord line load to equivalent node loads before it reaches the truss solver.
- Phase 4: report and export services consume JSON-compatible analysis results.
- Phase 5: a Ruby bridge sends model JSON to a Python process and stores its result in existing
  `GOStructAnalysis` BIM attributes.
- Phase 6: design-code checks consume solver demand results; they do not live inside the solver.
- Warehouse3D: `WarehouseProject` is an independent SI-unit project contract. `warehouse.py` owns
  parametric building generation; `warehouse_analysis.py` owns a first-order six-DOF space-frame
  backend; `warehouse_evaluation.py` owns preliminary screens and auditable cost allowances; and
  `warehouse_optimize.py` owns deterministic cacheable Pareto search. The Warehouse PySide/QML
  workspace consumes those JSON-compatible boundaries and does not import them back into the core.

## Compatibility rules

- Preserve the current sign convention and unit conversion from the Ruby GOFrame solver.
- Do not mutate input dictionaries while parsing combinations or solving.
- New properties must have defaults or a migration path before they are written back to a model.
- Project unit metadata lives in `projectInfo.units`; unknown or absent values default to `legacy_kg_m`.
- The result envelope stores the signed value with greatest absolute magnitude, matching Ruby.
- Member diagrams use tension-positive axial force and the legacy GOFrame local V/M display signs. UI
  controls may flip graph placement only; displayed numeric signs always remain solver signs.
- Beam results keep the same node/element shape as Frame results: axial values are zero, while shear,
  moment, slope, transverse deflection, and reactions are populated by the beam solver.
- Truss results use the same node/element shape for UI reuse: axial force is tension-positive and
  shear/moment/rotation values are zero by definition.
- Torsion is outside the 2D solver scope and must not be represented by `Rz`.
- Warehouse3D's native solver uses SI units (m, kN, Pa) and reports first-order linear-elastic demand.
  It is a preliminary-analysis contract, not an extension or replacement of legacy kg-m GOFrame data.

## Validation command

```powershell
cd go_struct_desktop
py -m pytest
```
