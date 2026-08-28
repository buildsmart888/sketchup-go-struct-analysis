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
from .template_browser import TemplateBrowserDialog, TemplateOption, TemplateParameter


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
        edit_span = QAction("Edit Selected Span Length", self)
        edit_span.setToolTip("Resize one selected span and retain downstream span lengths")
        edit_span.triggered.connect(self._edit_selected_span)
        insert_support = QAction("Insert Support in Span", self)
        insert_support.setToolTip("Split a span at a station and assign a support")
        insert_support.triggered.connect(self._insert_support)
        menu.addAction(edit_span)
        menu.addAction(insert_support)
        templates = menu.addMenu("New Template")
        for title, factory in (("Cantilever", self._new_cantilever), ("Simply Supported", self._new_simply_supported), ("Continuous Beam", self._new_continuous)):
            action = QAction(title, self)
            action.triggered.connect(factory)
            templates.addAction(action)
        catalog = QAction("Template Catalog", self)
        catalog.setToolTip("Browse beam starters with a short structural preview")
        catalog.triggered.connect(self._show_template_catalog)
        menu.addAction(catalog)
        loads = menu.addMenu("Beam Loads")
        full_udl = QAction("Apply Full-Span UDL to Selected", self)
        full_udl.triggered.connect(self._apply_full_span_udl)
        point_force = QAction("Place Point Force", self)
        point_force.triggered.connect(lambda: self.results_panel.canvas.set_tool("member_load"))
        point_moment = QAction("Place Point Moment", self)
        point_moment.triggered.connect(lambda: self.results_panel.canvas.set_tool("member_load"))
        loads.addAction(full_udl)
        loads.addAction(point_force)
        loads.addAction(point_moment)
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

    def _edit_selected_span(self) -> None:
        unit = self.input_panel.unit_system
        length, accepted = QInputDialog.getDouble(self, "Edit beam span", f"New span length ({unit.length_unit})", 5.0, 0.001, 1.0e6, 3)
        if accepted:
            self.results_panel.canvas.resize_selected_span(length / unit.length_factor)

    def _insert_support(self) -> None:
        unit = self.input_panel.unit_system
        location, accepted = QInputDialog.getDouble(self, "Insert beam support", f"Station x ({unit.length_unit})", 2.5, -1.0e6, 1.0e6, 3)
        if not accepted:
            return
        supports = ("Pinned", "RollerX", "Fixed")
        support, accepted = QInputDialog.getItem(self, "Insert beam support", "Support", supports, 1, False)
        if accepted:
            self.results_panel.canvas.insert_support(location / unit.length_factor, support)

    def _apply_full_span_udl(self) -> None:
        canvas = self.results_panel.canvas
        members = canvas.selection["members"]
        if len(members) != 1:
            self.statusBar().showMessage("Select exactly one span before applying a full-span UDL.", 4000)
            return
        cases = list(self.input_panel.model_data().get("loadcases", [])) or ["DL"]
        load_case, accepted = QInputDialog.getItem(self, "Full-span UDL", "Load case", cases, 0, False)
        if not accepted:
            return
        unit = self.input_panel.unit_system
        load, accepted = QInputDialog.getDouble(self, "Full-span UDL", f"Load ({unit.distributed_label()}, negative is downward)", -10.0, -1.0e9, 1.0e9, 4)
        if accepted:
            canvas.add_member_load(members[0], {"lcase": load_case, "type": "Distributed", "dir": "Global Y", "w1": load / unit.distributed_factor, "w2": load / unit.distributed_factor})

    def _new_cantilever(self) -> None:
        self._set_template(cantilever_template, "Cantilever")

    def _new_simply_supported(self) -> None:
        self._set_template(simply_supported_template, "Simply supported")

    def _new_continuous(self) -> None:
        spans, accepted = QInputDialog.getInt(self, "Continuous beam", "Number of spans", 2, 2, 50)
        if not accepted:
            return
        unit = self.input_panel.unit_system
        span_m, accepted = QInputDialog.getDouble(self, "Continuous beam", f"Each span ({unit.length_unit})", 5.0, 0.001, 1.0e6, 3)
        if accepted:
            self.set_model(continuous_beam_template(spans, span_m / unit.length_factor))
            self.run_analysis()
            self.statusBar().showMessage(f"New continuous beam: {spans} spans")

    def _show_template_catalog(self) -> None:
        options = (
            TemplateOption("cantilever", "Cantilever", "Fixed at one end; ideal for a bracket or overhang.", "cantilever", (TemplateParameter("span_m", "Span (m)", 5.0),)),
            TemplateOption("simple", "Simply Supported", "Pinned and roller supports with one editable span.", "simple", (TemplateParameter("span_m", "Span (m)", 6.0),)),
            TemplateOption(
                "continuous",
                "Continuous Beam",
                "Continuous spans with intermediate pinned supports and a roller at the right end.",
                "continuous",
                (TemplateParameter("span_count", "Number of spans", 2, 2, 50, integer=True), TemplateParameter("span_m", "Each span (m)", 5.0)),
            ),
        )
        dialog = TemplateBrowserDialog("Beam Template Catalog", options, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        values = dialog.selected_values()
        key = dialog.selected_key()
        if key == "cantilever":
            model = cantilever_template(float(values["span_m"]))
        elif key == "simple":
            model = simply_supported_template(float(values["span_m"]))
        elif key == "continuous":
            model = continuous_beam_template(int(values["span_count"]), float(values["span_m"]))
        else:
            return
        self.set_model(model)
        self.run_analysis()
        self.statusBar().showMessage(f"New {key} beam from Template Catalog")

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
