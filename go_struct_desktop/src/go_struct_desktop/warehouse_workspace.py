"""Desktop workspace for Warehouse3D preliminary modelling and optimization."""

from __future__ import annotations

import csv
import json
import sys
from math import sqrt
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QApplication, QAbstractItemView, QButtonGroup, QComboBox, QDockWidget, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressDialog, QPushButton, QPlainTextEdit, QSpinBox, QSplitter, QStyle, QTabWidget, QTableWidget, QTableWidgetItem, QToolBar, QToolButton, QVBoxLayout, QWidget

from go_struct_core import OpenSeesPyBackend, OptimizationSettings, WarehouseOptimizer, WarehouseProject, analyze_warehouse_data, generate_warehouse, preliminary_checks, preliminary_cost, warehouse_equilibrium


GROUP_COLOURS = {
    "column": "#f2bf45", "top_chord": "#eef6f7", "bottom_chord": "#cad5df", "web": "#46c9bc",
    "purlin": "#78a6f2", "bottom_tie": "#78a6f2", "eave_tie": "#78a6f2", "roof_bracing": "#ed7d6d", "wall_bracing": "#ed7d6d", "ground_beam": "#8c9bad",
}


class WarehouseInputPanel(QWidget):
    def __init__(self, project: WarehouseProject, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project = project
        layout = QVBoxLayout(self)
        title = QLabel("WAREHOUSE GEOMETRY")
        title.setStyleSheet("font-weight: 800; color: #0f766e; letter-spacing: 1px;")
        layout.addWidget(title)
        form = QFormLayout()
        self.width = self._line(project.geometry.width_m)
        self.length = self._line(project.geometry.length_m)
        self.bays = QSpinBox(); self.bays.setRange(1, 30); self.bays.setValue(project.geometry.bay_count)
        self.eave = self._line(project.geometry.eave_height_m)
        self.slope = self._line(project.geometry.roof_slope_deg)
        self.depth = self._line(project.geometry.truss_depth_m)
        self.panels = QSpinBox(); self.panels.setRange(2, 40); self.panels.setSingleStep(2); self.panels.setValue(project.geometry.panel_count)
        self.topology = QComboBox()
        self.topology.addItem("Warren — alternating diagonals", "warren")
        self.topology.addItem("Pratt — diagonals to centre", "pratt")
        self.topology.addItem("Howe — diagonals away from centre", "howe")
        self.topology.addItem("Fink — pitched W-web", "pitched")
        self._set_topology(project.geometry.topology)
        for label, widget in (("Width (m)", self.width), ("Length (m)", self.length), ("Bay count", self.bays), ("Eave height (m)", self.eave), ("Roof slope (deg)", self.slope), ("Truss depth (m)", self.depth), ("Panels / truss", self.panels), ("Topology", self.topology)):
            form.addRow(label, widget)
        layout.addLayout(form)
        layout.addSpacing(8)
        load_title = QLabel("PRELIMINARY LOADS (kN/m²)")
        load_title.setStyleSheet("font-weight: 800; color: #0f766e; letter-spacing: 1px;")
        layout.addWidget(load_title)
        loads = QFormLayout()
        self.dl = self._line(project.loads.roof_dead_kn_m2)
        self.ll = self._line(project.loads.roof_live_kn_m2)
        self.wind = self._line(project.loads.wind_wall_kn_m2)
        loads.addRow("Roof DL", self.dl); loads.addRow("Roof LL", self.ll); loads.addRow("Wall wind", self.wind)
        layout.addLayout(loads)
        self.generate_button = QPushButton("GENERATE 3D MODEL")
        self.generate_button.setStyleSheet("QPushButton { background: #e76143; color: white; font-weight: 800; padding: 10px; border: 0; } QPushButton:hover { background: #cc4c32; }")
        layout.addWidget(self.generate_button)
        disclaimer = QLabel("PRELIMINARY DESIGN — requires licensed engineer review.")
        disclaimer.setWordWrap(True); disclaimer.setStyleSheet("color: #a04835; font-size: 10px; font-weight: 700;")
        layout.addWidget(disclaimer)
        layout.addStretch()

    @staticmethod
    def _line(value: float) -> QLineEdit:
        field = QLineEdit(f"{value:g}")
        field.setAlignment(Qt.AlignmentFlag.AlignRight)
        return field

    def project(self) -> WarehouseProject:
        raw = self._project.to_dict()
        panels = self.panels.value()
        if panels % 2:
            panels += 1
        raw["geometry"].update({
            "width_m": float(self.width.text()), "length_m": float(self.length.text()), "bay_count": self.bays.value(),
            "eave_height_m": float(self.eave.text()), "roof_slope_deg": float(self.slope.text()),
            "truss_depth_m": float(self.depth.text()), "panel_count": panels, "topology": str(self.topology.currentData()),
        })
        raw["loads"].update({"roof_dead_kn_m2": float(self.dl.text()), "roof_live_kn_m2": float(self.ll.text()), "wind_wall_kn_m2": float(self.wind.text())})
        return WarehouseProject.from_dict(raw)

    def set_project(self, project: WarehouseProject) -> None:
        self._project = project
        self.width.setText(f"{project.geometry.width_m:g}"); self.length.setText(f"{project.geometry.length_m:g}")
        self.bays.setValue(project.geometry.bay_count); self.eave.setText(f"{project.geometry.eave_height_m:g}")
        self.slope.setText(f"{project.geometry.roof_slope_deg:g}"); self.depth.setText(f"{project.geometry.truss_depth_m:g}")
        self.panels.setValue(project.geometry.panel_count); self._set_topology(project.geometry.topology)
        self.dl.setText(f"{project.loads.roof_dead_kn_m2:g}"); self.ll.setText(f"{project.loads.roof_live_kn_m2:g}"); self.wind.setText(f"{project.loads.wind_wall_kn_m2:g}")

    def _set_topology(self, topology: str) -> None:
        index = self.topology.findData(topology)
        self.topology.setCurrentIndex(max(0, index))


class WarehouseViewport(QQuickWidget):
    """Qt Quick 3D view with orbit/pan/zoom supplied by OrbitCameraController."""

    member_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        qml = Path(__file__).with_name("assets") / "warehouse_view.qml"
        self.setSource(QUrl.fromLocalFile(str(qml)))
        self.setClearColor(Qt.GlobalColor.black)
        self._root = self.rootObject()
        self._generated: Any = None
        self._analysis: Mapping[str, Any] = {}
        self._checks: Mapping[str, Any] = {}
        self._mode = "model"
        self._result_key = "model"
        self._selected_member: int | None = None
        self._visible_groups: set[str] | None = None
        if self._root is not None:
            self._root.memberPicked.connect(self.member_selected.emit)

    def set_model(self, generated: Any, analysis: Mapping[str, Any] | None = None, checks: Mapping[str, Any] | None = None) -> None:
        self._generated = generated
        self._analysis = analysis or {}
        self._checks = checks or {}
        self._redraw()

    def set_display(self, mode: str | None = None, result_key: str | None = None, member_id: int | None = None) -> None:
        if mode is not None:
            self._mode = mode
        if result_key is not None:
            self._result_key = result_key
        if member_id is not None:
            self._selected_member = member_id
        self._redraw()

    def set_visible_groups(self, groups: set[str] | None) -> None:
        self._visible_groups = groups
        self._redraw()

    def set_standard_view(self, view_name: str) -> None:
        if self._root is not None:
            self._root.setView(view_name)

    def reset_view(self) -> None:
        if self._root is not None:
            self._root.resetView()

    def _result(self) -> Mapping[str, Any]:
        if self._result_key.startswith("case:"):
            return self._analysis.get("cases", {}).get(self._result_key.removeprefix("case:"), {})
        if self._result_key.startswith("combo:"):
            return self._analysis.get("combos", {}).get(self._result_key.removeprefix("combo:"), {})
        return {}

    def _redraw(self) -> None:
        if self._generated is None:
            return
        generated = self._generated
        node_by_id = {item.id: item for item in generated.nodes}
        xs = [node.x_m for node in generated.nodes]; ys = [node.y_m for node in generated.nodes]; zs = [node.z_m for node in generated.nodes]
        center = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, (min(zs) + max(zs)) / 2.0)
        extents = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
        result = self._result()
        displacement_by_id = {int(item["id"]): item.get("displacements", [0.0] * 6) for item in result.get("nodes", [])}
        axial_by_id = {int(item["id"]): float(item.get("axial_tension_kn", 0.0)) for item in result.get("members", [])}
        utilization_by_id = {int(item["id"]): float(item.get("utilization", 0.0)) for item in self._checks.get("members", [])}
        max_displacement = max((sqrt(sum(float(value) ** 2 for value in values[:3])) for values in displacement_by_id.values()), default=0.0)
        building_span = max(generated.project.geometry.width_m, generated.project.geometry.length_m)
        deformation_scale = min(30.0, max(1.0, building_span * 0.08 / max(max_displacement, 1.0e-9)))
        max_axial = max((abs(value) for value in axial_by_id.values()), default=1.0)
        records: list[dict[str, Any]] = []
        for member in generated.members:
            first, second = node_by_id[member.i], node_by_id[member.j]
            first_xyz = (first.x_m, first.y_m, first.z_m)
            second_xyz = (second.x_m, second.y_m, second.z_m)
            if self._mode == "deformed" and displacement_by_id:
                first_displacement = displacement_by_id.get(member.i, [0.0] * 6)
                second_displacement = displacement_by_id.get(member.j, [0.0] * 6)
                first_xyz = tuple(value + deformation_scale * float(displacement) for value, displacement in zip(first_xyz, first_displacement[:3]))
                second_xyz = tuple(value + deformation_scale * float(displacement) for value, displacement in zip(second_xyz, second_displacement[:3]))
            # Qt Quick 3D draws with +Y up, whereas structural coordinates use
            # +Z up.  Map the engineering world to the viewport explicitly:
            # scene X = engineering X, scene Y = engineering Z,
            # scene Z = -engineering Y (right-handed plan view).
            first_scene = (first_xyz[0] - center[0], first_xyz[2] - center[2], -(first_xyz[1] - center[1]))
            second_scene = (second_xyz[0] - center[0], second_xyz[2] - center[2], -(second_xyz[1] - center[1]))
            dx, dy, dz = (second_scene[index] - first_scene[index] for index in range(3))
            length = sqrt(dx * dx + dy * dy + dz * dz)
            if length <= 1.0e-9:
                continue
            direction = (dx / length, dy / length, dz / length)
            # Quaternion rotating Qt's primitive Y-axis to the member direction.
            dot = direction[1]
            cross = (direction[2], 0.0, -direction[0])
            if dot < -0.999999:
                quaternion = (0.0, 1.0, 0.0, 0.0)
            else:
                scale = sqrt(max(1.0e-12, 2.0 * (1.0 + dot)))
                quaternion = (scale / 2.0, cross[0] / scale, cross[1] / scale, cross[2] / scale)
            colour = GROUP_COLOURS.get(member.group, "#dbe7ef")
            if self._mode == "utilization":
                value = utilization_by_id.get(member.id, 0.0)
                colour = "#38c99b" if value < 0.60 else "#f1c453" if value < 0.90 else "#ef8a45" if value <= 1.0 else "#ef6250"
            elif self._mode == "axial":
                value = axial_by_id.get(member.id, 0.0)
                intensity = min(1.0, abs(value) / max_axial)
                colour = "#36d2ad" if value >= 0 else "#ef6250"
                if intensity < 0.15:
                    colour = "#52677c"
            if member.id == self._selected_member:
                colour = "#fff3a3"
            records.append({"id": member.id, "x": (first_scene[0] + second_scene[0]) / 2.0, "y": (first_scene[1] + second_scene[1]) / 2.0, "z": (first_scene[2] + second_scene[2]) / 2.0, "length": length, "qs": quaternion[0], "qx": quaternion[1], "qy": quaternion[2], "qz": quaternion[3], "color": colour, "selected": member.id == self._selected_member, "visible": self._visible_groups is None or member.group in self._visible_groups})
        if self._root is not None:
            self._root.setProperty("members", records)
            self._root.setProperty("displayMode", self._mode)
            self._root.setProperty("cameraDistance", max(16.0, max(extents) * 2.1))
            self._root.setProperty("groundX", 0.0)
            self._root.setProperty("groundY", 0.0)
            self._root.setProperty("groundZ", -center[2] - 0.12)
            self._root.setProperty("groundWidth", max(8.0, extents[0] * 1.15))
            self._root.setProperty("groundDepth", max(8.0, extents[1] * 1.25))
            self._root.setProperty("axisX", -extents[0] / 2.0)
            self._root.setProperty("axisY", -center[2])
            self._root.setProperty("axisZ", extents[1] / 2.0)
            self._root.setProperty("axisLength", max(2.5, min(5.0, max(extents) * 0.12)))
            titles = {"model": "3D PRELIMINARY MODEL", "utilization": "GOVERNING UTILIZATION", "axial": "AXIAL FORCE — TENSION / COMPRESSION", "deformed": "DEFORMED SHAPE — EXAGGERATED"}
            self._root.setProperty("viewTitle", titles.get(self._mode, "3D PRELIMINARY MODEL"))


class WarehouseResults(QWidget):
    member_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tabs = QTabWidget(self)
        self.summary = QPlainTextEdit(); self.summary.setReadOnly(True)
        self.member_table = QTableWidget(0, 6)
        self.member_table.setHorizontalHeaderLabels(("ID", "Group", "Combo", "N (kN)", "Slender.", "Util."))
        self.member_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.member_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.member_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.member_table.setAlternatingRowColors(True)
        self.member_table.horizontalHeader().setStretchLastSection(True)
        self.member_detail = QLabel("Select a highlighted member in the 3D view or this table.")
        self.member_detail.setWordWrap(True)
        member_page = QWidget(); member_layout = QVBoxLayout(member_page); member_layout.setContentsMargins(7, 7, 7, 7)
        member_layout.addWidget(QLabel("Governing preliminary member checks")); member_layout.addWidget(self.member_table); member_layout.addWidget(self.member_detail)
        self.cost = QPlainTextEdit(); self.cost.setReadOnly(True)
        self.optimization = QPlainTextEdit(); self.optimization.setReadOnly(True)
        self.reactions = QTableWidget(0, 9)
        self.reactions.setHorizontalHeaderLabels(("Set", "ΣFx", "ΣFy", "ΣFz", "ΣMx", "ΣMy", "ΣMz", "Residual", "Status"))
        self.reactions.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.reactions.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.reactions.horizontalHeader().setStretchLastSection(True)
        self.load_path = QPlainTextEdit(); self.load_path.setReadOnly(True)
        audit_page = QWidget(); audit_layout = QVBoxLayout(audit_page); audit_layout.setContentsMargins(7, 7, 7, 7)
        audit_layout.addWidget(QLabel("Global equilibrium — applied actions + support reactions (kN / kN-m)")); audit_layout.addWidget(self.reactions)
        audit_layout.addWidget(QLabel("Load distribution trace")); audit_layout.addWidget(self.load_path)
        self.tabs.addTab(self.summary, "Analysis")
        self.tabs.addTab(member_page, "Members")
        self.tabs.addTab(audit_page, "Reactions / Loads")
        self.tabs.addTab(self.cost, "Cost / BOQ")
        self.tabs.addTab(self.optimization, "Optimization")
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.addWidget(self.tabs)
        self.member_table.cellClicked.connect(self._member_clicked)
        self._member_checks: dict[int, Mapping[str, Any]] = {}

    def set_evaluation(self, generated: Any, analysis: Mapping[str, Any], checks: Mapping[str, Any], cost: Mapping[str, Any], equilibrium: Mapping[str, Any]) -> None:
        summary = analysis.get("model_summary", {})
        self.summary.setPlainText("\n".join((
            "PRELIMINARY 3D ANALYSIS", f"Status: {'PASS preliminary screens' if checks.get('feasible') else 'REVIEW REQUIRED'}",
            f"Backend: {analysis.get('backend', 'n/a')}", f"Nodes: {summary.get('nodes', 0)}    Members: {summary.get('members', 0)}",
            f"Maximum utilization: {checks.get('utilization', 0):.3f}", f"Maximum displacement: {checks.get('max_displacement_m', 0) * 1000:.1f} mm",
            f"Maximum drift: {checks.get('max_drift_ratio', 0):.5f}", "", "Warnings:", *(checks.get("reasons") or ["None"]), "", "This is not a final design or code certification.",
        )))
        breakdown = cost.get("breakdown_thb", {})
        lines = ["PRELIMINARY BOQ / COST ESTIMATE", f"Steel mass: {cost.get('steel_mass_kg', 0):,.0f} kg", f"Purchased mass incl. waste: {cost.get('purchased_steel_mass_kg', 0):,.0f} kg", ""]
        lines += [f"{name.replace('_', ' ').title()}: {value:,.0f} THB" for name, value in breakdown.items()]
        lines += ["", f"TOTAL: {cost.get('total_thb', 0):,.0f} THB", "", *cost.get("assumptions", [])]
        self.cost.setPlainText("\n".join(lines))
        members = list(checks.get("members", []))
        self._member_checks = {int(item["id"]): item for item in members}
        self.member_table.setRowCount(len(members))
        for row, member in enumerate(members):
            values = (member["id"], member.get("group", ""), member.get("combo", ""), f"{member.get('axial_tension_kn', 0.0):,.1f}", f"{member.get('slenderness', 0.0):.1f}", f"{member.get('utilization', 0.0):.3f}")
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column in {0, 3, 4, 5}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.member_table.setItem(row, column, item)
        self.member_table.resizeColumnsToContents()
        rows = equilibrium.get("sets", [])
        self.reactions.setRowCount(len(rows))
        for row, item in enumerate(rows):
            reaction = item.get("reactions", [0.0] * 6); residual = item.get("max_residual", 0.0)
            values = [item.get("name", ""), *(f"{value:,.2f}" for value in reaction), f"{residual:.2e}", "PASS" if item.get("balanced") else "CHECK"]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column > 0:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.reactions.setItem(row, column, cell)
        self.reactions.resizeColumnsToContents()
        trace = ["Applied equivalent nodal resultant before combinations:"]
        for case, item in equilibrium.get("load_distribution", {}).items():
            force = item["force_kn"]
            trace.append(f"{case:4}  {item['nodes']:3} nodes   Fx={force[0]:,.2f}  Fy={force[1]:,.2f}  Fz={force[2]:,.2f} kN")
        trace += ["", *equilibrium.get("assumptions", [])]
        self.load_path.setPlainText("\n".join(trace))

    def _member_clicked(self, row: int, _: int) -> None:
        item = self.member_table.item(row, 0)
        if item is not None:
            self.member_selected.emit(int(item.text()))

    def select_member(self, member_id: int) -> None:
        for row in range(self.member_table.rowCount()):
            item = self.member_table.item(row, 0)
            if item is None or int(item.text()) != member_id:
                continue
            self.member_table.selectRow(row)
            group = self.member_table.item(row, 1).text()
            combo = self.member_table.item(row, 2).text()
            axial = self.member_table.item(row, 3).text()
            utilization = self.member_table.item(row, 5).text()
            check = self._member_checks.get(member_id, {})
            self.member_detail.setText(f"Member {member_id} · {group} · governing {combo}\nAxial force {axial} kN · preliminary utilization {utilization}\nBasis: {check.get('check_expression', 'n/a')} | axial={check.get('axial_utilization', 0.0):.3f}, bending={check.get('bending_utilization', 0.0):.3f}, slenderness={check.get('slenderness_utilization', 0.0):.3f}")
            return
        self.member_detail.setText(f"Member {member_id} selected. No governing check is available for this member.")

    def set_optimization(self, result: Mapping[str, Any]) -> None:
        lines = ["PARETO OPTIMIZATION", f"Seed: {result.get('seed')}    Evaluations: {result.get('evaluations')}", ""]
        for index, item in enumerate(result.get("pareto", []), 1):
            values = item["objectives"]
            candidate = item["candidate"]
            lines.append(f"#{index}  {values[0]:,.0f} THB | {values[1]:,.0f} kg | Util {values[2]:.3f}")
            lines.append(f"    {candidate['topology']} · {candidate['bay_count']} bays · {candidate['panel_count']} panels · depth {candidate['truss_depth_m']:.2f} m")
        self.optimization.setPlainText("\n".join(lines))


class WarehouseMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.project = WarehouseProject.default()
        self.generated: Any = None
        self.analysis: Mapping[str, Any] = {}
        self.checks: Mapping[str, Any] = {}
        self.cost: Mapping[str, Any] = {}
        self.equilibrium: Mapping[str, Any] = {}
        self._current_path: Path | None = None
        self.setWindowTitle("GO Struct Desktop | Warehouse Optimizer 3D")
        self.resize(1500, 920); self.setMinimumSize(1100, 720)
        self.setStyleSheet("QMainWindow { background: #f4f7fa; } QDockWidget::title { background: #ffffff; font-weight: 700; padding: 7px; } QLineEdit, QComboBox, QSpinBox { min-height: 27px; } QPlainTextEdit { background: #0b1624; color: #e5f0f6; font-family: Consolas; border: 0; }")
        self.input_panel = WarehouseInputPanel(self.project, self)
        self.input_panel.generate_button.clicked.connect(lambda: self.generate_and_analyze())
        self.viewport = WarehouseViewport(self)
        self.results = WarehouseResults(self)
        self.viewport.member_selected.connect(self._select_member)
        self.results.member_selected.connect(self._select_member)
        self.setCentralWidget(self.viewport)
        input_dock = QDockWidget("01  Building geometry", self); input_dock.setWidget(self.input_panel); input_dock.setMinimumWidth(300); self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, input_dock)
        result_dock = QDockWidget("02  Analysis, cost & Pareto", self); result_dock.setWidget(self.results); result_dock.setMinimumWidth(330); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, result_dock)
        self._build_actions()
        self.generate_and_analyze(notify=False)

    def _build_actions(self) -> None:
        style = self.style()
        new_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon), "New", self); new_action.setToolTip("Create a new warehouse project"); new_action.triggered.connect(self.new_project)
        open_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "Open", self); open_action.setToolTip("Open a Warehouse JSON project"); open_action.triggered.connect(self.open_project)
        save_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "Save", self); save_action.setToolTip("Save the current Warehouse JSON project"); save_action.triggered.connect(self.save_project)
        export_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), "Export BOQ / Pareto CSV", self); export_action.triggered.connect(self.export_csv)
        analyze_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "Analyze 3D", self); analyze_action.setToolTip("Generate the model and run preliminary 3D analysis"); analyze_action.triggered.connect(lambda: self.generate_and_analyze())
        optimize_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "Run Pareto Optimization", self); optimize_action.setToolTip("Search feasible structural alternatives"); optimize_action.triggered.connect(self.run_optimizer)
        file_menu = self.menuBar().addMenu("File"); file_menu.addActions((new_action, open_action, save_action, export_action))
        analysis_menu = self.menuBar().addMenu("Analysis"); analysis_menu.addAction(analyze_action); analysis_menu.addAction(optimize_action)
        toolbar = QToolBar("Warehouse", self); toolbar.setMovable(False); toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon); self.addToolBar(toolbar)
        toolbar.addActions((new_action, open_action, save_action)); toolbar.addSeparator(); toolbar.addAction(analyze_action); toolbar.addAction(optimize_action); toolbar.addSeparator()
        view_label = QLabel("  VIEW  "); view_label.setStyleSheet("font-weight: 800; color: #0f766e;"); toolbar.addWidget(view_label)
        for text, view_name, tooltip in (("ISO", "iso", "Isometric view"), ("FRONT", "front", "Front elevation"), ("RIGHT", "right", "Right elevation"), ("LEFT", "left", "Left elevation"), ("TOP", "top", "Roof plan"), ("BOTTOM", "bottom", "Underside plan")):
            button = QToolButton(); button.setText(text); button.setToolTip(tooltip); button.setAutoRaise(True); button.clicked.connect(lambda _=False, name=view_name: self.viewport.set_standard_view(name)); toolbar.addWidget(button)
        toolbar.addSeparator()
        self.result_selector = QComboBox(); self.result_selector.setMinimumWidth(180); self.result_selector.setToolTip("Load case or combination displayed in the viewport")
        self.result_selector.addItem("Model geometry", "model")
        self.result_selector.currentIndexChanged.connect(self._display_changed)
        toolbar.addWidget(self.result_selector)
        self.view_group = QButtonGroup(self); self.view_group.setExclusive(True)
        modes = (("Model", "model", QStyle.StandardPixmap.SP_FileDialogContentsView, "Show structural member groups"), ("Util.", "utilization", QStyle.StandardPixmap.SP_DialogApplyButton, "Show governing utilization: green to red"), ("Axial", "axial", QStyle.StandardPixmap.SP_ArrowUp, "Show axial tension (green) and compression (red)"), ("Deflect", "deformed", QStyle.StandardPixmap.SP_CommandLink, "Show exaggerated displaced geometry"))
        self.view_buttons: dict[str, QToolButton] = {}
        for text, mode, icon, tooltip in modes:
            button = QToolButton(); button.setText(text); button.setIcon(style.standardIcon(icon)); button.setCheckable(True); button.setToolTip(tooltip); button.setProperty("displayMode", mode)
            button.clicked.connect(self._display_changed)
            self.view_group.addButton(button); self.view_buttons[mode] = button; toolbar.addWidget(button)
        self.view_buttons["model"].setChecked(True)
        fit_button = QToolButton(); fit_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton)); fit_button.setText("Fit"); fit_button.setToolTip("Reset the 3D camera to the isometric view"); fit_button.clicked.connect(self.viewport.reset_view); toolbar.addWidget(fit_button)
        layer_menu = QMenu("Visible layers", self)
        self.group_actions: dict[str, QAction] = {}
        labels = {"column": "Columns", "top_chord": "Top chord", "bottom_chord": "Bottom chord", "web": "Truss webs", "purlin": "Purlins", "bottom_tie": "Bottom ties", "roof_bracing": "Roof bracing", "wall_bracing": "Wall bracing", "ground_beam": "Ground beams"}
        for group, label in labels.items():
            action = layer_menu.addAction(label); action.setCheckable(True); action.setChecked(True); action.toggled.connect(self._layers_changed); self.group_actions[group] = action
        layer_button = QToolButton(); layer_button.setText("Layers"); layer_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogListView)); layer_button.setToolTip("Show or hide structural systems"); layer_button.setMenu(layer_menu); layer_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup); toolbar.addWidget(layer_button)
        self.view_legend = QLabel("Groups  <span style='color:#f2bf45'>■</span> columns  <span style='color:#eef6f7'>■</span> chords  <span style='color:#46c9bc'>■</span> webs  <span style='color:#ed7d6d'>■</span> bracing")
        self.view_legend.setTextFormat(Qt.TextFormat.RichText); self.view_legend.setStyleSheet("color: #4b5a67; padding-left: 6px;"); toolbar.addWidget(self.view_legend)

    def _display_changed(self) -> None:
        mode = next((name for name, button in self.view_buttons.items() if button.isChecked()), "model")
        result_key = str(self.result_selector.currentData())
        self.viewport.set_display(mode=mode, result_key=result_key)
        legends = {"model": "Groups  <span style='color:#f2bf45'>■</span> columns  <span style='color:#eef6f7'>■</span> chords  <span style='color:#46c9bc'>■</span> webs  <span style='color:#ed7d6d'>■</span> bracing", "utilization": "Utilization  <span style='color:#38c99b'>■</span> 0–0.60  <span style='color:#f1c453'>■</span> 0.60–0.90  <span style='color:#ef8a45'>■</span> 0.90–1.00  <span style='color:#ef6250'>■</span> >1.00", "axial": "Axial force  <span style='color:#36d2ad'>■</span> tension (+)  <span style='color:#52677c'>■</span> low force  <span style='color:#ef6250'>■</span> compression (−)", "deformed": "Deformed shape — visually exaggerated; consult Analysis for actual displacement."}
        self.view_legend.setText(legends[mode])

    def _layers_changed(self) -> None:
        visible = {group for group, action in self.group_actions.items() if action.isChecked()}
        self.viewport.set_visible_groups(visible)

    def _load_result_selector(self) -> None:
        self.result_selector.blockSignals(True)
        self.result_selector.clear(); self.result_selector.addItem("Model geometry", "model")
        for name in self.analysis.get("cases", {}):
            self.result_selector.addItem(f"Load case · {name}", f"case:{name}")
        for name in self.analysis.get("combos", {}):
            self.result_selector.addItem(f"Combination · {name}", f"combo:{name}")
        self.result_selector.blockSignals(False)

    def _select_member(self, member_id: int) -> None:
        self.viewport.set_display(member_id=member_id)
        self.results.select_member(member_id)
        self.statusBar().showMessage(f"Member {member_id} selected — inspect its governing check in the Members tab", 5000)

    def generate_and_analyze(self, notify: bool = True) -> None:
        progress = self._progress("Generating parametric 3D warehouse model…") if notify else None
        try:
            self.project = self.input_panel.project()
            self.generated = generate_warehouse(self.project)
            if progress:
                progress.setLabelText("Running 3D structural analysis…")
                QApplication.processEvents()
            backend = OpenSeesPyBackend() if OpenSeesPyBackend.available() else None
            self.analysis = analyze_warehouse_data(self.generated, backend)
            if progress:
                progress.setLabelText("Checking members and preparing preliminary BOQ…")
                QApplication.processEvents()
            self.checks = preliminary_checks(self.generated, self.analysis)
            self.cost = preliminary_cost(self.generated, self.analysis)
            self.equilibrium = warehouse_equilibrium(self.generated, self.analysis)
            self.viewport.set_model(self.generated, self.analysis, self.checks)
            self.viewport.reset_view()
            self.results.set_evaluation(self.generated, self.analysis, self.checks, self.cost, self.equilibrium)
            self._load_result_selector()
            self._display_changed()
            self.statusBar().showMessage(f"3D model analyzed: {len(self.generated.nodes)} nodes, {len(self.generated.members)} members")
            if notify:
                QMessageBox.information(self, "3D model ready", f"Created and analyzed {len(self.generated.nodes)} nodes and {len(self.generated.members)} members.\n\nReview the Analysis and Cost / BOQ tabs for preliminary results.")
        except Exception as exc:
            QMessageBox.critical(self, "Warehouse input", str(exc))
        finally:
            if progress:
                progress.close()

    def run_optimizer(self) -> None:
        progress = self._progress("Preparing Pareto optimization candidates…")
        try:
            optimizer = WarehouseOptimizer(self.project)
            def report(snapshot: Mapping[str, Any]) -> None:
                progress.setLabelText(f"Pareto search complete: {snapshot['evaluated']} candidates checked, {snapshot['feasible']} feasible.")
                QApplication.processEvents()

            progress.setLabelText("Running Pareto optimization — please wait…")
            QApplication.processEvents()
            result = optimizer.run(OptimizationSettings(population_size=8, generations=2, seed=11, engine="pymoo"), on_progress=report)
            self.results.set_optimization(result)
            self.results.tabs.setCurrentWidget(self.results.optimization)
            self.statusBar().showMessage(f"Optimization complete: {len(result['pareto'])} Pareto candidates from {result['evaluations']} evaluations")
            QMessageBox.information(self, "Pareto optimization complete", f"Evaluated {result['evaluations']} candidates and found {len(result['pareto'])} Pareto candidate(s).\n\nOpen the Optimization tab to compare them.")
        except Exception as exc:
            QMessageBox.critical(self, "Optimization", str(exc))
        finally:
            progress.close()

    def _progress(self, message: str) -> QProgressDialog:
        progress = QProgressDialog(message, None, 0, 0, self)
        progress.setWindowTitle("GO Struct Warehouse Optimizer 3D")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
        QApplication.processEvents()
        return progress

    def new_project(self) -> None:
        self.project = WarehouseProject.default(); self.input_panel.set_project(self.project); self.generate_and_analyze(); self._current_path = None

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Warehouse Project", "", "Warehouse JSON (*.gowarehouse.json *.json)")
        if not path:
            return
        try:
            self.project = WarehouseProject.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
            self.input_panel.set_project(self.project); self._current_path = Path(path); self.generate_and_analyze()
        except Exception as exc:
            QMessageBox.critical(self, "Open Warehouse Project", str(exc))

    def save_project(self) -> None:
        path = self._current_path
        if path is None:
            selected, _ = QFileDialog.getSaveFileName(self, "Save Warehouse Project", "warehouse.gowarehouse.json", "Warehouse JSON (*.gowarehouse.json)")
            if not selected:
                return
            path = Path(selected)
            if path.suffix != ".json":
                path = path.with_suffix(".gowarehouse.json")
            self._current_path = path
        path.write_text(json.dumps(self.project.to_dict(), indent=2), encoding="utf-8")
        self.statusBar().showMessage(f"Saved {path.name}")

    def export_csv(self) -> None:
        if not self.cost:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export preliminary BOQ", "warehouse_boq.csv", "CSV (*.csv)")
        if not path:
            return
        with Path(path).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream); writer.writerow(("Item", "Amount", "Unit"))
            writer.writerow(("Steel mass", self.cost["steel_mass_kg"], "kg"))
            for name, value in self.cost["breakdown_thb"].items():
                writer.writerow((name, value, "THB"))
            writer.writerow(("Total", self.cost["total_thb"], "THB"))
        self.statusBar().showMessage(f"Exported {Path(path).name}")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("GO Struct Warehouse Optimizer 3D")
    app.setFont(QFont("Segoe UI", 10))
    window = WarehouseMainWindow(); window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
