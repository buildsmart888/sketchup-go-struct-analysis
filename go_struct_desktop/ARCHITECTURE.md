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

The UI owns editable tables, file dialogs, rendering, and presentation units such as mm. The core
owns validation, source units, stiffness calculations, and result semantics.

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

## Validation command

```powershell
cd go_struct_desktop
py -m pytest
```
