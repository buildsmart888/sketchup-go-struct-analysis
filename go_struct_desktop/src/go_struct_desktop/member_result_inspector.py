"""Selected-member result inspector with compact, linked sampled-result charts."""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QComboBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .contours import stress_value
from .units import UnitSystem, get_unit_system


_QUANTITIES = {
    "n_kg": ("Axial N", QColor("#0f766e")),
    "v_kg": ("Shear V", QColor("#b45309")),
    "m_kg_m": ("Moment M", QColor("#1d4ed8")),
    "v_mm": ("Deflection", QColor("#be123c")),
    "stress_kg_cm2": ("Elastic stress", QColor("#7c3aed")),
}


class ResultSparkline(QWidget):
    """A compact signed chart; it deliberately reuses the sampled solver output."""

    def __init__(self, key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._member: Mapping[str, Any] | None = None
        self._units = get_unit_system("legacy_kg_m")
        self.setMinimumSize(142, 94)

    def set_member(self, member: Mapping[str, Any] | None) -> None:
        self._member = member
        self.update()

    def set_unit_system(self, key: str) -> None:
        self._units = get_unit_system(key)
        self.update()

    def _value(self, point: Mapping[str, Any]) -> float:
        if self._key == "stress_kg_cm2":
            return stress_value(point)
        return float(point.get(self._key, 0.0))

    def _display_value(self, value: float) -> float:
        if self._key in {"n_kg", "v_kg"}:
            return self._units.force(value)
        if self._key == "m_kg_m":
            return self._units.moment(value)
        if self._key == "v_mm":
            return self._units.length(value / 1000.0)
        return value

    def _unit(self) -> str:
        if self._key in {"n_kg", "v_kg"}:
            return self._units.force_unit
        if self._key == "m_kg_m":
            return self._units.moment_label()
        if self._key == "v_mm":
            return self._units.length_unit
        return "kg/cm2"

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        label, color = _QUANTITIES[self._key]
        painter.setPen(QColor("#334155"))
        painter.drawText(8, 16, f"{label} ({self._unit()})")
        if not self._member or not self._member.get("points"):
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No result")
            return
        points = self._member["points"]
        values = [self._display_value(self._value(point)) for point in points]
        maximum = max(max(abs(value) for value in values), 1.0e-12)
        left, right, top, bottom = 8.0, 8.0, 25.0, 13.0
        width, height = max(self.width() - left - right, 1.0), max(self.height() - top - bottom, 1.0)
        length = max(float(self._member.get("length_m", 0.0)), 1.0e-12)

        def screen(point: Mapping[str, Any], value: float) -> QPointF:
            return QPointF(left + float(point["x_m"]) / length * width, top + (maximum - value) / (2.0 * maximum) * height)

        zero_y = top + height / 2.0
        painter.setPen(QPen(QColor("#cbd5e1"), 1.0))
        painter.drawLine(QPointF(left, zero_y), QPointF(left + width, zero_y))
        line = QPolygonF([screen(point, value) for point, value in zip(points, values)])
        fill = QPolygonF([QPointF(left, zero_y), *line, QPointF(left + width, zero_y)])
        transparent = QColor(color)
        transparent.setAlpha(46)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(transparent)
        painter.drawPolygon(fill)
        painter.setPen(QPen(color, 1.7))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(line)
        extrema = max(values, key=abs)
        painter.setPen(QColor("#475569"))
        painter.drawText(QPointF(left + 2.0, top + 12.0), f"max {extrema:,.3f}")


class MemberResultInspector(QWidget):
    """Dock content linked to the canvas selection and active Case/Combo results."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._members: list[Mapping[str, Any]] = []
        self._units = get_unit_system("legacy_kg_m")
        self.member_selector = QComboBox(self)
        self.summary = QLabel("Select a member on the canvas.", self)
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color: #475569;")
        self._charts = {key: ResultSparkline(key, self) for key in _QUANTITIES}
        self._build_layout()
        self.member_selector.currentIndexChanged.connect(self._refresh)

    @property
    def selected_member_id(self) -> int | None:
        value = self.member_selector.currentData()
        return int(value) if value is not None else None

    def set_members(self, members: list[Mapping[str, Any]]) -> None:
        current = self.member_selector.currentData()
        self._members = members
        self.member_selector.blockSignals(True)
        self.member_selector.clear()
        for member in members:
            self.member_selector.addItem(f"E{member['id']}  N{member['n1']} - N{member['n2']}", member["id"])
        index = self.member_selector.findData(current)
        self.member_selector.setCurrentIndex(index if index >= 0 else (0 if members else -1))
        self.member_selector.blockSignals(False)
        self._refresh()

    def set_selection(self, selection: Mapping[str, list[int]]) -> None:
        members = selection.get("members", [])
        if len(members) != 1:
            return
        index = self.member_selector.findData(members[0])
        if index >= 0:
            self.member_selector.setCurrentIndex(index)

    def set_unit_system(self, key: str) -> None:
        self._units = get_unit_system(key)
        for chart in self._charts.values():
            chart.set_unit_system(key)
        self._refresh()

    def _build_layout(self) -> None:
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Member", self))
        controls.addWidget(self.member_selector, 1)
        grid = QGridLayout()
        for index, key in enumerate(_QUANTITIES):
            grid.addWidget(self._charts[key], index // 2, index % 2)
        box = QFrame(self)
        box.setFrameShape(QFrame.Shape.StyledPanel)
        summary_layout = QVBoxLayout(box)
        summary_layout.addWidget(self.summary)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(controls)
        layout.addWidget(box)
        layout.addLayout(grid)

    def _refresh(self) -> None:
        member = next((item for item in self._members if item.get("id") == self.member_selector.currentData()), None)
        for chart in self._charts.values():
            chart.set_member(member)
        if member is None:
            self.summary.setText("Select a member on the canvas.")
            return
        points = member.get("points", [])
        max_deflection = max((abs(float(point.get("v_mm", 0.0))) for point in points), default=0.0)
        max_moment = max((abs(float(point.get("m_kg_m", 0.0))) for point in points), default=0.0)
        self.summary.setText(
            f"E{member['id']}  N{member['n1']} -> N{member['n2']}\n"
            f"L = {self._units.length(float(member.get('length_m', 0.0))):.3f} {self._units.length_unit} | "
            f"|M|max = {self._units.moment(max_moment):.3f} {self._units.moment_label()} | "
            f"|v|max = {self._units.format_displacement(max_deflection / 1000.0)} {self._units.length_unit}"
        )
