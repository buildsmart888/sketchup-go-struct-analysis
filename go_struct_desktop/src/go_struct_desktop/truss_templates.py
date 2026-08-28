"""Editable, analysis-ready templates for common planar truss layouts."""

from __future__ import annotations

from typing import Any


def _base(name: str, nodes: list[dict[str, Any]], elements: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "projectInfo": {"name": name, "analysisType": "Truss", "units": "legacy_kg_m", "project": "", "company": "", "engineer": "", "location": ""},
        "settings": {"include_self_weight": False},
        "nodes": nodes,
        "sections": [{"id": 1, "e": 2.0e9, "a": 1000.0, "i": 1.0, "density": 0.0}],
        "elements": elements,
        "loadcases": ["DL"],
        "loadcombos": [{"name": "Service", "factors": {"DL": 1.0}}],
        "nloads": [],
        "eloads": [],
    }


def triangle_truss_template(width_m: float = 6.0, height_m: float = 3.0) -> dict[str, Any]:
    return _base(
        "Triangle Truss",
        [{"id": 1, "x": 0.0, "y": 0.0, "support": "Pinned"}, {"id": 2, "x": width_m, "y": 0.0, "support": "RollerX"}, {"id": 3, "x": width_m / 2.0, "y": height_m, "support": "Free"}],
        [
            {"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 2, "n1": 1, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 3, "n1": 2, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
        ],
    )


def warren_truss_template(panel_count: int = 4, panel_m: float = 3.0, height_m: float = 2.0) -> dict[str, Any]:
    if panel_count < 2:
        raise ValueError("Warren truss requires at least two panels")
    nodes: list[dict[str, Any]] = [
        {"id": index + 1, "x": index * panel_m, "y": 0.0, "support": "Pinned" if index == 0 else "RollerX" if index == panel_count else "Free"}
        for index in range(panel_count + 1)
    ]
    nodes.extend({"id": panel_count + 2 + index, "x": (index + 0.5) * panel_m, "y": height_m, "support": "Free"} for index in range(panel_count))
    elements: list[dict[str, Any]] = []

    def add(n1: int, n2: int) -> None:
        elements.append({"id": len(elements) + 1, "n1": n1, "n2": n2, "sec": 1, "release": "Rigid-Rigid"})

    for index in range(panel_count):
        add(index + 1, index + 2)
        top = panel_count + 2 + index
        add(index + 1, top)
        add(top, index + 2)
        if index:
            add(top - 1, top)
    return _base(f"Warren Truss | {panel_count} panels", nodes, elements)


def pratt_truss_template(panel_count: int = 4, panel_m: float = 3.0, height_m: float = 2.5) -> dict[str, Any]:
    if panel_count < 2:
        raise ValueError("Pratt truss requires at least two panels")
    nodes: list[dict[str, Any]] = [
        {"id": index + 1, "x": index * panel_m, "y": 0.0, "support": "Pinned" if index == 0 else "RollerX" if index == panel_count else "Free"}
        for index in range(panel_count + 1)
    ]
    nodes.extend({"id": panel_count + 2 + index, "x": index * panel_m, "y": height_m, "support": "Free"} for index in range(panel_count + 1))
    elements: list[dict[str, Any]] = []

    def add(n1: int, n2: int) -> None:
        elements.append({"id": len(elements) + 1, "n1": n1, "n2": n2, "sec": 1, "release": "Rigid-Rigid"})

    top_offset = panel_count + 2
    for index in range(panel_count):
        add(index + 1, index + 2)
        add(top_offset + index, top_offset + index + 1)
    for index in range(panel_count + 1):
        add(index + 1, top_offset + index)
    midpoint = panel_count / 2.0
    for index in range(panel_count):
        if index < midpoint:
            add(index + 1, top_offset + index + 1)
        else:
            add(index + 2, top_offset + index)
    return _base(f"Pratt Truss | {panel_count} panels", nodes, elements)
