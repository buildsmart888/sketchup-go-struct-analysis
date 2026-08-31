"""Lightweight isometric section preview for the selected member's assigned section."""

from __future__ import annotations

import math
from typing import Any, Mapping

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SectionViewPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._section: Mapping[str, Any] | None = None
        self.title = QLabel("Select a member to inspect its section.", self)
        self.preview = _SectionPreview(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.title)
        layout.addWidget(self.preview, 1)

    def set_model_and_selection(self, model: Mapping[str, Any], selection: Mapping[str, list[int]]) -> None:
        members = set(selection.get("members", []))
        member = next((item for item in model.get("elements", []) if int(item.get("id", -1)) in members), None)
        section = next((item for item in model.get("sections", []) if member and int(item.get("id", -1)) == int(member.get("sec", -1))), None)
        self._section = section
        if section is None:
            self.title.setText("Select one member to inspect its extruded section.")
        else:
            self.title.setText(f"Section {section['id']} | {section.get('name') or section.get('material') or 'Elastic section'}")
        self.preview.update()


class _SectionPreview(QWidget):
    def __init__(self, owner: SectionViewPanel) -> None:
        super().__init__(owner)
        self.owner = owner
        self.setMinimumHeight(180)

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f8fafc"))
        section = self.owner._section
        if section is None:
            painter.setPen(QColor("#64748b"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No section selected")
            return
        area = max(float(section.get("a", 1.0)), 1.0e-6)
        depth = float(section.get("depth_cm", 0.0)) or math.sqrt(max(12.0 * float(section.get("i", 1.0)) / area, 1.0e-6))
        width = float(section.get("width_cm", 0.0)) or max(area / depth, depth * 0.35)
        scale = min((self.width() - 120) / max(width * 2.3, 1.0), (self.height() - 80) / max(depth * 1.7, 1.0))
        width_px, depth_px = width * scale, depth * scale
        x, y = self.width() / 2.0 - width_px / 2.0, self.height() / 2.0 - depth_px / 2.0
        front = QPolygonF([QPointF(x, y), QPointF(x + width_px, y), QPointF(x + width_px, y + depth_px), QPointF(x, y + depth_px)])
        offset_x, offset_y = 34.0, -24.0
        top = QPolygonF([QPointF(x, y), QPointF(x + width_px, y), QPointF(x + width_px + offset_x, y + offset_y), QPointF(x + offset_x, y + offset_y)])
        side = QPolygonF([QPointF(x + width_px, y), QPointF(x + width_px, y + depth_px), QPointF(x + width_px + offset_x, y + depth_px + offset_y), QPointF(x + width_px + offset_x, y + offset_y)])
        painter.setPen(QPen(QColor("#1e293b"), 1.5))
        painter.setBrush(QColor("#ccfbf1")); painter.drawPolygon(front)
        painter.setBrush(QColor("#99f6e4")); painter.drawPolygon(top)
        painter.setBrush(QColor("#5eead4")); painter.drawPolygon(side)
        painter.setPen(QColor("#334155"))
        painter.drawText(14, self.height() - 28, f"b = {width:.2f} cm")
        painter.drawText(14, self.height() - 10, f"h = {depth:.2f} cm | A = {area:.2f} cm2 | I = {float(section.get('i', 0.0)):.2f} cm4")
