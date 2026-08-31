# GO Struct Analysis Workflow

The desktop workspace separates a project into explicit states rather than treating analysis as a hidden side effect.

1. **Start**: choose a blank project or an editable example from `File > New`.
2. **Define**: open `Analysis > Define Project Data` to maintain project data, sections, load cases, and combinations.
3. **Model and load**: author graphically or in the docked tables. Existing results become **Stale** after an edit.
4. **Check**: use `Analysis > Check Model`. Double-click a finding to select and fit its affected objects. Errors block Frame analysis.
5. **Analyze**: the status badge moves through `Analyzing...` and ends at `Results`, or reports a failure.
6. **Review**: choose a Case or Combination. Envelope remains available for diagrams, but not for Matrix/DOF or FBD equilibrium.
7. **Report**: export HTML, PDF, CSV tables, XLSX, canvas PNG, or canvas SVG from `Report`.

## Authoring additions

- Select one node and use `Model > Draw Member by Length / Angle` for precise geometry.
- `Spring` supports use `Kx`, `Ky`, and `Kr` in the Node property inspector or Nodes table. At least one stiffness must be positive.
- Distributed member loads accept a `Start x` and `End x`; leave End x as `0` in the table for a full-span load.
- `Model > Section / Material Catalog` applies editable steel, concrete, or timber starter properties to the active section.
- In the Frame workspace, choose `Model > Hybrid Frame-Truss Templates` for a roof truss carried by
  Steel or Concrete Frame columns. Chords and webs are axial-only Truss members; columns remain Frame members.
  Use the Members table or Properties dock to change a member between `Frame` and `Truss` when appropriate.
  Truss members cannot receive member loads or end releases; apply roof actions as nodal loads instead.
  The catalog separates chord profile, Pratt/Howe/Warren/X web pattern, and geometry. Its current template
  metadata explicitly records a 2D, bottom-chord-support, pinned-joint generator assumption for future 3D work.

## Advanced result views

- `Animate` animates the exaggerated solved deformation only; it does not change calculated displacements.
- `Stress` colours members from elastic top/bottom-fibre stress calculated from `N/A +/- M c/I`. Red is positive and blue is negative. This is a visual review aid, not a design-code check.
- `View > Section View` provides an isometric section preview for the selected member. Width/depth may be edited in the Sections table.

## Contour results

- Choose `N`, `V`, `M`, or `D`, then select `Contour` on the results toolbar. The canvas paints a sampled colour band along every member diagram and shows a matching legend.
- `Global` keeps one numeric range for every member, so colour intensity can be compared across the model. `Member` normalizes each member for local reading; selecting one member makes the legend show that member's numeric range.
- In `View > Display > Results`, choose either a signed convention (blue negative, red positive) or a sequential spectrum, plus `Auto`, `Detail`, or `Fast for large models`. Performance mode changes drawing samples only, never solver values or hover precision.
- `View > Selected Member Results` opens linked compact N, V, M, deflection, and elastic-stress charts. Clicking a member on the canvas selects it in this inspector.
- `N`, `V`, and `M` labels and values always use the solver sign. `N graph`, `V graph`, and `M graph` flip only the side on which each diagram is drawn. Hybrid Truss axial diagrams keep green tension (`+N`) and red compression (`-N`), including contour fill.

## Matrix viewer

`View > Matrix & DOF` displays global and reduced stiffness, DOF mapping, load vector, displacement vector, residual at free DOFs, and member local stiffness. It labels each member as Frame or Truss; a Truss member's local matrix has axial translation stiffness only. It only accepts an individual Load Case or Load Combination, because an Envelope is assembled from different governing states and is not one equilibrium system.
