"""Editable, analysis-ready templates for common planar truss layouts."""

from __future__ import annotations

from typing import Any

from .truss_profiles import PROFILE_KINDS, profile_truss_geometry


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


def _positive(value: float, label: str) -> float:
    value = float(value)
    if value <= 0.0:
        raise ValueError(f"{label} must be greater than zero")
    return value


def _tag_template(model: dict[str, Any], kind: str, **parameters: float | int) -> dict[str, Any]:
    project_info = model["projectInfo"]
    project_info["trussTemplate"] = {"kind": kind, **parameters}
    return model


def triangle_truss_template(width_m: float = 6.0, height_m: float = 3.0) -> dict[str, Any]:
    width_m, height_m = _positive(width_m, "Triangle width"), _positive(height_m, "Triangle height")
    return _tag_template(_base(
        "Triangle Truss",
        [{"id": 1, "x": 0.0, "y": 0.0, "support": "Pinned"}, {"id": 2, "x": width_m, "y": 0.0, "support": "RollerX"}, {"id": 3, "x": width_m / 2.0, "y": height_m, "support": "Free"}],
        [
            {"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 2, "n1": 1, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 3, "n1": 2, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
        ],
    ), "triangle", width_m=width_m, height_m=height_m)


def warren_truss_template(panel_count: int = 4, panel_m: float = 3.0, height_m: float = 2.0) -> dict[str, Any]:
    if panel_count < 2:
        raise ValueError("Warren truss requires at least two panels")
    panel_m, height_m = _positive(panel_m, "Panel width"), _positive(height_m, "Truss height")
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
    return _tag_template(_base(f"Warren Truss | {panel_count} panels", nodes, elements), "warren", panel_count=panel_count, panel_m=panel_m, height_m=height_m)


def pratt_truss_template(panel_count: int = 4, panel_m: float = 3.0, height_m: float = 2.5) -> dict[str, Any]:
    if panel_count < 2:
        raise ValueError("Pratt truss requires at least two panels")
    panel_m, height_m = _positive(panel_m, "Panel width"), _positive(height_m, "Truss height")
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
    return _tag_template(_base(f"Pratt Truss | {panel_count} panels", nodes, elements), "pratt", panel_count=panel_count, panel_m=panel_m, height_m=height_m)


def howe_truss_template(panel_count: int = 4, panel_m: float = 3.0, height_m: float = 2.5) -> dict[str, Any]:
    """Parallel-chord Howe truss with diagonals reversed from the Pratt layout."""
    if panel_count < 2:
        raise ValueError("Howe truss requires at least two panels")
    panel_m, height_m = _positive(panel_m, "Panel width"), _positive(height_m, "Truss height")
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
            add(index + 2, top_offset + index)
        else:
            add(index + 1, top_offset + index + 1)
    return _tag_template(_base(f"Howe Truss | {panel_count} panels", nodes, elements), "howe", panel_count=panel_count, panel_m=panel_m, height_m=height_m)


def roof_truss_template(panel_count: int = 4, panel_m: float = 3.0, height_m: float = 3.0) -> dict[str, Any]:
    """Pitched roof truss with a bottom chord, verticals, and inward web members."""
    if panel_count < 2 or panel_count % 2:
        raise ValueError("Roof truss requires an even number of panels (at least two)")
    panel_m, height_m = _positive(panel_m, "Panel width"), _positive(height_m, "Roof height")
    nodes: list[dict[str, Any]] = [
        {"id": index + 1, "x": index * panel_m, "y": 0.0, "support": "Pinned" if index == 0 else "RollerX" if index == panel_count else "Free"}
        for index in range(panel_count + 1)
    ]
    top_offset = panel_count + 2
    for index in range(1, panel_count):
        rise = 1.0 - abs((2.0 * index / panel_count) - 1.0)
        nodes.append({"id": top_offset + index - 1, "x": index * panel_m, "y": height_m * rise, "support": "Free"})
    elements: list[dict[str, Any]] = []

    def top_node(index: int) -> int:
        return top_offset + index - 1

    def add(n1: int, n2: int) -> None:
        elements.append({"id": len(elements) + 1, "n1": n1, "n2": n2, "sec": 1, "release": "Rigid-Rigid"})

    for index in range(panel_count):
        add(index + 1, index + 2)
    add(1, top_node(1))
    for index in range(1, panel_count - 1):
        add(top_node(index), top_node(index + 1))
    add(top_node(panel_count - 1), panel_count + 1)
    for index in range(1, panel_count):
        add(index + 1, top_node(index))
    midpoint = panel_count // 2
    for index in range(1, midpoint):
        add(index + 1, top_node(index + 1))
    for index in range(midpoint, panel_count - 1):
        add(index + 2, top_node(index))
    return _tag_template(_base(f"Roof Truss | {panel_count} panels", nodes, elements), "roof", panel_count=panel_count, panel_m=panel_m, height_m=height_m)


def king_post_truss_template(width_m: float = 6.0, height_m: float = 3.0) -> dict[str, Any]:
    """A compact king-post roof truss, useful for short spans."""
    width_m, height_m = _positive(width_m, "King-post span"), _positive(height_m, "King-post height")
    nodes = [
        {"id": 1, "x": 0.0, "y": 0.0, "support": "Pinned"},
        {"id": 2, "x": width_m / 2.0, "y": 0.0, "support": "Free"},
        {"id": 3, "x": width_m, "y": 0.0, "support": "RollerX"},
        {"id": 4, "x": width_m / 2.0, "y": height_m, "support": "Free"},
    ]
    links = ((1, 2), (2, 3), (1, 4), (4, 3), (2, 4))
    elements = [{"id": index, "n1": first, "n2": second, "sec": 1, "release": "Rigid-Rigid"} for index, (first, second) in enumerate(links, start=1)]
    return _tag_template(_base("King Post Truss", nodes, elements), "king_post", width_m=width_m, height_m=height_m)


def fink_truss_template(panel_count: int = 4, panel_m: float = 3.0, height_m: float = 3.0) -> dict[str, Any]:
    """Pitched, triangulated Fink-style starter derived from the roof truss geometry."""
    model = roof_truss_template(panel_count if panel_count % 2 == 0 else panel_count + 1, panel_m, height_m)
    model["projectInfo"]["name"] = f"Fink Truss | {model['projectInfo']['trussTemplate']['panel_count']} panels"
    return _tag_template(model, "fink", panel_count=model["projectInfo"]["trussTemplate"]["panel_count"], panel_m=panel_m, height_m=height_m)


def profiled_truss_template(
    kind: str,
    panel_count: int = 4,
    panel_m: float = 3.0,
    depth_m: float = 2.0,
    rise_m: float = 1.5,
    bottom_rise_m: float = 0.75,
    web_pattern: str = "pratt",
) -> dict[str, Any]:
    """Create a standard panelled truss for flat, sloping, raised-bottom, or curved profiles."""

    if kind not in PROFILE_KINDS:
        raise ValueError(f"Unsupported truss profile {kind!r}")
    rise_value = float(rise_m)
    bottom_rise_value = float(bottom_rise_m)
    if rise_value < 0.0 or bottom_rise_value < 0.0:
        raise ValueError("Truss rise values cannot be negative")
    nodes, elements = profile_truss_geometry(
        kind,
        int(panel_count),
        _positive(panel_m, "Panel width"),
        _positive(depth_m, "Truss depth"),
        rise_value if kind in {"sloping", "mono", "gable", "raised_bottom", "curved"} else 0.0,
        bottom_rise_value if kind == "raised_bottom" else 0.0,
        web_pattern=web_pattern,
    )
    label = kind.replace("_", " ").title()
    return _tag_template(
        _base(f"{label} Truss | {panel_count} panels", nodes, elements),
        kind,
        panel_count=int(panel_count),
        panel_m=float(panel_m),
        depth_m=float(depth_m),
        rise_m=float(rise_m),
        bottom_rise_m=float(bottom_rise_m),
        web_pattern=web_pattern,
        dimension="2D",
        support_placement="bottom_chord",
        joint_model="pinned",
    )
