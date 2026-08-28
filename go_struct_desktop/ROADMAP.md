# Desktop Roadmap

## Completed: Phase 1

- JSON-compatible GOFrame schema and 2D frame stiffness solver.
- Load cases, combinations, and maximum-absolute result envelopes.

## Completed: Phase 2

- PySide Frame workspace for model editing, JSON open/save, analysis, and tabular results.

## Current: Phase 2.1

- Reusable member post-processing for axial force (N), shear (V), moment (M), and FE deflection.
- Interactive member diagrams with governing envelope information.
- Detailed end-action/extrema view, topology screening, and load-case equilibrium checks.

The current 2D solver does not calculate torsion (T). Torsion requires a future 3D frame model with
six nodal degrees of freedom and torsional member stiffness.

## Next: Phase 3

- Beam and Truss workspaces using the same editor, result, diagram, and diagnostic conventions.

## Later: Phase 4

- Report, PDF, JSON/CSV/Excel export, and print-ready calculation packages.

## Later: Phase 5 and 6

- SketchUp Ruby-to-Python bridge.
- Steel and concrete design-code checks.
