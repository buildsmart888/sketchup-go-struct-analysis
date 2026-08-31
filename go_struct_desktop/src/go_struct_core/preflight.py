"""Fast, solver-independent checks shown before analysis runs."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Mapping

from .errors import ModelValidationError
from .schema import FrameModel


def check_frame_model(data: Mapping[str, Any] | FrameModel) -> list[dict[str, Any]]:
    """Return clickable pre-analysis issues without attempting a stiffness solution."""
    try:
        model = data if isinstance(data, FrameModel) else FrameModel.from_dict(data)
    except ModelValidationError as exc:
        return [{"severity": "error", "message": message, "nodes": [], "members": []} for message in exc.errors]

    issues: list[dict[str, Any]] = []
    nodes = {node.id: node for node in model.nodes}
    by_coordinate: dict[tuple[float, float], list[int]] = defaultdict(list)
    for node in model.nodes:
        by_coordinate[(round(node.x, 9), round(node.y, 9))].append(node.id)
    for node_ids in by_coordinate.values():
        if len(node_ids) > 1:
            issues.append({"severity": "warning", "message": "Nodes share coordinates but are not merged.", "nodes": node_ids, "members": []})

    by_pair: dict[tuple[int, int], list[int]] = defaultdict(list)
    connected: set[int] = set()
    for member in model.elements:
        pair = tuple(sorted((member.n1, member.n2)))
        by_pair[pair].append(member.id)
        connected.update(pair)
        first, second = nodes[member.n1], nodes[member.n2]
        if math.hypot(second.x - first.x, second.y - first.y) <= 1.0e-9:
            issues.append({"severity": "error", "message": f"Member E{member.id} has zero length.", "nodes": [member.n1, member.n2], "members": [member.id]})
    for pair, member_ids in by_pair.items():
        if len(member_ids) > 1:
            issues.append({"severity": "warning", "message": "Duplicate members connect the same nodes.", "nodes": list(pair), "members": member_ids})
    for node in model.nodes:
        if node.id not in connected:
            issues.append({"severity": "warning", "message": f"Node N{node.id} is disconnected from every member.", "nodes": [node.id], "members": []})

    restrained = 0
    for node in model.nodes:
        restrained += {"Fixed": 3, "Pinned": 2, "RollerX": 1, "RollerY": 1}.get(node.support, 0)
        if node.support == "Spring" and node.kx + node.ky + node.kr <= 0.0:
            issues.append({"severity": "error", "message": f"Spring support at N{node.id} needs at least one positive stiffness.", "nodes": [node.id], "members": []})
    if restrained == 0 and not any(node.support == "Spring" for node in model.nodes):
        issues.append({"severity": "error", "message": "The model has no restraints and will be unstable.", "nodes": [], "members": []})
    elif restrained < 3:
        issues.append({"severity": "warning", "message": "Few restrained degrees of freedom: check for a mechanism before analysis.", "nodes": [node.id for node in model.nodes if node.support != "Free"], "members": []})

    for load in model.element_loads:
        if load.type == "Distributed" and load.x2_m is not None and load.x2_m < load.x1_m:
            issues.append({"severity": "error", "message": f"Distributed load on E{load.elem} ends before it starts.", "nodes": [], "members": [load.elem]})
    if not issues:
        issues.append({"severity": "info", "message": "No pre-analysis issues found.", "nodes": [], "members": []})
    return issues
