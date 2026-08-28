# Desktop Roadmap

## Completed: Phase 1

- JSON-compatible GOFrame schema and 2D frame stiffness solver.
- Load cases, combinations, and maximum-absolute result envelopes.

## Completed: Phase 2

- PySide Frame workspace for model editing, JSON open/save, analysis, and tabular results.

## Current: Phase 2.1

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

## Next: Phase 3

- Beam and Truss workspaces using the same editor, result, diagram, and diagnostic conventions.

## Later: Phase 4

- Report, PDF, JSON/CSV/Excel export, and print-ready calculation packages.

## Later: Phase 5 and 6

- SketchUp Ruby-to-Python bridge.
- Steel and concrete design-code checks.
