"""Euler-Bernoulli 1D beam analysis with the shared GO Struct JSON contract."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from .errors import ModelValidationError
from .frame import resolve_combination_factors
from .schema import FrameElement, FrameModel, FrameSection, LoadCombination


_RELEASED_ROTATIONS = {
    "Rigid-Rigid": (),
    "Pin-Rigid": (1,),
    "Rigid-Pin": (3,),
    "Pin-Pin": (1, 3),
}


@dataclass(frozen=True)
class BeamModel:
    """Validated horizontal-beam view over the stable Frame JSON field names.

    Keeping the common JSON shape lets the desktop's existing canvas, load editor, result
    tables, units, and file tooling be reused without making the beam solver depend on UI code.
    """

    frame: FrameModel

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "BeamModel":
        frame = FrameModel.from_dict(raw)
        errors: list[str] = []
        analysis_type = str(frame.project_info.get("analysisType", "Beam"))
        if analysis_type.lower() not in {"beam", "2d beam"}:
            errors.append("projectInfo.analysisType must be 'Beam' for the Beam workspace")
        node_by_id = {node.id: node for node in frame.nodes}
        for element in frame.elements:
            start, end = node_by_id[element.n1], node_by_id[element.n2]
            if abs(end.y - start.y) > 1.0e-9:
                errors.append(f"beam member {element.id} must be horizontal")
            if end.x <= start.x:
                errors.append(f"beam member {element.id} must run from lower X node I to higher X node J")
        for load in frame.nodal_loads:
            if abs(load.fx) > 1.0e-12:
                errors.append(f"beam nodal load at node {load.node} cannot use Fx; use Fy or Mz")
        for load in frame.element_loads:
            if load.type != "Point Moment" and load.direction not in {"Local Y", "Global Y"}:
                errors.append(f"beam load on member {load.elem} must use Local Y or Global Y")
        if errors:
            raise ModelValidationError(errors)
        return cls(frame=frame)

    def to_dict(self) -> dict[str, Any]:
        data = self.frame.to_dict()
        data["projectInfo"]["analysisType"] = "Beam"
        return data


def _rigid_stiffness(section: FrameSection, length: float) -> np.ndarray:
    ei = section.e * section.inertia_m4
    return (ei / length**3) * np.array(
        [[12.0, 6.0 * length, -12.0, 6.0 * length], [6.0 * length, 4.0 * length**2, -6.0 * length, 2.0 * length**2],
         [-12.0, -6.0 * length, 12.0, -6.0 * length], [6.0 * length, 2.0 * length**2, -6.0 * length, 4.0 * length**2]],
        dtype=float,
    )


def _condense(stiffness: np.ndarray, rigid_load: np.ndarray, release: str) -> tuple[np.ndarray, np.ndarray]:
    released = _RELEASED_ROTATIONS[release]
    if not released:
        return stiffness, -rigid_load
    active = tuple(index for index in range(4) if index not in released)
    k_aa = stiffness[np.ix_(active, active)]
    k_ar = stiffness[np.ix_(active, released)]
    k_ra = stiffness[np.ix_(released, active)]
    k_rr = stiffness[np.ix_(released, released)]
    condensed_stiffness = k_aa - k_ar @ np.linalg.solve(k_rr, k_ra)
    condensed_load = rigid_load[list(active)] - k_ar @ np.linalg.solve(k_rr, rigid_load[list(released)])
    output_stiffness = np.zeros((4, 4), dtype=float)
    output_fixed_end = np.zeros(4, dtype=float)
    output_stiffness[np.ix_(active, active)] = condensed_stiffness
    output_fixed_end[list(active)] = -condensed_load
    return output_stiffness, output_fixed_end


def _element_stiffness(section: FrameSection, length: float, release: str) -> np.ndarray:
    stiffness, _ = _condense(_rigid_stiffness(section, length), np.zeros(4, dtype=float), release)
    return stiffness


def _distributed_fixed_end(w1: float, w2: float, section: FrameSection, length: float, release: str) -> np.ndarray:
    """Internal fixed-end actions for a linearly varying transverse load."""
    delta = w2 - w1
    rigid_load = np.array(
        [
            w1 * length / 2.0 + 3.0 * delta * length / 20.0,
            w1 * length**2 / 12.0 + delta * length**2 / 30.0,
            w1 * length / 2.0 + 7.0 * delta * length / 20.0,
            -w1 * length**2 / 12.0 - delta * length**2 / 20.0,
        ],
        dtype=float,
    )
    _, fixed_end = _condense(_rigid_stiffness(section, length), rigid_load, release)
    return fixed_end


def _point_fixed_end(value: float, moment: float, x_m: float, section: FrameSection, length: float, release: str) -> np.ndarray:
    ratio = min(1.0, max(0.0, x_m / length))
    rigid_load = np.array(
        [
            value * (1.0 - 3.0 * ratio**2 + 2.0 * ratio**3),
            value * length * (ratio - 2.0 * ratio**2 + ratio**3),
            value * (3.0 * ratio**2 - 2.0 * ratio**3),
            value * length * (-ratio**2 + ratio**3),
        ],
        dtype=float,
    )
    rigid_load += np.array(
        [moment * (-6.0 * ratio + 6.0 * ratio**2) / length, moment * (1.0 - 4.0 * ratio + 3.0 * ratio**2),
         moment * (6.0 * ratio - 6.0 * ratio**2) / length, moment * (-2.0 * ratio + 3.0 * ratio**2)],
        dtype=float,
    )
    _, fixed_end = _condense(_rigid_stiffness(section, length), rigid_load, release)
    return fixed_end


def _empty_nodes(model: FrameModel) -> list[dict[str, float | int]]:
    return [{"id": node.id, "x": node.x, "y": node.y, "dx": 0.0, "dy": 0.0, "rz": 0.0, "fx": 0.0, "fy": 0.0, "mz": 0.0} for node in model.nodes]


def _empty_elements(model: FrameModel) -> list[dict[str, Any]]:
    return [{"id": item.id, "n1": item.n1, "n2": item.n2, "n1_forces": {"axial": 0.0, "shear": 0.0, "moment": 0.0}, "n2_forces": {"axial": 0.0, "shear": 0.0, "moment": 0.0}} for item in model.elements]


def _combine(model: FrameModel, cases: Mapping[str, dict[str, Any]], combo: LoadCombination) -> dict[str, Any]:
    combined = {"nodes": _empty_nodes(model), "elements": _empty_elements(model)}
    for case_name, factor in resolve_combination_factors(combo).items():
        case = cases.get(case_name)
        if case is None:
            continue
        for target, source in zip(combined["nodes"], case["nodes"], strict=True):
            for key in ("dx", "dy", "rz", "fx", "fy", "mz"):
                target[key] += float(source[key]) * factor
        for target, source in zip(combined["elements"], case["elements"], strict=True):
            for end in ("n1_forces", "n2_forces"):
                for key in ("axial", "shear", "moment"):
                    target[end][key] += float(source[end][key]) * factor
    return combined


def _apply_envelope(target: dict[str, Any], candidate: Mapping[str, Any]) -> None:
    for target_node, source_node in zip(target["nodes"], candidate["nodes"], strict=True):
        for key in ("dx", "dy", "rz", "fx", "fy", "mz"):
            if abs(float(source_node[key])) > abs(float(target_node[key])):
                target_node[key] = source_node[key]
    for target_member, source_member in zip(target["elements"], candidate["elements"], strict=True):
        for end in ("n1_forces", "n2_forces"):
            for key in ("axial", "shear", "moment"):
                if abs(float(source_member[end][key])) > abs(float(target_member[end][key])):
                    target_member[end][key] = source_member[end][key]


def _analyze(model: FrameModel) -> dict[str, Any]:
    node_index = {node.id: index for index, node in enumerate(model.nodes)}
    sections = {section.id: section for section in model.sections}
    total_dofs = len(model.nodes) * 2
    stiffness = np.zeros((total_dofs, total_dofs), dtype=float)
    states: dict[int, tuple[FrameElement, FrameSection, float, np.ndarray, tuple[int, int, int, int]]] = {}
    for element in model.elements:
        start = model.nodes[node_index[element.n1]]
        end = model.nodes[node_index[element.n2]]
        length = end.x - start.x
        section = sections[element.sec]
        dofs = (node_index[element.n1] * 2, node_index[element.n1] * 2 + 1, node_index[element.n2] * 2, node_index[element.n2] * 2 + 1)
        local_stiffness = _element_stiffness(section, length, element.release)
        stiffness[np.ix_(dofs, dofs)] += local_stiffness
        states[element.id] = (element, section, length, local_stiffness, dofs)

    fixed: set[int] = set()
    for index, node in enumerate(model.nodes):
        if node.support == "Fixed":
            fixed.update((index * 2, index * 2 + 1))
        elif node.support in {"Pinned", "RollerX"}:
            fixed.add(index * 2)
    free = tuple(index for index in range(total_dofs) if index not in fixed)
    if not fixed:
        return {"ok": False, "error": "Beam has no vertical restraints."}

    nodal_by_case = {case: [load for load in model.nodal_loads if load.lcase == case] for case in model.load_cases}
    member_by_case = {case: [load for load in model.element_loads if load.lcase == case] for case in model.load_cases}
    case_results: dict[str, dict[str, Any]] = {}
    for load_case in model.load_cases:
        force = np.zeros(total_dofs, dtype=float)
        for load in nodal_by_case[load_case]:
            force[node_index[load.node] * 2 : node_index[load.node] * 2 + 2] += (load.fy, load.mz)
        fixed_ends: dict[int, np.ndarray] = {}
        for element_id, (element, section, length, _local_stiffness, dofs) in states.items():
            fixed_end = np.zeros(4, dtype=float)
            if load_case == "DL" and model.settings.include_self_weight and section.density > 0.0:
                fixed_end += _distributed_fixed_end(-section.area_m2 * section.density, -section.area_m2 * section.density, section, length, element.release)
            for load in member_by_case[load_case]:
                if load.elem != element_id:
                    continue
                if load.type == "Distributed":
                    fixed_end += _distributed_fixed_end(load.w1, load.w2, section, length, element.release)
                elif load.type == "Point Force":
                    fixed_end += _point_fixed_end(load.p, 0.0, load.x_m, section, length, element.release)
                else:
                    fixed_end += _point_fixed_end(0.0, load.m, load.x_m, section, length, element.release)
            fixed_ends[element_id] = fixed_end
            force[list(dofs)] -= fixed_end
        displacements = np.zeros(total_dofs, dtype=float)
        # A released end can leave an otherwise unused nodal rotation with no physical stiffness.
        # It is not a mechanism: remove only those zero rows with no applied nodal moment.
        active_free = tuple(
            dof for dof in free
            if np.max(np.abs(stiffness[dof, :])) > 1.0e-12 or abs(force[dof]) > 1.0e-12
        )
        if any(np.max(np.abs(stiffness[dof, :])) <= 1.0e-12 and abs(force[dof]) > 1.0e-12 for dof in free):
            return {"ok": False, "error": "A load is applied to a released beam rotation with no stiffness."}
        if active_free:
            reduced = stiffness[np.ix_(active_free, active_free)]
            if np.linalg.matrix_rank(reduced) < len(active_free):
                return {"ok": False, "error": "Matrix singular. Beam may be unstable or have an unconstrained release."}
            try:
                displacements[list(active_free)] = np.linalg.solve(reduced, force[list(active_free)])
            except np.linalg.LinAlgError as exc:
                return {"ok": False, "error": f"Matrix singular. Beam may be unstable.\n{exc}"}
        reactions = stiffness @ displacements - force
        nodes = _empty_nodes(model)
        for index, node in enumerate(nodes):
            node["dy"] = float(displacements[index * 2])
            node["rz"] = float(displacements[index * 2 + 1])
            if index * 2 in fixed:
                node["fy"] = float(reactions[index * 2])
            if index * 2 + 1 in fixed:
                node["mz"] = float(reactions[index * 2 + 1])
        elements: list[dict[str, Any]] = []
        for element_id, (element, _section, _length, local_stiffness, dofs) in states.items():
            actions = local_stiffness @ displacements[list(dofs)] + fixed_ends[element_id]
            elements.append({"id": element.id, "n1": element.n1, "n2": element.n2, "n1_forces": {"axial": 0.0, "shear": float(actions[0]), "moment": float(actions[1])}, "n2_forces": {"axial": 0.0, "shear": float(actions[2]), "moment": float(actions[3])}})
        case_results[load_case] = {"nodes": nodes, "elements": elements}
    combos = {combo.name: _combine(model, case_results, combo) for combo in model.load_combinations}
    envelope = {"nodes": _empty_nodes(model), "elements": _empty_elements(model)}
    for index, result in enumerate(combos.values()):
        if index == 0:
            envelope = {"nodes": [dict(node) for node in result["nodes"]], "elements": [{**element, "n1_forces": dict(element["n1_forces"]), "n2_forces": dict(element["n2_forces"])} for element in result["elements"]]}
        else:
            _apply_envelope(envelope, result)
    return {"ok": True, **envelope, "cases": case_results, "combos": combos, "steps": ["1. Assembling Euler-Bernoulli beam stiffness matrix", f"  Nodes: {len(model.nodes)}, Members: {len(model.elements)}", "2. Processing load cases", "3. Processing combinations and envelope", "  Analysis Complete."]}


def analyze_beam_data(data: Mapping[str, Any] | BeamModel) -> dict[str, Any]:
    """Analyze a horizontal Euler-Bernoulli beam with the shared GO Struct result shape."""
    try:
        model = data if isinstance(data, BeamModel) else BeamModel.from_dict(data)
        result = _analyze(model.frame)
        if result.get("ok"):
            result["analysisType"] = "Beam"
        return result
    except ModelValidationError as exc:
        return {"ok": False, "error": str(exc), "errors": exc.errors}
