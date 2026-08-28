# GO Struct Desktop

This directory is the Python foundation for the future GO Struct Analysis desktop application.
It is deliberately independent from SketchUp and PySide so the numerical engine can be tested,
reused by a CLI, and later called by the Ruby extension through a bridge.

## Current scope

- A JSON-compatible schema for the current GOFrame model.
- A NumPy implementation of the 2D frame direct-stiffness solver.
- Load cases, linear load combinations, and maximum-absolute envelopes.
- Regression, equilibrium, and validation tests.
- A dockable PySide 2D Frame workspace with editable model tables, model/deformed-shape views, and results.
- Member diagrams for axial force (N), shear (V), moment (M), and FE deflection.
- Canvas overlays for N, V, M, FE deflection, or all diagrams on the structural model.
- Optional diagram value labels plus crosshair hover markers and tooltips for member force and deflection values.
- Canvas model editor: select, pan, grid/snap, box selection, create snapped nodes, draw members, drag nodes with live preview, split members, duplicate, align, fit selection, and undo/redo.
- Property inspector for node coordinates/support/nodal load, member endpoints/section/releases, and batch support/member updates.
- Canvas support and load tools, including edit-on-click for existing nodal and member loads.
- A Display dock for independent model, load, result-convention, and free-body layers.
- Directionally correct nodal forces/moments and uniform or linearly varying member loads in Local X/Y or Global X/Y for an active input load case.
- Free-body diagrams for a single analysis case or combination, including support reactions and global equilibrium residuals.
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

## Canvas authoring

The workspace uses two stable toolbar rows: Modeling and Loading beside the file commands, then Analysis and Results below it. The result diagram selector is a direct `Model`/`N`/`V`/`M`/`D`/`All` mode-button group, rather than a dropdown. Use the modeling tools to switch among Select, Node, Member, Split, support, load, and Pan. Node and Member tools use
the configured grid step and can snap to endpoints, member midpoints, or member intersections. Select objects by click or selection
box; choose Nodes, Members, or Both before selecting. A left-to-right window selects objects fully
inside it, while a right-to-left window selects crossing members too. Drag a selected node to move,
extend, or trim its connected members; press `Delete` and confirm to remove selected members or
nodes. `Ctrl+D`, `Ctrl+Z`, and `Ctrl+Y` duplicate, undo, and redo model changes. Canvas edits update
the same model shown in the input tables and require analysis to be run again.

`Model Input` and `Analysis Results` are movable, floatable, and closable docks. Reopen them from
`View > Model Input` and `View > Analysis Results`; this leaves the canvas available as a focused central work area.
Open `View > Properties` for selection-aware editing. `Model`, `Loads`, and `Results` menus expose
the matching canvas tools and input tables. `File > Export Analysis JSON` writes a normalized model,
solver result, and post-processing data package for review or later reporting.

## Display and free body layers

Open `View > Display` to control model labels, load values and direction labels, diagram fill, and
visual sign conventions. Auto/Manual diagram scale and `View > Fit Diagram` control the result
overlay without changing result values. These choices transform presentation only; the solver's native
values and units are unchanged. The Free body view accepts a single Case or Combo, never an Envelope, because
an envelope can contain values governed by different combinations and is not a balanced load state.
