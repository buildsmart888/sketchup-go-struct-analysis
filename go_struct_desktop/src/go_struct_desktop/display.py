"""UI-only display settings for model, load, result, and FBD layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QTabWidget, QVBoxLayout, QWidget


@dataclass(frozen=True)
class DisplaySettings:
    """Presentation choices; solver result values remain in their native convention."""

    show_grid: bool = True
    show_nodes: bool = True
    show_node_ids: bool = True
    show_member_ids: bool = False
    show_supports: bool = True
    show_local_axes: bool = False
    show_loads: bool = True
    show_load_values: bool = True
    show_load_directions: bool = False
    show_reactions: bool = True
    show_equilibrium: bool = True
    diagram_fill: bool = True
    diagram_placement: str = "local_positive"
    axial_positive: str = "tension"
    shear_positive: str = "clockwise"
    moment_positive: str = "bottom_tension"
    diagram_scale_mode: str = "auto"
    diagram_scale_multiplier: float = 1.0
    fbd_reference_x: float = 0.0
    fbd_reference_y: float = 0.0

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "DisplaySettings":
        value = value or {}
        valid = {field: value[field] for field in cls.__dataclass_fields__ if field in value}
        return cls(**valid)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DisplayPanel(QWidget):
    """Compact dock content for canvas layers and visual sign conventions."""

    settings_changed = Signal(object)
    load_case_changed = Signal(str)
    view_mode_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = DisplaySettings()
        self.view_mode = QComboBox(self)
        self.view_mode.addItem("Model", "model")
        self.view_mode.addItem("Results", "results")
        self.view_mode.addItem("Free body", "fbd")
        self.view_mode.setCurrentIndex(1)
        self.load_case = QComboBox(self)

        self.grid = QCheckBox("Grid", self)
        self.nodes = QCheckBox("Nodes", self)
        self.node_ids = QCheckBox("Node IDs", self)
        self.member_ids = QCheckBox("Member IDs", self)
        self.supports = QCheckBox("Supports", self)
        self.local_axes = QCheckBox("Local axes", self)
        self.loads = QCheckBox("Loads", self)
        self.load_values = QCheckBox("Load values", self)
        self.load_directions = QCheckBox("Load direction labels", self)
        self.reactions = QCheckBox("Support reactions", self)
        self.equilibrium = QCheckBox("Equilibrium residual", self)
        self.diagram_fill = QCheckBox("Diagram fill", self)
        self.diagram_placement = QComboBox(self)
        self.diagram_placement.addItem("Positive on local +Y", "local_positive")
        self.diagram_placement.addItem("Positive on local -Y", "local_negative")
        self.axial_positive = QComboBox(self)
        self.axial_positive.addItem("Tension positive", "tension")
        self.axial_positive.addItem("Compression positive", "compression")
        self.shear_positive = QComboBox(self)
        self.shear_positive.addItem("Clockwise positive", "clockwise")
        self.shear_positive.addItem("Counter-clockwise positive", "counter_clockwise")
        self.moment_positive = QComboBox(self)
        self.moment_positive.addItem("Bottom fibre tension", "bottom_tension")
        self.moment_positive.addItem("Top fibre tension", "top_tension")
        self.diagram_scale_mode = QComboBox(self)
        self.diagram_scale_mode.addItem("Auto", "auto")
        self.diagram_scale_mode.addItem("Manual", "manual")
        self.diagram_scale_multiplier = QDoubleSpinBox(self)
        self.diagram_scale_multiplier.setRange(0.1, 10.0)
        self.diagram_scale_multiplier.setSingleStep(0.1)
        self.diagram_scale_multiplier.setValue(1.0)
        self.fbd_reference_x = QDoubleSpinBox(self)
        self.fbd_reference_x.setRange(-1.0e6, 1.0e6)
        self.fbd_reference_x.setDecimals(3)
        self.fbd_reference_y = QDoubleSpinBox(self)
        self.fbd_reference_y.setRange(-1.0e6, 1.0e6)
        self.fbd_reference_y.setDecimals(3)
        self._build_layout()
        self._apply_settings(self._settings)
        for control in (
            self.grid, self.nodes, self.node_ids, self.member_ids, self.supports, self.local_axes,
            self.loads, self.load_values, self.load_directions, self.reactions, self.equilibrium,
            self.diagram_fill,
        ):
            control.toggled.connect(self._emit_settings)
        for control in (self.diagram_placement, self.axial_positive, self.shear_positive, self.moment_positive, self.diagram_scale_mode):
            control.currentIndexChanged.connect(self._emit_settings)
        self.diagram_scale_multiplier.valueChanged.connect(self._emit_settings)
        self.fbd_reference_x.valueChanged.connect(self._emit_settings)
        self.fbd_reference_y.valueChanged.connect(self._emit_settings)
        self.load_case.currentIndexChanged.connect(lambda: self.load_case_changed.emit(str(self.load_case.currentData() or "")))
        self.view_mode.currentIndexChanged.connect(lambda: self.view_mode_changed.emit(str(self.view_mode.currentData() or "model")))

    @property
    def settings(self) -> DisplaySettings:
        return self._settings

    def set_load_cases(self, names: list[str]) -> None:
        current = self.load_case.currentData()
        self.load_case.blockSignals(True)
        self.load_case.clear()
        for name in names:
            self.load_case.addItem(name, name)
        index = self.load_case.findData(current)
        self.load_case.setCurrentIndex(index if index >= 0 else 0)
        self.load_case.blockSignals(False)

    def _build_layout(self) -> None:
        tabs = QTabWidget(self)
        tabs.addTab(self._model_tab(), "Model")
        tabs.addTab(self._loads_tab(), "Loads")
        tabs.addTab(self._results_tab(), "Results")
        tabs.addTab(self._fbd_tab(), "FBD")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(tabs)

    def _model_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        for control in (self.grid, self.nodes, self.node_ids, self.member_ids, self.supports, self.local_axes):
            layout.addWidget(control)
        layout.addStretch()
        return tab

    def _loads_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QFormLayout(tab)
        layout.addRow("Input case", self.load_case)
        for control in (self.loads, self.load_values, self.load_directions):
            layout.addRow(control)
        return tab

    def _results_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QFormLayout(tab)
        layout.addRow("Canvas view", self.view_mode)
        layout.addRow(self.diagram_fill)
        layout.addRow("Placement", self.diagram_placement)
        layout.addRow("Axial N", self.axial_positive)
        layout.addRow("Shear V", self.shear_positive)
        layout.addRow("Moment M", self.moment_positive)
        layout.addRow("Diagram scale", self.diagram_scale_mode)
        layout.addRow("Scale factor", self.diagram_scale_multiplier)
        return tab

    def reset_diagram_scale(self) -> None:
        self.diagram_scale_mode.setCurrentIndex(self.diagram_scale_mode.findData("auto"))
        self.diagram_scale_multiplier.setValue(1.0)

    def _fbd_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QFormLayout(tab)
        layout.addRow(self.reactions)
        layout.addRow(self.equilibrium)
        layout.addRow("Moment reference X (m)", self.fbd_reference_x)
        layout.addRow("Moment reference Y (m)", self.fbd_reference_y)
        return tab

    def _emit_settings(self) -> None:
        settings = DisplaySettings(
            show_grid=self.grid.isChecked(),
            show_nodes=self.nodes.isChecked(),
            show_node_ids=self.node_ids.isChecked(),
            show_member_ids=self.member_ids.isChecked(),
            show_supports=self.supports.isChecked(),
            show_local_axes=self.local_axes.isChecked(),
            show_loads=self.loads.isChecked(),
            show_load_values=self.load_values.isChecked(),
            show_load_directions=self.load_directions.isChecked(),
            show_reactions=self.reactions.isChecked(),
            show_equilibrium=self.equilibrium.isChecked(),
            diagram_fill=self.diagram_fill.isChecked(),
            diagram_placement=str(self.diagram_placement.currentData()),
            axial_positive=str(self.axial_positive.currentData()),
            shear_positive=str(self.shear_positive.currentData()),
            moment_positive=str(self.moment_positive.currentData()),
            diagram_scale_mode=str(self.diagram_scale_mode.currentData()),
            diagram_scale_multiplier=self.diagram_scale_multiplier.value(),
            fbd_reference_x=self.fbd_reference_x.value(),
            fbd_reference_y=self.fbd_reference_y.value(),
        )
        self._settings = settings
        self.settings_changed.emit(settings)

    def _apply_settings(self, settings: DisplaySettings) -> None:
        self.grid.setChecked(settings.show_grid)
        self.nodes.setChecked(settings.show_nodes)
        self.node_ids.setChecked(settings.show_node_ids)
        self.member_ids.setChecked(settings.show_member_ids)
        self.supports.setChecked(settings.show_supports)
        self.local_axes.setChecked(settings.show_local_axes)
        self.loads.setChecked(settings.show_loads)
        self.load_values.setChecked(settings.show_load_values)
        self.load_directions.setChecked(settings.show_load_directions)
        self.reactions.setChecked(settings.show_reactions)
        self.equilibrium.setChecked(settings.show_equilibrium)
        self.diagram_fill.setChecked(settings.diagram_fill)
        self.diagram_placement.setCurrentIndex(self.diagram_placement.findData(settings.diagram_placement))
        self.axial_positive.setCurrentIndex(self.axial_positive.findData(settings.axial_positive))
        self.shear_positive.setCurrentIndex(self.shear_positive.findData(settings.shear_positive))
        self.moment_positive.setCurrentIndex(self.moment_positive.findData(settings.moment_positive))
        self.diagram_scale_mode.setCurrentIndex(self.diagram_scale_mode.findData(settings.diagram_scale_mode))
        self.diagram_scale_multiplier.setValue(settings.diagram_scale_multiplier)
        self.fbd_reference_x.setValue(settings.fbd_reference_x)
        self.fbd_reference_y.setValue(settings.fbd_reference_y)
