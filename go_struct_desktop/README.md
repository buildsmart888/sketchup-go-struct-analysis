# GO Struct Desktop

This directory is the Python foundation for the future GO Struct Analysis desktop application.
It is deliberately independent from SketchUp and PySide so the numerical engine can be tested,
reused by a CLI, and later called by the Ruby extension through a bridge.

## Phase 1 scope

- A JSON-compatible schema for the current GOFrame model.
- A NumPy implementation of the 2D frame direct-stiffness solver.
- Load cases, linear load combinations, and maximum-absolute envelopes.
- Regression, equilibrium, and validation tests.

GOBeam, GOTruss, reports, the PySide interface, and the SketchUp bridge are intentionally outside
this first increment. The existing Ruby extension remains the production SketchUp integration.

## Units and compatibility

The frame input uses the same field names and units as the Ruby GOFrame dialog:

- Coordinates: m
- `e`: kg/m2
- `a`: cm2, converted internally to m2
- `i`: cm4, converted internally to m4
- Density: kg/m3
- Nodal forces and distributed loads: kg and kg/m
- Moments: kg-m

`analyze_frame_data()` returns the legacy result shape (`ok`, `nodes`, `elements`, `cases`,
`combos`, and `steps`) so a later bridge can exchange JSON without redesigning the data contract.

## Development

```powershell
cd go_struct_desktop
py -m pip install -e ".[dev]"
py -m pytest
```

For the future desktop UI, install the optional GUI dependency with `.[dev,gui]`.
