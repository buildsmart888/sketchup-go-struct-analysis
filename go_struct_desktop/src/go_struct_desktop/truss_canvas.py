"""Truss-specific restrictions for the shared structural canvas."""

from __future__ import annotations

from typing import Any, Mapping

from .canvas import FrameCanvas
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen

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
        if mode in {"v_kg", "m_kg_m", "v_mm"}:
            self.authoring_message.emit("Truss members report axial force N only.")
            mode = "none"
        super().set_diagram_mode(mode)

    def _member_pen(self, element: Mapping[str, Any]) -> QPen:
        member = next((item for item in (self._result or {}).get("elements", []) if int(item.get("id", -1)) == int(element["id"])), None)
        axial = float(member["n1_forces"]["axial"]) if member else 0.0
        color = QColor("#b91c1c") if axial < -1.0e-12 else QColor("#15803d") if axial > 1.0e-12 else QColor("#475569")
        pen = QPen(color, 3.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        return pen

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
