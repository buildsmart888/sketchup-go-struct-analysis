"""Dockable stiffness-matrix and degree-of-freedom inspector."""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget


class MatrixViewerPanel(QWidget):
    """Presents one solvable case or combination; envelopes are intentionally absent."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._matrix: Mapping[str, Any] = {}
        self.selection = QComboBox(self)
        self.selection.currentIndexChanged.connect(self._refresh)
        self.note = QLabel("Run a frame analysis to inspect K, F, D, and degree-of-freedom mapping.", self)
        self.note.setWordWrap(True)
        self.dof_table = QTableWidget(0, 3, self)
        self.dof_table.setHorizontalHeaderLabels(["DOF", "State", "Index"])
        self.matrix_table = QTableWidget(0, 0, self)
        self.vector_table = QTableWidget(0, 3, self)
        self.vector_table.setHorizontalHeaderLabels(["DOF", "F", "D"])
        self.member_selector = QComboBox(self)
        self.member_selector.currentIndexChanged.connect(self._refresh_member)
        self.member_table = QTableWidget(0, 0, self)
        tabs = QTabWidget(self)
        tabs.addTab(self.dof_table, "DOF Map")
        tabs.addTab(self.matrix_table, "Global K")
        tabs.addTab(self.vector_table, "F / D")
        member_host = QWidget(self)
        member_layout = QVBoxLayout(member_host)
        member_layout.addWidget(self.member_selector)
        member_layout.addWidget(self.member_table)
        tabs.addTab(member_host, "Member K")
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Case / Combo", self))
        controls.addWidget(self.selection)
        controls.addStretch()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.note)
        layout.addLayout(controls)
        layout.addWidget(tabs)

    def set_matrix_data(self, matrix: Mapping[str, Any]) -> None:
        self._matrix = matrix
        current = self.selection.currentData()
        self.selection.blockSignals(True)
        self.selection.clear()
        for key in matrix.get("selections", {}):
            self.selection.addItem(key.removeprefix("case:").removeprefix("combo:"), key)
        index = self.selection.findData(current)
        self.selection.setCurrentIndex(index if index >= 0 else 0)
        self.selection.blockSignals(False)
        self.member_selector.blockSignals(True)
        self.member_selector.clear()
        for member in matrix.get("members", []):
            self.member_selector.addItem(f"E{member['id']}  N{member['n1']} - N{member['n2']}  [{member.get('memberType', 'Frame')}]", member["id"])
        self.member_selector.blockSignals(False)
        self._refresh()

    def set_result_selection(self, selection: str) -> None:
        if selection == "envelope":
            return
        index = self.selection.findData(selection)
        if index >= 0:
            self.selection.setCurrentIndex(index)

    def _refresh(self, _index: int | None = None) -> None:
        if not self._matrix:
            return
        selected = self._matrix.get("selections", {}).get(self.selection.currentData(), {})
        dofs = list(self._matrix.get("dofs", []))
        restrained = set(self._matrix.get("restrained_dofs", []))
        self.dof_table.setRowCount(len(dofs))
        for row, label in enumerate(dofs):
            for column, value in enumerate((label, "Restrained" if row in restrained else "Free", row)):
                self.dof_table.setItem(row, column, QTableWidgetItem(str(value)))
        stiffness = self._matrix.get("global_stiffness", [])
        self.matrix_table.setRowCount(len(stiffness))
        self.matrix_table.setColumnCount(len(stiffness))
        self.matrix_table.setHorizontalHeaderLabels([str(index) for index in range(len(stiffness))])
        self.matrix_table.setVerticalHeaderLabels([str(index) for index in range(len(stiffness))])
        for row, values in enumerate(stiffness):
            for column, value in enumerate(values):
                self.matrix_table.setItem(row, column, QTableWidgetItem(f"{float(value):.4e}"))
        force, displacement = selected.get("force", []), selected.get("displacement", [])
        self.vector_table.setRowCount(len(dofs))
        for row, label in enumerate(dofs):
            values = (label, force[row] if row < len(force) else 0.0, displacement[row] if row < len(displacement) else 0.0)
            for column, value in enumerate(values):
                self.vector_table.setItem(row, column, QTableWidgetItem(str(value) if column == 0 else f"{float(value):.6e}"))
        residual = max((abs(float(value)) for value in selected.get("free_residual", [])), default=0.0)
        self.note.setText(f"Envelope is intentionally unavailable: it is not one equilibrium system. Free-DOF residual max = {residual:.3e}.")
        self._refresh_member()

    def _refresh_member(self, _index: int | None = None) -> None:
        member = next((item for item in self._matrix.get("members", []) if item.get("id") == self.member_selector.currentData()), None)
        values = member.get("local_stiffness", []) if member else []
        self.member_table.setRowCount(len(values))
        self.member_table.setColumnCount(len(values))
        self.member_table.setHorizontalHeaderLabels([str(index) for index in range(len(values))])
        self.member_table.setVerticalHeaderLabels([str(index) for index in range(len(values))])
        for row, entries in enumerate(values):
            for column, value in enumerate(entries):
                self.member_table.setItem(row, column, QTableWidgetItem(f"{float(value):.4e}"))
