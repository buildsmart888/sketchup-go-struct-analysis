"""Interactive 2D rendering for the Frame workspace."""

from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from PySide6.QtCore import QElapsedTimer, QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QToolTip, QWidget

from .display import DisplaySettings
from .contours import ContourRange, colour_stops, contour_range, stress_value
from .spatial_index import CanvasSpatialIndex, nearest_point
from .units import UnitSystem, get_unit_system


class FrameCanvas(QWidget):
    """Draws the structural model, deformation, and selected member diagrams."""

    model_change_requested = Signal(object)
    selection_changed = Signal(object)
    pointer_changed = Signal(float, float)
    tool_changed = Signal(str)
    authoring_message = Signal(str)
    load_requested = Signal(str, object)
    load_edit_requested = Signal(str, object)
    delete_requested = Signal(object)

    _DIAGRAMS = {
        "n_kg": ("N", QColor("#0f766e")),
        "v_kg": ("V", QColor("#b45309")),
        "m_kg_m": ("M", QColor("#1d4ed8")),
        "v_mm": ("FE deflection", QColor("#be123c")),
    }
    _LOAD_CASE_COLORS = ("#15803d", "#2563eb", "#b45309", "#9333ea", "#dc2626", "#0f766e")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model: Mapping[str, Any] = {}
        self._result: Mapping[str, Any] | None = None
        self._result_selection = "envelope"
        self._view_mode = "results"
        self._load_case = ""
        self._display = DisplaySettings()
        self._units = get_unit_system("legacy_kg_m")
        self._deformed_members: list[Mapping[str, Any]] = []
        self._diagram_members: list[Mapping[str, Any]] = []
        self._diagram_maxima: dict[str, float] = {}
        self._diagram_mode = "none"
        self._show_diagram_values = False
        self._hover_points: list[tuple[QPointF, Mapping[str, Any], Mapping[str, Any]]] = []
        self._hover_cells: dict[tuple[int, int], list[tuple[QPointF, Mapping[str, Any], Mapping[str, Any]]]] = {}
        self._hover_cell_size = 32.0
        self._hover_sample: tuple[QPointF, Mapping[str, Any], Mapping[str, Any]] | None = None
        self._show_deformed = True
        self._stress_members: list[Mapping[str, Any]] = []
        self._show_stress = False
        self._contour_ranges: dict[tuple[str, str, str], ContourRange] = {}
        self._deformation_animation = False
        self._animation_phase = 0.0
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(33)
        self._animation_timer.timeout.connect(self._advance_deformation_animation)
        self._tool = "select"
        self._grid_visible = True
        self._snap_enabled = True
        self._snap_to_node = True
        self._grid_spacing = 1.0
        self._active_section = 1
        self._active_member_type = "Frame"
        self._selection_filter = "both"
        self._selected_nodes: set[int] = set()
        self._selected_members: set[int] = set()
        self._selection_origin: QPointF | None = None
        self._selection_rect: QRectF | None = None
        self._selection_crossing = False
        self._member_start: tuple[float, float] | None = None
        self._member_current: tuple[float, float] | None = None
        self._pending_support = "Pinned"
        self._pending_load: dict[str, Any] | None = None
        self._pending_load_position: QPointF | None = None
        self._node_drag_id: int | None = None
        self._node_drag_position: tuple[float, float] | None = None
        self._view_center = QPointF()
        self._view_model_center = QPointF()
        self._view_scale = 1.0
        self._zoom = 1.0
        self._pan = QPointF()
        self._label_rects: list[QRectF] = []
        self._drag_origin: QPoint | None = None
        self._geometry_cache: QPixmap | None = None
        self._geometry_cache_key: tuple[Any, ...] | None = None
        self._geometry_cache_pan = QPointF()
        self._spatial_index = CanvasSpatialIndex(self._model)
        self._interaction_active = False
        self._interaction_settle_timer = QTimer(self)
        self._interaction_settle_timer.setSingleShot(True)
        self._interaction_settle_timer.setInterval(150)
        self._interaction_settle_timer.timeout.connect(self._finish_interaction)
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setSingleShot(True)
        self._repaint_timer.timeout.connect(self._flush_repaint)
        self._repaint_clock = QElapsedTimer()
        self._repaint_clock.start()
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._flush_hover)
        self._hover_clock = QElapsedTimer()
        self._hover_clock.start()
        self._queued_hover: tuple[QPointF, QPoint] | None = None
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_model(self, model: Mapping[str, Any]) -> None:
        self._model = model
        self._spatial_index = CanvasSpatialIndex(model)
        self._invalidate_geometry_cache()
        sections = model.get("sections", [])
        if sections and self._active_section not in {int(section["id"]) for section in sections}:
            self._active_section = int(sections[0]["id"])
        self._zoom = 1.0
        self._pan = QPointF()
        self._clear_hover()
        self.update()

    @property
    def interaction_active(self) -> bool:
        """Whether canvas rendering is temporarily using the low-detail interaction path."""

        return self._interaction_active

    def _begin_interaction(self) -> None:
        if not self._interaction_active:
            self._interaction_active = True
            self._clear_hover()
        self._interaction_settle_timer.start()

    def _finish_interaction(self) -> None:
        if not self._interaction_active:
            return
        self._interaction_active = False
        self._clear_hover()
        self.update()

    def _request_repaint(self, *, interaction: bool = False) -> None:
        if not interaction:
            self.update()
            return
        self._begin_interaction()
        elapsed = self._repaint_clock.elapsed()
        if elapsed >= 16:
            self._repaint_clock.restart()
            self.update()
        elif not self._repaint_timer.isActive():
            self._repaint_timer.start(max(1, 16 - elapsed))

    def _flush_repaint(self) -> None:
        self._repaint_clock.restart()
        self.update()

    def _queue_hover(self, position: QPointF, global_position: QPoint) -> None:
        if self._interaction_active or (len(self._model.get("elements", [])) > 300 and not self._selected_members):
            self._clear_hover()
            return
        elapsed = self._hover_clock.elapsed()
        if elapsed >= 33:
            self._hover_clock.restart()
            self._show_hover_value(position, global_position)
            return
        self._queued_hover = (QPointF(position), QPoint(global_position))
        if not self._hover_timer.isActive():
            self._hover_timer.start(max(1, 33 - elapsed))

    def _flush_hover(self) -> None:
        if self._queued_hover is None or self._interaction_active:
            return
        position, global_position = self._queued_hover
        self._queued_hover = None
        self._hover_clock.restart()
        self._show_hover_value(position, global_position)

    def _detail_level(self) -> str:
        if self._interaction_active:
            return "interaction"
        member_count = len(self._model.get("elements", []))
        if member_count > 2000:
            return "large"
        if member_count > 300:
            return "reduced"
        return "full"

    def set_result(self, result: Mapping[str, Any] | None) -> None:
        self._result = result
        self._invalidate_geometry_cache()
        if result is None:
            self._deformed_members = []
            self._diagram_members = []
        self._clear_hover()
        self.update()

    def set_result_selection(self, selection: str) -> None:
        self._result_selection = selection
        self.update()

    def set_view_mode(self, mode: str) -> None:
        self._view_mode = mode if mode in {"model", "results", "fbd"} else "results"
        self.update()

    def set_load_case(self, load_case: str) -> None:
        self._load_case = load_case
        self.update()

    def set_display_settings(self, settings: DisplaySettings) -> None:
        self._display = settings
        self._grid_visible = settings.show_grid
        self._contour_ranges.clear()
        self._invalidate_geometry_cache()
        self.update()

    def set_unit_system(self, key: str) -> None:
        self._units = get_unit_system(key)
        self.update()

    def set_deformed_members(self, members: list[Mapping[str, Any]]) -> None:
        self._deformed_members = members
        self.update()

    def set_stress_members(self, members: list[Mapping[str, Any]]) -> None:
        self._stress_members = members
        self._contour_ranges.clear()
        self._invalidate_geometry_cache()
        self.update()

    def set_show_stress(self, show: bool) -> None:
        self._show_stress = show
        self._invalidate_geometry_cache()
        self.update()

    def _invalidate_geometry_cache(self) -> None:
        self._geometry_cache = None
        self._geometry_cache_key = None

    @property
    def diagram_mode(self) -> str:
        return self._diagram_mode

    def set_diagram_members(self, members: list[Mapping[str, Any]]) -> None:
        self._diagram_members = members
        self._diagram_maxima = {
            key: max((abs(float(point.get(key, 0.0))) for member in members for point in member.get("points", [])), default=0.0)
            for key in self._DIAGRAMS
        }
        self._contour_ranges.clear()
        self._clear_hover()
        self.update()

    def set_diagram_mode(self, mode: str) -> None:
        self._diagram_mode = mode if mode in {*self._DIAGRAMS, "all"} else "none"
        self._contour_ranges.clear()
        self._clear_hover()
        self.update()

    def set_show_diagram_values(self, show: bool) -> None:
        self._show_diagram_values = show
        self.update()

    def set_show_deformed(self, show: bool) -> None:
        self._show_deformed = show
        self.update()

    def set_deformation_animation(self, active: bool) -> None:
        self._deformation_animation = active
        if active:
            self._animation_timer.start()
        else:
            self._animation_timer.stop()
            self._animation_phase = 0.0
        self.update()

    def _advance_deformation_animation(self) -> None:
        self._animation_phase = (self._animation_phase + 0.055) % (2.0 * math.pi)
        self.update()

    def _deformation_factor(self) -> float:
        return 1.0 if not self._deformation_animation else 0.12 + 0.88 * (math.sin(self._animation_phase) + 1.0) / 2.0

    @property
    def tool(self) -> str:
        return self._tool

    @property
    def selection(self) -> dict[str, list[int]]:
        return {"nodes": sorted(self._selected_nodes), "members": sorted(self._selected_members)}

    def set_tool(self, tool: str) -> None:
        if tool in {"nodal_load", "member_load"}:
            self._pending_load = None
            self._pending_load_position = None
        self._tool = tool if tool in {"select", "node", "member", "pan", "support", "nodal_load", "member_load", "split", "zoom_window"} else "select"
        self._member_start = None
        self._member_current = None
        self._selection_origin = None
        self._selection_rect = None
        self._node_drag_id = None
        self._node_drag_position = None
        self.setCursor(Qt.CursorShape.OpenHandCursor if self._tool == "pan" else Qt.CursorShape.ArrowCursor)
        self.tool_changed.emit(self._tool)
        self.update()

    def set_pending_load(self, kind: str, values: Mapping[str, Any], preset: str) -> None:
        """Arm a configured load so the next canvas click places the chosen load type."""
        if kind not in {"nodal", "member"}:
            return
        self.set_tool("nodal_load" if kind == "nodal" else "member_load")
        self._pending_load = {"kind": kind, "values": dict(values), "preset": preset}
        self.authoring_message.emit(f"{preset.replace('_', ' ').title()} ready: click a {'node' if kind == 'nodal' else 'member'} to place it.")

    def clear_pending_load(self) -> None:
        if self._pending_load is None:
            return
        self._pending_load = None
        self._pending_load_position = None
        self.authoring_message.emit("Load placement cancelled.")
        self.update()

    def set_grid_visible(self, visible: bool) -> None:
        self._grid_visible = visible
        self.update()

    def set_snap_enabled(self, enabled: bool) -> None:
        self._snap_enabled = enabled

    def set_snap_to_node(self, enabled: bool) -> None:
        self._snap_to_node = enabled

    def set_grid_spacing(self, spacing: float) -> None:
        self._grid_spacing = max(float(spacing), 0.001)
        self.update()

    def set_active_section(self, section_id: int) -> None:
        self._active_section = section_id

    def set_active_member_type(self, member_type: str) -> None:
        self._active_member_type = member_type if member_type in {"Frame", "Truss"} else "Frame"

    def set_pending_support(self, support: str) -> None:
        self._pending_support = support if support in {"Free", "Pinned", "Fixed", "RollerX", "RollerY", "Spring"} else "Pinned"
        self.set_tool("support")

    def duplicate_selection(self) -> None:
        self._duplicate_selection(lambda x, y: (x + (self._grid_spacing if self._snap_enabled else 1.0), y + (self._grid_spacing if self._snap_enabled else 1.0)))

    def array_selection(self, count: int, delta_x: float, delta_y: float) -> None:
        if count < 1:
            return
        for index in range(1, count + 1):
            self._duplicate_selection(lambda x, y, factor=index: (x + factor * delta_x, y + factor * delta_y), select_new=index == count)

    def mirror_selection(self, axis: str) -> None:
        nodes = self._selection_nodes_including_members()
        if not nodes:
            self.authoring_message.emit("Select a node or member to mirror.")
            return
        coordinates = {int(node["id"]): node for node in self._model.get("nodes", [])}
        values = [coordinates[node_id] for node_id in nodes]
        center = sum(float(node["x"] if axis == "vertical" else node["y"]) for node in values) / len(values)
        if axis == "vertical":
            self._duplicate_selection(lambda x, y: (2.0 * center - x, y))
        else:
            self._duplicate_selection(lambda x, y: (x, 2.0 * center - y))

    def move_selection(self, delta_x: float, delta_y: float) -> None:
        node_ids = self._selection_nodes_including_members()
        if not node_ids:
            self.authoring_message.emit("Select a node or member to move.")
            return
        model = self._mutable_model()
        for node in model["nodes"]:
            if int(node["id"]) in node_ids:
                node["x"] = float(node["x"]) + delta_x
                node["y"] = float(node["y"]) + delta_y
        if not self._model_has_valid_member_lengths(model):
            self.authoring_message.emit("Move would create a zero-length member.")
            return
        self._emit_model(model)

    def select_members_by_section(self, section_id: int) -> None:
        members = {int(member["id"]) for member in self._model.get("elements", []) if int(member.get("sec", -1)) == section_id}
        self._set_selection(set(), members)
        self.authoring_message.emit(f"Selected {len(members)} member(s) using Section {section_id}.")

    def _selection_nodes_including_members(self) -> set[int]:
        member_ids = set(self._selected_members)
        node_ids = set(self._selected_nodes)
        for member in self._model.get("elements", []):
            if int(member["id"]) in member_ids:
                node_ids.update((int(member["n1"]), int(member["n2"])))
        if not node_ids:
            return set()
        return node_ids

    def _duplicate_selection(self, transform, select_new: bool = True) -> None:  # type: ignore[no-untyped-def]
        member_ids = set(self._selected_members)
        node_ids = self._selection_nodes_including_members()
        if not node_ids:
            self.authoring_message.emit("Select a node or member to duplicate.")
            return
        model = self._mutable_model()
        node_by_id = {int(node["id"]): node for node in model["nodes"]}
        mapping: dict[int, int] = {}
        for node_id in sorted(node_ids):
            source = node_by_id[node_id]
            new_id = self._next_id(model["nodes"])
            mapping[node_id] = new_id
            x, y = transform(float(source["x"]), float(source["y"]))
            if any(math.isclose(float(node["x"]), x, abs_tol=1.0e-9) and math.isclose(float(node["y"]), y, abs_tol=1.0e-9) for node in model["nodes"]):
                self.authoring_message.emit("Duplicate overlaps an existing node. Change the transform.")
                return
            model["nodes"].append({**source, "id": new_id, "x": x, "y": y})
        new_members: set[int] = set()
        for member in list(model["elements"]):
            if int(member["id"]) not in member_ids:
                continue
            new_id = self._next_id(model["elements"])
            model["elements"].append({**member, "id": new_id, "n1": mapping[int(member["n1"])], "n2": mapping[int(member["n2"])]})
            new_members.add(new_id)
            for load in list(model["eloads"]):
                if int(load["elem"]) == int(member["id"]):
                    model["eloads"].append({**load, "elem": new_id})
        for load in list(model["nloads"]):
            if int(load["node"]) in mapping:
                model["nloads"].append({**load, "node": mapping[int(load["node"])]})
        if select_new:
            self._set_selection(set(mapping.values()), new_members)
        self._emit_model(model)

    def align_selected(self, axis: str) -> None:
        node_ids = set(self._selected_nodes)
        if len(node_ids) < 2:
            self.authoring_message.emit("Select at least two nodes to align.")
            return
        model = self._mutable_model()
        selected = [node for node in model["nodes"] if int(node["id"]) in node_ids]
        coordinate = "x" if axis == "x" else "y"
        value = sum(float(node[coordinate]) for node in selected) / len(selected)
        for node in selected:
            node[coordinate] = value
        if not self._model_has_valid_member_lengths(model):
            self.authoring_message.emit("Alignment would create a zero-length member.")
            return
        self._emit_model(model)

    def fit_selection(self) -> None:
        selected = [node for node in self._model.get("nodes", []) if int(node["id"]) in self._selected_nodes]
        if not selected:
            self.fit_view()
            return
        min_x, max_x = min(float(node["x"]) for node in selected), max(float(node["x"]) for node in selected)
        min_y, max_y = min(float(node["y"]) for node in selected), max(float(node["y"]) for node in selected)
        all_nodes = self._model.get("nodes", [])
        all_min_x, all_max_x = min(float(node["x"]) for node in all_nodes), max(float(node["x"]) for node in all_nodes)
        all_min_y, all_max_y = min(float(node["y"]) for node in all_nodes), max(float(node["y"]) for node in all_nodes)
        base_scale = min(max(self.width() - 140.0, 1.0) / max(all_max_x - all_min_x, 1.0), max(self.height() - 140.0, 1.0) / max(all_max_y - all_min_y, 1.0))
        target_scale = min(max(self.width() - 140.0, 1.0) / max(max_x - min_x, 1.0), max(self.height() - 140.0, 1.0) / max(max_y - min_y, 1.0))
        self._zoom = max(0.35, min(8.0, target_scale / base_scale))
        current_scale = base_scale * self._zoom
        model_center_x, model_center_y = (all_min_x + all_max_x) / 2.0, (all_min_y + all_max_y) / 2.0
        selection_center_x, selection_center_y = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0
        self._pan = QPointF(-(selection_center_x - model_center_x) * current_scale, (selection_center_y - model_center_y) * current_scale)
        self.update()

    def set_selection_filter(self, selection_filter: str) -> None:
        self._selection_filter = selection_filter if selection_filter in {"nodes", "members", "both"} else "both"
        self._set_selection(set(), set())

    def fit_view(self) -> None:
        self._zoom = 1.0
        self._pan = QPointF()
        self.update()

    @property
    def has_hover_value(self) -> bool:
        return self._hover_sample is not None

    def wheelEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        model_x, model_y = self._screen_to_model(event.position())
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        old_zoom = self._zoom
        self._zoom = max(0.35, min(8.0, self._zoom * factor))
        if not math.isclose(old_zoom, self._zoom):
            new_scale = self._view_scale * self._zoom / old_zoom
            default_center = QPointF(self.width() / 2.0, self.height() / 2.0)
            desired_center = QPointF(
                event.position().x() - (model_x - self._view_model_center.x()) * new_scale,
                event.position().y() + (model_y - self._view_model_center.y()) * new_scale,
            )
            self._pan = desired_center - default_center
        self._request_repaint(interaction=True)

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.setFocus()
        if event.button() == Qt.MouseButton.RightButton and self._pending_load is not None:
            self.clear_pending_load()
            return
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and self._tool == "pan"):
            self._drag_origin = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._begin_interaction()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._pointer_moved(event.position())
            if self._tool == "node":
                self._create_node(self._snap_position(event.position()))
            elif self._tool == "member":
                self._member_start = self._snap_position(event.position())
                self._member_current = self._member_start
                self._request_repaint(interaction=True)
            elif self._tool == "support":
                node = self._node_at(event.position())
                if node is None:
                    self.authoring_message.emit("Click a node to assign a support.")
                else:
                    self._apply_support(int(node["id"]), self._pending_support)
            elif self._tool == "nodal_load":
                node = self._node_at(event.position())
                if node is None:
                    self.authoring_message.emit("Click a node to add a nodal load.")
                elif self._pending_load and self._pending_load["kind"] == "nodal":
                    self.add_nodal_load(int(node["id"]), self._pending_load["values"])
                else:
                    self.load_requested.emit("nodal", {"node": int(node["id"]), "preset": "generic"})
            elif self._tool == "member_load":
                member = self._member_at(event.position())
                if member is None:
                    self.authoring_message.emit("Click a member to add a member load.")
                elif self._pending_load and self._pending_load["kind"] == "member":
                    values = dict(self._pending_load["values"])
                    if values.get("type") in {"Point Force", "Point Moment"}:
                        values["x_m"] = self._member_station(int(member["id"]), self._screen_to_model(event.position()))
                    self.add_member_load(int(member["id"]), values)
                else:
                    self.load_requested.emit("member", {"member": int(member["id"]), "position": self._screen_to_model(event.position()), "preset": "generic"})
            elif self._tool == "split":
                member = self._member_at(event.position())
                if member is None:
                    self.authoring_message.emit("Click a member to split it.")
                else:
                    self._split_member(int(member["id"]), self._screen_to_model(event.position()))
            elif self._tool == "zoom_window":
                self._selection_origin = event.position()
                self._selection_rect = QRectF(event.position(), event.position())
                self._begin_interaction()
            elif self._tool == "select":
                load = self._load_at(event.position()) if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else None
                if load is not None:
                    self.load_edit_requested.emit(load[0], load[1])
                    return
                node = self._node_at(event.position()) if self._selection_filter in {"nodes", "both"} else None
                if node is not None:
                    self._set_selection({int(node["id"])}, set())
                    self._node_drag_id = int(node["id"])
                    self._node_drag_position = (float(node["x"]), float(node["y"]))
                else:
                    self._selection_origin = event.position()
                    self._selection_rect = QRectF(event.position(), event.position())
                    self._selection_crossing = False
                    self._begin_interaction()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._drag_origin is not None:
            current = event.position().toPoint()
            self._pan += QPointF(current - self._drag_origin)
            self._drag_origin = current
            self._request_repaint(interaction=True)
        else:
            self._pointer_moved(event.position())
            if self._pending_load is not None and self._tool in {"nodal_load", "member_load"}:
                self._pending_load_position = event.position()
                self._request_repaint(interaction=True)
            if self._tool == "member" and self._member_start is not None:
                self._member_current = self._snap_position(event.position())
                self._request_repaint(interaction=True)
            elif self._tool == "select" and self._node_drag_id is not None:
                self._node_drag_position = self._snap_position(event.position())
                self._request_repaint(interaction=True)
            elif self._tool == "select" and self._selection_origin is not None:
                self._selection_rect = QRectF(self._selection_origin, event.position()).normalized()
                self._selection_crossing = event.position().x() < self._selection_origin.x()
                self._request_repaint(interaction=True)
            elif self._tool == "zoom_window" and self._selection_origin is not None:
                self._selection_rect = QRectF(self._selection_origin, event.position()).normalized()
                self._request_repaint(interaction=True)
            else:
                self._queue_hover(event.position(), event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and self._drag_origin is not None):
            self._drag_origin = None
            self.setCursor(Qt.CursorShape.OpenHandCursor if self._tool == "pan" else Qt.CursorShape.ArrowCursor)
            self._interaction_settle_timer.start()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self._tool == "member" and self._member_start is not None:
                self._create_member(self._member_start, self._snap_position(event.position()))
                self._member_start = None
                self._member_current = None
            elif self._tool == "select" and self._node_drag_id is not None:
                self._move_node(self._node_drag_id, self._snap_position(event.position()))
                self._node_drag_id = None
                self._node_drag_position = None
            elif self._tool == "select" and self._selection_origin is not None:
                self._apply_selection(event.position())
                self._selection_origin = None
                self._selection_rect = None
                self._request_repaint(interaction=True)
            elif self._tool == "zoom_window" and self._selection_origin is not None:
                self._apply_zoom_window()
                self._selection_origin = None
                self._selection_rect = None
                self._request_repaint(interaction=True)
            self._interaction_settle_timer.start()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key() == Qt.Key.Key_Delete:
            self._request_delete_selection()
            return
        if event.key() == Qt.Key.Key_Escape:
            if self._pending_load is not None:
                self.clear_pending_load()
                return
            self._member_start = None
            self._member_current = None
            self._selection_origin = None
            self._selection_rect = None
            self._selection_crossing = False
            self._node_drag_id = None
            self._node_drag_position = None
            self._set_selection(set(), set())
            self.update()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        self._label_rects = []
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f8fafc"))

        nodes = self._model.get("nodes", [])
        if not nodes:
            painter.setPen(QColor("#64748b"))
            model_kind = str(self._model.get("projectInfo", {}).get("analysisType", "Frame"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"No {model_kind.lower()} model")
            return

        node_by_id = self._spatial_index.nodes
        min_x, min_y, max_x, max_y = self._spatial_index.bounds
        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)
        margin = 70.0
        usable_width = max(self.width() - 2.0 * margin, 1.0)
        usable_height = max(self.height() - 2.0 * margin, 1.0)
        scale = min(usable_width / span_x, usable_height / span_y) * self._zoom
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        viewport_center = QPointF(self.width() / 2.0, self.height() / 2.0) + self._pan
        self._view_center = viewport_center
        self._view_model_center = QPointF(center_x, center_y)
        self._view_scale = scale

        def screen(x: float, y: float) -> QPointF:
            return QPointF(viewport_center.x() + (x - center_x) * scale, viewport_center.y() - (y - center_y) * scale)

        detail_level = self._detail_level()
        if self._display.show_grid and self._grid_visible:
            self._draw_grid(painter, screen, min_x, max_x, min_y, max_y)
        self._draw_cached_member_geometry(painter, node_by_id, screen, interaction=detail_level == "interaction")

        self._draw_node_move_preview(painter, node_by_id, screen)
        self._draw_member_preview(painter, screen)
        if detail_level == "interaction":
            self._draw_lightweight_nodes(painter, nodes, screen)
            self._draw_selection_rect(painter)
            return

        self._update_hover_points(node_by_id, screen, span_x, span_y)
        if self._display.show_loads:
            self._draw_loads(painter, node_by_id, screen, self._display_load_factors(), show_labels=detail_level == "full")
        if detail_level == "full":
            self._draw_member_annotations(painter, node_by_id, screen)
        self._draw_pending_load_preview(painter, node_by_id, screen)
        if self._view_mode == "fbd":
            self._draw_fbd(painter, node_by_id, screen)
        elif self._view_mode == "results":
            self._draw_diagram_overlays(painter, node_by_id, screen, span_x, span_y)
            self._draw_deformed_shape(painter, node_by_id, screen, span_x, span_y)
            if detail_level == "full":
                self._draw_hover_crosshair(painter, node_by_id, screen, span_x, span_y)
        self._draw_nodes_and_supports(painter, nodes, screen, show_labels=detail_level == "full")
        if self._view_mode == "results" and detail_level != "interaction":
            self._draw_truss_axial_extrema(painter, node_by_id, screen)
        self._draw_selection_rect(painter)
        self._draw_legend(painter)

    def _geometry_cache_identity(self) -> tuple[Any, ...]:
        return (
            id(self._spatial_index),
            self.width(),
            self.height(),
            round(self._zoom, 8),
            self._show_stress,
            self._view_mode,
        )

    def _draw_cached_member_geometry(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen, *, interaction: bool) -> None:
        """Cache the stable member-line layer and translate it cheaply while panning."""

        key = self._geometry_cache_identity()
        cache_is_current = (
            self._geometry_cache is not None
            and self._geometry_cache_key == key
            and (interaction or self._geometry_cache_pan == self._pan)
        )
        if not cache_is_current:
            self._geometry_cache = QPixmap(self.size())
            self._geometry_cache.fill(Qt.GlobalColor.transparent)
            cache_painter = QPainter(self._geometry_cache)
            cache_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._draw_member_geometry(cache_painter, node_by_id, screen)
            cache_painter.end()
            self._geometry_cache_key = key
            self._geometry_cache_pan = QPointF(self._pan)

        if self._geometry_cache is not None:
            offset = self._pan - self._geometry_cache_pan if interaction else QPointF()
            painter.drawPixmap(QPoint(round(offset.x()), round(offset.y())), self._geometry_cache)
        self._draw_selected_member_geometry(painter, node_by_id, screen)

    def _draw_member_geometry(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen) -> None:
        for element in self._model.get("elements", []):
            first = node_by_id.get(element.get("n1"))
            second = node_by_id.get(element.get("n2"))
            if first is None or second is None:
                continue
            member_pen = self._stress_pen(element) if self._show_stress and self._view_mode == "results" else self._member_pen(element)
            painter.setPen(member_pen)
            painter.drawLine(screen(float(first["x"]), float(first["y"])), screen(float(second["x"]), float(second["y"])))

    def _draw_selected_member_geometry(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen) -> None:
        if not self._selected_members:
            return
        selected_pen = QPen(QColor("#0f766e"), 5.0)
        selected_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(selected_pen)
        for member_id in self._selected_members:
            member = next((item for item in self._model.get("elements", []) if int(item["id"]) == member_id), None)
            if member is None:
                continue
            first = node_by_id.get(member.get("n1"))
            second = node_by_id.get(member.get("n2"))
            if first is not None and second is not None:
                painter.drawLine(screen(float(first["x"]), float(first["y"])), screen(float(second["x"]), float(second["y"])))

    def _draw_pending_load_preview(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen) -> None:
        if self._pending_load is None or self._pending_load_position is None:
            return
        values = self._pending_load["values"]
        preset = str(self._pending_load["preset"]).replace("_", " ").title()
        color = QColor("#7c3aed")
        painter.setPen(QPen(color, 1.2, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(255, 255, 255, 220))
        message = f"Active: {preset} | click to place | Esc/right-click to cancel"
        text_rect = QRectF(16.0, 44.0, painter.fontMetrics().horizontalAdvance(message) + 14.0, painter.fontMetrics().height() + 8.0)
        painter.drawRect(text_rect)
        painter.setPen(color)
        painter.drawText(text_rect.adjusted(7.0, 0.0, 0.0, 0.0), Qt.AlignmentFlag.AlignVCenter, message)
        if self._pending_load["kind"] == "nodal":
            node = self._node_at(self._pending_load_position)
            if node is None:
                return
            point = screen(float(node["x"]), float(node["y"]))
            fx, fy, mz = float(values.get("fx", 0.0)), float(values.get("fy", 0.0)), float(values.get("mz", 0.0))
            if abs(fy) > 1.0e-12:
                self._draw_force_arrow(painter, screen, float(node["x"]), float(node["y"]), 0.0, math.copysign(32.0 / self._view_scale, fy), color)
            elif abs(fx) > 1.0e-12:
                self._draw_force_arrow(painter, screen, float(node["x"]), float(node["y"]), math.copysign(32.0 / self._view_scale, fx), 0.0, color)
            elif abs(mz) > 1.0e-12:
                self._draw_moment_arrow(painter, point, mz, color)
            else:
                painter.setPen(QPen(color, 1.8, Qt.PenStyle.DashLine))
                painter.drawEllipse(point, 10.0, 10.0)
            return

        member = self._member_at(self._pending_load_position)
        if member is None:
            return
        first, second = node_by_id.get(member.get("n1")), node_by_id.get(member.get("n2"))
        if first is None or second is None:
            return
        dx, dy = float(second["x"]) - float(first["x"]), float(second["y"]) - float(first["y"])
        length = math.hypot(dx, dy)
        if length <= 1.0e-12:
            return
        painter.setPen(QPen(color, 3.0, Qt.PenStyle.DashLine))
        painter.drawLine(screen(float(first["x"]), float(first["y"])), screen(float(second["x"]), float(second["y"])))
        cosine, sine = dx / length, dy / length
        load_type = str(values.get("type", "Distributed"))
        if load_type == "Distributed":
            for fraction in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
                value = float(values.get("w1", 0.0)) + (float(values.get("w2", values.get("w1", 0.0))) - float(values.get("w1", 0.0))) * fraction
                direction_x, direction_y = self._preview_load_direction(str(values.get("dir", "Local Y")), value, cosine, sine)
                self._draw_force_arrow(painter, screen, float(first["x"]) + dx * fraction, float(first["y"]) + dy * fraction, direction_x * 28.0 / self._view_scale, direction_y * 28.0 / self._view_scale, color)
            return
        station = self._member_station(int(member["id"]), self._screen_to_model(self._pending_load_position))
        x = float(first["x"]) + cosine * station
        y = float(first["y"]) + sine * station
        if load_type == "Point Moment":
            self._draw_moment_arrow(painter, screen(x, y), float(values.get("m", 0.0)) or 1.0, color)
        else:
            direction_x, direction_y = self._preview_load_direction(str(values.get("dir", "Local Y")), float(values.get("p", 0.0)), cosine, sine)
            self._draw_force_arrow(painter, screen, x, y, direction_x * 36.0 / self._view_scale, direction_y * 36.0 / self._view_scale, color)

    @staticmethod
    def _preview_load_direction(direction: str, value: float, cosine: float, sine: float) -> tuple[float, float]:
        sign = math.copysign(1.0, value if abs(value) > 1.0e-12 else -1.0)
        if direction == "Local X":
            return cosine * sign, sine * sign
        if direction == "Local Y":
            return -sine * sign, cosine * sign
        if direction == "Global X":
            return sign, 0.0
        return 0.0, sign

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

    def _member_pen(self, element: Mapping[str, Any]) -> QPen:
        is_truss = (
            str(element.get("memberType", "Frame")) == "Truss"
            and str(self._model.get("projectInfo", {}).get("analysisType", "Frame")).lower() not in {"truss", "2d truss"}
        )
        pen = QPen(QColor("#047857") if is_truss else QColor("#1e293b"), 2.6 if is_truss else 3.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        return pen

    def _stress_pen(self, element: Mapping[str, Any]) -> QPen:
        member = next((item for item in self._stress_members if int(item.get("id", -1)) == int(element.get("id", -1))), None)
        if member is None:
            return self._member_pen(element)
        values = [float(point.get("stress_top_kg_cm2", 0.0)) for point in member.get("points", [])]
        values.extend(float(point.get("stress_bottom_kg_cm2", 0.0)) for point in member.get("points", []))
        global_max = max((abs(float(point.get(key, 0.0))) for item in self._stress_members for point in item.get("points", []) for key in ("stress_top_kg_cm2", "stress_bottom_kg_cm2")), default=0.0)
        value = max(values, key=abs, default=0.0)
        ratio = min(abs(value) / global_max, 1.0) if global_max > 1.0e-12 else 0.0
        color = QColor("#dc2626") if value >= 0.0 else QColor("#2563eb")
        color.setAlphaF(0.35 + ratio * 0.65)
        pen = QPen(color, 5.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        return pen

    def _display_load_factors(self) -> dict[str, float]:
        if self._view_mode == "fbd":
            if self._result_selection.startswith("case:"):
                return {self._result_selection.removeprefix("case:"): 1.0}
            if self._result_selection.startswith("combo:"):
                return self._combination_factors(self._result_selection.removeprefix("combo:"))
            return {}
        selection = self._load_case or "all"
        if selection == "all":
            if self._view_mode == "model":
                return {str(load_case): 1.0 for load_case in self._model.get("loadcases", [])}
            load_case = self._model.get("loadcases", [""])[0] if self._model.get("loadcases") else ""
            return {str(load_case): 1.0} if load_case else {}
        if selection.startswith("case:"):
            return {selection.removeprefix("case:"): 1.0}
        if selection.startswith("combo:"):
            return self._combination_factors(selection.removeprefix("combo:"))
        return {selection: 1.0}

    def _combination_factors(self, name: str) -> dict[str, float]:
            combo = next((item for item in self._model.get("loadcombos", []) if item.get("name") == name), {})
            return {str(key): float(value) for key, value in combo.get("factors", {}).items()}

    def _load_case_color(self, load_case: str) -> QColor:
        cases = [str(value) for value in self._model.get("loadcases", [])]
        try:
            index = cases.index(load_case)
        except ValueError:
            index = 0
        return QColor(self._LOAD_CASE_COLORS[index % len(self._LOAD_CASE_COLORS)])

    def _draw_loads(
        self,
        painter: QPainter,
        node_by_id: Mapping[int, Mapping[str, Any]],
        screen,
        factors: Mapping[str, float],
        *,
        show_labels: bool = True,
    ) -> None:
        if not factors:
            return
        active_nodal = [load for load in self._model.get("nloads", []) if float(factors.get(str(load.get("lcase")), 0.0))]
        maximum_nodal = max(
            (max(abs(float(load.get(key, 0.0)) * float(factors.get(str(load.get("lcase")), 0.0))) for key in ("fx", "fy", "mz")) for load in active_nodal),
            default=0.0,
        )
        for load in active_nodal:
            node = node_by_id.get(load.get("node"))
            if node is None:
                continue
            load_case = str(load.get("lcase", ""))
            node_color = self._load_case_color(load_case)
            factor = float(factors.get(str(load.get("lcase")), 0.0))
            point = screen(float(node["x"]), float(node["y"]))
            for key, direction in (("fx", (1.0, 0.0)), ("fy", (0.0, 1.0))):
                value = float(load.get(key, 0.0)) * factor
                if abs(value) <= 1.0e-12:
                    continue
                length = 22.0 + 24.0 * abs(value) / maximum_nodal if maximum_nodal else 28.0
                model_length = length / self._view_scale
                self._draw_force_arrow(painter, screen, float(node["x"]), float(node["y"]), direction[0] * math.copysign(model_length, value), direction[1] * math.copysign(model_length, value), node_color)
            moment = float(load.get("mz", 0.0)) * factor
            if abs(moment) > 1.0e-12:
                self._draw_moment_arrow(painter, point, moment, node_color)
            if show_labels and self._display.show_load_values:
                labels = [f"{key.upper()} {float(load.get(key, 0.0)) * factor:,.2f}" for key in ("fx", "fy", "mz") if abs(float(load.get(key, 0.0)) * factor) > 1.0e-12]
                if labels:
                    painter.setPen(node_color)
                    prefix = f"[{load_case}] " if len(factors) > 1 else ""
                    painter.drawText(point + QPointF(10.0, -20.0), prefix + " | ".join(labels))

        element_by_id = {element.get("id"): element for element in self._model.get("elements", [])}
        active_member = [load for load in self._model.get("eloads", []) if float(factors.get(str(load.get("lcase")), 0.0))]
        distributed_loads = [load for load in active_member if load.get("type", "Distributed") == "Distributed"]
        point_loads = [load for load in active_member if load.get("type") in {"Point Force", "Point Moment"}]
        maximum_member = max(
            (max(abs(float(load.get(key, 0.0)) * float(factors.get(str(load.get("lcase")), 0.0))) for key in ("w1", "w2")) for load in distributed_loads),
            default=0.0,
        )
        maximum_point = max(
            (abs(float(load.get("p", load.get("m", 0.0)))) * float(factors.get(str(load.get("lcase")), 0.0)) for load in point_loads),
            default=0.0,
        )
        for load in distributed_loads:
            element = element_by_id.get(load.get("elem"))
            if not element:
                continue
            first, second = node_by_id.get(element.get("n1")), node_by_id.get(element.get("n2"))
            if first is None or second is None:
                continue
            load_case = str(load.get("lcase", ""))
            member_color = self._load_case_color(load_case)
            factor = float(factors.get(str(load.get("lcase")), 0.0))
            dx = float(second["x"]) - float(first["x"])
            dy = float(second["y"]) - float(first["y"])
            length = math.hypot(dx, dy)
            if length <= 1.0e-12:
                continue
            cosine, sine = dx / length, dy / length
            start = max(0.0, min(length, float(load.get("x1_m", 0.0)))) / length
            end = max(start, min(length, float(load.get("x2_m", length)))) / length
            for index, fraction in enumerate(tuple(start + (end - start) * step for step in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0))):
                value = (float(load.get("w1", 0.0)) + (float(load.get("w2", 0.0)) - float(load.get("w1", 0.0))) * fraction) * factor
                if abs(value) <= 1.0e-12:
                    continue
                if load.get("dir") == "Local X":
                    direction_x, direction_y = cosine * math.copysign(1.0, value), sine * math.copysign(1.0, value)
                elif load.get("dir") == "Local Y":
                    direction_x, direction_y = -sine * math.copysign(1.0, value), cosine * math.copysign(1.0, value)
                elif load.get("dir") == "Global X":
                    direction_x, direction_y = math.copysign(1.0, value), 0.0
                else:
                    direction_x, direction_y = 0.0, math.copysign(1.0, value)
                arrow_length = (16.0 + 28.0 * abs(value) / maximum_member) / self._view_scale if maximum_member else 24.0 / self._view_scale
                x = float(first["x"]) + dx * fraction
                y = float(first["y"]) + dy * fraction
                self._draw_force_arrow(painter, screen, x, y, direction_x * arrow_length, direction_y * arrow_length, member_color)
            if show_labels and self._display.show_load_values:
                middle_fraction = (start + end) / 2.0
                middle = screen(float(first["x"]) + dx * middle_fraction, float(first["y"]) + dy * middle_fraction)
                prefix = f"[{load_case}] " if len(factors) > 1 else ""
                label = f"{prefix}w {float(load.get('w1', 0.0)) * factor:,.2f} to {float(load.get('w2', 0.0)) * factor:,.2f} kg/m"
                if self._display.show_load_directions:
                    label += f" | {load.get('dir', 'Local Y')}"
                if start > 1.0e-9 or end < 1.0 - 1.0e-9:
                    label += f" | x={start * length:.2f}-{end * length:.2f} m"
                painter.setPen(member_color)
                painter.drawText(middle + QPointF(8.0, -26.0), label)
        for load in point_loads:
            element = element_by_id.get(load.get("elem"))
            if not element:
                continue
            first, second = node_by_id.get(element.get("n1")), node_by_id.get(element.get("n2"))
            if first is None or second is None:
                continue
            load_case = str(load.get("lcase", ""))
            member_color = self._load_case_color(load_case)
            dx = float(second["x"]) - float(first["x"])
            dy = float(second["y"]) - float(first["y"])
            length = math.hypot(dx, dy)
            if length <= 1.0e-12:
                continue
            cosine, sine = dx / length, dy / length
            factor = float(factors.get(str(load.get("lcase")), 0.0))
            at_x = min(length, max(0.0, float(load.get("x_m", 0.0))))
            x = float(first["x"]) + cosine * at_x
            y = float(first["y"]) + sine * at_x
            point = screen(x, y)
            if load.get("type") == "Point Force":
                value = float(load.get("p", 0.0)) * factor
                if abs(value) <= 1.0e-12:
                    continue
                if load.get("dir") == "Local X":
                    direction_x, direction_y = cosine * math.copysign(1.0, value), sine * math.copysign(1.0, value)
                elif load.get("dir") == "Local Y":
                    direction_x, direction_y = -sine * math.copysign(1.0, value), cosine * math.copysign(1.0, value)
                elif load.get("dir") == "Global X":
                    direction_x, direction_y = math.copysign(1.0, value), 0.0
                else:
                    direction_x, direction_y = 0.0, math.copysign(1.0, value)
                arrow_length = (22.0 + 30.0 * abs(value) / maximum_point) / self._view_scale if maximum_point else 30.0 / self._view_scale
                self._draw_force_arrow(painter, screen, x, y, direction_x * arrow_length, direction_y * arrow_length, member_color)
                if show_labels and self._display.show_load_values:
                    prefix = f"[{load_case}] " if len(factors) > 1 else ""
                    label = f"{prefix}P {value:,.2f} kg @ {at_x:.2f} m"
                    if self._display.show_load_directions:
                        label += f" | {load.get('dir', 'Local Y')}"
                    painter.setPen(member_color)
                    painter.drawText(point + QPointF(10.0, -22.0), label)
            else:
                value = float(load.get("m", 0.0)) * factor
                if abs(value) <= 1.0e-12:
                    continue
                self._draw_moment_arrow(painter, point, value, member_color)
                if show_labels and self._display.show_load_values:
                    painter.setPen(member_color)
                    prefix = f"[{load_case}] " if len(factors) > 1 else ""
                    painter.drawText(point + QPointF(18.0, -18.0), f"{prefix}M {value:,.2f} kg-m @ {at_x:.2f} m")

    def _draw_force_arrow(self, painter: QPainter, screen, x: float, y: float, vector_x: float, vector_y: float, color: QColor) -> None:
        tip = screen(x, y)
        tail = screen(x - vector_x, y - vector_y)
        direction = tip - tail
        length = math.hypot(direction.x(), direction.y())
        if length <= 1.0e-12:
            return
        unit = direction / length
        normal = QPointF(-unit.y(), unit.x())
        pen = QPen(color, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(color)
        painter.drawLine(tail, tip)
        painter.drawPolygon(QPolygonF([tip, tip - unit * 8.0 + normal * 4.0, tip - unit * 8.0 - normal * 4.0]))

    def _draw_moment_arrow(self, painter: QPainter, point: QPointF, value: float, color: QColor) -> None:
        rect = QRectF(point.x() - 15.0, point.y() - 15.0, 30.0, 30.0)
        span = 280 * 16 if value > 0 else -280 * 16
        start = 40 * 16 if value > 0 else 320 * 16
        painter.setPen(QPen(color, 1.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(rect, start, span)
        end_angle = math.radians((start + span) / 16.0)
        tip = QPointF(point.x() + 15.0 * math.cos(end_angle), point.y() - 15.0 * math.sin(end_angle))
        tangent = QPointF(-math.sin(end_angle), -math.cos(end_angle)) * (1.0 if value > 0 else -1.0)
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([tip, tip - tangent * 7.0 + QPointF(-tangent.y(), tangent.x()) * 3.5, tip - tangent * 7.0 - QPointF(-tangent.y(), tangent.x()) * 3.5]))

    def _draw_fbd(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen) -> None:
        factors = self._display_load_factors()
        if self._result is None:
            painter.setPen(QColor("#b45309"))
            painter.drawText(QRectF(18.0, 42.0, max(self.width() - 36.0, 1.0), 32.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Run analysis before viewing a free body diagram.")
            return
        if not factors or not self._result_selection.startswith(("case:", "combo:")):
            painter.setPen(QColor("#b45309"))
            painter.drawText(QRectF(18.0, 42.0, max(self.width() - 36.0, 1.0), 32.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Free body diagram requires a single Case or Combo. Envelope is not physically equilibrated.")
            return
        result_nodes = {node.get("id"): node for node in self._result.get("nodes", [])} if self._result else {}
        reaction_color = QColor("#b91c1c")
        maximum = max(
            (max(abs(float(node.get(key, 0.0))) for key in ("fx", "fy", "mz")) for node in result_nodes.values()),
            default=0.0,
        )
        if self._display.show_reactions:
            for node_id, node in node_by_id.items():
                if node.get("support") == "Free":
                    continue
                result = result_nodes.get(node_id)
                if result is None:
                    continue
                point = screen(float(node["x"]), float(node["y"]))
                labels: list[str] = []
                for key, direction, label in (("fx", (1.0, 0.0), "Rx"), ("fy", (0.0, 1.0), "Ry")):
                    value = float(result.get(key, 0.0))
                    if abs(value) <= 1.0e-12:
                        continue
                    length = 24.0 + 26.0 * abs(value) / maximum if maximum else 30.0
                    model_length = length / self._view_scale
                    self._draw_force_arrow(painter, screen, float(node["x"]), float(node["y"]), direction[0] * math.copysign(model_length, value), direction[1] * math.copysign(model_length, value), reaction_color)
                    labels.append(f"{label} {value:,.2f}")
                moment = float(result.get("mz", 0.0))
                if abs(moment) > 1.0e-12:
                    self._draw_moment_arrow(painter, point, moment, reaction_color)
                    labels.append(f"Mz {moment:,.2f}")
                if labels:
                    painter.setPen(reaction_color)
                    text = " | ".join(labels)
                    text_width = painter.fontMetrics().horizontalAdvance(text)
                    label_x = point.x() + 10.0
                    if label_x + text_width > self.width() - 10.0:
                        label_x = max(10.0, point.x() - text_width - 10.0)
                    painter.drawText(QPointF(label_x, min(point.y() + 34.0, self.height() - 10.0)), text)
        if self._display.show_equilibrium:
            fx, fy, moment = self._equilibrium_residual(factors, node_by_id, (self._display.fbd_reference_x, self._display.fbd_reference_y))
            painter.setPen(QColor("#334155"))
            title = self._result_selection.removeprefix("case:").removeprefix("combo:")
            lines = [
                f"Free body | {title}",
                f"ΣFx = {self._units.force(fx):,.3e} {self._units.force_unit}",
                f"ΣFy = {self._units.force(fy):,.3e} {self._units.force_unit}",
                f"ΣMz@{self._units.length(self._display.fbd_reference_x):g},{self._units.length(self._display.fbd_reference_y):g} = {self._units.moment(moment):,.3e} {self._units.moment_label()}",
            ]
            painter.drawText(QRectF(18.0, 42.0, 260.0, 92.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "\n".join(lines))

    def _equilibrium_residual(self, factors: Mapping[str, float], node_by_id: Mapping[int, Mapping[str, Any]], reference: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float, float]:
        total_fx = total_fy = total_moment = 0.0
        ref_x, ref_y = reference
        for load in self._model.get("nloads", []):
            factor = float(factors.get(str(load.get("lcase")), 0.0))
            node = node_by_id.get(load.get("node"))
            if not factor or node is None:
                continue
            fx, fy, mz = float(load.get("fx", 0.0)) * factor, float(load.get("fy", 0.0)) * factor, float(load.get("mz", 0.0)) * factor
            total_fx += fx
            total_fy += fy
            total_moment += mz + (float(node["x"]) - ref_x) * fy - (float(node["y"]) - ref_y) * fx
        elements = {element.get("id"): element for element in self._model.get("elements", [])}
        for load in self._model.get("eloads", []):
            factor = float(factors.get(str(load.get("lcase")), 0.0))
            element = elements.get(load.get("elem"))
            if not factor or element is None:
                continue
            first, second = node_by_id.get(element.get("n1")), node_by_id.get(element.get("n2"))
            if first is None or second is None:
                continue
            dx, dy = float(second["x"]) - float(first["x"]), float(second["y"]) - float(first["y"])
            length = math.hypot(dx, dy)
            if length <= 1.0e-12:
                continue
            if load.get("type", "Distributed") == "Point Force":
                value = float(load.get("p", 0.0)) * factor
                at_x = min(length, max(0.0, float(load.get("x_m", 0.0))))
                cosine, sine = dx / length, dy / length
                if load.get("dir") == "Local X":
                    fx, fy = cosine * value, sine * value
                elif load.get("dir") == "Local Y":
                    fx, fy = -sine * value, cosine * value
                elif load.get("dir") == "Global X":
                    fx, fy = value, 0.0
                else:
                    fx, fy = 0.0, value
                x = float(first["x"]) + cosine * at_x
                y = float(first["y"]) + sine * at_x
                total_fx += fx
                total_fy += fy
                total_moment += (x - ref_x) * fy - (y - ref_y) * fx
                continue
            if load.get("type") == "Point Moment":
                total_moment += float(load.get("m", 0.0)) * factor
                continue
            q1, q2 = float(load.get("w1", 0.0)) * factor, float(load.get("w2", 0.0)) * factor
            resultant = length * (q1 + q2) / 2.0
            local_x = length * (q1 + 2.0 * q2) / (3.0 * (q1 + q2)) if abs(q1 + q2) > 1.0e-12 else length / 2.0
            cosine, sine = dx / length, dy / length
            if load.get("dir") == "Local X":
                fx, fy = cosine * resultant, sine * resultant
            elif load.get("dir") == "Local Y":
                fx, fy = -sine * resultant, cosine * resultant
            elif load.get("dir") == "Global X":
                fx, fy = resultant, 0.0
            else:
                fx, fy = 0.0, resultant
            x = float(first["x"]) + cosine * local_x
            y = float(first["y"]) + sine * local_x
            total_fx += fx
            total_fy += fy
            total_moment += (x - ref_x) * fy - (y - ref_y) * fx
        if self._result:
            for node in self._result.get("nodes", []):
                model_node = node_by_id.get(node.get("id"))
                if model_node is None or model_node.get("support") == "Free":
                    continue
                fx, fy, mz = float(node.get("fx", 0.0)), float(node.get("fy", 0.0)), float(node.get("mz", 0.0))
                total_fx += fx
                total_fy += fy
                total_moment += mz + (float(model_node["x"]) - ref_x) * fy - (float(model_node["y"]) - ref_y) * fx
        return total_fx, total_fy, total_moment

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
        exaggeration = max(span_x, span_y) * 0.12 / maximum * self._deformation_factor()
        pen = QPen(QColor("#0f766e"), 2.0, Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        elements = self._model.get("elements", [])
        if self._detail_level() == "large":
            elements = [element for element in elements if int(element.get("id", -1)) in self._selected_members]
        for element in elements:
            first, second = node_by_id.get(element.get("n1")), node_by_id.get(element.get("n2"))
            first_result, second_result = result_nodes.get(element.get("n1")), result_nodes.get(element.get("n2"))
            if not first or not second or not first_result or not second_result:
                continue
            p1 = screen(float(first["x"]) + float(first_result.get("dx", 0.0)) * exaggeration, float(first["y"]) + float(first_result.get("dy", 0.0)) * exaggeration)
            p2 = screen(float(second["x"]) + float(second_result.get("dx", 0.0)) * exaggeration, float(second["y"]) + float(second_result.get("dy", 0.0)) * exaggeration)
            painter.drawLine(p1, p2)

    def _draw_deformed_member_curves(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen, span_x: float, span_y: float) -> None:
        maximum = 0.0
        members = self._deformed_members
        if self._detail_level() == "large":
            members = [member for member in members if int(member.get("id", -1)) in self._selected_members]
        for member in members:
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
        exaggeration = max(span_x, span_y) * 0.12 / maximum * self._deformation_factor()
        pen = QPen(QColor("#0f766e"), 2.0, Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for member in members:
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
        members = self._diagram_members
        if self._detail_level() == "large":
            members = [member for member in members if int(member.get("id", -1)) in self._selected_members]
            if not members:
                return
        for key in self._diagram_keys():
            amplitude = self._diagram_amplitude(key, span_x, span_y)
            if amplitude is None:
                continue
            _, color = self._DIAGRAMS[key]
            self._draw_member_diagram(painter, node_by_id, screen, key, amplitude, color, self._diagram_mode == "all", members)

    def _draw_member_diagram(
        self,
        painter: QPainter,
        node_by_id: Mapping[int, Mapping[str, Any]],
        screen,
        key: str,
        amplitude: float,
        color: QColor,
        compact: bool,
        members: list[Mapping[str, Any]],
    ) -> None:
        for member in members:
            node = node_by_id.get(member.get("n1"))
            points = self._contour_points(member.get("points", []))
            if node is None or len(points) < 2:
                continue
            member_amplitude = self._member_diagram_amplitude(key, member, amplitude, compact)
            member_color = self._diagram_color(key, self._display_diagram_value(key, float(points[0].get(key, 0.0))), color, member)
            pen = QPen(member_color, 1.7 if compact else 2.2, Qt.PenStyle.DashLine if key == "v_mm" else Qt.PenStyle.SolidLine)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            fill = QColor(member_color)
            # Regular diagrams need enough opacity to stay readable under the grid and deformed shape.
            fill.setAlpha(110 if compact else 145)
            angle = float(member.get("angle_rad", 0.0))
            direction_x, direction_y = math.cos(angle), math.sin(angle)
            normal_x, normal_y = -direction_y, direction_x
            base = QPolygonF()
            curve = QPolygonF()
            for point in points:
                x = float(point.get("x_m", 0.0))
                origin_x = float(node["x"]) + direction_x * x
                origin_y = float(node["y"]) + direction_y * x
                offset = self._diagram_offset(key, float(point.get(key, 0.0)), member_amplitude)
                base.append(screen(origin_x, origin_y))
                curve.append(screen(origin_x + normal_x * offset, origin_y + normal_y * offset))
            polygon = QPolygonF(base)
            for point in reversed(curve):
                polygon.append(point)
            if self._display.contour_enabled and self._diagram_mode != "all":
                self._draw_contour_bands(painter, base, curve, key, member)
            elif self._display.diagram_fill:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(fill)
                painter.drawPolygon(polygon)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(pen)
            painter.drawPolyline(curve)
            if self._show_diagram_values and self._detail_level() == "full":
                self._draw_diagram_value_labels(painter, curve, points, key, member_color)

    def _member_diagram_amplitude(self, key: str, member: Mapping[str, Any], global_amplitude: float, compact: bool) -> float:
        if not (self._display.contour_enabled and self._display.contour_scale == "member"):
            return global_amplitude
        maximum = max((abs(self._display_diagram_value(key, float(point.get(key, 0.0)))) for point in member.get("points", [])), default=0.0)
        if maximum <= 1.0e-12:
            return global_amplitude
        min_x, min_y, max_x, max_y = self._spatial_index.bounds
        span = max(max_x - min_x, max_y - min_y, 1.0)
        base = span * (0.075 if compact else 0.14) / maximum
        return base if self._display.diagram_scale_mode == "auto" else base * self._display.diagram_scale_multiplier

    def _contour_points(self, points: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        """Limit only draw samples, keeping calculation and hover data at full resolution."""

        if len(points) <= 2:
            return points
        detail = self._display.contour_detail
        if detail == "detail":
            maximum = len(points)
        elif detail == "fast":
            maximum = 9
        else:
            member_count = len(self._model.get("elements", []))
            maximum = 4 if member_count > 2000 else 9 if member_count > 300 else 25
        if len(points) <= maximum:
            return points
        stride = math.ceil((len(points) - 1) / (maximum - 1))
        selected = list(points[::stride])
        if selected[-1] is not points[-1]:
            selected.append(points[-1])
        return selected

    def _contour_range(self, key: str, member: Mapping[str, Any] | None = None) -> ContourRange:
        target = [member] if self._display.contour_scale == "member" and member is not None else self._diagram_members
        cache_key = (key, self._display.contour_scale if member is None else f"{self._display.contour_scale}:{member.get('id')}", self._display.contour_palette)
        cached = self._contour_ranges.get(cache_key)
        if cached is not None:
            return cached
        value_range = contour_range(
            target,
            key,
            self._display_diagram_value,
            signed=self._display.contour_palette != "spectrum",
        )
        self._contour_ranges[cache_key] = value_range
        return value_range

    def _contour_colour(self, key: str, point: Mapping[str, Any], member: Mapping[str, Any]) -> QColor:
        raw = stress_value(point) if key == "stress_kg_cm2" else float(point.get(key, 0.0))
        value = self._display_diagram_value(key, raw)
        if (
            self._display.contour_palette == "truss_axial"
            and key == "n_kg"
            and str(member.get("memberType", "Frame")) == "Truss"
        ):
            # A semantic Truss palette is opt-in; signed and spectrum palettes remain available.
            return self._diagram_color(key, value, QColor("#475569"), member)
        red, green, blue = colour_stops(value, self._contour_range(key, member), self._display.contour_palette)
        return QColor(red, green, blue)

    def _draw_contour_bands(self, painter: QPainter, base: QPolygonF, curve: QPolygonF, key: str, member: Mapping[str, Any]) -> None:
        """Paint one small quadrilateral per sampled interval for a smooth member contour."""

        points = self._contour_points(member.get("points", []))
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(len(points) - 1):
            midpoint_value = (self._contour_value(key, points[index]) + self._contour_value(key, points[index + 1])) / 2.0
            midpoint = {key: midpoint_value}
            if key == "stress_kg_cm2":
                midpoint = {"stress_top_kg_cm2": midpoint_value, "stress_bottom_kg_cm2": midpoint_value}
            fill = self._contour_colour(key, midpoint, member)
            fill.setAlpha(190)
            painter.setBrush(fill)
            painter.drawPolygon(QPolygonF([base[index], base[index + 1], curve[index + 1], curve[index]]))

    @staticmethod
    def _contour_value(key: str, point: Mapping[str, Any]) -> float:
        return stress_value(point) if key == "stress_kg_cm2" else float(point.get(key, 0.0))

    @staticmethod
    def _diagram_color(key: str, value: float, default: QColor, member: Mapping[str, Any] | None = None) -> QColor:
        if key == "n_kg" and member is not None and str(member.get("memberType", "Frame")) == "Truss":
            if value > 1.0e-12:
                return QColor("#15803d")
            if value < -1.0e-12:
                return QColor("#b91c1c")
            return QColor("#475569")
        return default

    def _draw_diagram_value_labels(self, painter: QPainter, curve: QPolygonF, points: list[Mapping[str, Any]], key: str, color: QColor) -> None:
        indices = {0, len(points) - 1, max(range(len(points)), key=lambda index: abs(float(points[index].get(key, 0.0))))}
        font = QFont(painter.font())
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(color)
        painter.setBrush(QColor(255, 255, 255, 220))
        for index in sorted(indices):
            text = self._format_diagram_value(key, self._display_diagram_value(key, float(points[index].get(key, 0.0))))
            anchor = curve[index] + QPointF(5.0, -5.0)
            metrics = painter.fontMetrics()
            rect = QRectF(anchor.x(), anchor.y() - metrics.height(), metrics.horizontalAdvance(text) + 6.0, metrics.height() + 4.0)
            if any(rect.intersects(previous) for previous in self._label_rects):
                continue
            self._label_rects.append(rect)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(rect)
            painter.setPen(color)
            painter.drawText(rect.adjusted(3.0, 0.0, 0.0, 0.0), Qt.AlignmentFlag.AlignVCenter, text)

    def _update_hover_points(self, node_by_id: Mapping[int, Mapping[str, Any]], screen, span_x: float, span_y: float) -> None:
        self._hover_points = []
        self._hover_cells = {}
        members = self._diagram_members
        if len(self._model.get("elements", [])) > 300:
            members = [member for member in members if int(member.get("id", -1)) in self._selected_members]
        for member in members:
            node = node_by_id.get(member.get("n1"))
            if node is None:
                continue
            angle = float(member.get("angle_rad", 0.0))
            for point in member.get("points", []):
                x = float(point.get("x_m", 0.0))
                location = screen(float(node["x"]) + math.cos(angle) * x, float(node["y"]) + math.sin(angle) * x)
                self._cache_hover_point(location, member, point)
                for key in self._diagram_keys():
                    amplitude = self._diagram_amplitude(key, span_x, span_y)
                    if amplitude is None:
                        continue
                    amplitude = self._member_diagram_amplitude(key, member, amplitude, self._diagram_mode == "all")
                    offset = self._diagram_offset(key, float(point.get(key, 0.0)), amplitude)
                    normal_x, normal_y = -math.sin(angle), math.cos(angle)
                    diagram_location = screen(
                        float(node["x"]) + math.cos(angle) * x + normal_x * offset,
                        float(node["y"]) + math.sin(angle) * x + normal_y * offset,
                    )
                    self._cache_hover_point(diagram_location, member, point)

    def _cache_hover_point(self, location: QPointF, member: Mapping[str, Any], point: Mapping[str, Any]) -> None:
        sample = (location, member, point)
        self._hover_points.append(sample)
        cell = (math.floor(location.x() / self._hover_cell_size), math.floor(location.y() / self._hover_cell_size))
        self._hover_cells.setdefault(cell, []).append(sample)

    def _show_hover_value(self, position: QPointF, global_position: QPoint) -> None:
        if not self._hover_points:
            self._clear_hover()
            return
        cell = (math.floor(position.x() / self._hover_cell_size), math.floor(position.y() / self._hover_cell_size))
        candidates = [
            sample
            for x in range(cell[0] - 1, cell[0] + 2)
            for y in range(cell[1] - 1, cell[1] + 2)
            for sample in self._hover_cells.get((x, y), [])
        ]
        if not candidates:
            self._clear_hover()
            return
        sample = min(candidates, key=lambda item: (item[0] - position).manhattanLength())
        location, member, point = sample
        if (location - position).manhattanLength() > 16.0:
            self._clear_hover()
            return
        if self._hover_sample != sample:
            self._hover_sample = sample
            self.update()
        lines = [
            f"E{member['id']} | N{member['n1']} - N{member['n2']} | x = {self._units.length(float(point['x_m'])):.3f} {self._units.length_unit}",
            f"N = {self._units.force(self._display_diagram_value('n_kg', float(point.get('n_kg', 0.0)))):,.3f} {self._units.force_unit} (Tension +)",
            f"V = {self._units.force(self._display_diagram_value('v_kg', float(point.get('v_kg', 0.0)))):,.3f} {self._units.force_unit} (Clockwise +)",
            f"M = {self._units.moment(self._display_diagram_value('m_kg_m', float(point.get('m_kg_m', 0.0)))):,.3f} {self._units.moment_label()} (Bottom fibre tension)",
            f"FE deflection = {self._units.format_displacement(float(point.get('v_mm', 0.0)) / 1000.0)} {self._units.length_unit}",
        ]
        QToolTip.showText(global_position, "\n".join(lines), self)

    def _draw_hover_crosshair(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen, span_x: float, span_y: float) -> None:
        if self._hover_sample is None:
            return
        _, member, point = self._hover_sample
        node_i = node_by_id.get(member.get("n1"))
        node_j = node_by_id.get(member.get("n2"))
        if node_i is None or node_j is None:
            return
        x = float(point.get("x_m", 0.0))
        angle = float(member.get("angle_rad", 0.0))
        base = screen(float(node_i["x"]) + math.cos(angle) * x, float(node_i["y"]) + math.sin(angle) * x)
        end = screen(float(node_j["x"]), float(node_j["y"]))
        start = screen(float(node_i["x"]), float(node_i["y"]))
        direction = end - start
        length = math.hypot(direction.x(), direction.y())
        if length <= 1.0e-12:
            return
        direction /= length
        normal = QPointF(-direction.y(), direction.x())
        guide = QPen(QColor("#475569"), 1.0, Qt.PenStyle.DotLine)
        painter.setPen(guide)
        painter.drawLine(base - normal * 64.0, base + normal * 64.0)
        painter.drawLine(base - direction * 7.0, base + direction * 7.0)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#0f172a"), 1.3))
        painter.drawEllipse(base, 3.6, 3.6)
        for key in self._diagram_keys():
            amplitude = self._diagram_amplitude(key, span_x, span_y)
            if amplitude is None:
                continue
            amplitude = self._member_diagram_amplitude(key, member, amplitude, self._diagram_mode == "all")
            offset = self._diagram_offset(key, float(point.get(key, 0.0)), amplitude)
            location = screen(
                float(node_i["x"]) + math.cos(angle) * x - math.sin(angle) * offset,
                float(node_i["y"]) + math.sin(angle) * x + math.cos(angle) * offset,
            )
            _, default_color = self._DIAGRAMS[key]
            color = self._diagram_color(key, self._display_diagram_value(key, float(point.get(key, 0.0))), default_color, member)
            painter.setPen(QPen(color, 1.8))
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(location, 4.2, 4.2)

    def _diagram_keys(self) -> list[str]:
        if self._diagram_mode == "all":
            return list(self._DIAGRAMS)
        return [self._diagram_mode] if self._diagram_mode in self._DIAGRAMS else []

    def _diagram_amplitude(self, key: str, span_x: float, span_y: float) -> float | None:
        maximum = self._diagram_maxima.get(key, 0.0)
        if maximum <= 1.0e-12:
            return None
        # A common scale per result selection preserves visual comparisons between members.
        base = max(span_x, span_y) * (0.075 if self._diagram_mode == "all" else 0.14) / maximum
        return base if self._display.diagram_scale_mode == "auto" else base * self._display.diagram_scale_multiplier

    def _display_diagram_value(self, key: str, value: float) -> float:
        """Return the native solver value; graph orientation is intentionally separate."""
        return value

    def _diagram_offset(self, key: str, value: float, amplitude: float) -> float:
        placement = 1.0 if self._display.diagram_placement == "local_positive" else -1.0
        orientation = {
            "n_kg": self._display.axial_graph_orientation,
            "v_kg": self._display.shear_graph_orientation,
            "m_kg_m": self._display.moment_graph_orientation,
        }.get(key, "native")
        if orientation == "flipped":
            placement *= -1.0
        return value * amplitude * placement

    def _clear_hover(self) -> None:
        self._hover_sample = None
        self._queued_hover = None
        QToolTip.hideText()

    def _format_diagram_value(self, key: str, value: float) -> str:
        label = {"n_kg": "N", "v_kg": "V", "m_kg_m": "M", "v_mm": "v"}[key]
        if key == "v_mm":
            return f"{label} {self._units.format_displacement(value / 1000.0)} {self._units.length_unit}"
        if key == "m_kg_m":
            return f"{label} {self._units.moment(value):,.2f} {self._units.moment_label()}"
        return f"{label} {self._units.force(value):,.2f} {self._units.force_unit}"

    def _draw_lightweight_nodes(self, painter: QPainter, nodes: list[Mapping[str, Any]], screen) -> None:
        """Draw nodes without labels or support glyphs while the pointer is actively moving."""

        if not self._display.show_nodes:
            return
        painter.setPen(QPen(QColor("#0f172a"), 3.0))
        painter.drawPoints(QPolygonF([screen(float(node["x"]), float(node["y"])) for node in nodes]))
        if self._selected_nodes:
            painter.setPen(QPen(QColor("#0f766e"), 6.0))
            painter.drawPoints(
                QPolygonF([screen(float(node["x"]), float(node["y"])) for node in nodes if int(node["id"]) in self._selected_nodes])
            )

    def _draw_nodes_and_supports(self, painter: QPainter, nodes: list[Mapping[str, Any]], screen, *, show_labels: bool = True) -> None:
        font = QFont(painter.font())
        font.setPointSize(9)
        painter.setFont(font)
        for node in nodes:
            point = screen(float(node["x"]), float(node["y"]))
            support = node.get("support", "Free")
            if support != "Free" and self._display.show_supports:
                support_pen = QPen(QColor("#334155"), 1.5)
                painter.setPen(support_pen)
                painter.setBrush(QColor("#cbd5e1"))
                if support == "Fixed":
                    # A hatched wall deliberately differs from the pinned triangular glyph.
                    painter.setBrush(QColor("#64748b"))
                    painter.drawRect(QRectF(point.x() - 14.0, point.y() + 14.0, 28.0, 5.0))
                    painter.setPen(QPen(QColor("#334155"), 2.2))
                    painter.drawLine(point + QPointF(0.0, 2.0), point + QPointF(0.0, 14.0))
                    painter.setPen(QPen(QColor("#64748b"), 1.1))
                    for offset in range(-16, 17, 5):
                        painter.drawLine(point + QPointF(offset, 24.0), point + QPointF(offset + 8.0, 19.0))
                else:
                    triangle = QPolygonF([point + QPointF(-10, 18), point + QPointF(10, 18), point + QPointF(0, 3)])
                    painter.drawPolygon(triangle)
                    if support == "Spring":
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        spring = QPolygonF([point + QPointF(-9, 18), point + QPointF(-4, 13), point + QPointF(1, 23), point + QPointF(6, 13), point + QPointF(11, 18)])
                        painter.drawPolyline(spring)
            if self._display.show_nodes:
                selected = int(node["id"]) in self._selected_nodes
                painter.setPen(QPen(QColor("#0f766e") if selected else QColor("#0f172a"), 2.2 if selected else 1.2))
                painter.setBrush(QColor("#ccfbf1") if selected else QColor("#ffffff"))
                painter.drawEllipse(point, 6.0 if selected else 4.2, 6.0 if selected else 4.2)
            if show_labels and self._display.show_node_ids:
                painter.setPen(QColor("#334155"))
                painter.drawText(point + QPointF(7, -8), f"N{node['id']}")

    def _draw_truss_axial_extrema(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen) -> None:
        """Mark governing tension and compression members without changing solver signs."""

        candidates = [
            member
            for member in self._diagram_members
            if str(member.get("memberType", "Truss" if str(self._model.get("projectInfo", {}).get("analysisType", "")).lower() in {"truss", "2d truss"} else "Frame")) == "Truss"
            and member.get("points")
        ]
        if not candidates:
            return
        values = [(float(member["points"][0].get("n_kg", 0.0)), member) for member in candidates]
        extrema = (("Max T", max((item for item in values if item[0] > 1.0e-12), default=None, key=lambda item: item[0]), QColor("#15803d")), ("Max C", min((item for item in values if item[0] < -1.0e-12), default=None, key=lambda item: item[0]), QColor("#b91c1c")))
        for label, item, color in extrema:
            if item is None:
                continue
            value, member = item
            first = node_by_id.get(member.get("n1"))
            second = node_by_id.get(member.get("n2"))
            if first is None or second is None:
                continue
            start = screen(float(first["x"]), float(first["y"]))
            end = screen(float(second["x"]), float(second["y"]))
            midpoint = (start + end) / 2.0
            halo = QPen(QColor(color.red(), color.green(), color.blue(), 75), 8.0)
            halo.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(halo)
            painter.drawLine(start, end)
            painter.setPen(QPen(color, 3.0))
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(midpoint, 5.0, 5.0)
            painter.setPen(color)
            painter.drawText(midpoint + QPointF(8.0, -10.0), f"{label} E{member['id']} {self._units.force(value):,.2f} {self._units.force_unit}")

    def _draw_member_annotations(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen) -> None:
        if not self._display.show_member_ids and not self._display.show_local_axes:
            return
        for member in self._model.get("elements", []):
            first, second = node_by_id.get(member.get("n1")), node_by_id.get(member.get("n2"))
            if first is None or second is None:
                continue
            start = screen(float(first["x"]), float(first["y"]))
            end = screen(float(second["x"]), float(second["y"]))
            direction = end - start
            length = math.hypot(direction.x(), direction.y())
            if length <= 1.0e-12:
                continue
            unit = direction / length
            normal = QPointF(-unit.y(), unit.x())
            middle = (start + end) / 2.0
            if self._display.show_member_ids:
                painter.setPen(QColor("#475569"))
                painter.drawText(middle + normal * 14.0, f"E{member['id']}")
            if self._display.show_local_axes:
                painter.setPen(QPen(QColor("#7c3aed"), 1.2))
                painter.drawLine(middle - unit * 12.0, middle + unit * 12.0)
                painter.setBrush(QColor("#7c3aed"))
                painter.drawPolygon(QPolygonF([middle + unit * 12.0, middle + unit * 5.0 + normal * 3.5, middle + unit * 5.0 - normal * 3.5]))
                painter.setPen(QColor("#7c3aed"))
                painter.drawText(middle + normal * 16.0, "i->j")

    def _draw_member_preview(self, painter: QPainter, screen) -> None:
        if self._member_start is None or self._member_current is None:
            return
        start = screen(*self._member_start)
        end = screen(*self._member_current)
        pen = QPen(QColor("#0f766e"), 2.0, Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawLine(start, end)
        painter.drawEllipse(end, 4.5, 4.5)
        dx = self._member_current[0] - self._member_start[0]
        dy = self._member_current[1] - self._member_start[1]
        length = math.hypot(dx, dy)
        angle = math.degrees(math.atan2(dy, dx))
        painter.setPen(QColor("#0f766e"))
        painter.drawText((start + end) / 2.0 + QPointF(8.0, -8.0), f"L {length:.3f} m | {angle:.1f} deg")

    def _draw_node_move_preview(self, painter: QPainter, node_by_id: Mapping[int, Mapping[str, Any]], screen) -> None:
        if self._node_drag_id is None or self._node_drag_position is None:
            return
        source = node_by_id.get(self._node_drag_id)
        if source is None:
            return
        start = screen(float(source["x"]), float(source["y"]))
        end = screen(*self._node_drag_position)
        painter.setPen(QPen(QColor("#2563eb"), 1.8, Qt.PenStyle.DashLine))
        painter.setBrush(QColor("#dbeafe"))
        painter.drawLine(start, end)
        painter.drawEllipse(end, 6.0, 6.0)

    def _draw_selection_rect(self, painter: QPainter) -> None:
        if self._selection_rect is None or self._selection_rect.width() < 4.0 or self._selection_rect.height() < 4.0:
            return
        color = QColor("#2563eb") if self._selection_crossing else QColor("#0f766e")
        painter.setPen(QPen(color, 1.0, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 28))
        painter.drawRect(self._selection_rect)

    def _pointer_moved(self, position: QPointF) -> None:
        x, y = self._screen_to_model(position)
        self.pointer_changed.emit(x, y)

    def _screen_to_model(self, position: QPointF) -> tuple[float, float]:
        return (
            self._view_model_center.x() + (position.x() - self._view_center.x()) / self._view_scale,
            self._view_model_center.y() - (position.y() - self._view_center.y()) / self._view_scale,
        )

    def _model_to_screen(self, x: float, y: float) -> QPointF:
        return QPointF(
            self._view_center.x() + (x - self._view_model_center.x()) * self._view_scale,
            self._view_center.y() - (y - self._view_model_center.y()) * self._view_scale,
        )

    def _snap_position(self, position: QPointF) -> tuple[float, float]:
        node = self._node_at(position)
        if self._snap_enabled and self._snap_to_node and node is not None:
            return float(node["x"]), float(node["y"])
        x, y = self._screen_to_model(position)
        if not self._snap_enabled:
            return x, y
        if self._snap_to_node:
            special = self._special_snap_position(position)
            if special is not None:
                return special
        return round(x / self._grid_spacing) * self._grid_spacing, round(y / self._grid_spacing) * self._grid_spacing

    def _special_snap_position(self, position: QPointF) -> tuple[float, float] | None:
        point = self._screen_to_model(position)
        radius = 10.0 / max(self._view_scale, 1.0e-12)
        nearest = nearest_point(point, self._spatial_index.snap_points_near(point, radius))
        return nearest[1] if nearest is not None and nearest[0] <= radius else None

    @staticmethod
    def _line_intersection(
        first_start: tuple[float, float], first_end: tuple[float, float], second_start: tuple[float, float], second_end: tuple[float, float]
    ) -> tuple[float, float] | None:
        x1, y1 = first_start
        x2, y2 = first_end
        x3, y3 = second_start
        x4, y4 = second_end
        denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denominator) <= 1.0e-12:
            return None
        first_ratio = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denominator
        second_ratio = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / denominator
        if not (1.0e-9 < first_ratio < 1.0 - 1.0e-9 and 1.0e-9 < second_ratio < 1.0 - 1.0e-9):
            return None
        return x1 + first_ratio * (x2 - x1), y1 + first_ratio * (y2 - y1)

    def _node_at(self, position: QPointF, threshold: float = 10.0) -> Mapping[str, Any] | None:
        point = self._screen_to_model(position)
        candidates = self._spatial_index.nodes_near(point, threshold / max(self._view_scale, 1.0e-12))
        if not candidates:
            return None
        node = min(candidates, key=lambda item: (self._model_to_screen(float(item["x"]), float(item["y"])) - position).manhattanLength())
        return node if (self._model_to_screen(float(node["x"]), float(node["y"])) - position).manhattanLength() <= threshold else None

    def _load_at(self, position: QPointF) -> tuple[str, dict[str, Any]] | None:
        nodes = self._spatial_index.nodes
        elements = {int(member["id"]): member for member in self._model.get("elements", [])}
        candidates: list[tuple[float, str, dict[str, Any]]] = []
        point = self._screen_to_model(position)
        anchors = self._spatial_index.loads_near(point, 64.0 / max(self._view_scale, 1.0e-12))
        nodal_indices = {index for kind, index, _ in anchors if kind == "nodal"}
        member_indices = {index for kind, index, _ in anchors if kind == "member"}
        for index, load in enumerate(self._model.get("nloads", [])):
            if index not in nodal_indices:
                continue
            node = nodes.get(int(load.get("node", -1)))
            if node is not None:
                anchor = self._model_to_screen(float(node["x"]), float(node["y"]))
                fx, fy, mz = float(load.get("fx", 0.0)), float(load.get("fy", 0.0)), float(load.get("mz", 0.0))
                if abs(fx) > 1.0e-12:
                    candidates.append(((anchor + QPointF(-math.copysign(22.0, fx), 0.0) - position).manhattanLength(), "nodal", {"index": index, "load": dict(load)}))
                if abs(fy) > 1.0e-12:
                    candidates.append(((anchor + QPointF(0.0, math.copysign(22.0, fy)) - position).manhattanLength(), "nodal", {"index": index, "load": dict(load)}))
                if abs(mz) > 1.0e-12:
                    candidates.append(((anchor + QPointF(14.0, -14.0) - position).manhattanLength(), "nodal", {"index": index, "load": dict(load)}))
        for index, load in enumerate(self._model.get("eloads", [])):
            if index not in member_indices:
                continue
            member = elements.get(int(load.get("elem", -1)))
            if member is None:
                continue
            first, second = nodes.get(int(member["n1"])), nodes.get(int(member["n2"]))
            if first is None or second is None:
                continue
            dx, dy = float(second["x"]) - float(first["x"]), float(second["y"]) - float(first["y"])
            length = math.hypot(dx, dy)
            if length <= 1.0e-12:
                continue
            at_x = float(load.get("x_m", length / 2.0)) if load.get("type") in {"Point Force", "Point Moment"} else length / 2.0
            at_x = min(length, max(0.0, at_x))
            anchor = self._model_to_screen(float(first["x"]) + dx * at_x / length, float(first["y"]) + dy * at_x / length)
            candidates.append(((anchor - position).manhattanLength(), "member", {"index": index, "load": dict(load), "member": int(member["id"])}))
        if not candidates:
            return None
        distance, kind, context = min(candidates, key=lambda item: item[0])
        return (kind, context) if distance <= 12.0 else None

    def _member_at(self, position: QPointF, threshold: float = 8.0) -> Mapping[str, Any] | None:
        candidates: list[tuple[float, Mapping[str, Any]]] = []
        point = self._screen_to_model(position)
        radius = threshold * 1.5 / max(self._view_scale, 1.0e-12)
        for segment in self._spatial_index.members_near(point, radius):
            start = self._model_to_screen(*segment.start)
            end = self._model_to_screen(*segment.end)
            direction = end - start
            length_sq = direction.x() ** 2 + direction.y() ** 2
            if length_sq <= 1.0e-12:
                continue
            ratio = max(0.0, min(1.0, ((position - start).x() * direction.x() + (position - start).y() * direction.y()) / length_sq))
            closest = start + direction * ratio
            candidates.append(((closest - position).manhattanLength(), segment.member))
        if not candidates:
            return None
        distance, member = min(candidates, key=lambda item: item[0])
        return member if distance <= threshold else None

    def _create_node(self, position: tuple[float, float]) -> int | None:
        if self._node_at(self._model_to_screen(*position)) is not None:
            self.authoring_message.emit("A node already exists at this location.")
            return None
        model = self._mutable_model()
        node_id = self._next_id(model["nodes"])
        model["nodes"].append({"id": node_id, "x": position[0], "y": position[1], "support": "Free"})
        self._set_selection({node_id}, set())
        self._emit_model(model)
        return node_id

    def _create_member(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        if math.hypot(end[0] - start[0], end[1] - start[1]) <= 1.0e-9:
            self.authoring_message.emit("Member endpoints must be different.")
            return
        model = self._mutable_model()
        node_ids = self._endpoint_ids(model, start, end)
        if node_ids is None:
            return
        n1, n2 = node_ids
        if any({int(member["n1"]), int(member["n2"])} == {n1, n2} for member in model["elements"]):
            self.authoring_message.emit("A member already connects these nodes.")
            return
        member_id = self._next_id(model["elements"])
        model["elements"].append({"id": member_id, "n1": n1, "n2": n2, "sec": self._active_section, "release": "Rigid-Rigid", **({"memberType": "Truss"} if self._active_member_type == "Truss" else {})})
        self._set_selection(set(), {member_id})
        self._emit_model(model)

    def create_member_by_geometry(self, start_node_id: int, length_m: float, angle_degrees: float) -> None:
        """Create a member from a selected node using explicit engineering dimensions."""
        start = next((node for node in self._model.get("nodes", []) if int(node["id"]) == start_node_id), None)
        if start is None or length_m <= 0.0:
            self.authoring_message.emit("Select a valid start node and enter a positive member length.")
            return
        angle = math.radians(angle_degrees)
        end = (float(start["x"]) + length_m * math.cos(angle), float(start["y"]) + length_m * math.sin(angle))
        self._create_member((float(start["x"]), float(start["y"])), end)

    def _apply_support(self, node_id: int, support: str) -> None:
        model = self._mutable_model()
        node = next((item for item in model["nodes"] if int(item["id"]) == node_id), None)
        if node is None:
            return
        node["support"] = support
        self._set_selection({node_id}, set())
        self._emit_model(model)

    def _move_node(self, node_id: int, position: tuple[float, float]) -> None:
        model = self._mutable_model()
        node = next((item for item in model["nodes"] if int(item["id"]) == node_id), None)
        if node is None:
            return
        if math.isclose(float(node["x"]), position[0], abs_tol=1.0e-9) and math.isclose(float(node["y"]), position[1], abs_tol=1.0e-9):
            return
        if any(
            int(other["id"]) != node_id
            and math.isclose(float(other["x"]), position[0], abs_tol=1.0e-9)
            and math.isclose(float(other["y"]), position[1], abs_tol=1.0e-9)
            for other in model["nodes"]
        ):
            self.authoring_message.emit("A node already exists at that location.")
            return
        node["x"], node["y"] = position
        if not self._model_has_valid_member_lengths(model):
            self.authoring_message.emit("Moving this node would create a zero-length member.")
            return
        self._emit_model(model)

    @staticmethod
    def _model_has_valid_member_lengths(model: Mapping[str, Any]) -> bool:
        nodes = {int(node["id"]): node for node in model.get("nodes", [])}
        return all(
            first is not None
            and second is not None
            and math.hypot(float(second["x"]) - float(first["x"]), float(second["y"]) - float(first["y"])) > 1.0e-9
            for member in model.get("elements", [])
            for first, second in [(nodes.get(int(member["n1"])), nodes.get(int(member["n2"])))]
        )

    def _split_member(self, member_id: int, position: tuple[float, float]) -> None:
        model = self._mutable_model()
        member = next((item for item in model["elements"] if int(item["id"]) == member_id), None)
        if member is None:
            return
        nodes = {int(node["id"]): node for node in model["nodes"]}
        first, second = nodes.get(int(member["n1"])), nodes.get(int(member["n2"]))
        if first is None or second is None:
            return
        dx, dy = float(second["x"]) - float(first["x"]), float(second["y"]) - float(first["y"])
        length_sq = dx * dx + dy * dy
        if length_sq <= 1.0e-12:
            return
        ratio = max(0.0, min(1.0, ((position[0] - float(first["x"])) * dx + (position[1] - float(first["y"])) * dy) / length_sq))
        if ratio <= 1.0e-8 or ratio >= 1.0 - 1.0e-8:
            self.authoring_message.emit("Split position must be inside the member.")
            return
        split_position = (float(first["x"]) + ratio * dx, float(first["y"]) + ratio * dy)
        new_node_id = self._next_id(model["nodes"])
        new_member_id = self._next_id(model["elements"])
        original_length = math.sqrt(length_sq)
        split_length = original_length * ratio
        left_member_length = math.hypot(split_position[0] - float(first["x"]), split_position[1] - float(first["y"]))
        right_member_length = math.hypot(float(second["x"]) - split_position[0], float(second["y"]) - split_position[1])
        member_type = str(member.get("memberType", "Frame"))
        original_release = str(member.get("release", "Rigid-Rigid")) if member_type == "Frame" else "Rigid-Rigid"
        first_release = "Pin-Rigid" if original_release in {"Pin-Rigid", "Pin-Pin"} else "Rigid-Rigid"
        second_release = "Rigid-Pin" if original_release in {"Rigid-Pin", "Pin-Pin"} else "Rigid-Rigid"
        model["nodes"].append({"id": new_node_id, "x": split_position[0], "y": split_position[1], "support": "Free"})
        member.update({"n2": new_node_id, "release": first_release})
        model["elements"].append({"id": new_member_id, "n1": new_node_id, "n2": int(second["id"]), "sec": int(member["sec"]), "release": second_release, **({"memberType": "Truss"} if member_type == "Truss" else {})})
        replacement_loads: list[dict[str, Any]] = []
        retained_loads: list[dict[str, Any]] = []
        for load in model["eloads"]:
            if int(load["elem"]) != member_id:
                retained_loads.append(load)
                continue
            if load.get("type", "Distributed") == "Distributed":
                w1, w2 = float(load.get("w1", 0.0)), float(load.get("w2", load.get("w1", 0.0)))
                load_start = float(load.get("x1_m", 0.0))
                load_end = float(load.get("x2_m", original_length))
                if load_end <= load_start:
                    continue
                def value_at(station: float) -> float:
                    return w1 + (w2 - w1) * (station - load_start) / (load_end - load_start)
                left_start, left_end = max(0.0, load_start), min(split_length, load_end, left_member_length)
                if left_end - left_start > 1.0e-9:
                    retained_loads.append({**load, "elem": member_id, "w1": value_at(left_start), "w2": value_at(left_end), "x1_m": left_start, "x2_m": left_end})
                right_start, right_end = max(split_length, load_start), min(original_length, load_end, split_length + right_member_length)
                if right_end - right_start > 1.0e-9:
                    replacement_loads.append({**load, "elem": new_member_id, "w1": value_at(right_start), "w2": value_at(right_end), "x1_m": right_start - split_length, "x2_m": right_end - split_length})
            else:
                at_x = float(load.get("x_m", 0.0))
                if at_x <= split_length:
                    retained_loads.append({**load, "elem": member_id})
                else:
                    replacement_loads.append({**load, "elem": new_member_id, "x_m": at_x - split_length})
        model["eloads"] = retained_loads + replacement_loads
        self._set_selection({new_node_id}, set())
        self._emit_model(model)

    def add_nodal_load(self, node_id: int, values: Mapping[str, Any]) -> None:
        model = self._mutable_model()
        load = {"node": node_id, **dict(values)}
        model["nloads"].append(load)
        self._set_selection({node_id}, set())
        self._emit_model(model)

    def add_member_load(self, member_id: int, values: Mapping[str, Any]) -> None:
        model = self._mutable_model()
        model["eloads"].append(self._normalized_member_load(member_id, values))
        self._set_selection(set(), {member_id})
        self._emit_model(model)

    def add_member_loads(self, member_ids: list[int], values: Mapping[str, Any]) -> None:
        """Apply the same member-load definition in one undoable canvas model change."""
        targets = sorted({int(member_id) for member_id in member_ids})
        valid = {int(member["id"]) for member in self._model.get("elements", [])}
        targets = [member_id for member_id in targets if member_id in valid]
        if not targets:
            self.authoring_message.emit("Select one or more members before applying a load.")
            return
        model = self._mutable_model()
        model["eloads"].extend(self._normalized_member_load(member_id, values) for member_id in targets)
        self._set_selection(set(), set(targets))
        self._emit_model(model)
        self.authoring_message.emit(f"Applied one {values.get('type', 'Distributed')} load to {len(targets)} member(s).")

    def add_member_loads_at_ratio(self, member_ids: list[int], values: Mapping[str, Any], ratio: float) -> None:
        """Apply a point action at a common relative location on every selected member."""
        ratio = max(0.0, min(1.0, float(ratio)))
        targets = sorted({int(member_id) for member_id in member_ids})
        model = self._mutable_model()
        nodes = {int(node["id"]): node for node in model.get("nodes", [])}
        members = {int(member["id"]): member for member in model.get("elements", [])}
        loads: list[dict[str, Any]] = []
        for member_id in targets:
            member = members.get(member_id)
            if member is None:
                continue
            first, second = nodes.get(int(member["n1"])), nodes.get(int(member["n2"]))
            if first is None or second is None:
                continue
            length = math.hypot(float(second["x"]) - float(first["x"]), float(second["y"]) - float(first["y"]))
            loads.append(self._normalized_member_load(member_id, {**dict(values), "x_m": length * ratio}))
        if not loads:
            self.authoring_message.emit("Select one or more valid members before applying a point action.")
            return
        model["eloads"].extend(loads)
        self._set_selection(set(), {int(load["elem"]) for load in loads})
        self._emit_model(model)
        self.authoring_message.emit(f"Applied one {values.get('type', 'Point Force')} at {ratio * 100.0:g}% of {len(loads)} member(s).")

    def update_nodal_load(self, index: int, values: Mapping[str, Any]) -> None:
        model = self._mutable_model()
        if not 0 <= index < len(model["nloads"]):
            return
        model["nloads"][index].update(dict(values))
        self._emit_model(model)

    def update_member_load(self, index: int, values: Mapping[str, Any]) -> None:
        model = self._mutable_model()
        if not 0 <= index < len(model["eloads"]):
            return
        current = model["eloads"][index]
        model["eloads"][index] = self._normalized_member_load(int(current["elem"]), values)
        self._emit_model(model)

    @staticmethod
    def _normalized_member_load(member_id: int, values: Mapping[str, Any]) -> dict[str, Any]:
        load = {"elem": member_id, **dict(values)}
        if load.get("type") == "Distributed":
            load.pop("type", None)
            load.pop("x_m", None)
            load.pop("p", None)
            load.pop("m", None)
        elif load.get("type") == "Point Force":
            load.pop("w1", None)
            load.pop("w2", None)
            load.pop("m", None)
        else:
            load.pop("w1", None)
            load.pop("w2", None)
            load.pop("p", None)
        return load

    def _member_station(self, member_id: int, position: tuple[float, float]) -> float:
        nodes = {int(node["id"]): node for node in self._model.get("nodes", [])}
        member = next((item for item in self._model.get("elements", []) if int(item["id"]) == member_id), None)
        if member is None:
            return 0.0
        first, second = nodes.get(int(member["n1"])), nodes.get(int(member["n2"]))
        if first is None or second is None:
            return 0.0
        dx, dy = float(second["x"]) - float(first["x"]), float(second["y"]) - float(first["y"])
        length_sq = dx * dx + dy * dy
        if length_sq <= 1.0e-12:
            return 0.0
        ratio = max(0.0, min(1.0, ((position[0] - float(first["x"])) * dx + (position[1] - float(first["y"])) * dy) / length_sq))
        return math.sqrt(length_sq) * ratio

    def _endpoint_ids(self, model: dict[str, Any], start: tuple[float, float], end: tuple[float, float]) -> tuple[int, int] | None:
        def find_or_create(position: tuple[float, float]) -> int:
            for node in model["nodes"]:
                if math.isclose(float(node["x"]), position[0], abs_tol=1.0e-9) and math.isclose(float(node["y"]), position[1], abs_tol=1.0e-9):
                    return int(node["id"])
            node_id = self._next_id(model["nodes"])
            model["nodes"].append({"id": node_id, "x": position[0], "y": position[1], "support": "Free"})
            return node_id

        return find_or_create(start), find_or_create(end)

    def _apply_selection(self, position: QPointF) -> None:
        if self._selection_rect is not None and self._selection_rect.width() >= 4.0 and self._selection_rect.height() >= 4.0:
            selected_nodes = {
                int(node["id"])
                for node in self._model.get("nodes", [])
                if self._selection_rect.contains(self._model_to_screen(float(node["x"]), float(node["y"])))
            } if self._selection_filter in {"nodes", "both"} else set()
            node_by_id = {int(node["id"]): node for node in self._model.get("nodes", [])}
            selected_members: set[int] = set()
            if self._selection_filter in {"members", "both"}:
                for member in self._model.get("elements", []):
                    first, second = node_by_id.get(int(member["n1"])), node_by_id.get(int(member["n2"]))
                    if first is None or second is None:
                        continue
                    start = self._model_to_screen(float(first["x"]), float(first["y"]))
                    end = self._model_to_screen(float(second["x"]), float(second["y"]))
                    contains = self._selection_rect.contains(start) and self._selection_rect.contains(end)
                    crosses = self._segment_crosses_rect(start, end, self._selection_rect)
                    if contains or (self._selection_crossing and crosses):
                        selected_members.add(int(member["id"]))
            self._set_selection(selected_nodes, selected_members)
            return
        node = self._node_at(position) if self._selection_filter in {"nodes", "both"} else None
        member = self._member_at(position) if node is None and self._selection_filter in {"members", "both"} else None
        self._set_selection({int(node["id"])} if node else set(), {int(member["id"])} if member else set())

    def _apply_zoom_window(self) -> None:
        if self._selection_rect is None or self._selection_rect.width() < 8.0 or self._selection_rect.height() < 8.0:
            self.authoring_message.emit("Drag a window to zoom.")
            return
        first = self._screen_to_model(self._selection_rect.topLeft())
        second = self._screen_to_model(self._selection_rect.bottomRight())
        self._fit_model_bounds(min(first[0], second[0]), max(first[0], second[0]), min(first[1], second[1]), max(first[1], second[1]))

    def _fit_model_bounds(self, min_x: float, max_x: float, min_y: float, max_y: float) -> None:
        all_nodes = self._model.get("nodes", [])
        if not all_nodes:
            return
        all_min_x, all_max_x = min(float(node["x"]) for node in all_nodes), max(float(node["x"]) for node in all_nodes)
        all_min_y, all_max_y = min(float(node["y"]) for node in all_nodes), max(float(node["y"]) for node in all_nodes)
        base_scale = min(max(self.width() - 140.0, 1.0) / max(all_max_x - all_min_x, 1.0), max(self.height() - 140.0, 1.0) / max(all_max_y - all_min_y, 1.0))
        target_scale = min(max(self.width() - 140.0, 1.0) / max(max_x - min_x, 1.0e-6), max(self.height() - 140.0, 1.0) / max(max_y - min_y, 1.0e-6))
        self._zoom = max(0.35, min(8.0, target_scale / base_scale))
        current_scale = base_scale * self._zoom
        model_center_x, model_center_y = (all_min_x + all_max_x) / 2.0, (all_min_y + all_max_y) / 2.0
        selection_center_x, selection_center_y = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0
        self._pan = QPointF(-(selection_center_x - model_center_x) * current_scale, (selection_center_y - model_center_y) * current_scale)

    @staticmethod
    def _segment_crosses_rect(start: QPointF, end: QPointF, rect: QRectF) -> bool:
        if rect.contains(start) or rect.contains(end):
            return True
        corners = (rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft())
        return any(
            FrameCanvas._segments_intersect(start, end, corners[index], corners[(index + 1) % len(corners)])
            for index in range(len(corners))
        )

    @staticmethod
    def _segments_intersect(first_start: QPointF, first_end: QPointF, second_start: QPointF, second_end: QPointF) -> bool:
        def cross(origin: QPointF, first: QPointF, second: QPointF) -> float:
            return (first.x() - origin.x()) * (second.y() - origin.y()) - (first.y() - origin.y()) * (second.x() - origin.x())

        first_a = cross(first_start, first_end, second_start)
        first_b = cross(first_start, first_end, second_end)
        second_a = cross(second_start, second_end, first_start)
        second_b = cross(second_start, second_end, first_end)
        return first_a * first_b <= 0.0 and second_a * second_b <= 0.0

    def _set_selection(self, nodes: set[int], members: set[int]) -> None:
        if nodes == self._selected_nodes and members == self._selected_members:
            return
        self._selected_nodes = nodes
        self._selected_members = members
        self.selection_changed.emit(self.selection)
        self.update()

    def _request_delete_selection(self) -> None:
        member_ids = set(self._selected_members)
        node_ids = set(self._selected_nodes)
        if not member_ids and not node_ids:
            return
        implied_members = {
            int(member["id"])
            for member in self._model.get("elements", [])
            if int(member["n1"]) in node_ids or int(member["n2"]) in node_ids
        }
        self.delete_requested.emit({"nodes": sorted(node_ids), "members": sorted(member_ids | implied_members)})

    def confirm_delete_selection(self) -> None:
        member_ids = set(self._selected_members)
        node_ids = set(self._selected_nodes)
        if not member_ids and not node_ids:
            return
        model = self._mutable_model()
        member_ids.update(
            int(member["id"])
            for member in model["elements"]
            if int(member["n1"]) in node_ids or int(member["n2"]) in node_ids
        )
        elements = [member for member in model["elements"] if int(member["id"]) not in member_ids]
        nodes = [node for node in model["nodes"] if int(node["id"]) not in node_ids]
        if not nodes or not elements:
            self.authoring_message.emit("The current model must keep at least one node and one member.")
            return
        model["nodes"] = nodes
        model["elements"] = elements
        model["nloads"] = [load for load in model["nloads"] if int(load["node"]) not in node_ids]
        model["eloads"] = [load for load in model["eloads"] if int(load["elem"]) not in member_ids]
        self._set_selection(set(), set())
        self._emit_model(model)

    def _mutable_model(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._model))

    @staticmethod
    def _next_id(items: list[Mapping[str, Any]]) -> int:
        return max((int(item["id"]) for item in items), default=0) + 1

    def _emit_model(self, model: dict[str, Any]) -> None:
        self.model_change_requested.emit(model)

    def _draw_legend(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor("#1e293b"), 3.0))
        painter.drawLine(18, 24, 44, 24)
        painter.setPen(QColor("#334155"))
        model_kind = str(self._model.get("projectInfo", {}).get("analysisType", "Frame"))
        painter.drawText(52, 29, model_kind)
        if self._view_mode == "results" and self._show_deformed and self._result:
            painter.setPen(QPen(QColor("#0f766e"), 2.0, Qt.PenStyle.DashLine))
            painter.drawLine(110, 24, 136, 24)
            painter.setPen(QColor("#334155"))
            painter.drawText(144, 29, "Deformed")
        x = 238
        if self._view_mode == "results" and self._diagram_mode != "none":
            keys = list(self._DIAGRAMS) if self._diagram_mode == "all" else [self._diagram_mode]
            for key in keys:
                label, color = self._DIAGRAMS[key]
                suffix = {"n_kg": " (T+)", "v_kg": " (CW+)", "m_kg_m": " (bottom tension)"}.get(key, "")
                label += suffix
                painter.setPen(QPen(color, 2.0, Qt.PenStyle.DashLine if key == "v_mm" else Qt.PenStyle.SolidLine))
                painter.drawLine(x, 24, x + 20, 24)
                painter.setPen(QColor("#334155"))
                painter.drawText(x + 26, 29, label)
                x += 26 + painter.fontMetrics().horizontalAdvance(label) + 18
        has_hybrid_truss = (
            model_kind != "Truss"
            and any(str(member.get("memberType", "Frame")) == "Truss" for member in self._model.get("elements", []))
        )
        if self._view_mode == "results" and has_hybrid_truss and self._diagram_mode in {"n_kg", "all"}:
            painter.setPen(QPen(QColor("#15803d"), 3.4))
            painter.drawLine(18, 48, 42, 48)
            painter.setPen(QColor("#334155"))
            painter.drawText(50, 53, "Hybrid truss tension (+N)")
            painter.setPen(QPen(QColor("#b91c1c"), 3.4))
            painter.drawLine(224, 48, 248, 48)
            painter.setPen(QColor("#334155"))
            painter.drawText(256, 53, "compression (-N)")
        if self._view_mode == "results" and self._display.contour_enabled and self._diagram_mode in self._DIAGRAMS:
            self._draw_contour_legend(painter, self._diagram_mode)
        if self._show_stress and self._view_mode == "results":
            painter.setPen(QPen(QColor("#dc2626"), 4.0))
            painter.drawLine(x, 24, x + 18, 24)
            painter.setPen(QColor("#334155"))
            painter.drawText(x + 24, 29, "Stress contour (+ red / - blue)")

    def _draw_contour_legend(self, painter: QPainter, key: str) -> None:
        selected = next((member for member in self._diagram_members if int(member.get("id", -1)) in self._selected_members), None)
        range_member = selected if self._display.contour_scale == "member" else None
        value_range = self._contour_range(key, range_member)
        width, height = 148.0, 126.0
        left = max(float(self.width()) - width - 18.0, 12.0)
        top = 46.0
        painter.setPen(QPen(QColor("#cbd5e1"), 1.0))
        painter.setBrush(QColor(255, 255, 255, 238))
        painter.drawRoundedRect(QRectF(left, top, width, height), 4.0, 4.0)
        label = self._DIAGRAMS[key][0]
        painter.setPen(QColor("#0f172a"))
        painter.drawText(QRectF(left + 9.0, top + 7.0, width - 18.0, 18.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{label} contour")
        bar_left, bar_top, bar_width, bar_height = left + 12.0, top + 33.0, 16.0, 64.0
        steps = 28
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(steps):
            value = value_range.maximum - value_range.span * index / max(steps - 1, 1)
            red, green, blue = colour_stops(value, value_range, self._display.contour_palette)
            painter.setBrush(QColor(red, green, blue))
            painter.drawRect(QRectF(bar_left, bar_top + bar_height * index / steps, bar_width, bar_height / steps + 1.0))
        painter.setPen(QColor("#334155"))
        painter.drawText(QPointF(bar_left + 25.0, bar_top + 8.0), self._format_diagram_value(key, value_range.maximum))
        if value_range.minimum < 0.0 < value_range.maximum:
            painter.drawText(QPointF(bar_left + 25.0, bar_top + bar_height / 2.0 + 4.0), self._format_diagram_value(key, 0.0))
        painter.drawText(QPointF(bar_left + 25.0, bar_top + bar_height), self._format_diagram_value(key, value_range.minimum))
        scale_label = "Global scale" if self._display.contour_scale == "global" else (f"Member E{selected['id']} scale" if selected else "Member scale")
        painter.setPen(QColor("#64748b"))
        painter.drawText(QRectF(left + 9.0, top + 103.0, width - 18.0, 15.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, scale_label)

    @staticmethod
    def _nice_step(value: float) -> float:
        if value <= 0:
            return 1.0
        base = 10.0 ** math.floor(math.log10(value))
        fraction = value / base
        return (1.0 if fraction <= 1.0 else 2.0 if fraction <= 2.0 else 5.0 if fraction <= 5.0 else 10.0) * base
