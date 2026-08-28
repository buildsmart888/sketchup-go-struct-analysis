"""Planar pin-jointed truss analysis with the shared GO Struct result contract."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from .errors import ModelValidationError
from .frame import resolve_combination_factors
from .schema import FrameModel, LoadCombination


@dataclass(frozen=True)
class TrussModel:
    """Validated truss view over the common project JSON field names."""

    frame: FrameModel

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TrussModel":
        frame = FrameModel.from_dict(raw)
        errors: list[str] = []
        analysis_type = str(frame.project_info.get("analysisType", "Truss"))
        if analysis_type.lower() not in {"truss", "2d truss"}:
            errors.append("projectInfo.analysisType must be 'Truss' for the Truss workspace")
        for element in frame.elements:
            if element.release != "Rigid-Rigid":
                errors.append(f"truss member {element.id} cannot use a frame end release")
        for load in frame.nodal_loads:
            if abs(load.mz) > 1.0e-12:
                errors.append(f"truss nodal load at node {load.node} cannot use Mz; apply Fx or Fy")
        if frame.element_loads:
            errors.append("truss loads must be applied at nodes; member loads are not supported")
        if frame.settings.include_self_weight:
            errors.append("truss self weight is not supported; convert it to nodal loads")
        if errors:
            raise ModelValidationError(errors)
        return cls(frame=frame)

    def to_dict(self) -> dict[str, Any]:
        data = self.frame.to_dict()
        data["projectInfo"]["analysisType"] = "Truss"
        return data


def _empty_nodes(model: FrameModel) -> list[dict[str, float | int]]:
    return [{"id": node.id, "x": node.x, "y": node.y, "dx": 0.0, "dy": 0.0, "rz": 0.0, "fx": 0.0, "fy": 0.0, "mz": 0.0} for node in model.nodes]


def _empty_elements(model: FrameModel) -> list[dict[str, Any]]:
    return [{"id": item.id, "n1": item.n1, "n2": item.n2, "n1_forces": {"axial": 0.0, "shear": 0.0, "moment": 0.0}, "n2_forces": {"axial": 0.0, "shear": 0.0, "moment": 0.0}} for item in model.elements]


def _combine(model: FrameModel, cases: Mapping[str, dict[str, Any]], combo: LoadCombination) -> dict[str, Any]:
    combined = {"nodes": _empty_nodes(model), "elements": _empty_elements(model)}
    for name, factor in resolve_combination_factors(combo).items():
        result = cases.get(name)
        if result is None:
            continue
        for target, source in zip(combined["nodes"], result["nodes"], strict=True):
            for key in ("dx", "dy", "rz", "fx", "fy", "mz"):
                target[key] += float(source[key]) * factor
        for target, source in zip(combined["elements"], result["elements"], strict=True):
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
            if abs(float(source_member[end]["axial"])) > abs(float(target_member[end]["axial"])):
                target_member[end]["axial"] = source_member[end]["axial"]


def _analyze(model: FrameModel) -> dict[str, Any]:
    node_index = {node.id: index for index, node in enumerate(model.nodes)}
    sections = {section.id: section for section in model.sections}
    total_dofs = len(model.nodes) * 2
    stiffness = np.zeros((total_dofs, total_dofs), dtype=float)
    members: dict[int, tuple[float, float, float, float, tuple[int, int, int, int]]] = {}
    for element in model.elements:
        first, second = model.nodes[node_index[element.n1]], model.nodes[node_index[element.n2]]
        dx, dy = second.x - first.x, second.y - first.y
        length = math.hypot(dx, dy)
        if length <= 1.0e-12:
            return {"ok": False, "error": f"Truss member {element.id} has zero length."}
        cosine, sine = dx / length, dy / length
        axial_stiffness = sections[element.sec].e * sections[element.sec].area_m2 / length
        local = axial_stiffness * np.array(
            [[cosine * cosine, cosine * sine, -cosine * cosine, -cosine * sine], [cosine * sine, sine * sine, -cosine * sine, -sine * sine],
             [-cosine * cosine, -cosine * sine, cosine * cosine, cosine * sine], [-cosine * sine, -sine * sine, cosine * sine, sine * sine]],
            dtype=float,
        )
        dofs = (node_index[element.n1] * 2, node_index[element.n1] * 2 + 1, node_index[element.n2] * 2, node_index[element.n2] * 2 + 1)
        stiffness[np.ix_(dofs, dofs)] += local
        members[element.id] = (length, cosine, sine, axial_stiffness, dofs)

    fixed: set[int] = set()
    for index, node in enumerate(model.nodes):
        if node.support in {"Fixed", "Pinned"}:
            fixed.update((index * 2, index * 2 + 1))
        elif node.support == "RollerX":
            fixed.add(index * 2 + 1)
        elif node.support == "RollerY":
            fixed.add(index * 2)
    free = tuple(dof for dof in range(total_dofs) if dof not in fixed)
    if not fixed:
        return {"ok": False, "error": "Truss has no support restraints."}

    cases: dict[str, dict[str, Any]] = {}
    for case_name in model.load_cases:
        force = np.zeros(total_dofs, dtype=float)
        for load in model.nodal_loads:
            if load.lcase == case_name:
                offset = node_index[load.node] * 2
                force[offset : offset + 2] += (load.fx, load.fy)
        displacements = np.zeros(total_dofs, dtype=float)
        if free:
            reduced = stiffness[np.ix_(free, free)]
            if np.linalg.matrix_rank(reduced) < len(free):
                return {"ok": False, "error": "Matrix singular. Truss may be unstable or missing a restraint."}
            try:
                displacements[list(free)] = np.linalg.solve(reduced, force[list(free)])
            except np.linalg.LinAlgError as exc:
                return {"ok": False, "error": f"Matrix singular. Truss may be unstable.\n{exc}"}
        reactions = stiffness @ displacements - force
        nodes = _empty_nodes(model)
        for index, node in enumerate(nodes):
            node["dx"] = float(displacements[index * 2])
            node["dy"] = float(displacements[index * 2 + 1])
            if index * 2 in fixed:
                node["fx"] = float(reactions[index * 2])
            if index * 2 + 1 in fixed:
                node["fy"] = float(reactions[index * 2 + 1])
        elements: list[dict[str, Any]] = []
        for element in model.elements:
            length, cosine, sine, axial_stiffness, dofs = members[element.id]
            extension = cosine * (displacements[dofs[2]] - displacements[dofs[0]]) + sine * (displacements[dofs[3]] - displacements[dofs[1]])
            tension = axial_stiffness * extension
            elements.append({"id": element.id, "n1": element.n1, "n2": element.n2, "n1_forces": {"axial": float(tension), "shear": 0.0, "moment": 0.0}, "n2_forces": {"axial": float(-tension), "shear": 0.0, "moment": 0.0}})
        cases[case_name] = {"nodes": nodes, "elements": elements}
    combos = {combo.name: _combine(model, cases, combo) for combo in model.load_combinations}
    envelope = {"nodes": _empty_nodes(model), "elements": _empty_elements(model)}
    for index, result in enumerate(combos.values()):
        if index == 0:
            envelope = {"nodes": [dict(node) for node in result["nodes"]], "elements": [{**item, "n1_forces": dict(item["n1_forces"]), "n2_forces": dict(item["n2_forces"])} for item in result["elements"]]}
        else:
            _apply_envelope(envelope, result)
    return {"ok": True, "analysisType": "Truss", **envelope, "cases": cases, "combos": combos, "steps": ["1. Assembling planar truss stiffness matrix", f"  Nodes: {len(model.nodes)}, Members: {len(model.elements)}", "2. Processing nodal load cases", "3. Processing combinations and envelope", "  Analysis Complete."]}


def analyze_truss_data(data: Mapping[str, Any] | TrussModel) -> dict[str, Any]:
    """Analyze a pin-jointed 2D truss with tension-positive axial member forces."""
    try:
        model = data if isinstance(data, TrussModel) else TrussModel.from_dict(data)
        return _analyze(model.frame)
    except ModelValidationError as exc:
        return {"ok": False, "error": str(exc), "errors": exc.errors}
