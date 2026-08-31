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
- Workspace persistence for docks, display settings, grid/snap state, plus autosave/recovery for unsaved model changes. Display conventions and the most recently used canvas tool are also retained in saved project files.
- Productivity tools for mirrored/array copies, move-by-delta, zoom window, and selecting members by section.
- Five built-in, analysis-ready examples covering point actions, triangular loads, portal combinations, member releases, and reaction checks.
- An EngiLab Frame.2D `.fr2d` importer plus automatic access to every locally installed sample.
- An initial 1D Beam workspace with a standalone Euler-Bernoulli solver, its own files/autosave,
  and editable cantilever, simply supported, continuous, and released-beam examples.
- A Hybrid Frame-Truss model: Frame members carry N/V/M while Truss members carry axial N only,
  with validated joint behaviour, matrix inspection, and editable roof-truss-on-column starters.

Beam and Truss have dedicated workspaces. The Frame result canvas also supports signed or spectrum
contours for N/V/M/deflection, global or per-member colour scales, a linked selected-member inspector,
and a fast drawing mode for large models. The SketchUp bridge remains outside the current increment;
the existing Ruby extension remains the production SketchUp integration.

The `Report` menu exports HTML or PDF calculation packages. Its Report content dialog can cover the
current result, every load case and combination, or all combinations, and can include canvas snapshots,
model/load schedules, node results, and member results. Pure Truss and Hybrid Frame-Truss canvas/report
views emphasize the maximum tension and maximum compression Truss members. See [the illustrated manual](docs/MANUAL.md)
or open the browser-friendly [HTML manual](docs/MANUAL.html) for Frame, Beam, Truss, and Hybrid workflows.

## Warehouse Optimizer 3D (preliminary)

`go-struct-warehouse` opens a separate parametric Warehouse3D workspace. It generates a complete
preliminary steel warehouse skeleton (columns, roof trusses, purlins, bracing, and ground beams),
performs a first-order 3D space-frame analysis, and presents preliminary checks, an auditable cost
estimate, and deterministic Pareto candidates for cost, steel mass, and maximum utilization.

The Warehouse viewport keeps the generated structure centred for orbit/pan/zoom and provides ISO,
Front, Right, Left, Top, and Bottom camera controls, member-group layers, interactive member picking,
and result modes for utilization, axial tension/compression, and exaggerated deflection. The
`Reactions / Loads` tab audits global force/moment equilibrium for every case and combination and
traces the equivalent nodal distribution of roof, wind, and self-weight actions. Member detail states
the preliminary screening expression and its axial, bending, and slenderness components.
In the 3D viewport: drag with the left mouse button to orbit; drag with the right mouse button (or
hold `Ctrl` while left-dragging) to pan; use the wheel to zoom; and use `Fit` to recenter the camera.
The on-canvas triad preserves the engineering convention: X is building length, Y is building width,
and Z is elevation/up; the viewport maps this Z-up convention to Qt Quick 3D's Y-up render space.

Warehouse JSON is a new SI-unit `.gowarehouse.json` format; it does not change GOFrame or GOTruss
files. The default 3D engine is the included NumPy direct-stiffness backend. An OpenSeesPy integration
point is exposed as an optional deployment extra, but must be qualified against the target binary
environment before it is selected for project work.

```powershell
cd go_struct_desktop
py -m pip install -e ".[dev,gui]"
go-struct-warehouse
```

For the qualified OpenSeesPy backend and pymoo mixed-variable NSGA-II engine,
install `py -m pip install -e ".[dev,gui,warehouse-opensees,warehouse-optimizer]"`.

This workspace is deliberately **preliminary design only**. Its yield/Euler/slenderness and movement
screens are configurable engineering checks, not a national design-code certification. Connection,
base-plate, anchor, and foundation figures are rule-based cost allowances; a licensed engineer must
review all results before construction use.

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

## Windows installer (Beta 0.1)

The installer contains the Frame, Beam, and Truss workspaces with their Python and Qt runtime, so a
recipient does not need Python installed. From this project folder, run:

```powershell
.\tools\build_windows_installer.ps1
```

The output is `release\installer\GO-Struct-Desktop-Beta-0.1-Setup.exe`. The installer creates Start
Menu shortcuts for each workspace and includes the illustrated HTML manual. Pass `-SkipTests` only for
an intentionally quick local packaging iteration; the default build runs the full test suite first.
Warehouse remains a source-only experimental workspace. OpenSeesPy and pymoo remain optional
developer integrations rather than installed binary dependencies.

## Run the Frame workspace

```powershell
cd go_struct_desktop
py -m pip install -e ".[dev,gui]"
go-struct-desktop
```

The desktop app opens with an editable portal-frame model. It supports `.goframe.json` files from
the Ruby dialog, and it writes the same input field names back to JSON.

Use `Model > Hybrid Frame-Truss Templates` to create a Flat, Sloping Flat, Mono, Gable,
Raised Bottom-Chord, or Curved panel truss on either Steel or Concrete Frame columns. The catalog
shows a dimensioned preview and lets the user choose Pratt, Howe, Warren, or X-braced webs before
creation. The generated chords/webs are Truss members, the columns are Frame members, and all sections
remain editable from the Members and Sections tables. Truss members must use nodal loads; the model
validator rejects member loads and released Truss ends. Template metadata records the current 2D,
bottom-chord-support, pinned-joint assumption so a future 3D generator can extend the same project data.

## Run the Beam workspace

```powershell
cd go_struct_desktop
py -m pip install -e ".[dev,gui]"
.\.venv\Scripts\go-struct-beam.exe
```

The Beam workspace opens with a two-span beam and writes `.gobeam.json` files. It accepts horizontal
members and transverse `Fy`/`Mz`, Local Y, or Global Y loads. This is a separate 1D solver, not a
restricted visual mode of the Frame solver; axial loads and non-horizontal members are reported as
invalid input. Canvas and Nodes-table editing lock every beam node to its common horizontal baseline.
Use `Beam > Add Span` to append a span from the right-most node, `Beam > Place ... support` to assign
supports, `Beam > Edit Selected Span Length` to retain downstream stations while resizing one span, or
`Beam > Insert Support in Span` to split a span at a station. Use `Beam Loads` to apply uniform or triangular loads to selected spans, or point forces/moments at one common relative span position; this keeps an unequal continuous beam aligned at, for example, 25% of every span. The Template Catalog presents a dimensioned beam preview and its
editable per-span length fields before the model is created. Its continuous-beam starter uses pinned intermediate
supports and a roller at the right end.

## Run the Truss workspace

```powershell
cd go_struct_desktop
py -m pip install -e ".[dev,gui]"
.\.venv\Scripts\go-struct-truss.exe
```

Alternatively, activate the virtual environment once with `.\.venv\Scripts\Activate.ps1`, then
run `go-struct-beam` or `go-struct-truss` without the path prefix.

The Truss workspace writes `.gotruss.json` files and uses a dedicated planar pin-jointed solver.
Members report tension-positive axial `N`; its axial-force diagram is green in tension and red in
compression for the active result selection, while the model members remain neutral. Apply only nodal `Fx/Fy` loads. Member loads, nodal
moments, self weight, and frame end releases are intentionally unavailable. Truss sections require only
`E` and `A`; the frame-only `I` and density fields are hidden. Use `Truss > New Template` to start a
Triangle, Warren, Pratt, Howe, or pitched Roof truss, then choose the span or panel width and height.
The canvas legend explicitly marks green as tension (`+N`) and red as compression (`-N`). Select `D` in
the result toolbar or `Deflected Shape` in the diagram view to show the solved truss deformation and its maximum displacement marker.
Use `Truss > Authoring` to assign the active section to a group of selected members, mirror half a
truss, adjust roof height, or rebuild a standard template with more/fewer panels. To model a roof line
load, select its chord members, choose `Convert Selected Chord Load to Nodes`, then enter the vertical
load per horizontal projected metre. The command reports the resultant and creates only nodal loads.
The Truss Template Catalog shows the topology drawing and all span/panel/height inputs together before
creating the editable model. Its profile forms offer Pratt, Howe, Warren, and X-braced web patterns, and
include Flat, Sloping Flat, Mono, Gable, Raised Bottom-Chord, and Curved forms in addition to the named
Warren/Pratt/Howe/Fink starters. The Member Forces table includes a
tension/compression state filter for rapid axial-force review.

## Canvas authoring

The workspace uses two stable toolbar rows: Modeling and Loading beside the file commands, then Analysis and Results below it. The loading group includes semantic icons for nodal force/moment, uniform/triangular member load, point force, and point moment: choose an icon, enter the values, then click one or more targets to place the same load repeatedly. The canvas shows a purple placement preview; press `Esc` or right-click to cancel the active tool. Truss keeps only its compatible nodal-force icon. The result diagram selector is a direct `Model`/`N`/`V`/`M`/`D`/`All`/`FBD` mode-button group, rather than a dropdown. Use the modeling tools to switch among Select, Node, Member, Split, support, load, and Pan. Node and Member tools use
the configured grid step and can snap to endpoints, member midpoints, or member intersections. Select objects by click or selection
box; choose Nodes, Members, or Both before selecting. A left-to-right window selects objects fully
inside it, while a right-to-left window selects crossing members too. Drag a selected node to move,
extend, or trim its connected members; press `Delete` and confirm to remove selected members or
nodes. `Ctrl+D`, `Ctrl+Z`, and `Ctrl+Y` duplicate, undo, and redo model changes. Canvas edits update
the same model shown in the input tables and require analysis to be run again.

For larger models, canvas interaction uses a separate lightweight path: while panning, zooming, or
dragging it draws only grid, member lines, and node points, then restores labels, loads, deformed
shape, contours, and diagram fills after 150 ms of pointer idle time. Cached model-space spatial
lookups keep node/member/load picking and midpoint/intersection snapping local to the cursor. Above
300 members labels and hover are limited to the selected member; above 2,000 members result overlays
are intentionally drawn for selected members only. This remains a QPainter backend; an OpenGL
renderer is a future implementation detail and does not change the solver or project files.

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
graph-side placement. `N`, `V`, and `M` always retain their solver values and solver signs: graph-side
flip changes only which side of a member receives the drawing. Auto/Manual diagram scale and `View > Fit Diagram`
also control presentation only. In Hybrid results, axial Truss diagrams and contour fills use green for
tension (`+N`) and red for compression (`-N`); Frame members keep their normal result colours. The Free body view accepts a single Case or Combo, never an Envelope, because
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
