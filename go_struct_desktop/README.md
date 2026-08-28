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
- Project display units for legacy kg-m, kN-m, N-mm, and tf-m; values are converted at the UI boundary while JSON and solver inputs remain legacy-compatible.
- Workspace persistence for docks, display settings, grid/snap state, plus autosave/recovery for unsaved model changes.
- Productivity tools for mirrored/array copies, move-by-delta, zoom window, and selecting members by section.
- Five built-in, analysis-ready examples covering point actions, triangular loads, portal combinations, member releases, and reaction checks.
- An EngiLab Frame.2D `.fr2d` importer plus automatic access to every locally installed sample.
- An initial 1D Beam workspace with a standalone Euler-Bernoulli solver, its own files/autosave,
  and editable cantilever, simply supported, continuous, and released-beam examples.

The Beam workspace foundation is in progress. GOTruss, reports, and the SketchUp bridge remain
outside the current increment. The existing Ruby extension remains the production SketchUp integration.

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

## Run the Beam workspace

```powershell
cd go_struct_desktop
py -m pip install -e ".[dev,gui]"
go-struct-beam
```

The Beam workspace opens with a two-span beam and writes `.gobeam.json` files. It accepts horizontal
members and transverse `Fy`/`Mz`, Local Y, or Global Y loads. This is a separate 1D solver, not a
restricted visual mode of the Frame solver; axial loads and non-horizontal members are reported as
invalid input. Canvas and Nodes-table editing lock every beam node to its common horizontal baseline.
Use `Beam > Add Span` to append a span from the right-most node, `Beam > Place ... support` to assign
supports, or `Beam > New Template` to begin with cantilever, simply supported, or continuous geometry.

## Run the Truss workspace

```powershell
cd go_struct_desktop
py -m pip install -e ".[dev,gui]"
go-struct-truss
```

The Truss workspace writes `.gotruss.json` files and uses a dedicated planar pin-jointed solver.
Members report tension-positive axial `N`; green members are in tension and red members are in
compression for the active result selection. Apply only nodal `Fx/Fy` loads. Member loads, nodal
moments, self weight, and frame end releases are intentionally unavailable. Use `Truss > New Template`
to start a Triangle, Warren, or Pratt truss.

## Canvas authoring

The workspace uses two stable toolbar rows: Modeling and Loading beside the file commands, then Analysis and Results below it. The result diagram selector is a direct `Model`/`N`/`V`/`M`/`D`/`All`/`FBD` mode-button group, rather than a dropdown. Use the modeling tools to switch among Select, Node, Member, Split, support, load, and Pan. Node and Member tools use
the configured grid step and can snap to endpoints, member midpoints, or member intersections. Select objects by click or selection
box; choose Nodes, Members, or Both before selecting. A left-to-right window selects objects fully
inside it, while a right-to-left window selects crossing members too. Drag a selected node to move,
extend, or trim its connected members; press `Delete` and confirm to remove selected members or
nodes. `Ctrl+D`, `Ctrl+Z`, and `Ctrl+Y` duplicate, undo, and redo model changes. Canvas edits update
the same model shown in the input tables and require analysis to be run again.

## Built-in examples

Use `File > Examples` to load five editable examples. They are not saved files, so save one under a
new `.goframe.json` name before keeping your own changes. The set includes a cantilever with member
point force/moment, a simply supported triangular load, a portal frame with combinations, a released
beam, and a two-span reaction/equilibrium check that opens in FBD view.

When EngiLab is installed at its standard location, `File > Examples > EngiLab Installed Examples`
lists every `.fr2d` sample found there (18 on the reference installation). `File > Import EngiLab
Frame.2D` imports any other compatible `.fr2d` file. The application converts Metric, US, and
Consistent units internally and displays the result in `kN-m`; it does not package or depend on the
original `.fr2d` files. Unsupported translational springs are omitted and reported in the status bar
after import.

`Model Input` and `Analysis Results` are movable, floatable, and closable docks. Reopen them from
`View > Model Input` and `View > Analysis Results`. Analysis Results starts in a compact height and can be dragged down to
120 px, leaving the canvas available as a focused central work area.
Open `View > Properties` for selection-aware editing. `Model`, `Loads`, and `Results` menus expose
the matching canvas tools and input tables. `File > Export Analysis JSON` writes a normalized model,
solver result, and post-processing data package for review or later reporting.

## Display and free body layers

Open `View > Display` to control model labels, load values and direction labels, diagram fill, and
visual sign conventions. Auto/Manual diagram scale and `View > Fit Diagram` control the result
overlay without changing result values. These choices transform presentation only; the solver's native
values and units are unchanged. The Free body view accepts a single Case or Combo, never an Envelope, because
an envelope can contain values governed by different combinations and is not a balanced load state.
Model view draws every input load case in a distinct colour and prefixes its load labels with the case
name. In `Display > Loads`, select `All input cases`, an individual case, or a `Combo`; a combo draws
factored loads using its defined case factors. Results view defaults to the first input case unless a
specific case or combo is selected.
The FBD panel also accepts a moment reference point. Double-clicking a Diagnostics row selects and
fits its implicated canvas objects, where applicable.

## Reliability and recovery

Choose `Display units` in the Project tab to work in Legacy kg-m, kN-m, N-mm, or tf-m. Existing
GOFrame JSON remains canonical in kg/m internally, so legacy files and the future Ruby bridge retain
their contract. Model table edits and canvas load dialogs convert to/from the chosen display system.

The desktop restores dock placement, display conventions, and grid/snap preferences on restart. Every
model edit writes a recovery snapshot; use `File > Recover Autosave` after an interrupted session.
