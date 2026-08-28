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

## In progress: Phase 2.2

- Canvas authoring foundation: Select, Node, Member, and Pan tools; grid and node snapping; live
  cursor coordinates; mouse-centred zoom; selection highlighting; box selection; safe object
  deletion; and undo/redo history.
- Selection filtering for nodes, members, or both; left-to-right contained selection and
  right-to-left crossing selection.
- Canvas changes flow back through the editable model tables and invalidate stale results.
- Next in this phase: property inspector and support/load authoring tools.

## Next: Phase 3

- Beam and Truss workspaces using the same editor, result, diagram, and diagnostic conventions.

## Later: Phase 4

- Report, PDF, JSON/CSV/Excel export, and print-ready calculation packages.

## Later: Phase 5 and 6

- SketchUp Ruby-to-Python bridge.
- Steel and concrete design-code checks.
