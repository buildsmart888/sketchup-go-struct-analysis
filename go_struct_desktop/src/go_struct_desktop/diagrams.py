"""Reusable member diagram viewer for Frame, Beam, and future Truss workspaces."""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QToolTip, QVBoxLayout, QWidget


QUANTITIES = {
    "n_kg": ("Axial N", "kg", QColor("#0f766e")),
    "v_kg": ("Shear V", "kg", QColor("#b45309")),
    "m_kg_m": ("Moment M", "kg-m", QColor("#1d4ed8")),
    "v_mm": ("Deflection v", "mm", QColor("#be123c")),
}


class DiagramCanvas(QWidget):
    """A compact interactive chart for one sampled member quantity."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._member: Mapping[str, Any] | None = None
        self._quantity = "m_kg_m"
        self.setMinimumHeight(280)
        self.setMouseTracking(True)

    def set_diagram(self, member: Mapping[str, Any] | None, quantity: str) -> None:
        self._member = member
        self._quantity = quantity
        self.update()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if not self._member:
            return
        points = self._member.get("points", [])
        if not points:
            return
        margin_left, margin_right = 58.0, 24.0
        width = max(self.width() - margin_left - margin_right, 1.0)
        length = float(self._member["length_m"])
        x_m = min(max((event.position().x() - margin_left) / width * length, 0.0), length)
        point = min(points, key=lambda item: abs(float(item["x_m"]) - x_m))
        label, unit, _ = QUANTITIES[self._quantity]
        QToolTip.showText(event.globalPosition().toPoint(), f"{label}: {float(point[self._quantity]):,.3f} {unit}\nx: {float(point['x_m']):,.3f} m", self)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        if not self._member:
            painter.setPen(QColor("#64748b"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Select a member to view its diagram")
            return
        points = self._member.get("points", [])
        if not points:
            return
        label, unit, color = QUANTITIES[self._quantity]
        values = [float(point[self._quantity]) for point in points]
        lower, upper = min(min(values), 0.0), max(max(values), 0.0)
        padding = max((upper - lower) * 0.14, 1.0e-9)
        lower, upper = lower - padding, upper + padding
        left, right, top, bottom = 58.0, 24.0, 34.0, 38.0
        chart_width = max(self.width() - left - right, 1.0)
        chart_height = max(self.height() - top - bottom, 1.0)
        length = float(self._member["length_m"])

        def screen(x_value: float, y_value: float) -> QPointF:
            return QPointF(left + x_value / length * chart_width, top + (upper - y_value) / (upper - lower) * chart_height)

        zero_y = screen(0.0, 0.0).y()
        painter.setPen(QPen(QColor("#cbd5e1"), 1.0))
        painter.drawLine(QPointF(left, zero_y), QPointF(left + chart_width, zero_y))
        painter.drawLine(QPointF(left, top), QPointF(left, top + chart_height))
        painter.setPen(QColor("#475569"))
        painter.drawText(QPointF(left, 18.0), f"{label} ({unit})")
        painter.drawText(QPointF(left + chart_width - 42.0, self.height() - 12.0), f"L = {length:.2f} m")
        painter.drawText(QPointF(7.0, top + 9.0), f"{upper:.2f}")
        painter.drawText(QPointF(7.0, top + chart_height), f"{lower:.2f}")

        line = QPolygonF([screen(float(point["x_m"]), float(point[self._quantity])) for point in points])
        fill = QPolygonF([QPointF(left, zero_y), *line, QPointF(left + chart_width, zero_y)])
        painter.setPen(Qt.PenStyle.NoPen)
        transparent = QColor(color)
        transparent.setAlpha(40)
        painter.setBrush(transparent)
        painter.drawPolygon(fill)
        pen = QPen(color, 2.3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(line)

        extrema = self._member.get("extrema", {}).get(self._quantity, {})
        for key, prefix in (("max", "max"), ("min", "min")):
            item = extrema.get(key)
            if not item:
                continue
            point = screen(float(item["x_m"]), float(item["value"]))
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(point, 3.4, 3.4)
            painter.setPen(QColor("#334155"))
            governing = f" [{item['combo']}]" if item.get("combo") else ""
            painter.drawText(point + QPointF(5.0, -6.0), f"{prefix} {float(item['value']):.2f}{governing}")


class FrameDiagramsPanel(QWidget):
    """Member and quantity selectors surrounding a reusable diagram canvas."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._members: list[Mapping[str, Any]] = []
        self.member_selector = QComboBox(self)
        self.quantity_selector = QComboBox(self)
        for key, (label, _, _) in QUANTITIES.items():
            self.quantity_selector.addItem(label, key)
        self.canvas = DiagramCanvas(self)
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(QLabel("Member", self))
        controls.addWidget(self.member_selector)
        controls.addSpacing(12)
        controls.addWidget(QLabel("Diagram", self))
        controls.addWidget(self.quantity_selector)
        controls.addStretch()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(controls)
        layout.addWidget(self.canvas)
        self.member_selector.currentIndexChanged.connect(self._update_canvas)
        self.quantity_selector.currentIndexChanged.connect(self._update_canvas)

    def set_members(self, members: list[Mapping[str, Any]]) -> None:
        current_id = self.member_selector.currentData()
        self._members = members
        self.member_selector.blockSignals(True)
        self.member_selector.clear()
        for member in members:
            self.member_selector.addItem(f"E{member['id']}  N{member['n1']} - N{member['n2']}", member["id"])
        if current_id is not None:
            index = self.member_selector.findData(current_id)
            if index >= 0:
                self.member_selector.setCurrentIndex(index)
        self.member_selector.blockSignals(False)
        self._update_canvas()

    def _update_canvas(self) -> None:
        member_id = self.member_selector.currentData()
        member = next((item for item in self._members if item["id"] == member_id), None)
        self.canvas.set_diagram(member, self.quantity_selector.currentData() or "m_kg_m")
