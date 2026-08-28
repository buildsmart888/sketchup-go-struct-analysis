"""Truss workspace entry point using the shared GO Struct authoring shell."""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QApplication, QInputDialog

from go_struct_core import TrussModel, analyze_truss_data, build_frame_postprocess

from .app import MainWindow, WorkspaceDefinition
from .examples import FrameExample
from .truss_canvas import TrussCanvas
from .truss_templates import howe_truss_template, pratt_truss_template, roof_truss_template, triangle_truss_template, warren_truss_template


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
        for mode in ("v_kg", "m_kg_m", "v_mm", "all"):
            button = self.diagram_buttons[mode]
            button.hide()
            for action in self.analysis_toolbar.actions():
                if self.analysis_toolbar.widgetForAction(action) is button:
                    action.setVisible(False)
                    break
        selector = self.results_panel.diagrams.quantity_selector
        for index in range(selector.count() - 1, -1, -1):
            if selector.itemData(index) != "n_kg":
                selector.removeItem(index)
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
