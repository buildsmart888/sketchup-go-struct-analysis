"""Pure authoring helpers for pin-jointed truss projects."""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from typing import Any


def distribute_vertical_line_load(
    model: Mapping[str, Any], member_ids: Iterable[int], intensity: float, load_case: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert a vertical line load on selected roof-chord members into equivalent node loads.

    The load is measured per horizontal projected metre. Each selected member contributes half of
    its resultant to each endpoint, so adjacent selected roof-chord members accumulate naturally
    at their common panel node. This keeps the pin-jointed solver's nodal-load contract intact.
    """
    selected = {int(value) for value in member_ids}
    if not selected:
        raise ValueError("Select one or more roof-chord members first")
    data = copy.deepcopy(dict(model))
    nodes = {int(node["id"]): node for node in data.get("nodes", [])}
    member_map = {int(member["id"]): member for member in data.get("elements", [])}
    if missing := sorted(selected - set(member_map)):
        raise ValueError(f"Selected members no longer exist: {', '.join(str(value) for value in missing)}")
    if load_case not in data.get("loadcases", []):
        raise ValueError(f"Unknown load case: {load_case}")

    forces: dict[int, float] = {}
    projected_length = 0.0
    for member_id in sorted(selected):
        member = member_map[member_id]
        first, second = nodes.get(int(member["n1"])), nodes.get(int(member["n2"]))
        if first is None or second is None:
            raise ValueError(f"Member {member_id} references a missing node")
        horizontal_length = abs(float(second["x"]) - float(first["x"]))
        if horizontal_length <= 1.0e-12:
            raise ValueError(f"Member {member_id} has no horizontal projection")
        resultant = float(intensity) * horizontal_length
        forces[int(member["n1"])] = forces.get(int(member["n1"]), 0.0) + resultant / 2.0
        forces[int(member["n2"])] = forces.get(int(member["n2"]), 0.0) + resultant / 2.0
        projected_length += horizontal_length

    loads = data.setdefault("nloads", [])
    for node_id, fy in sorted(forces.items()):
        loads.append({"node": node_id, "lcase": load_case, "fx": 0.0, "fy": fy, "mz": 0.0})
    return data, {
        "member_ids": sorted(selected),
        "node_forces": forces,
        "projected_length_m": projected_length,
        "resultant_fy": float(intensity) * projected_length,
    }
