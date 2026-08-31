"""Dialogs and docks that make the modelling workflow explicit."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class ProjectStartDialog(QDialog):
    """Start a blank project or one of the current workspace's editable examples."""

    def __init__(self, workspace_name: str, examples: tuple[Any, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Start {workspace_name.title()} Project")
        self.resize(520, 360)
        self.options = QListWidget(self)
        self.options.addItem(QListWidgetItem("Blank project"))
        for example in examples:
            item = QListWidgetItem(str(example.title))
            item.setData(Qt.ItemDataRole.UserRole, example)
            item.setToolTip(str(example.description))
            self.options.addItem(item)
        self.description = QLabel("Create an empty, editable project.", self)
        self.description.setWordWrap(True)
        self.options.currentItemChanged.connect(self._describe)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose a starting point", self))
        layout.addWidget(self.options)
        layout.addWidget(self.description)
        layout.addWidget(buttons)
        self.options.setCurrentRow(0)

    def selected_example(self) -> Any | None:
        item = self.options.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _describe(self, item: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        example = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.description.setText(str(example.description) if example else "Create an empty, editable project.")


class DefineHubDialog(QDialog):
    """A compact gateway to the project data tables without duplicating their editors."""

    def __init__(self, activate: Callable[[str], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Define Project Data")
        self.resize(560, 320)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Define data before drawing: sections, cases, combinations, and project units remain the single source of truth in Model Input.", self))
        entries = (
            ("Project", "Name, engineer, location, display units, and self weight."),
            ("Sections", "Section stiffness and density used by new members."),
            ("Load Cases", "Input load cases and their names."),
            ("Combinations", "Linear load combinations used for results and reports."),
        )
        for title, detail in entries:
            row = QHBoxLayout()
            label = QLabel(f"<b>{title}</b><br>{detail}", self)
            button = QPushButton("Open", self)
            button.clicked.connect(lambda _checked=False, tab=title: self._open(activate, tab))
            row.addWidget(label, 1)
            row.addWidget(button)
            layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open(self, activate: Callable[[str], None], title: str) -> None:
        activate(title)
        self.accept()


class ModelCheckDialog(QDialog):
    issue_selected = Signal(object)

    def __init__(self, issues: list[Mapping[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._issues = list(issues)
        self.setWindowTitle("Check Model")
        self.resize(720, 360)
        self.table = QTableWidget(len(issues), 2, self)
        self.table.setHorizontalHeaderLabels(["Level", "Finding"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        for row, issue in enumerate(issues):
            self.table.setItem(row, 0, QTableWidgetItem(str(issue.get("severity", "info")).upper()))
            self.table.setItem(row, 1, QTableWidgetItem(str(issue.get("message", ""))))
        self.table.cellDoubleClicked.connect(self._select)
        note = QLabel("Double-click a finding to select and fit the related objects on the canvas. Errors must be resolved before analysis.", self)
        note.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(note)
        layout.addWidget(self.table)
        layout.addWidget(buttons)

    def _select(self, row: int, _column: int) -> None:
        if 0 <= row < len(self._issues):
            self.issue_selected.emit(dict(self._issues[row]))


class SectionCatalogDialog(QDialog):
    """Small starter catalogue that fills the existing editable section table."""

    PRESETS = {
        "Steel I Beam": {"material": "Steel", "e": 2.04e9, "a": 82.0, "i": 8500.0, "density": 7850.0, "width_cm": 14.0, "depth_cm": 30.0},
        "Steel Column": {"material": "Steel", "e": 2.04e9, "a": 145.0, "i": 19500.0, "density": 7850.0, "width_cm": 20.0, "depth_cm": 35.0},
        "Concrete Beam": {"material": "Concrete", "e": 2.1e9, "a": 900.0, "i": 67500.0, "density": 2400.0, "width_cm": 30.0, "depth_cm": 60.0},
        "Concrete Column": {"material": "Concrete", "e": 2.1e9, "a": 1600.0, "i": 213333.0, "density": 2400.0, "width_cm": 40.0, "depth_cm": 40.0},
        "Timber Rectangular": {"material": "Timber", "e": 1.1e8, "a": 450.0, "i": 33750.0, "density": 550.0, "width_cm": 15.0, "depth_cm": 30.0},
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Section & Material Catalog")
        self.preset = QComboBox(self)
        self.preset.addItems(self.PRESETS)
        self.name = QLabel(self)
        self.e, self.a, self.i, self.density, self.width, self.depth = (QDoubleSpinBox(self) for _ in range(6))
        for control in (self.e, self.a, self.i, self.density, self.width, self.depth):
            control.setRange(0.0, 1.0e12); control.setDecimals(4)
        form = QFormLayout()
        form.addRow("Profile", self.name)
        form.addRow("E (kg/m2)", self.e); form.addRow("A (cm2)", self.a); form.addRow("I (cm4)", self.i)
        form.addRow("Density (kg/m3)", self.density); form.addRow("Width b (cm)", self.width); form.addRow("Depth h (cm)", self.depth)
        self.preset.currentTextChanged.connect(self._apply_preset)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self); layout.addWidget(QLabel("Choose a starter then adjust it before applying to the active section.", self)); layout.addWidget(self.preset); layout.addLayout(form); layout.addWidget(buttons)
        self._apply_preset(self.preset.currentText())

    def values(self) -> dict[str, Any]:
        source = self.PRESETS[self.preset.currentText()]
        return {"name": self.preset.currentText(), "material": source["material"], "e": self.e.value(), "a": self.a.value(), "i": self.i.value(), "density": self.density.value(), "width_cm": self.width.value(), "depth_cm": self.depth.value()}

    def _apply_preset(self, name: str) -> None:
        values = self.PRESETS[name]
        self.name.setText(f"{values['material']} | editable properties")
        for control, key in ((self.e, "e"), (self.a, "a"), (self.i, "i"), (self.density, "density"), (self.width, "width_cm"), (self.depth, "depth_cm")):
            control.setValue(float(values[key]))
