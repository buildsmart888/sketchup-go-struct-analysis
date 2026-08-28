"""Beam workspace entry point built on the shared GO Struct desktop shell."""

from __future__ import annotations

import sys
from typing import Any, Mapping

from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QApplication, QInputDialog

from go_struct_core import BeamModel, analyze_beam_data, build_frame_postprocess

from .app import MainWindow, WorkspaceDefinition
from .beam_canvas import BeamCanvas
from .beam_templates import cantilever_template, continuous_beam_template, simply_supported_template
from .examples import BUILT_IN_BEAM_EXAMPLES


def default_beam_model() -> dict[str, Any]:
    """Start with a continuous beam so V/M/D are immediately meaningful."""
    return BUILT_IN_BEAM_EXAMPLES[2].model()


BEAM_WORKSPACE = WorkspaceDefinition(
    key="beam",
    title="GO Struct Desktop | 1D Beam",
    model_name="beam",
    default_model=default_beam_model,
    normalize_model=lambda model: BeamModel.from_dict(model).to_dict(),
    analyze=analyze_beam_data,
    postprocess=build_frame_postprocess,
    examples=BUILT_IN_BEAM_EXAMPLES,
    file_extension=".gobeam.json",
    canvas_class=BeamCanvas,
)


class BeamMainWindow(MainWindow):
    """Dedicated entry point while retaining the common editor and result docks."""

    def __init__(self) -> None:
        super().__init__(BEAM_WORKSPACE)
        self._add_beam_authoring_actions()

    def _add_beam_authoring_actions(self) -> None:
        menu = self.menuBar().addMenu("Beam")
        add_span = QAction("Add Span", self)
        add_span.setToolTip("Append a horizontal span from the right-most beam node")
        add_span.triggered.connect(self._add_span)
        menu.addAction(add_span)
        templates = menu.addMenu("New Template")
        for title, factory in (("Cantilever", self._new_cantilever), ("Simply Supported", self._new_simply_supported), ("Continuous Beam", self._new_continuous)):
            action = QAction(title, self)
            action.triggered.connect(factory)
            templates.addAction(action)
        menu.addSeparator()
        for support in ("Fixed", "Pinned", "RollerX"):
            action = QAction(f"Place {support} support", self)
            action.triggered.connect(lambda _checked=False, value=support: self.results_panel.canvas.set_pending_support(value))
            menu.addAction(action)
        self.modeling_toolbar.addAction(add_span)

    def _model_edited(self) -> None:
        if self._suppress_model_events:
            return
        model = self.input_panel.model_data()
        nodes = model.get("nodes", [])
        if nodes:
            baseline = float(nodes[0]["y"])
            if any(abs(float(node["y"]) - baseline) > 1.0e-12 for node in nodes):
                for node in nodes:
                    node["y"] = baseline
                self._set_input_model(model)
                self.statusBar().showMessage("Beam nodes remain on one horizontal baseline.")
        super()._model_edited()

    def _add_span(self) -> None:
        unit = self.input_panel.unit_system
        length, accepted = QInputDialog.getDouble(self, "Add beam span", f"Span length ({unit.length_unit})", 5.0, 0.001, 1.0e6, 3)
        if accepted:
            self.results_panel.canvas.add_span(length / unit.length_factor, section_id=self.results_panel.active_section.currentData())

    def _new_cantilever(self) -> None:
        self._set_template(cantilever_template, "Cantilever")

    def _new_simply_supported(self) -> None:
        self._set_template(simply_supported_template, "Simply supported")

    def _new_continuous(self) -> None:
        spans, accepted = QInputDialog.getInt(self, "Continuous beam", "Number of spans", 2, 2, 50)
        if accepted:
            self.set_model(continuous_beam_template(spans))
            self.run_analysis()
            self.statusBar().showMessage(f"New continuous beam: {spans} spans")

    def _set_template(self, factory, label: str) -> None:  # type: ignore[no-untyped-def]
        self.set_model(factory())
        self.run_analysis()
        self.statusBar().showMessage(f"New {label.lower()} beam")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("GO Struct Beam")
    app.setFont(QFont("Segoe UI", 10))
    window = BeamMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
