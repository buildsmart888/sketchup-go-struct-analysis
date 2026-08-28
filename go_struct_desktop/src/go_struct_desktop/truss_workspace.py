"""Truss workspace entry point using the shared GO Struct authoring shell."""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from go_struct_core import TrussModel, analyze_truss_data, build_frame_postprocess

from .app import MainWindow, WorkspaceDefinition
from .examples import FrameExample
from .truss_canvas import TrussCanvas
from .truss_templates import howe_truss_template, pratt_truss_template, roof_truss_template, triangle_truss_template, warren_truss_template
from .template_browser import TemplateBrowserDialog, TemplateOption, TemplateParameter


def _loaded_triangle() -> dict[str, Any]:
    model = triangle_truss_template()
    model["nloads"] = [{"node": 3, "lcase": "DL", "fx": 0.0, "fy": -20.0, "mz": 0.0}]
    return model


def _loaded_warren() -> dict[str, Any]:
    model = warren_truss_template()
    top_nodes = [node for node in model["nodes"] if float(node["y"]) > 0.0]
    model["nloads"] = [{"node": int(node["id"]), "lcase": "DL", "fx": 0.0, "fy": -8.0, "mz": 0.0} for node in top_nodes]
    return model


def _loaded_pratt() -> dict[str, Any]:
    model = pratt_truss_template()
    top_nodes = [node for node in model["nodes"] if float(node["y"]) > 0.0]
    model["nloads"] = [{"node": int(node["id"]), "lcase": "DL", "fx": 0.0, "fy": -8.0, "mz": 0.0} for node in top_nodes[1:-1]]
    return model


def _loaded_howe() -> dict[str, Any]:
    model = howe_truss_template()
    top_nodes = [node for node in model["nodes"] if float(node["y"]) > 0.0]
    model["nloads"] = [{"node": int(node["id"]), "lcase": "DL", "fx": 0.0, "fy": -8.0, "mz": 0.0} for node in top_nodes[1:-1]]
    return model


def _loaded_roof() -> dict[str, Any]:
    model = roof_truss_template()
    top_nodes = [node for node in model["nodes"] if float(node["y"]) > 0.0]
    model["nloads"] = [{"node": int(node["id"]), "lcase": "DL", "fx": 0.0, "fy": -6.0, "mz": 0.0} for node in top_nodes]
    return model


TRUSS_EXAMPLES: tuple[FrameExample, ...] = (
    FrameExample("truss_triangle", "1. Triangle Truss", "Three-bar truss with a symmetric apex load.", _loaded_triangle, "case:DL", "n_kg"),
    FrameExample("truss_warren", "2. Warren Truss", "Four-panel Warren truss with vertical chord loads.", _loaded_warren, "case:DL", "n_kg"),
    FrameExample("truss_pratt", "3. Pratt Truss", "Four-panel Pratt truss with top-chord nodal loads.", _loaded_pratt, "case:DL", "n_kg"),
    FrameExample("truss_howe", "4. Howe Truss", "Four-panel Howe truss with top-chord nodal loads.", _loaded_howe, "case:DL", "n_kg"),
    FrameExample("truss_roof", "5. Roof Truss", "Pitched roof truss with distributed nodal roof loading.", _loaded_roof, "case:DL", "n_kg"),
)


def default_truss_model() -> dict[str, Any]:
    return TRUSS_EXAMPLES[1].model()


TRUSS_WORKSPACE = WorkspaceDefinition(
    key="truss",
    title="GO Struct Desktop | 2D Truss",
    model_name="truss",
    default_model=default_truss_model,
    normalize_model=lambda model: TrussModel.from_dict(model).to_dict(),
    analyze=analyze_truss_data,
    postprocess=build_frame_postprocess,
    examples=TRUSS_EXAMPLES,
    file_extension=".gotruss.json",
    canvas_class=TrussCanvas,
)


class TrussMainWindow(MainWindow):
    """Dedicated truss entry point with frame-only controls removed from the active surface."""

    def __init__(self) -> None:
        super().__init__(TRUSS_WORKSPACE)
        self._configure_truss_ui()
        self._add_truss_actions()

    def _configure_truss_ui(self) -> None:
        self.results_panel._tool_buttons["member_load"].hide()
        for mode in ("v_kg", "m_kg_m", "all"):
            button = self.diagram_buttons[mode]
            button.hide()
            for action in self.analysis_toolbar.actions():
                if self.analysis_toolbar.widgetForAction(action) is button:
                    action.setVisible(False)
                    break
        selector = self.results_panel.diagrams.quantity_selector
        for index in range(selector.count() - 1, -1, -1):
            if selector.itemData(index) not in {"n_kg", "v_mm"}:
                selector.removeItem(index)
        deflection_index = selector.findData("v_mm")
        if deflection_index >= 0:
            selector.setItemText(deflection_index, "Deflected Shape")
        self.diagram_buttons["v_mm"].setToolTip("Show the deflected truss shape from nodal displacement")
        member_load_tab = self.input_panel.tabs.indexOf(self.input_panel.element_loads)
        self.input_panel.tabs.setTabVisible(member_load_tab, False)
        self.input_panel.nodal_loads.table.setColumnHidden(4, True)
        self.input_panel.elements.table.setColumnHidden(4, True)
        self.input_panel.sections.table.setColumnHidden(3, True)
        self.input_panel.sections.table.setColumnHidden(4, True)
        self.input_panel.self_weight.setVisible(False)
        self.inspector.node_mz.setEnabled(False)
        self.inspector.member_release.setEnabled(False)
        self.inspector.batch_release.setEnabled(False)
        for column in (2, 3, 5, 6):
            self.results_panel.member_results.setColumnHidden(column, True)
        self.results_panel.member_results.setHorizontalHeaderItem(1, self.results_panel.member_results.horizontalHeaderItem(1).clone())
        self.results_panel.member_results.horizontalHeaderItem(1).setText("Axial N at I")
        self.results_panel.member_results.horizontalHeaderItem(4).setText("Axial N at J")

    def _add_truss_actions(self) -> None:
        menu = self.menuBar().addMenu("Truss")
        templates = menu.addMenu("New Template")
        for title, action in (("Triangle", self._new_triangle), ("Warren", self._new_warren), ("Pratt", self._new_pratt), ("Howe", self._new_howe), ("Roof", self._new_roof)):
            item = QAction(title, self)
            item.triggered.connect(action)
            templates.addAction(item)
        catalog = QAction("Template Catalog", self)
        catalog.setToolTip("Browse truss starters with their intended force path")
        catalog.triggered.connect(self._show_template_catalog)
        menu.addAction(catalog)
        authoring = menu.addMenu("Authoring")
        assign_section = QAction("Assign Active Section to Selected", self)
        assign_section.triggered.connect(self.results_panel.canvas.assign_active_section_to_selection)
        mirror_vertical = QAction("Mirror Selection Vertically", self)
        mirror_vertical.triggered.connect(lambda: self.results_panel.canvas.mirror_selection("vertical"))
        roof_height = QAction("Set Roof Height", self)
        roof_height.triggered.connect(self._set_roof_height)
        roof_load = QAction("Convert Selected Chord Load to Nodes", self)
        roof_load.setToolTip("Convert a vertical line load over selected roof-chord members into equivalent nodal loads")
        roof_load.triggered.connect(self._convert_roof_load)
        panels = QAction("Regenerate Template Panels", self)
        panels.setToolTip("Rebuild a template with more or fewer panels; existing nodal loads are cleared")
        panels.triggered.connect(self._regenerate_template_panels)
        authoring.addAction(assign_section)
        authoring.addAction(mirror_vertical)
        authoring.addAction(roof_height)
        authoring.addAction(roof_load)
        authoring.addAction(panels)
        menu.addSeparator()
        for support in ("Pinned", "RollerX", "RollerY", "Fixed"):
            item = QAction(f"Place {support} support", self)
            item.triggered.connect(lambda _checked=False, value=support: self.results_panel.canvas.set_pending_support(value))
            menu.addAction(item)

    def _new_triangle(self) -> None:
        dimensions = self._dimensions("Triangle truss", 6.0, 3.0)
        if dimensions:
            self._load_template(triangle_truss_template(*dimensions), "triangle truss")

    def _new_warren(self) -> None:
        dimensions = self._panel_dimensions("Warren truss", 2.0)
        if dimensions:
            panels, panel_m, height_m = dimensions
            self._load_template(warren_truss_template(panels, panel_m, height_m), f"Warren truss: {panels} panels")

    def _new_pratt(self) -> None:
        dimensions = self._panel_dimensions("Pratt truss", 2.5)
        if dimensions:
            panels, panel_m, height_m = dimensions
            self._load_template(pratt_truss_template(panels, panel_m, height_m), f"Pratt truss: {panels} panels")

    def _new_howe(self) -> None:
        dimensions = self._panel_dimensions("Howe truss", 2.5)
        if dimensions:
            panels, panel_m, height_m = dimensions
            self._load_template(howe_truss_template(panels, panel_m, height_m), f"Howe truss: {panels} panels")

    def _new_roof(self) -> None:
        dimensions = self._panel_dimensions("Roof truss", 3.0, even_panels=True)
        if dimensions:
            panels, panel_m, height_m = dimensions
            self._load_template(roof_truss_template(panels, panel_m, height_m), f"Roof truss: {panels} panels")

    def _set_roof_height(self) -> None:
        unit = self.input_panel.unit_system
        height, accepted = QInputDialog.getDouble(self, "Set roof height", f"Roof height ({unit.length_unit})", 3.0, 0.001, 10000.0, 3)
        if accepted:
            self.results_panel.canvas.set_roof_height(height / unit.length_factor)

    def _convert_roof_load(self) -> None:
        cases = list(self.input_panel.model_data().get("loadcases", [])) or ["DL"]
        load_case, accepted = QInputDialog.getItem(self, "Roof chord load", "Load case", cases, 0, False)
        if not accepted:
            return
        unit = self.input_panel.unit_system
        intensity, accepted = QInputDialog.getDouble(
            self,
            "Roof chord load",
            f"Vertical line load ({unit.distributed_label()}, negative is downward)",
            -10.0,
            -1.0e9,
            1.0e9,
            4,
        )
        if accepted:
            self.results_panel.canvas.distribute_roof_load(intensity / unit.distributed_factor, load_case)

    def _show_template_catalog(self) -> None:
        options = (
            TemplateOption("triangle", "Triangle Truss", "Three-bar truss for a compact, determinate system.", "triangle", (TemplateParameter("span_m", "Span (m)", 6.0), TemplateParameter("height_m", "Height (m)", 3.0))),
            TemplateOption("warren", "Warren Truss", "Alternating triangular web system for uniform panel spacing.", "warren", (TemplateParameter("panel_count", "Number of panels", 4, 2, 50, integer=True), TemplateParameter("panel_m", "Panel width (m)", 3.0), TemplateParameter("height_m", "Height (m)", 2.0))),
            TemplateOption("pratt", "Pratt Truss", "Verticals and inward diagonals toward the centre.", "pratt", (TemplateParameter("panel_count", "Number of panels", 4, 2, 50, integer=True), TemplateParameter("panel_m", "Panel width (m)", 3.0), TemplateParameter("height_m", "Height (m)", 2.5))),
            TemplateOption("howe", "Howe Truss", "Verticals and reversed diagonal direction from Pratt.", "howe", (TemplateParameter("panel_count", "Number of panels", 4, 2, 50, integer=True), TemplateParameter("panel_m", "Panel width (m)", 3.0), TemplateParameter("height_m", "Height (m)", 2.5))),
            TemplateOption("roof", "Pitched Roof Truss", "Pitched top chord with bottom chord and web bracing; it requires an even panel count.", "roof", (TemplateParameter("panel_count", "Number of panels (even)", 4, 2, 50, integer=True), TemplateParameter("panel_m", "Panel width (m)", 3.0), TemplateParameter("height_m", "Height (m)", 3.0))),
        )
        dialog = TemplateBrowserDialog("Truss Template Catalog", options, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        values = dialog.selected_values()
        key = dialog.selected_key()
        if key == "triangle":
            model = triangle_truss_template(float(values["span_m"]), float(values["height_m"]))
        elif key == "warren":
            model = warren_truss_template(int(values["panel_count"]), float(values["panel_m"]), float(values["height_m"]))
        elif key == "pratt":
            model = pratt_truss_template(int(values["panel_count"]), float(values["panel_m"]), float(values["height_m"]))
        elif key == "howe":
            model = howe_truss_template(int(values["panel_count"]), float(values["panel_m"]), float(values["height_m"]))
        elif key == "roof":
            panels = int(values["panel_count"])
            if panels % 2:
                self.statusBar().showMessage("Roof template requires an even number of panels.", 4000)
                return
            model = roof_truss_template(panels, float(values["panel_m"]), float(values["height_m"]))
        else:
            return
        self._load_template(model, f"{key.title()} truss from Template Catalog")

    def _regenerate_template_panels(self) -> None:
        model = self.input_panel.model_data()
        template = model.get("projectInfo", {}).get("trussTemplate", {})
        kind = str(template.get("kind", ""))
        factories = {"warren": warren_truss_template, "pratt": pratt_truss_template, "howe": howe_truss_template, "roof": roof_truss_template}
        factory = factories.get(kind)
        if factory is None:
            self.statusBar().showMessage("Panel regeneration is available for Warren, Pratt, Howe, and Roof templates.", 4500)
            return
        current_panels = int(template.get("panel_count", 4))
        panels, accepted = QInputDialog.getInt(self, "Regenerate truss panels", "Number of panels", current_panels, 2, 50)
        if not accepted:
            return
        if kind == "roof" and panels % 2:
            self.statusBar().showMessage("Roof truss requires an even number of panels.", 4000)
            return
        question = "Regenerate the template geometry? Existing nodal loads are cleared because their old node IDs may not exist."
        if QMessageBox.question(self, "Regenerate truss panels", question, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        panel_m, height_m = float(template.get("panel_m", 3.0)), float(template.get("height_m", 2.5))
        rebuilt = factory(panels, panel_m, height_m)
        rebuilt["sections"] = model.get("sections", rebuilt["sections"])
        rebuilt["loadcases"] = model.get("loadcases", rebuilt["loadcases"])
        rebuilt["loadcombos"] = model.get("loadcombos", rebuilt["loadcombos"])
        rebuilt["settings"] = model.get("settings", rebuilt["settings"])
        for key in ("project", "company", "engineer", "location", "units"):
            rebuilt["projectInfo"][key] = model.get("projectInfo", {}).get(key, rebuilt["projectInfo"].get(key, ""))
        self._load_template(rebuilt, f"{kind.title()} truss: {panels} panels")

    def _dimensions(self, title: str, default_width: float, default_height: float) -> tuple[float, float] | None:
        width, accepted = QInputDialog.getDouble(self, title, "Span (m)", default_width, 0.1, 10000.0, 3)
        if not accepted:
            return None
        height, accepted = QInputDialog.getDouble(self, title, "Height (m)", default_height, 0.1, 10000.0, 3)
        return (width, height) if accepted else None

    def _panel_dimensions(self, title: str, default_height: float, even_panels: bool = False) -> tuple[int, float, float] | None:
        panels, accepted = QInputDialog.getInt(self, title, "Number of panels", 4, 2, 50)
        if not accepted:
            return None
        if even_panels and panels % 2:
            self.statusBar().showMessage("Roof truss requires an even number of panels", 4000)
            return None
        panel_m, accepted = QInputDialog.getDouble(self, title, "Panel width (m)", 3.0, 0.1, 10000.0, 3)
        if not accepted:
            return None
        height, accepted = QInputDialog.getDouble(self, title, "Height (m)", default_height, 0.1, 10000.0, 3)
        return (panels, panel_m, height) if accepted else None

    def _load_template(self, model: dict[str, Any], message: str) -> None:
        self.set_model(model)
        self.run_analysis()
        self.statusBar().showMessage(f"New {message}")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("GO Struct Truss")
    app.setFont(QFont("Segoe UI", 10))
    window = TrussMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
