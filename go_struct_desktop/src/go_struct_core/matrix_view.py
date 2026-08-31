"""Inspectable stiffness-system payloads for a solved 2D frame."""

from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np

from .frame import _distributed_load_fixed_end, _local_stiffness, _point_load_fixed_end, _transform, _truss_local_stiffness, resolve_combination_factors
from .schema import FrameModel


def build_frame_matrix_view(data: Mapping[str, Any] | FrameModel, analysis: Mapping[str, Any]) -> dict[str, Any]:
    """Expose K, F, D and member matrices for cases/combos, never the envelope."""
    model = data if isinstance(data, FrameModel) else FrameModel.from_dict(data)
    node_index = {node.id: index for index, node in enumerate(model.nodes)}
    section_by_id = {section.id: section for section in model.sections}
    total = len(model.nodes) * 3
    stiffness = np.zeros((total, total), dtype=float)
    member_items: list[dict[str, Any]] = []
    states: dict[int, tuple[Any, float, float, np.ndarray, np.ndarray, tuple[int, ...]]] = {}
    for element in model.elements:
        first, second = model.nodes[node_index[element.n1]], model.nodes[node_index[element.n2]]
        dx, dy = second.x - first.x, second.y - first.y
        length, angle = math.hypot(dx, dy), math.atan2(dy, dx)
        transform = _transform(angle)
        local = (
            _truss_local_stiffness(section_by_id[element.sec], length)
            if element.member_type == "Truss"
            else _local_stiffness(section_by_id[element.sec], length, element.release)
        )
        dofs = (node_index[element.n1] * 3, node_index[element.n1] * 3 + 1, node_index[element.n1] * 3 + 2, node_index[element.n2] * 3, node_index[element.n2] * 3 + 1, node_index[element.n2] * 3 + 2)
        global_member = transform.T @ local @ transform
        stiffness[np.ix_(dofs, dofs)] += global_member
        states[element.id] = (element, length, angle, local, transform, dofs)
        member_items.append({"id": element.id, "n1": element.n1, "n2": element.n2, "memberType": element.member_type, "length_m": length, "angle_deg": math.degrees(angle), "dofs": list(dofs), "local_stiffness": local.tolist(), "global_stiffness": global_member.tolist()})

    fixed: list[int] = []
    for index, node in enumerate(model.nodes):
        if node.support == "Fixed":
            fixed.extend((index * 3, index * 3 + 1, index * 3 + 2))
        elif node.support == "Pinned":
            fixed.extend((index * 3, index * 3 + 1))
        elif node.support == "RollerX":
            fixed.append(index * 3 + 1)
        elif node.support == "RollerY":
            fixed.append(index * 3)
        elif node.support == "Spring":
            stiffness[index * 3, index * 3] += node.kx
            stiffness[index * 3 + 1, index * 3 + 1] += node.ky
            stiffness[index * 3 + 2, index * 3 + 2] += node.kr
    fixed = sorted(set(fixed))
    free = [index for index in range(total) if index not in fixed]
    constrained = stiffness.copy()
    for dof in fixed:
        constrained[dof, :] = 0.0
        constrained[:, dof] = 0.0
        constrained[dof, dof] = 1.0

    dof_labels = [f"N{node.id}.{label}" for node in model.nodes for label in ("Ux", "Uy", "Rz")]
    case_forces: dict[str, np.ndarray] = {}
    for load_case in model.load_cases:
        force = np.zeros(total, dtype=float)
        for load in model.nodal_loads:
            if load.lcase == load_case:
                index = node_index[load.node] * 3
                force[index : index + 3] += (load.fx, load.fy, load.mz)
        for load in model.element_loads:
            if load.lcase != load_case:
                continue
            element, length, angle, _local, transform, dofs = states[load.elem]
            section = section_by_id[element.sec]
            if load.type == "Point Force":
                px, py = (load.p, 0.0) if load.direction == "Local X" else (0.0, load.p) if load.direction == "Local Y" else (load.p * math.cos(angle), -load.p * math.sin(angle)) if load.direction == "Global X" else (load.p * math.sin(angle), load.p * math.cos(angle))
                fixed_end = _point_load_fixed_end(px, py, 0.0, load.x_m, section, length, element.release)
            elif load.type == "Point Moment":
                fixed_end = _point_load_fixed_end(0.0, 0.0, load.m, load.x_m, section, length, element.release)
            else:
                if load.direction == "Local X":
                    wx1, wy1, wx2, wy2 = load.w1, 0.0, load.w2, 0.0
                elif load.direction == "Local Y":
                    wx1, wy1, wx2, wy2 = 0.0, load.w1, 0.0, load.w2
                elif load.direction == "Global X":
                    wx1, wy1, wx2, wy2 = load.w1 * math.cos(angle), -load.w1 * math.sin(angle), load.w2 * math.cos(angle), -load.w2 * math.sin(angle)
                else:
                    wx1, wy1, wx2, wy2 = load.w1 * math.sin(angle), load.w1 * math.cos(angle), load.w2 * math.sin(angle), load.w2 * math.cos(angle)
                fixed_end = _distributed_load_fixed_end(wx1, wx2, wy1, wy2, length, element.release, load.x1_m, load.x2_m)
            force[list(dofs)] -= transform.T @ fixed_end
        force[fixed] = 0.0
        case_forces[load_case] = force

    selections: dict[str, dict[str, Any]] = {}
    for name, result in analysis.get("cases", {}).items():
        displacement = np.array([value for node in result.get("nodes", []) for value in (node.get("dx", 0.0), node.get("dy", 0.0), node.get("rz", 0.0))], dtype=float)
        force = case_forces.get(name, np.zeros(total))
        residual = stiffness @ displacement - force
        selections[f"case:{name}"] = {"force": force.tolist(), "displacement": displacement.tolist(), "free_residual": residual[free].tolist()}
    for combo in model.load_combinations:
        result = analysis.get("combos", {}).get(combo.name)
        if result is None:
            continue
        factors = resolve_combination_factors(combo)
        force = sum((factor * case_forces.get(name, np.zeros(total)) for name, factor in factors.items()), np.zeros(total))
        displacement = np.array([value for node in result.get("nodes", []) for value in (node.get("dx", 0.0), node.get("dy", 0.0), node.get("rz", 0.0))], dtype=float)
        residual = stiffness @ displacement - force
        selections[f"combo:{combo.name}"] = {"force": force.tolist(), "displacement": displacement.tolist(), "free_residual": residual[free].tolist()}
    return {"dofs": dof_labels, "global_stiffness": stiffness.tolist(), "reduced_stiffness": stiffness[np.ix_(free, free)].tolist(), "restrained_dofs": fixed, "free_dofs": free, "members": member_items, "selections": selections}
