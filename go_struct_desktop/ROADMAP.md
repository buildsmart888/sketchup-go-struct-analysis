# Desktop Roadmap

## Completed: Phase 1

- JSON-compatible GOFrame schema and 2D frame stiffness solver.
- Load cases, combinations, and maximum-absolute result envelopes.

## Completed: Phase 2

- PySide Frame workspace for model editing, JSON open/save, analysis, and tabular results.

## Completed: Phase 2.1 Results and diagrams

- Reusable member post-processing for axial force (N), shear (V), moment (M), and FE deflection.
- Interactive member diagrams with governing envelope information.
- Canvas overlays for individual or combined N, V, M, and FE-deflection diagrams.
- Detailed end-action/extrema view, topology screening, and load-case equilibrium checks.

The current 2D solver does not calculate torsion (T). Torsion requires a future 3D frame model with
six nodal degrees of freedom and torsional member stiffness.

## Completed: Phase 2.2

- Canvas authoring foundation: Select, Node, Member, and Pan tools; grid and node snapping; live
  cursor coordinates; mouse-centred zoom; selection highlighting; box selection; safe object
  deletion; and undo/redo history.
- Selection filtering for nodes, members, or both; left-to-right contained selection and
  right-to-left crossing selection.
- Canvas changes flow back through the editable model tables and invalidate stale results.

## Completed: Phase 2.3 Model editor

- Selection-aware Property dock for node coordinates, support, load-case nodal loads, member
  endpoints/section/releases, and batch edits.
- Canvas editing: drag nodes with snap/preview, split members with load redistribution, duplicate,
  align, fit selection, keyboard shortcuts, and confirmed deletion.
- Canvas support, nodal-load, and member-load tools with compact dialogs; existing loads can be
  clicked for editing, including point-load position.
- Load directions extend to Local X/Y and Global X/Y in schema, solver, diagrams, FBD, and tables.
- Result viewer links canvas/table selection, supports Auto/Manual diagram scale, and avoids
  overlapping diagram value labels.
- Diagnostics now detect duplicate nodes, duplicate members, disconnected nodes, non-nodal member
  intersections, restraint shortages, and solver mechanisms.
- Model Input and Analysis Results now use independently movable, floatable, and closable docks;
  compact grouped canvas controls live in the main toolbar beside file/edit commands.

## Completed: Display and FBD foundation

- UI-only display settings for model, load, result-convention, and FBD layers.
- Directionally correct nodal force/moment and linearly varying distributed-load rendering.
- Free-body drawing for a single case or combo, with reactions and global residuals. Envelopes are
  explicitly excluded from FBD equilibrium.
- Member load schema now supports distributed load, point force, and point moment. Point locations use
  `x_m` measured from member I toward member J; they flow through the solver, diagrams, input canvas,
  and FBD equilibrium.

## Completed: Phase 2.4 Reliability and workflow hardening

- Project-level display units for legacy kg-m, kN-m, N-mm, and tf-m, with conversion at UI boundaries
  and a stable legacy JSON/solver contract.
- Regression coverage now includes cantilever, portal combination/equilibrium, point-load/moment, and
  simply-supported UDL FE benchmarks.
- Workspace layout, display settings, and grid/snap preferences persist; unsaved model edits write a
  recoverable autosave snapshot.
- Double-click Diagnostics selects and fits implicated nodes/members. FBD can evaluate moment residual
  about an explicit reference point.
- Mirror, array, move-by-delta, zoom-window, and select-by-section tools build on the common canvas
  model-change/undo history path.

## Completed: Phase 2 closeout

- Direct result-mode buttons provide Model, N, V, M, Deflection, All, and FBD views; explicit
  analysis requests report completion with elapsed time and analyzed model counts.
- Model view can display a selected input load case, every input load case together, or the factored
  loads for a load combination. FBD remains deliberately limited to one solvable case or combination.
- Deflection values use unit-aware precision so small metric deflections remain readable.
- Five editable built-in examples cover cantilevers, simply supported beams, portal combinations,
  member releases, point force/moment, triangular load, and reaction checks.
- An EngiLab Frame.2D `.fr2d` importer provides access to every locally installed reference example,
  with a bundled fallback set when EngiLab is unavailable. Unsupported translational springs are
  reported during import rather than silently modeled incorrectly.

## Phase 2 exit status

Phase 2 is complete: GO Struct Desktop has a production-ready 2D Frame modeling and analysis
workspace. Beam and Truss remain separate workspaces, not incomplete Frame features.

## Completed: Phase 3.1 Beam workspace

- Standalone 1D Euler-Bernoulli Beam solver with support reactions, V/M, slope, FE deflection,
  point force/moment, uniform/triangular loading, load cases, combinations, and envelopes.
- Dedicated `go-struct-beam` desktop entry point with independent files/autosave and four editable
  Beam examples. It reuses the established editor, canvas, units, result diagrams, FBD, and docks.
- Beam authoring locks node/member editing to one horizontal baseline, offers `Add Span`, selected-span
  resizing, support insertion, direct fixed/pinned/roller support placement, full-span UDL helpers, and
  cantilever/simply-supported/continuous templates.
- Beam input rejects non-horizontal members and axial loads instead of treating them as a 2D frame.
  More specialised layout helpers can follow from actual project workflows.

## Completed: Phase 3.2 Truss workspace

- Planar pin-jointed Truss solver with nodal `Fx/Fy`, reactions, tension/compression member forces,
  load cases, combinations, envelopes, and mechanism detection.
- Dedicated `go-struct-truss` entry point with `.gotruss.json` files, independent workspace state,
  axial-only `N` result display, and tension/compression member colours.
- Triangle, Warren, Pratt, Howe, and pitched Roof templates/examples, with span or panel-width and
  height inputs at creation time. Truss authoring hides frame-only inertia/density, member loads,
  releases, `V`, `M`, and bending-deflection result modes.
- Truss tools assign sections to a selected group, mirror selected geometry, adjust roof height, and
  regenerate Warren/Pratt/Howe/Roof template panel counts. A selected roof chord can convert a vertical
  line load by horizontal projection into equivalent nodal loads with a reported resultant.

## Phase 3 exit status

Beam and Truss now have dedicated authoring workflows rather than only specialised solvers. Both provide
a template catalog, editable templates, workspace-specific result summaries, and regression coverage.
The next planned deliverable is Phase 4 report, PDF, and data-export packages.

## Later: Phase 4

- Report, PDF, JSON/CSV/Excel export, and print-ready calculation packages.

## Later: Phase 5 and 6

- SketchUp Ruby-to-Python bridge.
- Steel and concrete design-code checks.
