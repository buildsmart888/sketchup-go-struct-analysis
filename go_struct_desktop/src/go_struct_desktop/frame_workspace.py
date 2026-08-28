"""The first reusable PySide workspace: 2D rigid-frame analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from go_struct_core import FrameModel

from .canvas import FrameCanvas
from .diagrams import FrameDiagramsPanel
from .editors import CombinationEditor, Column, ProjectEditor, TableEditor, as_float, as_int


SUPPORTS = ("Free", "Pinned", "Fixed", "RollerX", "RollerY")
RELEASES = ("Rigid-Rigid", "Pin-Rigid", "Rigid-Pin", "Pin-Pin")
DIRECTIONS = ("Local Y", "Global Y")


def default_frame_model() -> dict[str, Any]:
    return {
        "projectInfo": {"name": "Portal Frame", "project": "", "company": "", "engineer": "", "location": ""},
        "settings": {"include_self_weight": False},
        "nodes": [
            {"id": 1, "x": 0.0, "y": 0.0, "support": "Fixed"},
            {"id": 2, "x": 6.0, "y": 0.0, "support": "Fixed"},
            {"id": 3, "x": 0.0, "y": 4.0, "support": "Free"},
            {"id": 4, "x": 6.0, "y": 4.0, "support": "Free"},
        ],
        "sections": [
            {"id": 1, "e": 2000000000.0, "a": 900.0, "i": 67500.0, "density": 2400.0},
            {"id": 2, "e": 2000000000.0, "a": 1500.0, "i": 312500.0, "density": 2400.0},
        ],
        "elements": [
            {"id": 1, "n1": 1, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 2, "n1": 2, "n2": 4, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 3, "n1": 3, "n2": 4, "sec": 2, "release": "Rigid-Rigid"},
        ],
        "loadcases": ["DL", "LL"],
        "loadcombos": [
            {"name": "Service", "factors": {"DL": 1.0, "LL": 1.0}},
            {"name": "ULS", "factors": {"DL": 1.2, "LL": 1.6}},
        ],
        "nloads": [{"node": 3, "lcase": "LL", "fx": 10.0, "fy": 0.0, "mz": 0.0}],
        "eloads": [{"elem": 3, "lcase": "DL", "dir": "Global Y", "w1": -20.0, "w2": -20.0}],
    }


class FrameInputPanel(QWidget):
    """Model input tabs. This class has no solver or file-system knowledge."""

    model_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._synchronizing_cases = False
        self.project = ProjectEditor(self)
        self.self_weight = QCheckBox("Include self weight", self)
        self.nodes = TableEditor(
            [Column("ID", "id", 1, as_int), Column("X (m)", "x", 0.0, as_float), Column("Y (m)", "y", 0.0, as_float), Column("Support", "support", "Free", choices=SUPPORTS)],
            self,
        )
        self.elements = TableEditor(
            [Column("ID", "id", 1, as_int), Column("Node I", "n1", 1, as_int), Column("Node J", "n2", 2, as_int), Column("Section", "sec", 1, as_int), Column("Release", "release", "Rigid-Rigid", choices=RELEASES)],
            self,
        )
        self.sections = TableEditor(
            [Column("ID", "id", 1, as_int), Column("E (kg/m2)", "e", 2.0e9, as_float), Column("A (cm2)", "a", 900.0, as_float), Column("I (cm4)", "i", 67500.0, as_float), Column("Density (kg/m3)", "density", 0.0, as_float)],
            self,
        )
        self.load_cases = TableEditor([Column("Load case", "name", "DL")], self)
        self.combinations = CombinationEditor(self)
        self.nodal_loads = TableEditor(
            [Column("Node", "node", 1, as_int), Column("Load case", "lcase", "DL", choices=("DL",)), Column("Fx (kg)", "fx", 0.0, as_float), Column("Fy (kg)", "fy", 0.0, as_float), Column("Mz (kg-m)", "mz", 0.0, as_float)],
            self,
        )
        self.element_loads = TableEditor(
            [Column("Element", "elem", 1, as_int), Column("Load case", "lcase", "DL", choices=("DL",)), Column("Direction", "dir", "Local Y", choices=DIRECTIONS), Column("W1 (kg/m)", "w1", 0.0, as_float), Column("W2 (kg/m)", "w2", 0.0, as_float)],
            self,
        )
        self._build_layout()
        for editor in (self.project, self.nodes, self.elements, self.sections, self.nodal_loads, self.element_loads, self.combinations):
            editor.changed.connect(self.model_changed)
        self.self_weight.toggled.connect(self.model_changed)
        self.load_cases.changed.connect(self._on_load_cases_changed)

    def _build_layout(self) -> None:
        tabs = QTabWidget(self)
        tabs.addTab(self._general_tab(), "Project")
        tabs.addTab(self.nodes, "Nodes")
        tabs.addTab(self.elements, "Members")
        tabs.addTab(self.sections, "Sections")
        tabs.addTab(self.load_cases, "Load Cases")
        tabs.addTab(self.combinations, "Combinations")
        tabs.addTab(self.nodal_loads, "Nodal Loads")
        tabs.addTab(self.element_loads, "Member Loads")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(tabs)

    def _general_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.project)
        layout.addWidget(self.self_weight)
        layout.addStretch()
        return tab

    def set_model(self, model: Mapping[str, Any]) -> None:
        parsed = FrameModel.from_dict(model).to_dict()
        self.project.set_values(parsed.get("projectInfo", {}))
        self.self_weight.blockSignals(True)
        self.self_weight.setChecked(parsed.get("settings", {}).get("include_self_weight") is True)
        self.self_weight.blockSignals(False)
        self.nodes.set_rows(parsed["nodes"])
        self.elements.set_rows(parsed["elements"])
        self.sections.set_rows(parsed["sections"])
        self.load_cases.set_rows([{"name": value} for value in parsed["loadcases"]])
        self._synchronize_load_cases()
        self.combinations.set_rows(parsed["loadcombos"])
        self.nodal_loads.set_rows(parsed["nloads"])
        self.element_loads.set_rows(parsed["eloads"])
        self.model_changed.emit()

    def model_data(self) -> dict[str, Any]:
        return {
            "projectInfo": self.project.values(),
            "settings": {"include_self_weight": self.self_weight.isChecked()},
            "nodes": self.nodes.values(),
            "elements": self.elements.values(),
            "sections": self.sections.values(),
            "loadcases": self._load_case_names(),
            "loadcombos": self.combinations.values(),
            "nloads": self.nodal_loads.values(),
            "eloads": self.element_loads.values(),
        }

    def _load_case_names(self) -> list[str]:
        return [row["name"] for row in self.load_cases.values() if row["name"]] or ["DL"]

    def _on_load_cases_changed(self) -> None:
        self._synchronize_load_cases()
        self.model_changed.emit()

    def _synchronize_load_cases(self) -> None:
        if self._synchronizing_cases:
            return
        self._synchronizing_cases = True
        load_cases = self._load_case_names()
        self.nodal_loads.set_choices("lcase", load_cases)
        self.element_loads.set_choices("lcase", load_cases)
        self.combinations.set_load_cases(load_cases)
        self._synchronizing_cases = False


class FrameResultsPanel(QWidget):
    """Visual and tabular output for an already-computed frame analysis."""

    model_change_requested = Signal(object)
    canvas_status_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model: Mapping[str, Any] = {}
        self._analysis: Mapping[str, Any] | None = None
        self._postprocess: Mapping[str, Any] | None = None
        self.canvas = FrameCanvas(self)
        self.canvas_tools = QButtonGroup(self)
        self.canvas_tools.setExclusive(True)
        self._tool_buttons: dict[str, QToolButton] = {}
        for tool, label, tooltip in (
            ("select", "Select", "Select nodes or members"),
            ("node", "Node", "Create a snapped node"),
            ("member", "Member", "Draw a member between nodes"),
            ("pan", "Pan", "Pan the canvas"),
        ):
            button = QToolButton(self)
            button.setText(label)
            button.setToolTip(tooltip)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, value=tool: self.canvas.set_tool(value))
            self.canvas_tools.addButton(button)
            self._tool_buttons[tool] = button
        self._tool_buttons["select"].setChecked(True)
        self.grid_toggle = QCheckBox("Grid", self)
        self.grid_toggle.setChecked(True)
        self.snap_toggle = QCheckBox("Snap", self)
        self.snap_toggle.setChecked(True)
        self.snap_nodes_toggle = QCheckBox("Nodes", self)
        self.snap_nodes_toggle.setChecked(True)
        self.grid_spacing = QDoubleSpinBox(self)
        self.grid_spacing.setRange(0.05, 100.0)
        self.grid_spacing.setDecimals(3)
        self.grid_spacing.setSingleStep(0.25)
        self.grid_spacing.setValue(1.0)
        self.grid_spacing.setSuffix(" m")
        self.active_section = QComboBox(self)
        self.fit_button = QToolButton(self)
        self.fit_button.setText("Fit")
        self.fit_button.setToolTip("Fit model to canvas")
        self.selection_label = QLabel("Selection: none", self)
        self.result_selector = QComboBox(self)
        self.canvas_diagram_selector = QComboBox(self)
        self.canvas_diagram_selector.addItem("No diagrams", "none")
        self.canvas_diagram_selector.addItem("Axial N", "n_kg")
        self.canvas_diagram_selector.addItem("Shear V", "v_kg")
        self.canvas_diagram_selector.addItem("Moment M", "m_kg_m")
        self.canvas_diagram_selector.addItem("FE deflection", "v_mm")
        self.canvas_diagram_selector.addItem("All diagrams", "all")
        self.diagram_values_toggle = QCheckBox("Values", self)
        self.deformed_toggle = QCheckBox("Deformed", self)
        self.deformed_toggle.setChecked(True)
        self.summary = self._result_table(["Max displacement (mm)", "Max axial (kg)", "Max moment (kg-m)"], 1)
        self.node_results = self._result_table(["Node", "dx (mm)", "dy (mm)", "Rz (rad)", "Rx (kg)", "Ry (kg)", "Mz (kg-m)"], 0)
        self.member_results = self._result_table(["Member", "N1 axial", "N1 shear", "N1 moment", "N2 axial", "N2 shear", "N2 moment"], 0)
        self.diagrams = FrameDiagramsPanel(self)
        self.calculation_details = QPlainTextEdit(self)
        self.calculation_details.setReadOnly(True)
        self.diagnostics = self._result_table(["Status", "Check"], 0)
        self.equilibrium = self._result_table(["Load Case", "Residual Fx (kg)", "Residual Fy (kg)", "Residual Mz (kg-m)", "Pass"], 0)
        self.steps = QPlainTextEdit(self)
        self.steps.setReadOnly(True)
        self._build_layout()
        self.result_selector.currentIndexChanged.connect(self._selection_changed)
        self.canvas_diagram_selector.currentIndexChanged.connect(self._canvas_diagram_changed)
        self.diagram_values_toggle.toggled.connect(self.canvas.set_show_diagram_values)
        self.deformed_toggle.toggled.connect(self.canvas.set_show_deformed)
        self.grid_toggle.toggled.connect(self.canvas.set_grid_visible)
        self.snap_toggle.toggled.connect(self.canvas.set_snap_enabled)
        self.snap_nodes_toggle.toggled.connect(self.canvas.set_snap_to_node)
        self.grid_spacing.valueChanged.connect(self.canvas.set_grid_spacing)
        self.active_section.currentIndexChanged.connect(self._active_section_changed)
        self.fit_button.clicked.connect(self.canvas.fit_view)
        self.canvas.model_change_requested.connect(self.model_change_requested)
        self.canvas.selection_changed.connect(self._canvas_selection_changed)
        self.canvas.pointer_changed.connect(self._canvas_pointer_changed)
        self.canvas.tool_changed.connect(self._canvas_tool_changed)
        self.canvas.authoring_message.connect(self.canvas_status_changed)

    @property
    def analysis(self) -> Mapping[str, Any] | None:
        return self._analysis

    def set_model(self, model: Mapping[str, Any]) -> None:
        self._model = model
        sections = model.get("sections", [])
        current_section = self.active_section.currentData()
        self.active_section.blockSignals(True)
        self.active_section.clear()
        for section in sections:
            self.active_section.addItem(f"Section {section['id']}", int(section["id"]))
        selected_index = self.active_section.findData(current_section)
        self.active_section.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        self.active_section.blockSignals(False)
        if self.active_section.currentData() is not None:
            self.canvas.set_active_section(int(self.active_section.currentData()))
        self.canvas.set_model(model)

    def clear_analysis(self) -> None:
        self._analysis = None
        self._postprocess = None
        self.result_selector.blockSignals(True)
        self.result_selector.clear()
        self.result_selector.blockSignals(False)
        self.canvas.set_result(None)
        self.canvas.set_diagram_members([])
        self.summary.setRowCount(0)
        self.node_results.setRowCount(0)
        self.member_results.setRowCount(0)
        self.diagrams.set_members([])
        self.calculation_details.clear()
        self.diagnostics.setRowCount(0)
        self.equilibrium.setRowCount(0)
        self.steps.clear()

    def set_analysis(self, analysis: Mapping[str, Any], postprocess: Mapping[str, Any]) -> None:
        self._analysis = analysis
        self._postprocess = postprocess
        self.result_selector.blockSignals(True)
        self.result_selector.clear()
        self.result_selector.addItem("Envelope", "envelope")
        for name in analysis.get("cases", {}):
            self.result_selector.addItem(f"Case | {name}", f"case:{name}")
        for name in analysis.get("combos", {}):
            self.result_selector.addItem(f"Combo | {name}", f"combo:{name}")
        self.result_selector.blockSignals(False)
        self._populate_diagnostics()
        self._selection_changed()

    def _build_layout(self) -> None:
        authoring_controls = QHBoxLayout()
        authoring_controls.setContentsMargins(0, 0, 0, 0)
        for tool in ("select", "node", "member", "pan"):
            authoring_controls.addWidget(self._tool_buttons[tool])
        authoring_controls.addSpacing(8)
        authoring_controls.addWidget(self.grid_toggle)
        authoring_controls.addWidget(self.snap_toggle)
        authoring_controls.addWidget(self.snap_nodes_toggle)
        authoring_controls.addWidget(QLabel("Step", self))
        authoring_controls.addWidget(self.grid_spacing)
        authoring_controls.addWidget(self.fit_button)
        authoring_controls.addWidget(QLabel("New member", self))
        authoring_controls.addWidget(self.active_section)
        authoring_controls.addStretch()
        authoring_controls.addWidget(self.selection_label)

        result_controls = QHBoxLayout()
        result_controls.setContentsMargins(0, 0, 0, 0)
        result_controls.addWidget(QLabel("Result", self))
        result_controls.addWidget(self.result_selector)
        result_controls.addWidget(QLabel("Canvas", self))
        result_controls.addWidget(self.canvas_diagram_selector)
        result_controls.addWidget(self.diagram_values_toggle)
        result_controls.addStretch()
        result_controls.addWidget(self.deformed_toggle)

        result_tabs = QTabWidget(self)
        result_tabs.addTab(self.summary, "Summary")
        result_tabs.addTab(self.diagrams, "Diagrams")
        result_tabs.addTab(self.node_results, "Node Results")
        result_tabs.addTab(self.member_results, "Member Forces")
        result_tabs.addTab(self.calculation_details, "Calculation Details")
        result_tabs.addTab(self.diagnostics, "Diagnostics")
        result_tabs.addTab(self.equilibrium, "Equilibrium")
        result_tabs.addTab(self.steps, "Solver Log")
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        canvas_host = QWidget(self)
        canvas_layout = QVBoxLayout(canvas_host)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.addLayout(authoring_controls)
        canvas_layout.addLayout(result_controls)
        canvas_layout.addWidget(self.canvas)
        splitter.addWidget(canvas_host)
        splitter.addWidget(result_tabs)
        splitter.setSizes([490, 250])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(splitter)

    def _selection_changed(self) -> None:
        if not self._analysis:
            return
        selection = self.result_selector.currentData() or "envelope"
        selected, selected_postprocess = self._selected_data(str(selection))
        self.canvas.set_result(selected)
        self.canvas.set_deformed_members(selected_postprocess.get("members", []))
        self.canvas.set_diagram_members(selected_postprocess.get("members", []))
        self.diagrams.set_members(selected_postprocess.get("members", []))
        self._populate_tables(selected)
        self._populate_calculation_details(str(selection), selected_postprocess)
        self.steps.setPlainText("\n".join(self._analysis.get("steps", [])))

    def _canvas_diagram_changed(self) -> None:
        self.canvas.set_diagram_mode(str(self.canvas_diagram_selector.currentData() or "none"))

    def _active_section_changed(self) -> None:
        section_id = self.active_section.currentData()
        if section_id is not None:
            self.canvas.set_active_section(int(section_id))

    def _canvas_selection_changed(self, selection: Mapping[str, list[int]]) -> None:
        nodes = selection.get("nodes", [])
        members = selection.get("members", [])
        if nodes:
            text = f"Node{'s' if len(nodes) > 1 else ''}: {', '.join(str(node) for node in nodes)}"
        elif members:
            text = f"Member{'s' if len(members) > 1 else ''}: {', '.join(str(member) for member in members)}"
        else:
            text = "Selection: none"
        self.selection_label.setText(text)

    def _canvas_pointer_changed(self, x: float, y: float) -> None:
        self.canvas_status_changed.emit(
            f"X: {x:.3f} m | Y: {y:.3f} m | {self.canvas.tool.title()} | Grid {self.grid_spacing.value():.3f} m | "
            f"{'Snap' if self.snap_toggle.isChecked() else 'Free'}"
        )

    def _canvas_tool_changed(self, tool: str) -> None:
        self.canvas_status_changed.emit(f"Canvas tool: {tool.title()}")

    def _selected_data(self, selection: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        if selection.startswith("case:"):
            name = selection.removeprefix("case:")
            return self._analysis.get("cases", {}).get(name, self._analysis), self._postprocess.get("cases", {}).get(name, {})
        if selection.startswith("combo:"):
            name = selection.removeprefix("combo:")
            return self._analysis.get("combos", {}).get(name, self._analysis), self._postprocess.get("combos", {}).get(name, {})
        return self._analysis, self._postprocess.get("envelope", {})

    def _populate_tables(self, result: Mapping[str, Any]) -> None:
        nodes = result.get("nodes", [])
        elements = result.get("elements", [])
        maximum_displacement = max((float(node.get("dx", 0.0)) ** 2 + float(node.get("dy", 0.0)) ** 2 for node in nodes), default=0.0) ** 0.5 * 1000.0
        maximum_axial = max((abs(float(member[side]["axial"])) for member in elements for side in ("n1_forces", "n2_forces")), default=0.0)
        maximum_moment = max((abs(float(member[side]["moment"])) for member in elements for side in ("n1_forces", "n2_forces")), default=0.0)
        self.summary.setRowCount(1)
        for column, value in enumerate((maximum_displacement, maximum_axial, maximum_moment)):
            self.summary.setItem(0, column, QTableWidgetItem(f"{value:,.4f}"))

        self.node_results.setRowCount(len(nodes))
        for row, node in enumerate(nodes):
            values = (node["id"], float(node["dx"]) * 1000.0, float(node["dy"]) * 1000.0, node["rz"], node["fx"], node["fy"], node["mz"])
            for column, value in enumerate(values):
                self.node_results.setItem(row, column, QTableWidgetItem(str(value) if column == 0 else f"{float(value):,.5f}"))

        self.member_results.setRowCount(len(elements))
        for row, member in enumerate(elements):
            first, second = member["n1_forces"], member["n2_forces"]
            values = (member["id"], first["axial"], first["shear"], first["moment"], second["axial"], second["shear"], second["moment"])
            for column, value in enumerate(values):
                self.member_results.setItem(row, column, QTableWidgetItem(str(value) if column == 0 else f"{float(value):,.4f}"))

    def _populate_calculation_details(self, selection: str, postprocess: Mapping[str, Any]) -> None:
        convention = self._postprocess.get("conventions", {}) if self._postprocess else {}
        lines = [
            "2D Frame Direct Stiffness Analysis",
            "",
            "System: K u = F",
            f"Selection: {selection}",
            f"Model: {len(self._model.get('nodes', []))} nodes, {len(self._model.get('elements', []))} members, {len(self._model.get('sections', []))} sections",
            "",
            "Conventions:",
        ]
        lines.extend(f"- {name}: {description}" for name, description in convention.items())
        lines.extend(["", "Member calculations:"])
        for member in postprocess.get("members", []):
            actions = member.get("end_actions", {})
            extrema = member.get("extrema", {})
            lines.append(f"E{member['id']} | N{member['n1']} - N{member['n2']} | L = {float(member['length_m']):.4f} m | {member['release']}")
            if actions:
                lines.append(f"  End actions: Ni={float(actions['n_i']):.3f}, Vi={float(actions['v_i']):.3f}, Mi={float(actions['m_i']):.3f}; Nj={float(actions['n_j']):.3f}, Vj={float(actions['v_j']):.3f}, Mj={float(actions['m_j']):.3f}")
            load = member.get("distributed_load", {})
            if load:
                lines.append(f"  Factored distributed load: qx={float(load.get('qx1_kg_m', 0.0)):.3f} to {float(load.get('qx2_kg_m', 0.0)):.3f} kg/m; qy={float(load.get('qy1_kg_m', 0.0)):.3f} to {float(load.get('qy2_kg_m', 0.0)):.3f} kg/m")
            for key, label in (("n_kg", "N"), ("v_kg", "V"), ("m_kg_m", "M"), ("v_mm", "v")):
                value = extrema.get(key, {}).get("abs")
                if value:
                    governing = f" ({value['combo']})" if value.get("combo") else ""
                    lines.append(f"  {label} max abs = {float(value['value']):.4f} at x = {float(value['x_m']):.4f} m{governing}")
        self.calculation_details.setPlainText("\n".join(lines))

    def _populate_diagnostics(self) -> None:
        diagnostics = self._postprocess.get("diagnostics", {}) if self._postprocess else {}
        items = diagnostics.get("items", [])
        self.diagnostics.setRowCount(len(items))
        for row, item in enumerate(items):
            self.diagnostics.setItem(row, 0, QTableWidgetItem(str(item.get("severity", "info")).upper()))
            self.diagnostics.setItem(row, 1, QTableWidgetItem(str(item.get("message", ""))))
        checks = diagnostics.get("equilibrium", [])
        self.equilibrium.setRowCount(len(checks))
        for row, check in enumerate(checks):
            residual = check["residual"]
            values = (check["load_case"], residual["fx_kg"], residual["fy_kg"], residual["mz_kg_m"], "PASS" if check["ok"] else "CHECK")
            for column, value in enumerate(values):
                self.equilibrium.setItem(row, column, QTableWidgetItem(str(value) if column in (0, 4) else f"{float(value):.3e}"))

    @staticmethod
    def _result_table(headers: list[str], rows: int) -> QTableWidget:
        table = QTableWidget(rows, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        return table
