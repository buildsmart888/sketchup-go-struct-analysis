"""Geometry-first generators shared by planar and hybrid truss template catalogs."""

from __future__ import annotations

from typing import Any


PROFILE_KINDS = ("flat", "sloping", "mono", "gable", "raised_bottom", "curved")
WEB_PATTERNS = ("pratt", "howe", "warren", "x")


def profile_truss_geometry(
    kind: str,
    panel_count: int,
    panel_m: float,
    depth_m: float,
    rise_m: float = 0.0,
    bottom_rise_m: float = 0.0,
    base_y: float = 0.0,
    top_section: int = 1,
    bottom_section: int = 1,
    web_section: int = 1,
    member_type: str = "Truss",
    end_supports: bool = True,
    web_pattern: str = "pratt",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build a pin-jointed, panelled truss with independently profiled chords.

    The generator intentionally works from node coordinates rather than named truss formulas.  This
    keeps bottom-chord and top-chord variations compatible with the same web layout and Hybrid solver.
    """

    if kind not in PROFILE_KINDS:
        raise ValueError(f"Unsupported truss profile {kind!r}")
    if web_pattern not in WEB_PATTERNS:
        raise ValueError(f"Unsupported truss web pattern {web_pattern!r}")
    if panel_count < 2:
        raise ValueError("A profiled truss requires at least two panels")
    if panel_m <= 0.0 or depth_m <= 0.0:
        raise ValueError("Panel width and truss depth must be greater than zero")
    if kind in {"sloping", "mono", "gable", "raised_bottom", "curved"} and rise_m < 0.0:
        raise ValueError("Truss rise cannot be negative")
    if kind == "raised_bottom" and bottom_rise_m < 0.0:
        raise ValueError("Bottom-chord rise cannot be negative")

    def roof_shape(ratio: float) -> float:
        return 1.0 - abs(2.0 * ratio - 1.0)

    def arc_shape(ratio: float) -> float:
        return 4.0 * ratio * (1.0 - ratio)

    def elevations(ratio: float) -> tuple[float, float]:
        if kind == "flat":
            bottom = base_y
            top = bottom + depth_m
        elif kind == "sloping":
            bottom = base_y + rise_m * ratio
            top = bottom + depth_m
        elif kind == "mono":
            bottom = base_y
            top = bottom + depth_m + rise_m * ratio
        elif kind == "gable":
            bottom = base_y
            top = bottom + depth_m + rise_m * roof_shape(ratio)
        elif kind == "raised_bottom":
            bottom = base_y + bottom_rise_m * roof_shape(ratio)
            top = bottom + depth_m + rise_m * roof_shape(ratio)
        else:  # curved
            bottom = base_y
            top = bottom + depth_m + rise_m * arc_shape(ratio)
        return bottom, top

    panel_nodes = panel_count + 1
    nodes: list[dict[str, Any]] = []
    for index in range(panel_nodes):
        ratio = index / panel_count
        bottom, _top = elevations(ratio)
        nodes.append(
            {
                "id": index + 1,
                "x": index * panel_m,
                "y": bottom,
                "support": "Pinned" if end_supports and index == 0 else "RollerX" if end_supports and index == panel_count else "Free",
            }
        )
    top_node_count = panel_count if web_pattern == "warren" else panel_nodes
    for index in range(top_node_count):
        ratio = (index + 0.5) / panel_count if web_pattern == "warren" else index / panel_count
        _bottom, top = elevations(ratio)
        nodes.append({"id": panel_nodes + index + 1, "x": ratio * panel_count * panel_m, "y": top, "support": "Free"})

    elements: list[dict[str, Any]] = []

    def add(n1: int, n2: int, section: int) -> None:
        element: dict[str, Any] = {
            "id": len(elements) + 1,
            "n1": n1,
            "n2": n2,
            "sec": section,
            "release": "Rigid-Rigid",
        }
        if member_type != "Frame":
            element["memberType"] = member_type
        elements.append(element)

    top_offset = panel_nodes
    for index in range(panel_count):
        add(index + 1, index + 2, bottom_section)
    for index in range(top_node_count - 1):
        add(top_offset + index + 1, top_offset + index + 2, top_section)
    if web_pattern == "warren":
        for index in range(panel_count):
            top = top_offset + index + 1
            add(index + 1, top, web_section)
            add(top, index + 2, web_section)
    else:
        for index in range(panel_nodes):
            add(index + 1, top_offset + index + 1, web_section)
        for index in range(panel_count):
            pratt_forward = index < panel_count / 2.0
            if web_pattern == "howe":
                pratt_forward = not pratt_forward
            if web_pattern == "x":
                add(index + 1, top_offset + index + 2, web_section)
                add(top_offset + index + 1, index + 2, web_section)
            elif pratt_forward:
                add(index + 1, top_offset + index + 2, web_section)
            else:
                add(top_offset + index + 1, index + 2, web_section)
    return nodes, elements
