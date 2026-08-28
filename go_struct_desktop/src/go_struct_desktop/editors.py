"""Reusable data-entry widgets for the structural workspaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .units import UNIT_SYSTEMS


Converter = Callable[[str], Any]


def as_text(value: str) -> str:
    return value.strip()


def as_int(value: str) -> int:
    return int(float(value))


def as_float(value: str) -> float:
    return float(value)


@dataclass(frozen=True)
class Column:
    title: str
    key: str
    default: Any
    convert: Converter = as_text
    choices: tuple[str, ...] = ()


class TableEditor(QWidget):
    """A compact tabular editor with stable add/remove controls."""

    changed = Signal()

    def __init__(self, columns: Sequence[Column], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.columns = tuple(columns)
        self._choice_values = {column.key: column.choices for column in self.columns if column.choices}
        self.table = QTableWidget(0, len(self.columns), self)
        self.table.setHorizontalHeaderLabels([column.title for column in self.columns])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self.changed)

        add_button = self._tool_button("+", "Add row", self.add_row)
        remove_button = self._tool_button("-", "Remove selected rows", self.remove_selected)
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(add_button)
        controls.addWidget(remove_button)
        controls.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(controls)
        layout.addWidget(self.table)

    @staticmethod
    def _tool_button(text: str, tooltip: str, callback) -> QToolButton:  # type: ignore[no-untyped-def]
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(28, 28)
        button.clicked.connect(callback)
        return button

    def set_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for row in rows:
            self._insert_row(row)
        self.table.blockSignals(False)
        self.changed.emit()

    def add_row(self) -> None:
        self._insert_row({})
        self.changed.emit()

    def remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
        if rows:
            self.changed.emit()

    def values(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in range(self.table.rowCount()):
            result: dict[str, Any] = {}
            for column_index, column in enumerate(self.columns):
                widget = self.table.cellWidget(row, column_index)
                text = widget.currentText() if isinstance(widget, QComboBox) else self.table.item(row, column_index).text() if self.table.item(row, column_index) else ""
                result[column.key] = column.convert(text) if text.strip() else column.default
            rows.append(result)
        return rows

    def set_choices(self, key: str, values: Sequence[str]) -> None:
        column_index = next((index for index, column in enumerate(self.columns) if column.key == key), None)
        if column_index is None:
            return
        self._choice_values[key] = tuple(values)
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, column_index)
            if not isinstance(widget, QComboBox):
                continue
            current = widget.currentText()
            widget.blockSignals(True)
            widget.clear()
            widget.addItems(list(values))
            if current in values:
                widget.setCurrentText(current)
            widget.blockSignals(False)

    def set_column_title(self, key: str, title: str) -> None:
        index = next((item for item, column in enumerate(self.columns) if column.key == key), None)
        if index is not None:
            self.table.setHorizontalHeaderItem(index, QTableWidgetItem(title))

    def _insert_row(self, row: Mapping[str, Any]) -> None:
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)
        for column_index, column in enumerate(self.columns):
            value = row.get(column.key, column.default)
            if column.choices:
                combo = QComboBox(self.table)
                combo.addItems(self._choice_values.get(column.key, column.choices))
                combo.setCurrentText(str(value))
                combo.currentTextChanged.connect(self.changed)
                self.table.setCellWidget(row_index, column_index, combo)
            else:
                self.table.setItem(row_index, column_index, QTableWidgetItem(str(value)))


class CombinationEditor(QWidget):
    """Edits linear combinations with one numeric factor column per load case."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load_cases: list[str] = []
        self.table = QTableWidget(self)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self.changed)
        add_button = TableEditor._tool_button("+", "Add load combination", self.add_row)
        remove_button = TableEditor._tool_button("-", "Remove selected combinations", self.remove_selected)
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(add_button)
        controls.addWidget(remove_button)
        controls.addStretch()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(controls)
        layout.addWidget(self.table)
        self.set_load_cases(["DL"])

    def set_load_cases(self, load_cases: Sequence[str], rows: Sequence[Mapping[str, Any]] | None = None) -> None:
        previous = self.values() if rows is None else list(rows)
        self._load_cases = list(load_cases) or ["DL"]
        self.table.blockSignals(True)
        self.table.clear()
        self.table.setColumnCount(2 + len(self._load_cases))
        self.table.setHorizontalHeaderLabels(["Name", "Formula", *self._load_cases])
        self.table.setRowCount(0)
        for row in previous:
            self._insert_row(row)
        self.table.blockSignals(False)
        self.changed.emit()

    def set_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self.set_load_cases(self._load_cases, rows)

    def add_row(self) -> None:
        self._insert_row({"name": f"Comb {self.table.rowCount() + 1}", "factors": {}})
        self.changed.emit()

    def remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
        if rows:
            self.changed.emit()

    def values(self) -> list[dict[str, Any]]:
        combinations: list[dict[str, Any]] = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            name = name_item.text().strip() if name_item else ""
            factors: dict[str, float] = {}
            formula_item = self.table.item(row, 1)
            formula = formula_item.text().strip() if formula_item else ""
            for offset, load_case in enumerate(self._load_cases, start=2):
                item = self.table.item(row, offset)
                text = item.text().strip() if item else ""
                if text:
                    factors[load_case] = float(text)
            combination = {"name": name or f"Comb {row + 1}", "factors": factors}
            if formula:
                combination["eq"] = formula
            combinations.append(combination)
        return combinations

    def _insert_row(self, row: Mapping[str, Any]) -> None:
        factors = row.get("factors", {})
        self.table.insertRow(self.table.rowCount())
        index = self.table.rowCount() - 1
        self.table.setItem(index, 0, QTableWidgetItem(str(row.get("name", f"Comb {index + 1}"))))
        self.table.setItem(index, 1, QTableWidgetItem(str(row.get("eq", ""))))
        for offset, load_case in enumerate(self._load_cases, start=2):
            value = factors.get(load_case, "") if isinstance(factors, Mapping) else ""
            self.table.setItem(index, offset, QTableWidgetItem(str(value)))


class ProjectEditor(QWidget):
    """Project metadata and global analysis settings."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.fields = {key: QLineEdit(self) for key in ("name", "project", "company", "engineer", "location")}
        self.units = QComboBox(self)
        for unit in UNIT_SYSTEMS.values():
            self.units.addItem(unit.label, unit.key)
        form = QFormLayout(self)
        form.setContentsMargins(12, 12, 12, 12)
        for label, key in (("Frame name", "name"), ("Project", "project"), ("Company", "company"), ("Engineer", "engineer"), ("Location", "location")):
            form.addRow(label, self.fields[key])
            self.fields[key].textChanged.connect(self.changed)
        form.addRow("Display units", self.units)
        self.units.currentIndexChanged.connect(self.changed)

    def set_values(self, values: Mapping[str, Any]) -> None:
        for key, field in self.fields.items():
            field.blockSignals(True)
            field.setText(str(values.get(key, "")))
            field.blockSignals(False)
        self.units.blockSignals(True)
        index = self.units.findData(str(values.get("units", "legacy_kg_m")))
        self.units.setCurrentIndex(index if index >= 0 else 0)
        self.units.blockSignals(False)

    def values(self) -> dict[str, str]:
        return {**{key: field.text().strip() for key, field in self.fields.items()}, "units": str(self.units.currentData())}
