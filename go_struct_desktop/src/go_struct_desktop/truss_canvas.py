"""Truss-specific restrictions for the shared structural canvas."""

from __future__ import annotations

from typing import Any, Mapping

from .canvas import FrameCanvas
import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from .truss_tools import distribute_vertical_line_load


class TrussCanvas(FrameCanvas):
    """Allow bar authoring while preventing frame-only result and load tools."""

    def set_model(self, model: Mapping[str, Any]) -> None:
        normalized = dict(model)
        project_info = dict(normalized.get("projectInfo", {}))
        project_info["analysisType"] = "Truss"
        normalized["projectInfo"] = project_info
        super().set_model(normalized)

    def set_tool(self, tool: str) -> None:
        if tool == "member_load":
            self.authoring_message.emit("Truss loads must be applied at nodes; member loads are unavailable.")
            super().set_tool("select")
            return
        super().set_tool(tool)

    def set_diagram_mode(self, mode: str) -> None:
        if mode == "all":
            mode = "n_kg"
        if mode == "v_mm":
            self.set_show_deformed(True)
            self.authoring_message.emit("Showing truss deflected shape from solved nodal displacements.")
            super().set_diagram_mode("none")
            return
        if mode in {"v_kg", "m_kg_m"}:
            self.authoring_message.emit("Truss members report axial force N only.")
            mode = "none"
        super().set_diagram_mode(mode)

    def _diagram_color(self, key: str, value: float, default: QColor, member: Mapping[str, Any] | None = None) -> QColor:
        if key != "n_kg":
            return default
        if value > 1.0e-12:
            return QColor("#15803d")
        if value < -1.0e-12:
            return QColor("#b91c1c")
        return QColor("#475569")

    def _draw_deformed_member_curves(self, painter: QPainter, node_by_id, screen, span_x: float, span_y: float) -> None:  # type: ignore[no-untyped-def]
        super()._draw_deformed_member_curves(painter, node_by_id, screen, span_x, span_y)
        maximum = 0.0
        maximum_point: tuple[Mapping[str, Any], Mapping[str, Any], float, float, float, float] | None = None
        for member in self._deformed_members:
            node = node_by_id.get(member.get("n1"))
            if node is None:
                continue
            angle = float(member.get("angle_rad", 0.0))
            for point in member.get("points", []):
                distance = float(point.get("x_m", 0.0))
                original_x = float(node["x"]) + math.cos(angle) * distance
                original_y = float(node["y"]) + math.sin(angle) * distance
                deformed_x, deformed_y = float(point.get("x_deformed_m", original_x)), float(point.get("y_deformed_m", original_y))
                displacement = math.hypot(deformed_x - original_x, deformed_y - original_y)
                if displacement > maximum:
                    maximum = displacement
                    maximum_point = member, point, original_x, original_y, deformed_x, deformed_y
        if maximum_point is None or maximum <= 1.0e-15:
            return
        _, _point, original_x, original_y, deformed_x, deformed_y = maximum_point
        exaggeration = max(span_x, span_y) * 0.12 / maximum
        marker = screen(original_x + (deformed_x - original_x) * exaggeration, original_y + (deformed_y - original_y) * exaggeration)
        painter.setPen(QPen(QColor("#be123c"), 1.7))
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(marker, 5.0, 5.0)
        label = f"Max |Delta| = {self._units.format_displacement(maximum)} {self._units.length_unit}"
        painter.setPen(QColor("#9f1239"))
        painter.drawText(marker + QPointF(8.0, -10.0), label)

    def _draw_legend(self, painter: QPainter) -> None:
        super()._draw_legend(painter)
        if self._diagram_mode != "n_kg":
            return
        painter.setPen(QPen(QColor("#15803d"), 3.4))
        painter.drawLine(18, 48, 42, 48)
        painter.setPen(QColor("#334155"))
        painter.drawText(50, 53, "Tension (+N)")
        painter.setPen(QPen(QColor("#b91c1c"), 3.4))
        painter.drawLine(164, 48, 188, 48)
        painter.setPen(QColor("#334155"))
        painter.drawText(196, 53, "Compression (-N)")

    def assign_active_section_to_selection(self) -> None:
        if not self._selected_members:
            self.authoring_message.emit("Select one or more truss members first.")
            return
        model = self._mutable_model()
        for member in model["elements"]:
            if int(member["id"]) in self._selected_members:
                member["sec"] = self._active_section
        self._emit_model(model)
        self.authoring_message.emit(f"Assigned Section {self._active_section} to {len(self._selected_members)} truss member(s).")

    def set_roof_height(self, height_m: float) -> None:
        if height_m <= 0.0:
            self.authoring_message.emit("Roof height must be greater than zero.")
            return
        model = self._mutable_model()
        positive_nodes = [node for node in model.get("nodes", []) if float(node["y"]) > 1.0e-9]
        current_height = max((float(node["y"]) for node in positive_nodes), default=0.0)
        if current_height <= 1.0e-12:
            self.authoring_message.emit("The current truss has no roof profile to resize.")
            return
        factor = float(height_m) / current_height
        for node in positive_nodes:
            node["y"] = float(node["y"]) * factor
        self._emit_model(model)
        self.authoring_message.emit(f"Roof height set to {height_m:g} m.")

    def distribute_roof_load(self, intensity: float, load_case: str) -> None:
        try:
            model, summary = distribute_vertical_line_load(self._model, self._selected_members, intensity, load_case)
        except ValueError as exc:
            self.authoring_message.emit(str(exc))
            return
        self._emit_model(model)
        self.authoring_message.emit(
            f"Applied {intensity:g} per projected m to {len(summary['member_ids'])} member(s): "
            f"total Fy = {summary['resultant_fy']:.4g}."
        )
