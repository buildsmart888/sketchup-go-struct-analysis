# GO Struct Desktop

This directory is the Python foundation for the future GO Struct Analysis desktop application.
It is deliberately independent from SketchUp and PySide so the numerical engine can be tested,
reused by a CLI, and later called by the Ruby extension through a bridge.

## Current scope

- A JSON-compatible schema for the current GOFrame model.
- A NumPy implementation of the 2D frame direct-stiffness solver.
- Load cases, linear load combinations, and maximum-absolute envelopes.
- Regression, equilibrium, and validation tests.
- A PySide 2D Frame workspace with editable model tables, model/deformed-shape views, and results.
- Member diagrams for axial force (N), shear (V), moment (M), and FE deflection.
- Canvas overlays for N, V, M, FE deflection, or all diagrams on the structural model.
- Optional diagram value labels plus crosshair hover markers and tooltips for member force and deflection values.
- Calculation details, topology screening, and load-case equilibrium checks.

GOBeam, GOTruss, reports, and the SketchUp bridge remain outside the current increment. The existing
Ruby extension remains the production SketchUp integration.

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

The 2D frame solver does not calculate torsion (T). Its node degrees of freedom are `Ux`, `Uy`, and
`Rz`; a torsion result requires a future 3D frame solver.

## Development

```powershell
cd go_struct_desktop
py -m pip install -e ".[dev]"
py -m pytest
```

## Run the Frame workspace

```powershell
cd go_struct_desktop
py -m pip install -e ".[dev,gui]"
go-struct-desktop
```

The desktop app opens with an editable portal-frame model. It supports `.goframe.json` files from
the Ruby dialog, and it writes the same input field names back to JSON.
