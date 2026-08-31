"""Lightweight model-space index used by interactive structural canvases.

The solver still owns model data.  This index is rebuilt only when that model changes and keeps
mouse interactions from repeatedly scanning every node/member or every pair of members.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
from typing import Any, Iterable, Mapping


Point = tuple[float, float]


@dataclass(frozen=True)
class IndexedSegment:
    member: Mapping[str, Any]
    start: Point
    end: Point

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (
            min(self.start[0], self.end[0]),
            min(self.start[1], self.end[1]),
            max(self.start[0], self.end[0]),
            max(self.start[1], self.end[1]),
        )


class CanvasSpatialIndex:
    """Uniform-grid lookup for nodes, members, load anchors, and snap candidates."""

    _MAX_CELLS_PER_MEMBER = 256

    def __init__(self, model: Mapping[str, Any]) -> None:
        self.model = model
        self.nodes = {int(node["id"]): node for node in model.get("nodes", [])}
        self.segments = self._segments()
        self.bounds = self._bounds()
        self.cell_size = self._cell_size()
        self._nodes: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
        self._members: dict[tuple[int, int], list[IndexedSegment]] = {}
        self._loads: dict[tuple[int, int], list[tuple[str, int, Point]]] = {}
        self._snap_points: dict[tuple[int, int], list[Point]] = {}
        self._global_members: list[IndexedSegment] = []
        self._populate()

    def _bounds(self) -> tuple[float, float, float, float]:
        points = [(float(node["x"]), float(node["y"])) for node in self.nodes.values()]
        if not points:
            return (0.0, 0.0, 1.0, 1.0)
        return (
            min(x for x, _ in points),
            min(y for _, y in points),
            max(x for x, _ in points),
            max(y for _, y in points),
        )

    def _segments(self) -> list[IndexedSegment]:
        values: list[IndexedSegment] = []
        for member in self.model.get("elements", []):
            first = self.nodes.get(int(member.get("n1", -1)))
            second = self.nodes.get(int(member.get("n2", -1)))
            if first is None or second is None:
                continue
            values.append(
                IndexedSegment(
                    member,
                    (float(first["x"]), float(first["y"])),
                    (float(second["x"]), float(second["y"])),
                )
            )
        return values

    def _cell_size(self) -> float:
        points = [(float(node["x"]), float(node["y"])) for node in self.nodes.values()]
        if not points:
            return 1.0
        span = max(max(x for x, _ in points) - min(x for x, _ in points), max(y for _, y in points) - min(y for _, y in points), 1.0)
        divisions = min(64, max(8, int(math.sqrt(max(len(self.segments), 1)) * 2.0)))
        return span / divisions

    def _cell(self, point: Point) -> tuple[int, int]:
        return (math.floor(point[0] / self.cell_size), math.floor(point[1] / self.cell_size))

    def _cells_for_bounds(self, bounds: tuple[float, float, float, float]) -> list[tuple[int, int]]:
        left, bottom = self._cell((bounds[0], bounds[1]))
        right, top = self._cell((bounds[2], bounds[3]))
        if (right - left + 1) * (top - bottom + 1) > self._MAX_CELLS_PER_MEMBER:
            return []
        return [(x, y) for x in range(left, right + 1) for y in range(bottom, top + 1)]

    def _add(self, target: dict[tuple[int, int], list[Any]], point: Point, value: Any) -> None:
        target.setdefault(self._cell(point), []).append(value)

    def _populate(self) -> None:
        for node in self.nodes.values():
            self._add(self._nodes, (float(node["x"]), float(node["y"])), node)
        for segment in self.segments:
            cells = self._cells_for_bounds(segment.bounds)
            if not cells:
                self._global_members.append(segment)
            else:
                for cell in cells:
                    self._members.setdefault(cell, []).append(segment)
            midpoint = ((segment.start[0] + segment.end[0]) / 2.0, (segment.start[1] + segment.end[1]) / 2.0)
            self._add(self._snap_points, midpoint, midpoint)
        self._add_intersections()
        self._add_load_anchors()

    def _add_intersections(self) -> None:
        checked: set[tuple[int, int]] = set()
        for members in self._members.values():
            for first, second in combinations(members, 2):
                ids = tuple(sorted((int(first.member["id"]), int(second.member["id"]))))
                if ids in checked:
                    continue
                checked.add(ids)
                intersection = self.line_intersection(first.start, first.end, second.start, second.end)
                if intersection is not None:
                    self._add(self._snap_points, intersection, intersection)
        # Very long members are intentionally kept out of the uniform grid.  They still need
        # intersection snaps, but only compare against indexed members once per rebuild.
        for first in self._global_members:
            for second in self.segments:
                if first is second:
                    continue
                ids = tuple(sorted((int(first.member["id"]), int(second.member["id"]))))
                if ids in checked:
                    continue
                checked.add(ids)
                intersection = self.line_intersection(first.start, first.end, second.start, second.end)
                if intersection is not None:
                    self._add(self._snap_points, intersection, intersection)

    def _add_load_anchors(self) -> None:
        for index, load in enumerate(self.model.get("nloads", [])):
            node = self.nodes.get(int(load.get("node", -1)))
            if node is not None:
                self._add(self._loads, (float(node["x"]), float(node["y"])), ("nodal", index, (float(node["x"]), float(node["y"]))))
        by_member = {int(segment.member["id"]): segment for segment in self.segments}
        for index, load in enumerate(self.model.get("eloads", [])):
            segment = by_member.get(int(load.get("elem", -1)))
            if segment is None:
                continue
            length = math.dist(segment.start, segment.end)
            if length <= 1.0e-12:
                continue
            station = float(load.get("x_m", length / 2.0)) if load.get("type") in {"Point Force", "Point Moment"} else length / 2.0
            ratio = min(1.0, max(0.0, station / length))
            point = (segment.start[0] + (segment.end[0] - segment.start[0]) * ratio, segment.start[1] + (segment.end[1] - segment.start[1]) * ratio)
            self._add(self._loads, point, ("member", index, point))

    def _nearby(self, target: Mapping[tuple[int, int], list[Any]], point: Point, radius: float) -> list[Any]:
        radius_cells = max(1, math.ceil(radius / self.cell_size))
        center_x, center_y = self._cell(point)
        values: list[Any] = []
        for x in range(center_x - radius_cells, center_x + radius_cells + 1):
            for y in range(center_y - radius_cells, center_y + radius_cells + 1):
                values.extend(target.get((x, y), []))
        return values

    def nodes_near(self, point: Point, radius: float) -> list[Mapping[str, Any]]:
        return self._nearby(self._nodes, point, radius)

    def members_near(self, point: Point, radius: float) -> list[IndexedSegment]:
        values = self._nearby(self._members, point, radius)
        values.extend(self._global_members)
        return list({int(item.member["id"]): item for item in values}.values())

    def loads_near(self, point: Point, radius: float) -> list[tuple[str, int, Point]]:
        return self._nearby(self._loads, point, radius)

    def snap_points_near(self, point: Point, radius: float) -> list[Point]:
        return self._nearby(self._snap_points, point, radius)

    @staticmethod
    def line_intersection(first_start: Point, first_end: Point, second_start: Point, second_end: Point) -> Point | None:
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


def nearest_point(point: Point, candidates: Iterable[Point]) -> tuple[float, Point] | None:
    """Return distance and nearest candidate without constructing a temporary UI object."""

    values = [(math.dist(point, candidate), candidate) for candidate in candidates]
    return min(values, key=lambda value: value[0]) if values else None
