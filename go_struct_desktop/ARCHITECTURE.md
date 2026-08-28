# Architecture

## Current boundaries

`src/go_struct_core` owns validated input models and numerical analysis only. It must not import
PySide, SketchUp, reporting, or file-dialog APIs. The public boundary for the current phase is:

```text
legacy GOFrame JSON -> FrameModel -> frame solver -> JSON-compatible result
```

The PySide workspace is a separate consumer of that boundary:

```text
FrameInputPanel -> FrameModel -> frame solver -> FrameResultsPanel
```

Before results reach the UI, `build_frame_postprocess()` samples each member for N/V/M and FE
deflection, records extrema, and creates governing-combination envelope data. This keeps diagram
math, sign conventions, and diagnostics independent from PySide.

The UI owns editable tables, file dialogs, canvas authoring, rendering, and presentation units such
as mm. The core owns validation, source units, stiffness calculations, and result semantics.

Canvas authoring emits a complete JSON-compatible model change to the main window. The main window
updates `FrameInputPanel`, which remains the model source of truth and sends the refreshed model
back to the canvas and results panel. The main window records compatible model snapshots for
undo/redo. This keeps mouse authoring and table editing synchronized.

The data contract mirrors `go_struct_analysis/goframe.rb` and the `collectData()` function in
`go_struct_analysis/templates/goframe_dialog.html`.

## Planned consumers

- Phase 3: Beam and Truss solvers use the same model/result and validation conventions.
- Phase 4: report and export services consume JSON-compatible analysis results.
- Phase 5: a Ruby bridge sends model JSON to a Python process and stores its result in existing
  `GOStructAnalysis` BIM attributes.
- Phase 6: design-code checks consume solver demand results; they do not live inside the solver.

## Compatibility rules

- Preserve the current sign convention and unit conversion from the Ruby GOFrame solver.
- Do not mutate input dictionaries while parsing combinations or solving.
- New properties must have defaults or a migration path before they are written back to a model.
- The result envelope stores the signed value with greatest absolute magnitude, matching Ruby.
- Member diagrams use tension-positive axial force and the legacy GOFrame local V/M display signs.
- Torsion is outside the 2D solver scope and must not be represented by `Rz`.

## Validation command

```powershell
cd go_struct_desktop
py -m pytest
```
