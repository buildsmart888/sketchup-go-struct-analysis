"""Selection-aware property and load dialogs for the Frame model editor."""

from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .units import UnitSystem, get_unit_system


SUPPORTS = ("Free", "Pinned", "Fixed", "RollerX", "RollerY")
RELEASES = ("Rigid-Rigid", "Pin-Rigid", "Rigid-Pin", "Pin-Pin")
DIRECTIONS = ("Local X", "Local Y", "Global X", "Global Y")
MEMBER_LOAD_TYPES = ("Distributed", "Point Force", "Point Moment")


def _spin(parent: QWidget, value: float = 0.0, minimum: float = -1.0e9, maximum: float = 1.0e9) -> QDoubleSpinBox:
    control = QDoubleSpinBox(parent)
    control.setRange(minimum, maximum)
    control.setDecimals(4)
    control.setSingleStep(0.1)
    control.setValue(value)
    return control


class PropertyInspector(QWidget):
    """Edits selected nodes and members without duplicating the table data model."""

    model_change_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model: Mapping[str, Any] = {}
        self._selection: dict[str, list[int]] = {"nodes": [], "members": []}
        self.title = QLabel("No selection", self)
        self.title.setStyleSheet("font-weight: 700;")
        self.note = QLabel("Select a node or member on the canvas.", self)
        self.note.setWordWrap(True)

        self.node_box = QGroupBox("Node", self)
        node_form = QFormLayout(self.node_box)
        self.node_id = QLabel("-", self.node_box)
        self.node_x = _spin(self.node_box)
        self.node_y = _spin(self.node_box)
        self.node_support = QComboBox(self.node_box)
        self.node_support.addItems(SUPPORTS)
        self.node_case = QComboBox(self.node_box)
        self.node_fx = _spin(self.node_box)
        self.node_fy = _spin(self.node_box)
        self.node_mz = _spin(self.node_box)
        self.node_apply = QPushButton("Apply node", self.node_box)
        node_form.addRow("ID", self.node_id)
        node_form.addRow("X (m)", self.node_x)
        node_form.addRow("Y (m)", self.node_y)
        node_form.addRow("Support", self.node_support)
        node_form.addRow("Load case", self.node_case)
        node_form.addRow("Fx (kg)", self.node_fx)
        node_form.addRow("Fy (kg)", self.node_fy)
        node_form.addRow("Mz (kg-m)", self.node_mz)
        node_form.addRow(self.node_apply)

        self.member_box = QGroupBox("Member", self)
        member_form = QFormLayout(self.member_box)
        self.member_id = QLabel("-", self.member_box)
        self.member_n1 = QComboBox(self.member_box)
        self.member_n2 = QComboBox(self.member_box)
        self.member_section = QComboBox(self.member_box)
        self.member_release = QComboBox(self.member_box)
        self.member_release.addItems(RELEASES)
        self.member_geometry = QLabel("-", self.member_box)
        self.member_apply = QPushButton("Apply member", self.member_box)
        member_form.addRow("ID", self.member_id)
        member_form.addRow("Node I", self.member_n1)
        member_form.addRow("Node J", self.member_n2)
        member_form.addRow("Section", self.member_section)
        member_form.addRow("Release", self.member_release)
        member_form.addRow("Geometry", self.member_geometry)
        member_form.addRow(self.member_apply)

        self.batch_box = QGroupBox("Batch edit", self)
        batch_form = QFormLayout(self.batch_box)
        self.batch_support = QComboBox(self.batch_box)
        self.batch_support.addItems(SUPPORTS)
        self.batch_support_apply = QPushButton("Apply to selected nodes", self.batch_box)
        self.batch_section = QComboBox(self.batch_box)
        self.batch_release = QComboBox(self.batch_box)
        self.batch_release.addItems(RELEASES)
        self.batch_member_apply = QPushButton("Apply to selected members", self.batch_box)
        batch_form.addRow("Support", self.batch_support)
        batch_form.addRow(self.batch_support_apply)
        batch_form.addRow("Section", self.batch_section)
        batch_form.addRow("Release", self.batch_release)
        batch_form.addRow(self.batch_member_apply)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.title)
        layout.addWidget(self.note)
        layout.addWidget(self.node_box)
        layout.addWidget(self.member_box)
        layout.addWidget(self.batch_box)
        layout.addStretch()
        self.node_case.currentIndexChanged.connect(self._load_node_case)
        self.node_apply.clicked.connect(self._apply_node)
        self.member_apply.clicked.connect(self._apply_member)
        self.batch_support_apply.clicked.connect(self._apply_batch_support)
        self.batch_member_apply.clicked.connect(self._apply_batch_members)
        self._refresh()

    def set_model(self, model: Mapping[str, Any]) -> None:
        self._model = model
        self._refresh()

    def set_selection(self, selection: Mapping[str, list[int]]) -> None:
        self._selection = {"nodes": list(selection.get("nodes", [])), "members": list(selection.get("members", []))}
        self._refresh()

    def _refresh(self) -> None:
        nodes = self._model.get("nodes", [])
        sections = self._model.get("sections", [])
        cases = self._model.get("loadcases", [])
        self._fill_combo(self.node_case, [(str(case), str(case)) for case in cases])
        self._fill_combo(self.member_n1, [(f"N{node['id']}", int(node["id"])) for node in nodes])
        self._fill_combo(self.member_n2, [(f"N{node['id']}", int(node["id"])) for node in nodes])
        section_items = [(f"Section {section['id']}", int(section["id"])) for section in sections]
        self._fill_combo(self.member_section, section_items)
        self._fill_combo(self.batch_section, section_items)
        selected_nodes = self._selection["nodes"]
        selected_members = self._selection["members"]
        self.node_box.setVisible(len(selected_nodes) == 1 and not selected_members)
        self.member_box.setVisible(len(selected_members) == 1 and not selected_nodes)
        self.batch_box.setVisible(len(selected_nodes) + len(selected_members) > 1)
        if len(selected_nodes) == 1 and not selected_members:
            node = next((item for item in nodes if int(item["id"]) == selected_nodes[0]), None)
            if node:
                self.title.setText(f"Node N{node['id']}")
                self.note.setText("Coordinates, restraint, and the selected load-case nodal load.")
                self.node_id.setText(str(node["id"]))
                self.node_x.setValue(float(node["x"]))
                self.node_y.setValue(float(node["y"]))
                self.node_support.setCurrentText(str(node.get("support", "Free")))
                self._load_node_case()
            return
        if len(selected_members) == 1 and not selected_nodes:
            member = next((item for item in self._model.get("elements", []) if int(item["id"]) == selected_members[0]), None)
            if member:
                self.title.setText(f"Member E{member['id']}")
                self.note.setText("Endpoint, section, release, and read-only geometry.")
                self.member_id.setText(str(member["id"]))
                self.member_n1.setCurrentIndex(self.member_n1.findData(int(member["n1"])))
                self.member_n2.setCurrentIndex(self.member_n2.findData(int(member["n2"])))
                self.member_section.setCurrentIndex(self.member_section.findData(int(member["sec"])))
                self.member_release.setCurrentText(str(member.get("release", "Rigid-Rigid")))
                by_id = {int(node["id"]): node for node in nodes}
                first, second = by_id.get(int(member["n1"])), by_id.get(int(member["n2"]))
                if first and second:
                    dx, dy = float(second["x"]) - float(first["x"]), float(second["y"]) - float(first["y"])
                    self.member_geometry.setText(f"L = {math.hypot(dx, dy):.4f} m | {math.degrees(math.atan2(dy, dx)):.2f} deg")
            return
        if selected_nodes or selected_members:
            self.title.setText(f"{len(selected_nodes)} node(s), {len(selected_members)} member(s)")
            self.note.setText("Use batch controls to apply support, section, or release values.")
        else:
            self.title.setText("No selection")
            self.note.setText("Select a node or member on the canvas.")

    @staticmethod
    def _fill_combo(combo: QComboBox, items: list[tuple[str, Any]]) -> None:
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for label, value in items:
            combo.addItem(label, value)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _load_node_case(self) -> None:
        if len(self._selection["nodes"]) != 1:
            return
        node_id = self._selection["nodes"][0]
        load_case = self.node_case.currentData()
        load = next((item for item in self._model.get("nloads", []) if int(item.get("node", -1)) == node_id and item.get("lcase") == load_case), {})
        self.node_fx.setValue(float(load.get("fx", 0.0)))
        self.node_fy.setValue(float(load.get("fy", 0.0)))
        self.node_mz.setValue(float(load.get("mz", 0.0)))

    def _apply_node(self) -> None:
        if len(self._selection["nodes"]) != 1:
            return
        node_id = self._selection["nodes"][0]
        model = self._mutable_model()
        node = next(item for item in model["nodes"] if int(item["id"]) == node_id)
        node.update({"x": self.node_x.value(), "y": self.node_y.value(), "support": self.node_support.currentText()})
        load_case = str(self.node_case.currentData() or "DL")
        target = next((item for item in model["nloads"] if int(item.get("node", -1)) == node_id and item.get("lcase") == load_case), None)
        values = {"node": node_id, "lcase": load_case, "fx": self.node_fx.value(), "fy": self.node_fy.value(), "mz": self.node_mz.value()}
        if target is None:
            if any(abs(float(values[key])) > 1.0e-12 for key in ("fx", "fy", "mz")):
                model["nloads"].append(values)
        else:
            target.update(values)
        self.model_change_requested.emit(model)

    def _apply_member(self) -> None:
        if len(self._selection["members"]) != 1:
            return
        member_id = self._selection["members"][0]
        n1, n2 = int(self.member_n1.currentData()), int(self.member_n2.currentData())
        if n1 == n2:
            self.note.setText("Node I and Node J must be different.")
            return
        model = self._mutable_model()
        member = next(item for item in model["elements"] if int(item["id"]) == member_id)
        member.update({"n1": n1, "n2": n2, "sec": int(self.member_section.currentData()), "release": self.member_release.currentText()})
        self.model_change_requested.emit(model)

    def _apply_batch_support(self) -> None:
        if not self._selection["nodes"]:
            return
        ids = set(self._selection["nodes"])
        model = self._mutable_model()
        for node in model["nodes"]:
            if int(node["id"]) in ids:
                node["support"] = self.batch_support.currentText()
        self.model_change_requested.emit(model)

    def _apply_batch_members(self) -> None:
        if not self._selection["members"]:
            return
        ids = set(self._selection["members"])
        model = self._mutable_model()
        for member in model["elements"]:
            if int(member["id"]) in ids:
                member["sec"] = int(self.batch_section.currentData())
                member["release"] = self.batch_release.currentText()
        self.model_change_requested.emit(model)

    def _mutable_model(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._model))


class LoadDialog(QDialog):
    """Small modal input for a canvas load tool."""

    def __init__(self, kind: str, load_cases: list[str], member_length: float = 0.0, parent: QWidget | None = None, units: UnitSystem | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.units = units or get_unit_system("legacy_kg_m")
        self.setWindowTitle("Nodal load" if kind == "nodal" else "Member load")
        form = QFormLayout(self)
        self.load_case = QComboBox(self)
        self.load_case.addItems(load_cases or ["DL"])
        form.addRow("Load case", self.load_case)
        self.fx = _spin(self)
        self.fy = _spin(self)
        self.mz = _spin(self)
        self.load_type = QComboBox(self)
        self.load_type.addItems(MEMBER_LOAD_TYPES)
        self.direction = QComboBox(self)
        self.direction.addItems(DIRECTIONS)
        self.direction.setCurrentText("Local Y")
        self.x_m = _spin(self, self.units.length(member_length / 2.0), 0.0, max(self.units.length(member_length), 0.0))
        self.p = _spin(self)
        self.m = _spin(self)
        self.w1 = _spin(self)
        self.w2 = _spin(self)
        if kind == "nodal":
            form.addRow(f"Fx ({self.units.force_unit})", self.fx)
            form.addRow(f"Fy ({self.units.force_unit})", self.fy)
            form.addRow(f"Mz ({self.units.moment_label()})", self.mz)
        else:
            form.addRow("Type", self.load_type)
            form.addRow("Direction", self.direction)
            form.addRow(f"At x ({self.units.length_unit})", self.x_m)
            form.addRow(f"P ({self.units.force_unit})", self.p)
            form.addRow(f"M ({self.units.moment_label()})", self.m)
            form.addRow(f"W1 ({self.units.distributed_label()})", self.w1)
            form.addRow(f"W2 ({self.units.distributed_label()})", self.w2)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict[str, Any]:
        if self.kind == "nodal":
            return {"lcase": self.load_case.currentText(), "fx": self.fx.value() / self.units.force_factor, "fy": self.fy.value() / self.units.force_factor, "mz": self.mz.value() / self.units.moment_factor}
        return {
            "lcase": self.load_case.currentText(),
            "type": self.load_type.currentText(),
            "dir": self.direction.currentText(),
            "x_m": self.x_m.value() / self.units.length_factor,
            "p": self.p.value() / self.units.force_factor,
            "m": self.m.value() / self.units.moment_factor,
            "w1": self.w1.value() / self.units.distributed_factor,
            "w2": self.w2.value() / self.units.distributed_factor,
        }

    def set_values(self, values: Mapping[str, Any]) -> None:
        self.load_case.setCurrentText(str(values.get("lcase", self.load_case.currentText())))
        if self.kind == "nodal":
            self.fx.setValue(self.units.force(float(values.get("fx", 0.0))))
            self.fy.setValue(self.units.force(float(values.get("fy", 0.0))))
            self.mz.setValue(self.units.moment(float(values.get("mz", 0.0))))
            return
        self.load_type.setCurrentText(str(values.get("type", "Distributed")))
        self.direction.setCurrentText(str(values.get("dir", "Local Y")))
        self.x_m.setValue(self.units.length(float(values.get("x_m", 0.0))))
        self.p.setValue(self.units.force(float(values.get("p", 0.0))))
        self.m.setValue(self.units.moment(float(values.get("m", 0.0))))
        self.w1.setValue(self.units.distributed(float(values.get("w1", values.get("w", 0.0)))))
        self.w2.setValue(self.units.distributed(float(values.get("w2", values.get("w1", values.get("w", 0.0))))))
