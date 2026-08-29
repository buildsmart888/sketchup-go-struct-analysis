"""The first reusable PySide workspace: 2D rigid-frame analysis."""

from __future__ import annotations

import json
import math
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
    QSizePolicy,
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
from .display import DisplaySettings
from .editors import CombinationEditor, Column, ProjectEditor, TableEditor, as_float, as_int
from .inspector import LoadDialog
from .units import UnitSystem, get_unit_system


SUPPORTS = ("Free", "Pinned", "Fixed", "RollerX", "RollerY")
RELEASES = ("Rigid-Rigid", "Pin-Rigid", "Rigid-Pin", "Pin-Pin")
DIRECTIONS = ("Local X", "Local Y", "Global X", "Global Y")
MEMBER_LOAD_TYPES = ("Distributed", "Point Force", "Point Moment")


def default_frame_model() -> dict[str, Any]:
    return {
        "projectInfo": {"name": "Portal Frame", "project": "", "company": "", "engineer": "", "location": "", "units": "legacy_kg_m"},
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
    units_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._synchronizing_cases = False
        self._changing_units = False
        self._unit_key = "legacy_kg_m"
        self._display_preferences: dict[str, Any] = {}
        self._authoring_preferences: dict[str, Any] = {}
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
            [
                Column("Element", "elem", 1, as_int),
                Column("Load case", "lcase", "DL", choices=("DL",)),
                Column("Type", "type", "Distributed", choices=MEMBER_LOAD_TYPES),
                Column("Direction", "dir", "Local Y", choices=DIRECTIONS),
                Column("At x (m)", "x_m", 0.0, as_float),
                Column("P (kg)", "p", 0.0, as_float),
                Column("M (kg-m)", "m", 0.0, as_float),
                Column("W1 (kg/m)", "w1", 0.0, as_float),
                Column("W2 (kg/m)", "w2", 0.0, as_float),
            ],
            self,
        )
        self._build_layout()
        for editor in (self.project, self.nodes, self.elements, self.sections, self.nodal_loads, self.element_loads, self.combinations):
            editor.changed.connect(self.model_changed)
        self.self_weight.toggled.connect(self.model_changed)
        self.load_cases.changed.connect(self._on_load_cases_changed)
        self.project.units.currentIndexChanged.connect(self._on_units_changed)
        self._update_unit_headers()

    def _build_layout(self) -> None:
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._general_tab(), "Project")
        self.tabs.addTab(self.nodes, "Nodes")
        self.tabs.addTab(self.elements, "Members")
        self.tabs.addTab(self.sections, "Sections")
        self.tabs.addTab(self.load_cases, "Load Cases")
        self.tabs.addTab(self.combinations, "Combinations")
        self.tabs.addTab(self.nodal_loads, "Nodal Loads")
        self.tabs.addTab(self.element_loads, "Member Loads")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.tabs)

    def activate_tab(self, name: str) -> None:
        index = next((item for item in range(self.tabs.count()) if self.tabs.tabText(item) == name), -1)
        if index >= 0:
            self.tabs.setCurrentIndex(index)

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
        self._changing_units = True
        self._unit_key = str(parsed.get("projectInfo", {}).get("units", "legacy_kg_m"))
        self._display_preferences = dict(parsed.get("settings", {}).get("display", {}))
        self._authoring_preferences = dict(parsed.get("settings", {}).get("authoring", {}))
        self.project.set_values(parsed.get("projectInfo", {}))
        self.self_weight.blockSignals(True)
        self.self_weight.setChecked(parsed.get("settings", {}).get("include_self_weight") is True)
        self.self_weight.blockSignals(False)
        self.nodes.set_rows(self._display_rows(parsed["nodes"], "nodes"))
        self.elements.set_rows(parsed["elements"])
        self.sections.set_rows(self._display_rows(parsed["sections"], "sections"))
        self.load_cases.set_rows([{"name": value} for value in parsed["loadcases"]])
        self._synchronize_load_cases()
        self.combinations.set_rows(parsed["loadcombos"])
        self.nodal_loads.set_rows(self._display_rows(parsed["nloads"], "nloads"))
        self.element_loads.set_rows(self._display_rows(parsed["eloads"], "eloads"))
        self._update_unit_headers()
        self._changing_units = False
        self.units_changed.emit(self._unit_key)
        self.model_changed.emit()

    def model_data(self) -> dict[str, Any]:
        return self._model_data_for_units(self._unit_key)

    def set_display_preferences(self, values: Mapping[str, Any]) -> None:
        self._display_preferences = dict(values)

    def set_authoring_preferences(self, values: Mapping[str, Any]) -> None:
        self._authoring_preferences = dict(values)

    def _model_data_for_units(self, unit_key: str) -> dict[str, Any]:
        project_info = self.project.values()
        project_info["units"] = unit_key
        return {
            "projectInfo": project_info,
            "settings": {
                "include_self_weight": self.self_weight.isChecked(),
                **({"display": dict(self._display_preferences)} if self._display_preferences else {}),
                **({"authoring": dict(self._authoring_preferences)} if self._authoring_preferences else {}),
            },
            "nodes": self._canonical_rows(self.nodes.values(), "nodes", unit_key),
            "elements": self.elements.values(),
            "sections": self._canonical_rows(self.sections.values(), "sections", unit_key),
            "loadcases": self._load_case_names(),
            "loadcombos": self.combinations.values(),
            "nloads": self._canonical_rows(self.nodal_loads.values(), "nloads", unit_key),
            "eloads": self._canonical_rows(self.element_loads.values(), "eloads", unit_key),
        }

    def _on_units_changed(self, _index: int | None = None) -> None:
        if self._changing_units:
            return
        new_key = str(self.project.units.currentData())
        if new_key == self._unit_key:
            return
        canonical = self._model_data_for_units(self._unit_key)
        canonical["projectInfo"]["units"] = new_key
        self._changing_units = True
        self._unit_key = new_key
        self.nodes.set_rows(self._display_rows(canonical["nodes"], "nodes"))
        self.sections.set_rows(self._display_rows(canonical["sections"], "sections"))
        self.nodal_loads.set_rows(self._display_rows(canonical["nloads"], "nloads"))
        self.element_loads.set_rows(self._display_rows(canonical["eloads"], "eloads"))
        self._update_unit_headers()
        self._changing_units = False
        self.units_changed.emit(new_key)
        self.model_changed.emit()

    @property
    def unit_system(self) -> UnitSystem:
        return get_unit_system(self._unit_key)

    def _display_rows(self, rows: list[Mapping[str, Any]], kind: str) -> list[dict[str, Any]]:
        unit = self.unit_system
        converted: list[dict[str, Any]] = []
        for source in rows:
            row = dict(source)
            if kind == "nodes":
                row["x"], row["y"] = unit.length(float(row["x"])), unit.length(float(row["y"]))
            elif kind == "sections":
                row["e"] = float(row["e"]) * unit.force_factor / unit.length_factor**2
                row["density"] = float(row.get("density", 0.0)) * unit.force_factor / unit.length_factor**3
            elif kind == "nloads":
                row["fx"], row["fy"], row["mz"] = unit.force(float(row["fx"])), unit.force(float(row["fy"])), unit.moment(float(row["mz"]))
            elif kind == "eloads":
                row["x_m"] = unit.length(float(row.get("x_m", 0.0)))
                row["p"] = unit.force(float(row.get("p", 0.0)))
                row["m"] = unit.moment(float(row.get("m", 0.0)))
                row["w1"] = unit.distributed(float(row.get("w1", 0.0)))
                row["w2"] = unit.distributed(float(row.get("w2", 0.0)))
            converted.append(row)
        return converted

    @staticmethod
    def _canonical_rows(rows: list[dict[str, Any]], kind: str, unit_key: str) -> list[dict[str, Any]]:
        unit = get_unit_system(unit_key)
        converted: list[dict[str, Any]] = []
        for source in rows:
            row = dict(source)
            if kind == "nodes":
                row["x"], row["y"] = float(row["x"]) / unit.length_factor, float(row["y"]) / unit.length_factor
            elif kind == "sections":
                row["e"] = float(row["e"]) * unit.length_factor**2 / unit.force_factor
                row["density"] = float(row.get("density", 0.0)) * unit.length_factor**3 / unit.force_factor
            elif kind == "nloads":
                row["fx"], row["fy"], row["mz"] = float(row["fx"]) / unit.force_factor, float(row["fy"]) / unit.force_factor, float(row["mz"]) / unit.moment_factor
            elif kind == "eloads":
                row["x_m"] = float(row.get("x_m", 0.0)) / unit.length_factor
                row["p"] = float(row.get("p", 0.0)) / unit.force_factor
                row["m"] = float(row.get("m", 0.0)) / unit.moment_factor
                row["w1"] = float(row.get("w1", 0.0)) / unit.distributed_factor
                row["w2"] = float(row.get("w2", 0.0)) / unit.distributed_factor
            converted.append(row)
        return converted

    def _update_unit_headers(self) -> None:
        unit = self.unit_system
        self.nodes.set_column_title("x", f"X ({unit.length_unit})")
        self.nodes.set_column_title("y", f"Y ({unit.length_unit})")
        self.sections.set_column_title("e", f"E ({unit.force_unit}/{unit.length_unit}2)")
        self.sections.set_column_title("density", f"Density ({unit.force_unit}/{unit.length_unit}3)")
        self.nodal_loads.set_column_title("fx", f"Fx ({unit.force_label()})")
        self.nodal_loads.set_column_title("fy", f"Fy ({unit.force_label()})")
        self.nodal_loads.set_column_title("mz", f"Mz ({unit.moment_label()})")
        self.element_loads.set_column_title("x_m", f"At x ({unit.length_unit})")
        self.element_loads.set_column_title("p", f"P ({unit.force_label()})")
        self.element_loads.set_column_title("m", f"M ({unit.moment_label()})")
        self.element_loads.set_column_title("w1", f"W1 ({unit.distributed_label()})")
        self.element_loads.set_column_title("w2", f"W2 ({unit.distributed_label()})")

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
    load_placement_started = Signal(str)
    delete_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None, canvas_class: type[FrameCanvas] = FrameCanvas) -> None:
        super().__init__(parent)
        self._model: Mapping[str, Any] = {}
        self._analysis: Mapping[str, Any] | None = None
        self._postprocess: Mapping[str, Any] | None = None
        self._diagnostic_items: list[Mapping[str, Any]] = []
        self._units = get_unit_system("legacy_kg_m")
        self.canvas = canvas_class(self)
        self.canvas_tools = QButtonGroup(self)
        self.canvas_tools.setExclusive(True)
        self._tool_buttons: dict[str, QToolButton] = {}
        for tool, label, tooltip in (
            ("select", "Select", "Select nodes or members"),
            ("node", "Node", "Create a snapped node"),
            ("member", "Member", "Draw a member between nodes"),
            ("split", "Split", "Split a member at the clicked location"),
            ("nodal_load", "Node load", "Add a nodal load"),
            ("member_load", "Member load", "Add a member load"),
            ("pan", "Pan", "Pan the canvas"),
        ):
            button = QToolButton(self)
            button.setText(label)
            button.setToolTip(tooltip)
            button.setCheckable(True)
            button.setMinimumWidth(64)
            button.clicked.connect(lambda _checked=False, value=tool: self.canvas.set_tool(value))
            self.canvas_tools.addButton(button)
            self._tool_buttons[tool] = button
        self._tool_buttons["select"].setChecked(True)
        self.selection_filter = QComboBox(self)
        self.selection_filter.addItem("Both", "both")
        self.selection_filter.addItem("Nodes", "nodes")
        self.selection_filter.addItem("Members", "members")
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
        self.support_type = QComboBox(self)
        self.support_type.addItems(SUPPORTS)
        self.support_type.setCurrentText("Pinned")
        self.support_button = QToolButton(self)
        self.support_button.setText("Support")
        self.support_button.setToolTip("Assign the selected support type by clicking a node")
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
        self.grid_spacing.valueChanged.connect(self._grid_spacing_changed)
        self.selection_filter.currentIndexChanged.connect(self._selection_filter_changed)
        self.active_section.currentIndexChanged.connect(self._active_section_changed)
        self.fit_button.clicked.connect(self.canvas.fit_view)
        self.canvas.model_change_requested.connect(self.model_change_requested)
        self.canvas.selection_changed.connect(self._canvas_selection_changed)
        self.canvas.pointer_changed.connect(self._canvas_pointer_changed)
        self.canvas.tool_changed.connect(self._canvas_tool_changed)
        self.canvas.authoring_message.connect(self.canvas_status_changed)
        self.canvas.load_requested.connect(self._request_load)
        self.canvas.load_edit_requested.connect(self._edit_load)
        self.canvas.delete_requested.connect(self.delete_requested)
        self.support_button.clicked.connect(lambda: self.canvas.set_pending_support(self.support_type.currentText()))
        self.node_results.cellClicked.connect(self._select_node_result)
        self.member_results.cellClicked.connect(self._select_member_result)
        self.diagnostics.cellDoubleClicked.connect(self._select_diagnostic)

    @property
    def analysis(self) -> Mapping[str, Any] | None:
        return self._analysis

    def set_model(self, model: Mapping[str, Any]) -> None:
        self._model = model
        self.set_unit_system(str(model.get("projectInfo", {}).get("units", "legacy_kg_m")))
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

    def set_unit_system(self, key: str) -> None:
        new_units = get_unit_system(key)
        old_units = self._units
        canonical_grid = self.grid_spacing.value() / old_units.length_factor
        self._units = new_units
        self.grid_spacing.blockSignals(True)
        self.grid_spacing.setValue(canonical_grid * new_units.length_factor)
        self.grid_spacing.setSuffix(f" {new_units.length_unit}")
        self.grid_spacing.blockSignals(False)
        self.canvas.set_grid_spacing(canonical_grid)
        self.canvas.set_unit_system(new_units.key)
        self.diagrams.set_unit_system(new_units.key)
        self.summary.setHorizontalHeaderLabels(self._summary_headers(new_units))
        self.node_results.setHorizontalHeaderLabels(["Node", f"dx ({new_units.length_unit})", f"dy ({new_units.length_unit})", "Rz (rad)", f"Rx ({new_units.force_unit})", f"Ry ({new_units.force_unit})", f"Mz ({new_units.moment_label()})"])
        self.member_results.setHorizontalHeaderLabels(["Member", f"N1 axial ({new_units.force_unit})", f"N1 shear ({new_units.force_unit})", f"N1 moment ({new_units.moment_label()})", f"N2 axial ({new_units.force_unit})", f"N2 shear ({new_units.force_unit})", f"N2 moment ({new_units.moment_label()})"])
        self.equilibrium.setHorizontalHeaderLabels(["Load Case", f"Residual Fx ({new_units.force_unit})", f"Residual Fy ({new_units.force_unit})", f"Residual Mz ({new_units.moment_label()})", "Pass"])
        if self._analysis:
            self._selection_changed()

    def _grid_spacing_changed(self, value: float) -> None:
        self.canvas.set_grid_spacing(value / self._units.length_factor)

    def set_display_settings(self, settings: DisplaySettings) -> None:
        self.grid_toggle.blockSignals(True)
        self.grid_toggle.setChecked(settings.show_grid)
        self.grid_toggle.blockSignals(False)
        self.canvas.set_display_settings(settings)

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
        self.results_tabs = QTabWidget(self)
        self.results_tabs.addTab(self.summary, "Summary")
        self.results_tabs.addTab(self.diagrams, "Diagrams")
        self.results_tabs.addTab(self.node_results, "Node Results")
        self.results_tabs.addTab(self.member_results, "Member Forces")
        self.results_tabs.addTab(self.calculation_details, "Calculation Details")
        self.results_tabs.addTab(self.diagnostics, "Diagnostics")
        self.results_tabs.addTab(self.equilibrium, "Equilibrium")
        self.results_tabs.addTab(self.steps, "Solver Log")
        self.diagrams.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.results_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.canvas)

    def detach_results_tabs(self) -> QTabWidget:
        """Hand the result tabs to the main window's dock layout."""
        self.results_tabs.setParent(None)
        return self.results_tabs

    def _selection_changed(self) -> None:
        if not self._analysis:
            return
        selection = self.result_selector.currentData() or "envelope"
        selected, selected_postprocess = self._selected_data(str(selection))
        self.canvas.set_result(selected)
        self.canvas.set_result_selection(str(selection))
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

    def _selection_filter_changed(self) -> None:
        self.canvas.set_selection_filter(str(self.selection_filter.currentData() or "both"))

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
        if len(nodes) == 1:
            self._select_result_row(self.node_results, nodes[0])
        elif len(members) == 1:
            self._select_result_row(self.member_results, members[0])

    def _select_node_result(self, row: int, _column: int) -> None:
        item = self.node_results.item(row, 0)
        if item is not None:
            self.canvas._set_selection({int(item.text())}, set())

    def _select_member_result(self, row: int, _column: int) -> None:
        item = self.member_results.item(row, 0)
        if item is not None:
            self.canvas._set_selection(set(), {int(item.text())})

    @staticmethod
    def _select_result_row(table: QTableWidget, target_id: int) -> None:
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is not None and item.text() == str(target_id):
                table.selectRow(row)
                return

    def _canvas_pointer_changed(self, x: float, y: float) -> None:
        self.canvas_status_changed.emit(
            f"X: {self._units.length(x):.3f} {self._units.length_unit} | Y: {self._units.length(y):.3f} {self._units.length_unit} | {self.canvas.tool.title()} | Grid {self.grid_spacing.value():.3f} {self._units.length_unit} | "
            f"{'Snap' if self.snap_toggle.isChecked() else 'Free'}"
        )

    def _canvas_tool_changed(self, tool: str) -> None:
        self.canvas_status_changed.emit(f"Canvas tool: {tool.title()}")

    def _request_load(self, kind: str, context: Mapping[str, Any]) -> None:
        if kind == "nodal":
            dialog = LoadDialog("nodal", list(self._model.get("loadcases", [])), parent=self, units=self._units, preset=str(context.get("preset", "generic")))
            if dialog.exec() == dialog.DialogCode.Accepted:
                self.canvas.add_nodal_load(int(context["node"]), dialog.values())
            return
        member_id = int(context["member"])
        member = next((item for item in self._model.get("elements", []) if int(item["id"]) == member_id), None)
        nodes = {int(node["id"]): node for node in self._model.get("nodes", [])}
        if member is None or int(member["n1"]) not in nodes or int(member["n2"]) not in nodes:
            return
        first, second = nodes[int(member["n1"])], nodes[int(member["n2"])]
        dx, dy = float(second["x"]) - float(first["x"]), float(second["y"]) - float(first["y"])
        length = math.hypot(dx, dy)
        dialog = LoadDialog("member", list(self._model.get("loadcases", [])), length, self, self._units, preset=str(context.get("preset", "generic")))
        requested = context.get("position", (float(first["x"]), float(first["y"])))
        if length > 1.0e-12:
            at_x = max(0.0, min(length, ((float(requested[0]) - float(first["x"])) * dx + (float(requested[1]) - float(first["y"])) * dy) / length))
            dialog.x_m.setValue(at_x)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.canvas.add_member_load(member_id, dialog.values())

    def begin_load_placement(self, preset: str) -> None:
        """Configure a typed load first, then place it repeatedly by clicking the canvas."""
        kind = "nodal" if preset in {"nodal_force", "nodal_moment"} else "member"
        dialog = LoadDialog(kind, list(self._model.get("loadcases", [])), parent=self, units=self._units, preset=preset)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.canvas.set_pending_load(kind, dialog.values(), preset)
            self.load_placement_started.emit(preset)

    def _edit_load(self, kind: str, context: Mapping[str, Any]) -> None:
        index = int(context["index"])
        load = context["load"]
        if kind == "nodal":
            dialog = LoadDialog("nodal", list(self._model.get("loadcases", [])), parent=self, units=self._units)
            dialog.set_values(load)
            if dialog.exec() == dialog.DialogCode.Accepted:
                self.canvas.update_nodal_load(index, {"node": load["node"], **dialog.values()})
            return
        member_id = int(context["member"])
        member = next((item for item in self._model.get("elements", []) if int(item["id"]) == member_id), None)
        nodes = {int(node["id"]): node for node in self._model.get("nodes", [])}
        if member is None or int(member["n1"]) not in nodes or int(member["n2"]) not in nodes:
            return
        first, second = nodes[int(member["n1"])], nodes[int(member["n2"])]
        length = math.hypot(float(second["x"]) - float(first["x"]), float(second["y"]) - float(first["y"]))
        dialog = LoadDialog("member", list(self._model.get("loadcases", [])), length, self, self._units)
        dialog.set_values(load)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.canvas.update_member_load(index, dialog.values())

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
        maximum_displacement_m = max((float(node.get("dx", 0.0)) ** 2 + float(node.get("dy", 0.0)) ** 2 for node in nodes), default=0.0) ** 0.5
        maximum_axial = max((abs(float(member[side]["axial"])) for member in elements for side in ("n1_forces", "n2_forces")), default=0.0)
        maximum_tension = max((float(member["n1_forces"]["axial"]) for member in elements), default=0.0)
        maximum_compression = min((float(member["n1_forces"]["axial"]) for member in elements), default=0.0)
        maximum_shear = max((abs(float(member[side]["shear"])) for member in elements for side in ("n1_forces", "n2_forces")), default=0.0)
        maximum_moment = max((abs(float(member[side]["moment"])) for member in elements for side in ("n1_forces", "n2_forces")), default=0.0)
        self.summary.setRowCount(1)
        analysis_type = str(self._model.get("projectInfo", {}).get("analysisType", "Frame")).lower()
        if analysis_type == "beam":
            values = (self._units.format_displacement(maximum_displacement_m), f"{self._units.force(maximum_shear):,.4f}", f"{self._units.moment(maximum_moment):,.4f}")
        elif analysis_type == "truss":
            values = (self._units.format_displacement(maximum_displacement_m), f"{self._units.force(maximum_tension):,.4f}", f"{self._units.force(maximum_compression):,.4f}")
        else:
            values = (self._units.format_displacement(maximum_displacement_m), f"{self._units.force(maximum_axial):,.4f}", f"{self._units.moment(maximum_moment):,.4f}")
        for column, value in enumerate(values):
            self.summary.setItem(0, column, QTableWidgetItem(value))

        self.node_results.setRowCount(len(nodes))
        for row, node in enumerate(nodes):
            values = (node["id"], self._units.format_displacement(float(node["dx"])), self._units.format_displacement(float(node["dy"])), node["rz"], self._units.force(float(node["fx"])), self._units.force(float(node["fy"])), self._units.moment(float(node["mz"])))
            for column, value in enumerate(values):
                if column in (0, 1, 2):
                    text = str(value)
                else:
                    text = f"{float(value):,.5f}"
                self.node_results.setItem(row, column, QTableWidgetItem(text))

        self.member_results.setRowCount(len(elements))
        for row, member in enumerate(elements):
            first, second = member["n1_forces"], member["n2_forces"]
            values = (member["id"], self._units.force(float(first["axial"])), self._units.force(float(first["shear"])), self._units.moment(float(first["moment"])), self._units.force(float(second["axial"])), self._units.force(float(second["shear"])), self._units.moment(float(second["moment"])))
            for column, value in enumerate(values):
                self.member_results.setItem(row, column, QTableWidgetItem(str(value) if column == 0 else f"{float(value):,.4f}"))
            if analysis_type == "truss":
                axial = float(first["axial"])
                state = "Tension" if axial > 1.0e-12 else "Compression" if axial < -1.0e-12 else "Zero"
                self.member_results.setItem(row, 2, QTableWidgetItem(state))

    def _summary_headers(self, units: UnitSystem) -> list[str]:
        analysis_type = str(self._model.get("projectInfo", {}).get("analysisType", "Frame")).lower()
        if analysis_type == "beam":
            return [f"Max deflection ({units.length_unit})", f"Max shear ({units.force_unit})", f"Max moment ({units.moment_label()})"]
        if analysis_type == "truss":
            return [f"Max displacement ({units.length_unit})", f"Max tension ({units.force_unit})", f"Max compression ({units.force_unit})"]
        return [f"Max displacement ({units.length_unit})", f"Max axial ({units.force_unit})", f"Max moment ({units.moment_label()})"]

    def _populate_calculation_details(self, selection: str, postprocess: Mapping[str, Any]) -> None:
        convention = self._postprocess.get("conventions", {}) if self._postprocess else {}
        lines = [
            f"2D {self._model.get('projectInfo', {}).get('analysisType', 'Frame')} Direct Stiffness Analysis",
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
                    if key == "v_mm":
                        amount = self._units.format_displacement(float(value["value"]) / 1000.0)
                    else:
                        amount = f"{float(value['value']):.4f}"
                    lines.append(f"  {label} max abs = {amount} at x = {float(value['x_m']):.4f} m{governing}")
        self.calculation_details.setPlainText("\n".join(lines))

    def _populate_diagnostics(self) -> None:
        diagnostics = self._postprocess.get("diagnostics", {}) if self._postprocess else {}
        items = list(diagnostics.get("items", []))
        self._diagnostic_items = items
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

    def _select_diagnostic(self, row: int, _column: int) -> None:
        if row < 0 or row >= len(self._diagnostic_items):
            return
        item = self._diagnostic_items[row]
        nodes = {int(value) for value in item.get("nodes", [])}
        members = {int(value) for value in item.get("members", [])}
        if not nodes and not members:
            self.canvas_status_changed.emit("This diagnostic has no specific canvas objects.")
            return
        self.canvas._set_selection(nodes, members)
        self.canvas.fit_selection()
        self.canvas_status_changed.emit("Selected objects referenced by diagnostic. Double-click another row to inspect it.")

    @staticmethod
    def _result_table(headers: list[str], rows: int) -> QTableWidget:
        table = QTableWidget(rows, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        return table
