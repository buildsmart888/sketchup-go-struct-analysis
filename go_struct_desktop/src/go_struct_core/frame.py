"""2D frame direct-stiffness analysis matching the current Ruby GOFrame contract."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from .errors import ModelValidationError
from .schema import FrameElement, FrameModel, FrameSection, LoadCombination


@dataclass(frozen=True)
class _ElementState:
    element: FrameElement
    section: FrameSection
    length: float
    angle: float
    local_stiffness: np.ndarray
    transform: np.ndarray
    transform_transpose: np.ndarray
    dofs: tuple[int, int, int, int, int, int]
    n1_index: int
    n2_index: int


def _transform(angle: float) -> np.ndarray:
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return np.array(
        [
            [cosine, sine, 0.0, 0.0, 0.0, 0.0],
            [-sine, cosine, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, cosine, sine, 0.0],
            [0.0, 0.0, 0.0, -sine, cosine, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def _local_stiffness(section: FrameSection, length: float, release: str) -> np.ndarray:
    stiffness = np.zeros((6, 6), dtype=float)
    eal = section.e * section.area_m2 / length
    ei_l = section.e * section.inertia_m4 / length
    ei_l2 = 6.0 * section.e * section.inertia_m4 / length**2
    ei_l3 = 12.0 * section.e * section.inertia_m4 / length**3
    stiffness[0, 0] = eal
    stiffness[0, 3] = -eal
    stiffness[3, 0] = -eal
    stiffness[3, 3] = eal

    if release == "Rigid-Rigid":
        stiffness[1, 1] = ei_l3
        stiffness[1, 2] = ei_l2
        stiffness[1, 4] = -ei_l3
        stiffness[1, 5] = ei_l2
        stiffness[2, 1] = ei_l2
        stiffness[2, 2] = 4.0 * ei_l
        stiffness[2, 4] = -ei_l2
        stiffness[2, 5] = 2.0 * ei_l
        stiffness[4, 1] = -ei_l3
        stiffness[4, 2] = -ei_l2
        stiffness[4, 4] = ei_l3
        stiffness[4, 5] = -ei_l2
        stiffness[5, 1] = ei_l2
        stiffness[5, 2] = 2.0 * ei_l
        stiffness[5, 4] = -ei_l2
        stiffness[5, 5] = 4.0 * ei_l
    elif release == "Pin-Rigid":
        value_l3 = 3.0 * section.e * section.inertia_m4 / length**3
        value_l2 = 3.0 * section.e * section.inertia_m4 / length**2
        value_l = 3.0 * section.e * section.inertia_m4 / length
        stiffness[1, 1] = value_l3
        stiffness[1, 4] = -value_l3
        stiffness[1, 5] = value_l2
        stiffness[4, 1] = -value_l3
        stiffness[4, 4] = value_l3
        stiffness[4, 5] = -value_l2
        stiffness[5, 1] = value_l2
        stiffness[5, 4] = -value_l2
        stiffness[5, 5] = value_l
    elif release == "Rigid-Pin":
        value_l3 = 3.0 * section.e * section.inertia_m4 / length**3
        value_l2 = 3.0 * section.e * section.inertia_m4 / length**2
        value_l = 3.0 * section.e * section.inertia_m4 / length
        stiffness[1, 1] = value_l3
        stiffness[1, 2] = value_l2
        stiffness[1, 4] = -value_l3
        stiffness[2, 1] = value_l2
        stiffness[2, 2] = value_l
        stiffness[2, 4] = -value_l2
        stiffness[4, 1] = -value_l3
        stiffness[4, 2] = -value_l2
        stiffness[4, 4] = value_l3
    return stiffness


def _fixed_end_forces(wx1: float, wx2: float, wy1: float, wy2: float, length: float, release: str) -> np.ndarray:
    forces = np.zeros(6, dtype=float)
    delta_x = wx2 - wx1
    forces[0] = -(wx1 * length / 2.0) - (delta_x * length / 6.0)
    forces[3] = -(wx1 * length / 2.0) - (delta_x * length / 3.0)
    delta_y = wy2 - wy1
    if release == "Rigid-Rigid":
        forces[1] = -(wy1 * length / 2.0) - (3.0 * delta_y * length / 20.0)
        forces[2] = -(wy1 * length**2 / 12.0) - (delta_y * length**2 / 30.0)
        forces[4] = -(wy1 * length / 2.0) - (7.0 * delta_y * length / 20.0)
        forces[5] = (wy1 * length**2 / 12.0) + (delta_y * length**2 / 20.0)
    elif release == "Pin-Rigid":
        forces[1] = -(3.0 * wy1 * length / 8.0) - (delta_y * length / 10.0)
        forces[4] = -(5.0 * wy1 * length / 8.0) - (2.0 * delta_y * length / 5.0)
        forces[5] = (wy1 * length**2 / 8.0) + (delta_y * length**2 / 15.0)
    elif release == "Rigid-Pin":
        forces[1] = -(5.0 * wy1 * length / 8.0) - (13.0 * delta_y * length / 120.0)
        forces[2] = -(wy1 * length**2 / 8.0) - (7.0 * delta_y * length**2 / 120.0)
        forces[4] = -(3.0 * wy1 * length / 8.0) - (47.0 * delta_y * length / 120.0)
    elif release == "Pin-Pin":
        forces[1] = -(wy1 * length / 2.0) - (delta_y * length / 6.0)
        forces[4] = -(wy1 * length / 2.0) - (delta_y * length / 3.0)
    return forces


def _point_load_fixed_end(
    px: float,
    py: float,
    mz: float,
    x_m: float,
    section: FrameSection,
    length: float,
    release: str,
) -> np.ndarray:
    """Return fixed-end actions for a point force/moment using consistent FE loading."""
    ratio = min(1.0, max(0.0, x_m / length))
    rigid_load = np.zeros(6, dtype=float)
    rigid_load[0] = px * (1.0 - ratio)
    rigid_load[3] = px * ratio
    rigid_load[1] = py * (1.0 - 3.0 * ratio**2 + 2.0 * ratio**3)
    rigid_load[2] = py * length * (ratio - 2.0 * ratio**2 + ratio**3)
    rigid_load[4] = py * (3.0 * ratio**2 - 2.0 * ratio**3)
    rigid_load[5] = py * length * (-ratio**2 + ratio**3)
    rigid_load[1] += mz * (-6.0 * ratio + 6.0 * ratio**2) / length
    rigid_load[2] += mz * (1.0 - 4.0 * ratio + 3.0 * ratio**2)
    rigid_load[4] += mz * (6.0 * ratio - 6.0 * ratio**2) / length
    rigid_load[5] += mz * (-2.0 * ratio + 3.0 * ratio**2)

    released = {
        "Rigid-Rigid": (),
        "Pin-Rigid": (2,),
        "Rigid-Pin": (5,),
        "Pin-Pin": (2, 5),
    }[release]
    if not released:
        return -rigid_load
    active = tuple(index for index in range(6) if index not in released)
    rigid_stiffness = _local_stiffness(section, length, "Rigid-Rigid")
    active_load = rigid_load[list(active)]
    released_load = rigid_load[list(released)]
    coupling = rigid_stiffness[np.ix_(active, released)]
    release_stiffness = rigid_stiffness[np.ix_(released, released)]
    condensed_load = active_load - coupling @ np.linalg.solve(release_stiffness, released_load)
    forces = np.zeros(6, dtype=float)
    forces[list(active)] = -condensed_load
    return forces


def resolve_combination_factors(combination: LoadCombination) -> dict[str, float]:
    """Return factor objects or parse the legacy ``eq`` expression without mutation."""
    if combination.factors:
        return dict(combination.factors)
    if not combination.equation:
        return {}
    factors: dict[str, float] = {}
    for term in re.findall(r"[+-]?[^-+]+", combination.equation):
        match = re.fullmatch(r"([+-]?\s*\d*\.?\d*)\s*(.+)", term.strip())
        if not match:
            continue
        factor_text = re.sub(r"\s+", "", match.group(1))
        factor = 1.0 if factor_text in ("", "+") else -1.0 if factor_text == "-" else float(factor_text)
        factors[match.group(2).strip()] = factor
    return factors


def _empty_node_results(model: FrameModel) -> list[dict[str, float | int]]:
    return [
        {"id": node.id, "x": node.x, "y": node.y, "dx": 0.0, "dy": 0.0, "rz": 0.0, "fx": 0.0, "fy": 0.0, "mz": 0.0}
        for node in model.nodes
    ]


def _empty_element_results(model: FrameModel) -> list[dict[str, Any]]:
    return [
        {
            "id": element.id,
            "n1": element.n1,
            "n2": element.n2,
            "n1_forces": {"axial": 0.0, "shear": 0.0, "moment": 0.0},
            "n2_forces": {"axial": 0.0, "shear": 0.0, "moment": 0.0},
        }
        for element in model.elements
    ]


def _apply_envelope(target: dict[str, Any], candidate: dict[str, Any]) -> None:
    for target_node, candidate_node in zip(target["nodes"], candidate["nodes"], strict=True):
        for key in ("dx", "dy", "rz", "fx", "fy", "mz"):
            if abs(candidate_node[key]) > abs(target_node[key]):
                target_node[key] = candidate_node[key]
    for target_element, candidate_element in zip(target["elements"], candidate["elements"], strict=True):
        for end in ("n1_forces", "n2_forces"):
            for key in ("axial", "shear", "moment"):
                if abs(candidate_element[end][key]) > abs(target_element[end][key]):
                    target_element[end][key] = candidate_element[end][key]


def _combine_case_results(model: FrameModel, case_results: Mapping[str, dict[str, Any]], combination: LoadCombination) -> dict[str, Any]:
    combined = {"nodes": _empty_node_results(model), "elements": _empty_element_results(model)}
    for case_name, factor in resolve_combination_factors(combination).items():
        case = case_results.get(case_name)
        if case is None:
            continue
        for combined_node, case_node in zip(combined["nodes"], case["nodes"], strict=True):
            for key in ("dx", "dy", "rz", "fx", "fy", "mz"):
                combined_node[key] += case_node[key] * factor
        for combined_element, case_element in zip(combined["elements"], case["elements"], strict=True):
            for end in ("n1_forces", "n2_forces"):
                for key in ("axial", "shear", "moment"):
                    combined_element[end][key] += case_element[end][key] * factor
    return combined


def _analyze(model: FrameModel) -> dict[str, Any]:
    node_index = {node.id: index for index, node in enumerate(model.nodes)}
    section_by_id = {section.id: section for section in model.sections}
    total_dofs = len(model.nodes) * 3
    global_stiffness = np.zeros((total_dofs, total_dofs), dtype=float)
    states: dict[int, _ElementState] = {}

    for element in model.elements:
        n1_index = node_index[element.n1]
        n2_index = node_index[element.n2]
        n1 = model.nodes[n1_index]
        n2 = model.nodes[n2_index]
        dx = n2.x - n1.x
        dy = n2.y - n1.y
        length = math.hypot(dx, dy)
        if length <= 0.0:
            return {"ok": False, "error": f"Element {element.id} has zero length."}
        angle = math.atan2(dy, dx)
        transform = _transform(angle)
        local_stiffness = _local_stiffness(section_by_id[element.sec], length, element.release)
        dofs = (n1_index * 3, n1_index * 3 + 1, n1_index * 3 + 2, n2_index * 3, n2_index * 3 + 1, n2_index * 3 + 2)
        state = _ElementState(
            element=element,
            section=section_by_id[element.sec],
            length=length,
            angle=angle,
            local_stiffness=local_stiffness,
            transform=transform,
            transform_transpose=transform.T,
            dofs=dofs,
            n1_index=n1_index,
            n2_index=n2_index,
        )
        states[element.id] = state
        global_stiffness[np.ix_(dofs, dofs)] += state.transform_transpose @ state.local_stiffness @ state.transform

    fixed_dofs: list[int] = []
    for index, node in enumerate(model.nodes):
        if node.support == "Fixed":
            fixed_dofs.extend((index * 3, index * 3 + 1, index * 3 + 2))
        elif node.support == "Pinned":
            fixed_dofs.extend((index * 3, index * 3 + 1))
        elif node.support == "RollerX":
            fixed_dofs.append(index * 3 + 1)
        elif node.support == "RollerY":
            fixed_dofs.append(index * 3)
    fixed_dof_set = set(fixed_dofs)

    constrained_stiffness = global_stiffness.copy()
    for dof in range(total_dofs):
        if abs(constrained_stiffness[dof, dof]) < 1.0e-9 and dof not in fixed_dof_set:
            constrained_stiffness[dof, dof] = 1.0
    for dof in fixed_dof_set:
        constrained_stiffness[dof, :] = 0.0
        constrained_stiffness[:, dof] = 0.0
        constrained_stiffness[dof, dof] = 1.0

    nodal_by_case: dict[str, list[Any]] = {case: [] for case in model.load_cases}
    for load in model.nodal_loads:
        nodal_by_case[load.lcase].append(load)
    element_by_case: dict[str, list[Any]] = {case: [] for case in model.load_cases}
    for load in model.element_loads:
        element_by_case[load.lcase].append(load)

    results_by_case: dict[str, dict[str, Any]] = {}
    for load_case in model.load_cases:
        force_vector = np.zeros(total_dofs, dtype=float)
        for load in nodal_by_case[load_case]:
            index = node_index[load.node]
            force_vector[index * 3 : index * 3 + 3] += (load.fx, load.fy, load.mz)

        fixed_end_by_element: dict[int, np.ndarray] = {}
        for element in model.elements:
            state = states[element.id]
            fixed_end = np.zeros(6, dtype=float)
            if load_case == "DL" and model.settings.include_self_weight and state.section.density > 0:
                weight = state.section.area_m2 * state.section.density
                fixed_end += _fixed_end_forces(
                    -weight * math.sin(state.angle),
                    -weight * math.sin(state.angle),
                    -weight * math.cos(state.angle),
                    -weight * math.cos(state.angle),
                    state.length,
                    element.release,
                )
            for load in element_by_case[load_case]:
                if load.elem != element.id:
                    continue
                if load.type == "Point Force":
                    px = py = 0.0
                    if load.direction == "Local Y":
                        py = load.p
                    else:
                        px = load.p * math.sin(state.angle)
                        py = load.p * math.cos(state.angle)
                    fixed_end += _point_load_fixed_end(px, py, 0.0, load.x_m, state.section, state.length, element.release)
                    continue
                if load.type == "Point Moment":
                    fixed_end += _point_load_fixed_end(0.0, 0.0, load.m, load.x_m, state.section, state.length, element.release)
                    continue
                wx1 = wy1 = wx2 = wy2 = 0.0
                if load.direction == "Local Y":
                    wy1, wy2 = load.w1, load.w2
                elif load.direction == "Global Y":
                    wx1, wy1 = load.w1 * math.sin(state.angle), load.w1 * math.cos(state.angle)
                    wx2, wy2 = load.w2 * math.sin(state.angle), load.w2 * math.cos(state.angle)
                fixed_end += _fixed_end_forces(wx1, wx2, wy1, wy2, state.length, element.release)
            fixed_end_by_element[element.id] = fixed_end
            if np.any(np.abs(fixed_end) > 1.0e-9):
                force_vector[list(state.dofs)] -= state.transform_transpose @ fixed_end

        force_vector[list(fixed_dof_set)] = 0.0
        try:
            displacements = np.linalg.solve(constrained_stiffness, force_vector)
        except np.linalg.LinAlgError as exc:
            return {"ok": False, "error": f"Matrix Singular. Structure may be unstable.\n{exc}"}

        case_nodes = _empty_node_results(model)
        for index, node_result in enumerate(case_nodes):
            node_result["dx"] = float(displacements[index * 3])
            node_result["dy"] = float(displacements[index * 3 + 1])
            node_result["rz"] = float(displacements[index * 3 + 2])

        case_elements: list[dict[str, Any]] = []
        for element in model.elements:
            state = states[element.id]
            local_displacements = state.transform @ displacements[list(state.dofs)]
            local_forces = state.local_stiffness @ local_displacements + fixed_end_by_element[element.id]
            case_elements.append(
                {
                    "id": element.id,
                    "n1": element.n1,
                    "n2": element.n2,
                    "n1_forces": {"axial": float(local_forces[0]), "shear": float(local_forces[1]), "moment": float(local_forces[2])},
                    "n2_forces": {"axial": float(local_forces[3]), "shear": float(local_forces[4]), "moment": float(local_forces[5])},
                }
            )
            global_forces = state.transform_transpose @ local_forces
            if any(dof in fixed_dof_set for dof in state.dofs[:3]):
                case_nodes[state.n1_index]["fx"] += float(global_forces[0])
                case_nodes[state.n1_index]["fy"] += float(global_forces[1])
                case_nodes[state.n1_index]["mz"] += float(global_forces[2])
            if any(dof in fixed_dof_set for dof in state.dofs[3:]):
                case_nodes[state.n2_index]["fx"] += float(global_forces[3])
                case_nodes[state.n2_index]["fy"] += float(global_forces[4])
                case_nodes[state.n2_index]["mz"] += float(global_forces[5])

        for load in nodal_by_case[load_case]:
            index = node_index[load.node]
            if index * 3 in fixed_dof_set:
                case_nodes[index]["fx"] -= load.fx
            if index * 3 + 1 in fixed_dof_set:
                case_nodes[index]["fy"] -= load.fy
            if index * 3 + 2 in fixed_dof_set:
                case_nodes[index]["mz"] -= load.mz
        results_by_case[load_case] = {"nodes": case_nodes, "elements": case_elements}

    combination_results = {
        combination.name: _combine_case_results(model, results_by_case, combination)
        for combination in model.load_combinations
    }
    envelope = {"nodes": _empty_node_results(model), "elements": _empty_element_results(model)}
    for index, result in enumerate(combination_results.values()):
        if index == 0:
            envelope = {
                "nodes": [dict(node) for node in result["nodes"]],
                "elements": [
                    {
                        **element,
                        "n1_forces": dict(element["n1_forces"]),
                        "n2_forces": dict(element["n2_forces"]),
                    }
                    for element in result["elements"]
                ],
            }
        else:
            _apply_envelope(envelope, result)

    steps = [
        "1. Assembling Global Stiffness Matrix & Analyzing Topography",
        f"  Nodes: {len(model.nodes)}, Elements: {len(model.elements)}",
        "2. Decomposing Global Stiffness Matrix",
        "3. Processing Load Cases",
        "4. Processing Load Combinations & Envelopes",
        f"  Total Load Cases Evaluated: {len(model.load_cases)}",
        f"  Total Combinations Evaluated: {len(model.load_combinations)}",
        "  Analysis Complete.",
    ]
    return {"ok": True, **envelope, "steps": steps, "cases": results_by_case, "combos": combination_results}


def analyze_frame_data(data: Mapping[str, Any] | FrameModel) -> dict[str, Any]:
    """Analyze legacy-compatible GOFrame JSON and return legacy-compatible JSON results."""

    try:
        model = data if isinstance(data, FrameModel) else FrameModel.from_dict(data)
        return _analyze(model)
    except ModelValidationError as exc:
        return {"ok": False, "error": str(exc), "errors": exc.errors}
