"""Interactive 2D rendering for the Frame workspace."""

from __future__ import annotations

import math
from typing import Any, Mapping

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


class FrameCanvas(QWidget):
    """Draws the structural model, deformation, and selected member diagrams."""

    _DIAGRAMS = {
        "n_kg": ("N", QColor("#0f766e")),
        "v_kg": ("V", QColor("#b45309")),
        "m_kg_m": ("M", QColor("#1d4ed8")),
        "v_mm": ("FE deflection", QColor("#be123c")),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model: Mapping[str, Any] = {}
        self._result: Mapping[str, Any] | None = None
        self._deformed_members: list[Mapping[str, Any]] = []
        self._diagram_members: list[Mapping[str, Any]] = []
        self._diagram_mode = "none"
        self._show_deformed = True
        self._zoom = 1.0
        self._pan = QPointF()
        self._drag_origin: QPoint | None = None
        self.setMinimumHeight(300)
        self.setMouseTracking(True)

    def set_model(self, model: Mapping[str, Any]) -> None:
        self._model = model
        self._zoom = 1.0
        self._pan = QPointF()
        self.update()

    def set_result(self, result: Mapping[str, Any] | None) -> None:
        self._result = result
        if result is None:
            self._deformed_members = []
            self._diagram_members = []
        self.update()

    def set_deformed_members(self, members: list[Mapping[str, Any]]) -> None:
        self._deformed_members = members
        self.update()

    @property
    def diagram_mode(self) -> str:
        return self._diagram_mode

    def set_diagram_members(self, members: list[Mapping[str, Any]]) -> None:
        self._diagram_members = members
        self.update()

    def set_diagram_mode(self, mode: str) -> None:
        self._diagram_mode = mode if mode in {*self._DIAGRAMS, "all"} else "none"
        self.update()

    def set_show_deformed(self, show: bool) -> None:
        self._show_deformed = show
        self.update()

    def wheelEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self._zoom = max(0.35, min(8.0, self._zoom * factor))
        self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._drag_origin is not None:
            current = event.position().toPoint()
            self._pan += QPointF(current - self._drag_origin)
            self._drag_origin = current
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f8fafc"))

        nodes = self._model.get("nodes", [])
        if not nodes:
            painter.setPen(QColor("#64748b"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No frame model")
            return

        node_by_id = {node["id"]: node for node in nodes}
        points = [(float(node["x"]), float(node["y"])) for node in nodes]
        min_x, max_x = min(x for x, _ in points), max(x for x, _ in points)
        min_y, max_y = min(y for _, y in points), max(y for _, y in points)
        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)
        margin = 70.0
        usable_width = max(self.width() - 2.0 * margin, 1.0)
        usable_height = max(self.height() - 2.0 * margin, 1.0)
        scale = min(usable_width / span_x, usable_height / span_y) * self._zoom
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        viewport_center = QPointF(self.width() / 2.0, self.height() / 2.0) + self._pan

        def screen(x: float, y: float) -> QPointF:
            return QPointF(viewport_center.x() + (x - center_x) * scale, viewport_center.y() - (y - center_y) * scale)

        self._draw_grid(painter, screen, min_x, max_x, min_y, max_y)
        self._draw_loads(painter, node_by_id, screen)

        member_pen = QPen(QColor("#1e293b"), 3.0)
        member_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(member_pen)
        for element in self._model.get("elements", []):
            first = node_by_id.get(element.get("n1"))
            second = node_by_id.get(element.get("n2"))
            if first is None or second is None:
                continue
            painter.drawLine(screen(float(first["x"]), float(first["y"])), screen(float(second["x"]), float(second["y"])))

        self._draw_diagram_overlays(painter, node_by_id, screen, span_x, span_y)
        self._draw_deformed_shape(painter, node_by_id, screen, span_x, span_y)
        self._draw_nodes_and_supports(painter, nodes, screen)
        self._draw_legend(painter)

    def _draw_grid(self, painter: QPainter, screen, min_x: float, max_x: float, min_y: float, max_y: float) -> None:
        grid_step = self._nice_step(max(max_x - min_x, max_y - min_y) / 6.0)
        painter.setPen(QPen(QColor("#e2e8f0"), 1.0))
        start_x = math.floor(min_x / grid_step) * grid_step
        start_y = math.floor(min_y / grid_step) * grid_step
        x = start_x
        while x <= max_x + grid_step:
            top, bottom = screen(x, min_y - grid_step), screen(x, max_y + grid_step)
            painter.drawLine(top, bottom)
            x += grid_step
        y = start_y
        while y <= max_y + grid_step:
            left, right = screen(min_x - grid_step, y), screen(max_x + grid_step, y)
            painter.drawLine(left, right)
            y += grid_step

    def _draw_loads(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen) -> None:
        pen = QPen(QColor("#dc2626"), 1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(QColor("#dc2626"))
        element_by_id = {element.get("id"): element for element in self._model.get("elements", [])}
        for load in self._model.get("eloads", []):
            element = element_by_id.get(load.get("elem"))
            if not element:
                continue
            first, second = node_by_id.get(element.get("n1")), node_by_id.get(element.get("n2"))
            if first is None or second is None:
                continue
            start = screen(float(first["x"]), float(first["y"]))
            end = screen(float(second["x"]), float(second["y"]))
            direction = end - start
            length = math.hypot(direction.x(), direction.y())
            if length < 1.0:
                continue
            normal = QPointF(-direction.y() / length, direction.x() / length)
            for fraction in (0.14, 0.38, 0.62, 0.86):
                point = start + direction * fraction
                head = point + normal * 22.0
                painter.drawLine(head, point)
                painter.drawPolygon(QPolygonF([point, point + normal * 7.0 + direction * 4.0 / length, point + normal * 7.0 - direction * 4.0 / length]))

    def _draw_deformed_shape(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen, span_x: float, span_y: float) -> None:
        if not self._show_deformed or not self._result:
            return
        if self._deformed_members:
            self._draw_deformed_member_curves(painter, node_by_id, screen, span_x, span_y)
            return
        result_nodes = {node["id"]: node for node in self._result.get("nodes", [])}
        maximum = max((math.hypot(float(node.get("dx", 0.0)), float(node.get("dy", 0.0))) for node in result_nodes.values()), default=0.0)
        if maximum <= 1.0e-15:
            return
        exaggeration = max(span_x, span_y) * 0.12 / maximum
        pen = QPen(QColor("#0f766e"), 2.0, Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for element in self._model.get("elements", []):
            first, second = node_by_id.get(element.get("n1")), node_by_id.get(element.get("n2"))
            first_result, second_result = result_nodes.get(element.get("n1")), result_nodes.get(element.get("n2"))
            if not first or not second or not first_result or not second_result:
                continue
            p1 = screen(float(first["x"]) + float(first_result.get("dx", 0.0)) * exaggeration, float(first["y"]) + float(first_result.get("dy", 0.0)) * exaggeration)
            p2 = screen(float(second["x"]) + float(second_result.get("dx", 0.0)) * exaggeration, float(second["y"]) + float(second_result.get("dy", 0.0)) * exaggeration)
            painter.drawLine(p1, p2)

    def _draw_deformed_member_curves(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen, span_x: float, span_y: float) -> None:
        maximum = 0.0
        for member in self._deformed_members:
            node = node_by_id.get(member["n1"])
            if node is None:
                continue
            angle = float(member["angle_rad"])
            for point in member.get("points", []):
                x = float(point["x_m"])
                original_x = float(node["x"]) + math.cos(angle) * x
                original_y = float(node["y"]) + math.sin(angle) * x
                maximum = max(maximum, math.hypot(float(point["x_deformed_m"]) - original_x, float(point["y_deformed_m"]) - original_y))
        if maximum <= 1.0e-15:
            return
        exaggeration = max(span_x, span_y) * 0.12 / maximum
        pen = QPen(QColor("#0f766e"), 2.0, Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for member in self._deformed_members:
            node = node_by_id.get(member["n1"])
            if node is None:
                continue
            angle = float(member["angle_rad"])
            curve = QPolygonF()
            for point in member.get("points", []):
                x = float(point["x_m"])
                original_x = float(node["x"]) + math.cos(angle) * x
                original_y = float(node["y"]) + math.sin(angle) * x
                deformed_x = original_x + (float(point["x_deformed_m"]) - original_x) * exaggeration
                deformed_y = original_y + (float(point["y_deformed_m"]) - original_y) * exaggeration
                curve.append(screen(deformed_x, deformed_y))
            painter.drawPolyline(curve)

    def _draw_diagram_overlays(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen, span_x: float, span_y: float) -> None:
        if not self._diagram_members or self._diagram_mode == "none":
            return
        keys = list(self._DIAGRAMS) if self._diagram_mode == "all" else [self._diagram_mode]
        for key in keys:
            maximum = max(
                (abs(float(point.get(key, 0.0))) for member in self._diagram_members for point in member.get("points", [])),
                default=0.0,
            )
            if maximum <= 1.0e-12:
                continue
            # A common scale per result selection preserves visual comparisons between members.
            amplitude = max(span_x, span_y) * (0.075 if self._diagram_mode == "all" else 0.14) / maximum
            label, color = self._DIAGRAMS[key]
            self._draw_member_diagram(painter, node_by_id, screen, key, amplitude, color, self._diagram_mode == "all")

    def _draw_member_diagram(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen, key: str, amplitude: float, color: QColor, compact: bool) -> None:
        pen = QPen(color, 1.7 if compact else 2.2, Qt.PenStyle.DashLine if key == "v_mm" else Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        fill = QColor(color)
        fill.setAlpha(38 if compact else 62)
        for member in self._diagram_members:
            node = node_by_id.get(member.get("n1"))
            points = member.get("points", [])
            if node is None or len(points) < 2:
                continue
            angle = float(member.get("angle_rad", 0.0))
            direction_x, direction_y = math.cos(angle), math.sin(angle)
            normal_x, normal_y = -direction_y, direction_x
            base = QPolygonF()
            curve = QPolygonF()
            for point in points:
                x = float(point.get("x_m", 0.0))
                origin_x = float(node["x"]) + direction_x * x
                origin_y = float(node["y"]) + direction_y * x
                offset = float(point.get(key, 0.0)) * amplitude
                base.append(screen(origin_x, origin_y))
                curve.append(screen(origin_x + normal_x * offset, origin_y + normal_y * offset))
            polygon = QPolygonF(base)
            for point in reversed(curve):
                polygon.append(point)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawPolygon(polygon)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(pen)
            painter.drawPolyline(curve)

    def _draw_nodes_and_supports(self, painter: QPainter, nodes: list[Mapping[str, Any]], screen) -> None:
        font = QFont(painter.font())
        font.setPointSize(9)
        painter.setFont(font)
        for node in nodes:
            point = screen(float(node["x"]), float(node["y"]))
            support = node.get("support", "Free")
            if support != "Free":
                support_pen = QPen(QColor("#334155"), 1.5)
                painter.setPen(support_pen)
                painter.setBrush(QColor("#cbd5e1"))
                triangle = QPolygonF([point + QPointF(-10, 18), point + QPointF(10, 18), point + QPointF(0, 3)])
                painter.drawPolygon(triangle)
                if support == "Fixed":
                    painter.drawLine(point + QPointF(-15, 21), point + QPointF(15, 21))
            painter.setPen(QPen(QColor("#0f172a"), 1.2))
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(point, 4.2, 4.2)
            painter.setPen(QColor("#334155"))
            painter.drawText(point + QPointF(7, -8), f"N{node['id']}")

    def _draw_legend(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor("#1e293b"), 3.0))
        painter.drawLine(18, 24, 44, 24)
        painter.setPen(QColor("#334155"))
        painter.drawText(52, 29, "Frame")
        if self._show_deformed and self._result:
            painter.setPen(QPen(QColor("#0f766e"), 2.0, Qt.PenStyle.DashLine))
            painter.drawLine(110, 24, 136, 24)
            painter.setPen(QColor("#334155"))
            painter.drawText(144, 29, "Deformed")
        if self._diagram_mode != "none":
            keys = list(self._DIAGRAMS) if self._diagram_mode == "all" else [self._diagram_mode]
            x = 238
            for key in keys:
                label, color = self._DIAGRAMS[key]
                painter.setPen(QPen(color, 2.0, Qt.PenStyle.DashLine if key == "v_mm" else Qt.PenStyle.SolidLine))
                painter.drawLine(x, 24, x + 20, 24)
                painter.setPen(QColor("#334155"))
                painter.drawText(x + 26, 29, label)
                x += 26 + painter.fontMetrics().horizontalAdvance(label) + 18

    @staticmethod
    def _nice_step(value: float) -> float:
        if value <= 0:
            return 1.0
        base = 10.0 ** math.floor(math.log10(value))
        fraction = value / base
        return (1.0 if fraction <= 1.0 else 2.0 if fraction <= 2.0 else 5.0 if fraction <= 5.0 else 10.0) * base
