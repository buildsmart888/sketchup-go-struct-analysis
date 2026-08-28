"""Truss-specific restrictions for the shared structural canvas."""

from __future__ import annotations

from typing import Any, Mapping

from .canvas import FrameCanvas
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen


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
