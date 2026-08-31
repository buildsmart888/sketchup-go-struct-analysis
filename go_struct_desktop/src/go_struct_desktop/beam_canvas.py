"""Beam-aware canvas constraints built on the shared Frame canvas renderer."""

from __future__ import annotations

import math
from typing import Any, Mapping

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPen

from .canvas import FrameCanvas


class BeamCanvas(FrameCanvas):
    """Keep Beam authoring horizontal so invalid geometry cannot be drawn by accident."""

    def _beam_y(self) -> float:
        nodes = self._model.get("nodes", [])
        return float(nodes[0]["y"]) if nodes else 0.0

    def set_model(self, model: Mapping[str, Any]) -> None:
        # The common input panel intentionally stores only editable project fields. Restore the
        # workspace identity for the canvas after ordinary table/canvas edits.
        normalized = dict(model)
        project_info = dict(normalized.get("projectInfo", {}))
        project_info["analysisType"] = "Beam"
        normalized["projectInfo"] = project_info
        super().set_model(normalized)

    def _beam_position(self, position: tuple[float, float]) -> tuple[float, float]:
        return float(position[0]), self._beam_y()

    def _snap_position(self, position: QPointF) -> tuple[float, float]:
        return self._beam_position(super()._snap_position(position))

    def _create_node(self, position: tuple[float, float]) -> int | None:
        return super()._create_node(self._beam_position(position))

    def _create_member(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        first, second = self._beam_position(start), self._beam_position(end)
        if second[0] < first[0]:
            first, second = second, first
        super()._create_member(first, second)

    def _move_node(self, node_id: int, position: tuple[float, float]) -> None:
        super()._move_node(node_id, self._beam_position(position))

    def move_selection(self, delta_x: float, delta_y: float) -> None:
        if abs(delta_y) > 1.0e-12:
            self.authoring_message.emit("Beam nodes move horizontally; vertical movement is locked.")
        super().move_selection(delta_x, 0.0)

    def array_selection(self, count: int, delta_x: float, delta_y: float) -> None:
        if abs(delta_y) > 1.0e-12:
            self.authoring_message.emit("Beam arrays remain on the beam baseline.")
        super().array_selection(count, delta_x, 0.0)

    def add_span(self, length: float, support: str = "Free", section_id: int | None = None) -> None:
        """Append one horizontal span from the current right-most node."""
        if length <= 0.0:
            self.authoring_message.emit("Span length must be greater than zero.")
            return
        model = self._mutable_model()
        if not model.get("nodes"):
            self.authoring_message.emit("Create a beam node before adding a span.")
            return
        start = max(model["nodes"], key=lambda node: float(node["x"]))
        end_x = float(start["x"]) + float(length)
        if any(math.isclose(float(node["x"]), end_x, abs_tol=1.0e-9) for node in model["nodes"]):
            self.authoring_message.emit("A beam node already exists at that span endpoint.")
            return
        node_id = self._next_id(model["nodes"])
        member_id = self._next_id(model["elements"])
        model["nodes"].append({"id": node_id, "x": end_x, "y": self._beam_y(), "support": support})
        model["elements"].append(
            {
                "id": member_id,
                "n1": int(start["id"]),
                "n2": node_id,
                "sec": int(section_id if section_id is not None else self._active_section),
                "release": "Rigid-Rigid",
            }
        )
        self._set_selection({node_id}, {member_id})
        self._emit_model(model)
        self.authoring_message.emit(f"Added span {member_id}: {length:g} m.")

    def resize_selected_span(self, length: float) -> None:
        """Change a selected span and translate every following beam node by the same delta."""
        if length <= 0.0:
            self.authoring_message.emit("Span length must be greater than zero.")
            return
        if len(self._selected_members) != 1:
            self.authoring_message.emit("Select exactly one beam span to edit its length.")
            return
        model = self._mutable_model()
        member_id = next(iter(self._selected_members))
        member = next((item for item in model["elements"] if int(item["id"]) == member_id), None)
        nodes = {int(node["id"]): node for node in model["nodes"]}
        if member is None or int(member["n1"]) not in nodes or int(member["n2"]) not in nodes:
            return
        first, second = nodes[int(member["n1"])], nodes[int(member["n2"])]
        current = float(second["x"]) - float(first["x"])
        delta = float(length) - current
        if abs(delta) <= 1.0e-12:
            return
        endpoint = float(second["x"])
        for node in model["nodes"]:
            if float(node["x"]) >= endpoint - 1.0e-9:
                node["x"] = float(node["x"]) + delta
        coordinates = sorted(float(node["x"]) for node in model["nodes"])
        if any(math.isclose(left, right, abs_tol=1.0e-9) for left, right in zip(coordinates, coordinates[1:])):
            self.authoring_message.emit("That span length would merge beam nodes.")
            return
        self._emit_model(model)
        self.authoring_message.emit(f"Span {member_id} set to {length:g} m; following stations moved by {delta:+g} m.")

    def insert_support(self, x: float, support: str = "RollerX") -> None:
        """Split the span containing x, then place a support at the new beam station."""
        nodes = {int(node["id"]): node for node in self._model.get("nodes", [])}
        target = next(
            (
                member
                for member in self._model.get("elements", [])
                if int(member["n1"]) in nodes
                and int(member["n2"]) in nodes
                and float(nodes[int(member["n1"])]["x"]) + 1.0e-9 < x < float(nodes[int(member["n2"])]["x"]) - 1.0e-9
            ),
            None,
        )
        if target is None:
            self.authoring_message.emit("Choose a location strictly inside an existing beam span.")
            return
        self._split_member(int(target["id"]), (float(x), self._beam_y()))
        inserted = next((node for node in self._model.get("nodes", []) if math.isclose(float(node["x"]), float(x), abs_tol=1.0e-9)), None)
        if inserted is not None:
            self._apply_support(int(inserted["id"]), support)
            self.authoring_message.emit(f"Inserted {support} support at x = {x:g} m.")

    def _draw_member_annotations(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen) -> None:
        super()._draw_member_annotations(painter, node_by_id, screen)
        if not self._display.show_member_ids:
            return
        painter.setPen(QColor("#64748b"))
        for member in self._model.get("elements", []):
            first, second = node_by_id.get(member.get("n1")), node_by_id.get(member.get("n2"))
            if first is None or second is None:
                continue
            length = abs(float(second["x"]) - float(first["x"]))
            midpoint = screen((float(first["x"]) + float(second["x"])) / 2.0, self._beam_y())
            painter.drawText(midpoint + QPointF(-30.0, 28.0), f"L = {self._units.length(length):g} {self._units.length_unit}")

    def _draw_nodes_and_supports(self, painter: QPainter, nodes: list[Mapping[str, Any]], screen, *, show_labels: bool = True) -> None:
        super()._draw_nodes_and_supports(painter, nodes, screen, show_labels=show_labels)
        if self._view_mode != "results" or not self._result:
            return
        reactions = {int(node["id"]): node for node in self._result.get("nodes", [])}
        painter.setPen(QPen(QColor("#9f1239"), 1.0))
        for node in nodes:
            if node.get("support", "Free") == "Free":
                continue
            reaction = reactions.get(int(node["id"]))
            if reaction is None or abs(float(reaction.get("fy", 0.0))) <= 1.0e-12:
                continue
            point = screen(float(node["x"]), float(node["y"]))
            painter.drawText(point + QPointF(10.0, 38.0), f"Ry {self._units.force(float(reaction['fy'])):,.3g}")

    def _draw_deformed_member_curves(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen, span_x: float, span_y: float) -> None:
        super()._draw_deformed_member_curves(painter, node_by_id, screen, span_x, span_y)
        maximum = 0.0
        maximum_point: tuple[float, float, float, float] | None = None
        for member in self._deformed_members:
            node = node_by_id.get(member.get("n1"))
            if node is None:
                continue
            for point in member.get("points", []):
                original_x = float(node["x"]) + float(point.get("x_m", 0.0))
                original_y = float(node["y"])
                deformed_x = float(point.get("x_deformed_m", original_x))
                deformed_y = float(point.get("y_deformed_m", original_y))
                displacement = math.hypot(deformed_x - original_x, deformed_y - original_y)
                if displacement > maximum:
                    maximum = displacement
                    maximum_point = original_x, original_y, deformed_x, deformed_y
        if maximum_point is None or maximum <= 1.0e-15:
            return
        original_x, original_y, deformed_x, deformed_y = maximum_point
        exaggeration = max(span_x, span_y) * 0.12 / maximum
        marker = screen(original_x + (deformed_x - original_x) * exaggeration, original_y + (deformed_y - original_y) * exaggeration)
        painter.setPen(QPen(QColor("#0f766e"), 1.7))
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(marker, 5.0, 5.0)
        painter.setPen(QColor("#0f766e"))
        painter.drawText(marker + QPointF(8.0, -10.0), f"Max |v| = {self._units.format_displacement(maximum)} {self._units.length_unit}")
