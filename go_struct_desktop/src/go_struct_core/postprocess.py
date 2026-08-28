"""Reusable post-processing for 2D frame member diagrams and diagnostics."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Mapping

from .frame import resolve_combination_factors
from .schema import FrameElement, FrameModel


def build_frame_postprocess(
    data: Mapping[str, Any] | FrameModel,
    analysis: Mapping[str, Any],
    sample_count: int = 41,
) -> dict[str, Any]:
    """Build member-force diagrams, FE deformation curves, and model diagnostics.

    Diagram convention follows the legacy GOFrame visualisation: axial force is tension-positive;
    start/end values use the internal action direction shown in the diagram, not raw nodal action
    signs. ``T`` torsion is intentionally absent because this is a planar 2D frame solver.
    """

    model = data if isinstance(data, FrameModel) else FrameModel.from_dict(data)
    if not analysis.get("ok"):
        return {"ok": False, "diagnostics": _model_diagnostics(model, analysis)}
    if sample_count < 2:
        raise ValueError("sample_count must be at least 2")

    factors_by_combo = {combo.name: resolve_combination_factors(combo) for combo in model.load_combinations}
    cases = {
        name: _selection_postprocess(model, result, {name: 1.0}, sample_count)
        for name, result in analysis.get("cases", {}).items()
    }
    combos = {
        name: _selection_postprocess(model, result, factors_by_combo.get(name, {}), sample_count)
        for name, result in analysis.get("combos", {}).items()
    }
    envelope = _envelope_postprocess(combos, model, sample_count)
    return {
        "ok": True,
        "cases": cases,
        "combos": combos,
        "envelope": envelope,
        "diagnostics": _model_diagnostics(model, analysis),
        "conventions": {
            "axial": "Tension positive",
            "shear": "Local member shear; positive values follow the displayed member axis",
            "moment": "Local bending moment; values use the legacy GOFrame diagram sign",
            "deflection": "Local transverse finite-element interpolation, in mm",
            "torsion": "Not available for the planar 2D frame solver",
        },
    }


def _selection_postprocess(
    model: FrameModel,
    result: Mapping[str, Any],
    load_factors: Mapping[str, float],
    sample_count: int,
) -> dict[str, Any]:
    result_by_element = {member["id"]: member for member in result.get("elements", [])}
    result_by_node = {node["id"]: node for node in result.get("nodes", [])}
    nodes = {node.id: node for node in model.nodes}
    members: list[dict[str, Any]] = []
    for element in model.elements:
        member_result = result_by_element.get(element.id)
        if member_result is None:
            continue
        members.append(
            _member_diagram(
                element,
                nodes[element.n1],
                nodes[element.n2],
                result_by_node[element.n1],
                result_by_node[element.n2],
                member_result,
                _distributed_loads(model, element, load_factors),
                _point_loads(model, element, load_factors),
                sample_count,
            )
        )
    return {"members": members, "summary": _selection_summary(members)}


def _member_diagram(
    element: FrameElement,
    node_i,
    node_j,
    result_i: Mapping[str, Any],
    result_j: Mapping[str, Any],
    member_result: Mapping[str, Any],
    loads: list[dict[str, float | str]],
    point_loads: list[dict[str, float | str]],
    sample_count: int,
) -> dict[str, Any]:
    dx = node_j.x - node_i.x
    dy = node_j.y - node_i.y
    length = math.hypot(dx, dy)
    angle = math.atan2(dy, dx)
    cosine, sine = math.cos(angle), math.sin(angle)
    n1, n2 = member_result["n1_forces"], member_result["n2_forces"]
    start_n, end_n = float(n1["axial"]), -float(n2["axial"])
    start_v, end_v = float(n1["shear"]), -float(n2["shear"])
    start_m, end_m = -float(n1["moment"]), float(n2["moment"])
    qx1 = sum(float(load["qx1"]) for load in loads)
    qx2 = sum(float(load["qx2"]) for load in loads)
    qy1 = sum(float(load["qy1"]) for load in loads)
    qy2 = sum(float(load["qy2"]) for load in loads)
    u_i, v_i = _to_local_displacement(result_i, cosine, sine)
    u_j, v_j = _to_local_displacement(result_j, cosine, sine)
    theta_i, theta_j = float(result_i["rz"]), float(result_j["rz"])
    positions = {length * index / (sample_count - 1) for index in range(sample_count)}
    positions.update(float(load["x_m"]) for load in point_loads)
    points: list[dict[str, float]] = []
    for x in sorted(positions):
        ratio = x / length
        axial = start_n + qx1 * x + (qx2 - qx1) * x**2 / (2.0 * length)
        shear = start_v + qy1 * x + (qy2 - qy1) * x**2 / (2.0 * length)
        moment = start_m + start_v * x + qy1 * x**2 / 2.0 + (qy2 - qy1) * x**3 / (6.0 * length)
        for load in point_loads:
            if x + 1.0e-10 < float(load["x_m"]):
                continue
            load_x = float(load["x_m"])
            axial += float(load["px_kg"])
            shear += float(load["py_kg"])
            moment += float(load["py_kg"]) * (x - load_x) - float(load["mz_kg_m"])
        local_u = (1.0 - ratio) * u_i + ratio * u_j
        local_v = _hermite_transverse_displacement(ratio, length, v_i, theta_i, v_j, theta_j)
        global_dx = cosine * local_u - sine * local_v
        global_dy = sine * local_u + cosine * local_v
        points.append(
            {
                "x_m": x,
                "n_kg": axial,
                "v_kg": shear,
                "m_kg_m": moment,
                "u_mm": local_u * 1000.0,
                "v_mm": local_v * 1000.0,
                "x_deformed_m": node_i.x + cosine * x + global_dx,
                "y_deformed_m": node_i.y + sine * x + global_dy,
            }
        )
    return {
        "id": element.id,
        "n1": element.n1,
        "n2": element.n2,
        "length_m": length,
        "angle_rad": angle,
        "release": element.release,
        "end_actions": {"n_i": start_n, "v_i": start_v, "m_i": start_m, "n_j": end_n, "v_j": end_v, "m_j": end_m},
        "distributed_load": {"qx1_kg_m": qx1, "qx2_kg_m": qx2, "qy1_kg_m": qy1, "qy2_kg_m": qy2},
        "point_loads": point_loads,
        "points": points,
        "extrema": {
            "n_kg": _extrema(points, "n_kg"),
            "v_kg": _extrema(points, "v_kg"),
            "m_kg_m": _extrema(points, "m_kg_m"),
            "v_mm": _extrema(points, "v_mm"),
        },
        "endpoint_residual": {
            "n_kg": axial - end_n,
            "v_kg": shear - end_v,
            "m_kg_m": moment - end_m,
        },
    }


def _distributed_loads(model: FrameModel, element: FrameElement, factors: Mapping[str, float]) -> list[dict[str, float | str]]:
    node_i = next(node for node in model.nodes if node.id == element.n1)
    node_j = next(node for node in model.nodes if node.id == element.n2)
    angle = math.atan2(node_j.y - node_i.y, node_j.x - node_i.x)
    section = next(section for section in model.sections if section.id == element.sec)
    loads: list[dict[str, float | str]] = []
    dl_factor = float(factors.get("DL", 0.0))
    if model.settings.include_self_weight and dl_factor and section.density > 0.0:
        weight = section.area_m2 * section.density * dl_factor
        loads.append({"case": "DL", "qx1": -weight * math.sin(angle), "qx2": -weight * math.sin(angle), "qy1": -weight * math.cos(angle), "qy2": -weight * math.cos(angle)})
    for load in model.element_loads:
        factor = float(factors.get(load.lcase, 0.0))
        if load.type != "Distributed" or load.elem != element.id or not factor:
            continue
        if load.direction == "Local X":
            loads.append({"case": load.lcase, "qx1": load.w1 * factor, "qx2": load.w2 * factor, "qy1": 0.0, "qy2": 0.0})
        elif load.direction == "Local Y":
            loads.append({"case": load.lcase, "qx1": 0.0, "qx2": 0.0, "qy1": load.w1 * factor, "qy2": load.w2 * factor})
        elif load.direction == "Global X":
            loads.append(
                {
                    "case": load.lcase,
                    "qx1": load.w1 * factor * math.cos(angle),
                    "qx2": load.w2 * factor * math.cos(angle),
                    "qy1": -load.w1 * factor * math.sin(angle),
                    "qy2": -load.w2 * factor * math.sin(angle),
                }
            )
        else:
            loads.append(
                {
                    "case": load.lcase,
                    "qx1": load.w1 * factor * math.sin(angle),
                    "qx2": load.w2 * factor * math.sin(angle),
                    "qy1": load.w1 * factor * math.cos(angle),
                    "qy2": load.w2 * factor * math.cos(angle),
                }
            )
    return loads


def _point_loads(model: FrameModel, element: FrameElement, factors: Mapping[str, float]) -> list[dict[str, float | str]]:
    node_i = next(node for node in model.nodes if node.id == element.n1)
    node_j = next(node for node in model.nodes if node.id == element.n2)
    angle = math.atan2(node_j.y - node_i.y, node_j.x - node_i.x)
    loads: list[dict[str, float | str]] = []
    for load in model.element_loads:
        factor = float(factors.get(load.lcase, 0.0))
        if load.type not in {"Point Force", "Point Moment"} or load.elem != element.id:
            continue
        px = py = mz = 0.0
        if load.type == "Point Force":
            if load.direction == "Local X":
                px = load.p * factor
            elif load.direction == "Local Y":
                py = load.p * factor
            elif load.direction == "Global X":
                px = load.p * factor * math.cos(angle)
                py = -load.p * factor * math.sin(angle)
            else:
                px = load.p * factor * math.sin(angle)
                py = load.p * factor * math.cos(angle)
        else:
            mz = load.m * factor
        loads.append({"case": load.lcase, "type": load.type, "x_m": load.x_m, "px_kg": px, "py_kg": py, "mz_kg_m": mz})
    return loads


def _to_local_displacement(result: Mapping[str, Any], cosine: float, sine: float) -> tuple[float, float]:
    dx, dy = float(result["dx"]), float(result["dy"])
    return cosine * dx + sine * dy, -sine * dx + cosine * dy


def _hermite_transverse_displacement(ratio: float, length: float, v_i: float, theta_i: float, v_j: float, theta_j: float) -> float:
    return (
        (1.0 - 3.0 * ratio**2 + 2.0 * ratio**3) * v_i
        + length * (ratio - 2.0 * ratio**2 + ratio**3) * theta_i
        + (3.0 * ratio**2 - 2.0 * ratio**3) * v_j
        + length * (-ratio**2 + ratio**3) * theta_j
    )


def _extrema(points: list[Mapping[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    minimum = min(points, key=lambda point: point[field])
    maximum = max(points, key=lambda point: point[field])
    absolute = max(points, key=lambda point: abs(point[field]))
    def value_at(point: Mapping[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {"value": point[field], "x_m": point["x_m"]}
        combo = point.get(f"{field}_combo")
        if combo:
            result["combo"] = combo
        return result

    return {"min": value_at(minimum), "max": value_at(maximum), "abs": value_at(absolute)}


def _selection_summary(members: list[Mapping[str, Any]]) -> dict[str, Any]:
    fields = ("n_kg", "v_kg", "m_kg_m", "v_mm")
    summary: dict[str, Any] = {}
    for field in fields:
        candidates = [member["extrema"][field]["abs"] | {"member_id": member["id"]} for member in members]
        summary[field] = max(candidates, key=lambda item: abs(item["value"])) if candidates else {"value": 0.0, "x_m": 0.0, "member_id": None}
    return summary


def _envelope_postprocess(combos: Mapping[str, Mapping[str, Any]], model: FrameModel, sample_count: int) -> dict[str, Any]:
    if not combos:
        return {"members": [], "summary": {}}
    combo_members = {name: {member["id"]: member for member in result["members"]} for name, result in combos.items()}
    members: list[dict[str, Any]] = []
    for element in model.elements:
        candidates = [(name, members_by_id[element.id]) for name, members_by_id in combo_members.items() if element.id in members_by_id]
        if not candidates:
            continue
        base = candidates[0][1]
        points: list[dict[str, Any]] = []
        for index, base_point in enumerate(base["points"]):
            point: dict[str, Any] = {"x_m": base_point["x_m"]}
            for field in ("n_kg", "v_kg", "m_kg_m", "u_mm", "v_mm"):
                governing_name, governing_member = max(candidates, key=lambda item: abs(item[1]["points"][index][field]))
                point[field] = governing_member["points"][index][field]
                point[f"{field}_combo"] = governing_name
            governing_name, governing_member = max(candidates, key=lambda item: math.hypot(item[1]["points"][index]["u_mm"], item[1]["points"][index]["v_mm"]))
            point["x_deformed_m"] = governing_member["points"][index]["x_deformed_m"]
            point["y_deformed_m"] = governing_member["points"][index]["y_deformed_m"]
            point["deformation_combo"] = governing_name
            points.append(point)
        members.append(
            {
                **{key: base[key] for key in ("id", "n1", "n2", "length_m", "angle_rad", "release")},
                "points": points,
                "extrema": {field: _extrema(points, field) for field in ("n_kg", "v_kg", "m_kg_m", "v_mm")},
                "end_actions": {},
                "distributed_load": {},
                "point_loads": [],
                "endpoint_residual": {},
            }
        )
    return {"members": members, "summary": _selection_summary(members)}


def _model_diagnostics(model: FrameModel, analysis: Mapping[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    incidences: dict[int, int] = defaultdict(int)
    for element in model.elements:
        incidences[element.n1] += 1
        incidences[element.n2] += 1
    for node in model.nodes:
        if incidences[node.id] == 0:
            items.append({"severity": "warning", "message": f"Node {node.id} is not connected to a member.", "nodes": [node.id]})
    coordinates: dict[tuple[float, float], list[int]] = defaultdict(list)
    for node in model.nodes:
        coordinates[(node.x, node.y)].append(node.id)
    for coordinate, node_ids in coordinates.items():
        if len(node_ids) > 1:
            items.append({"severity": "warning", "message": f"Nodes {', '.join(str(node_id) for node_id in node_ids)} share coordinates ({coordinate[0]:g}, {coordinate[1]:g}).", "nodes": node_ids})
    member_pairs: dict[tuple[int, int], list[int]] = defaultdict(list)
    for element in model.elements:
        member_pairs[tuple(sorted((element.n1, element.n2)))].append(element.id)
    for pair, member_ids in member_pairs.items():
        if len(member_ids) > 1:
            items.append({"severity": "warning", "message": f"Members {', '.join(str(member_id) for member_id in member_ids)} duplicate the N{pair[0]}-N{pair[1]} connection.", "members": member_ids})
    node_by_id = {node.id: node for node in model.nodes}
    for index, first in enumerate(model.elements):
        for second in model.elements[index + 1 :]:
            if {first.n1, first.n2} & {second.n1, second.n2}:
                continue
            if _segments_cross(
                (node_by_id[first.n1].x, node_by_id[first.n1].y),
                (node_by_id[first.n2].x, node_by_id[first.n2].y),
                (node_by_id[second.n1].x, node_by_id[second.n1].y),
                (node_by_id[second.n2].x, node_by_id[second.n2].y),
            ):
                items.append({"severity": "warning", "message": f"Members {first.id} and {second.id} intersect without a shared node. Split/connect them before analysis.", "members": [first.id, second.id]})
    restraints = sum(3 if node.support == "Fixed" else 2 if node.support == "Pinned" else 1 if node.support in {"RollerX", "RollerY"} else 0 for node in model.nodes)
    if restraints < 3:
        items.append({"severity": "warning", "message": "Fewer than three translational restraints are defined; the frame may be unstable.", "nodes": [node.id for node in model.nodes if node.support == "Free"]})
    if not analysis.get("ok"):
        items.append({"severity": "error", "message": str(analysis.get("error", "Analysis did not complete."))})
        items.append({"severity": "warning", "message": "Mechanism check: review free translations/rotations, member releases, and support directions near the unstable region."})
    elif not items:
        items.append({"severity": "info", "message": "Topology and restraint screening completed."})
    equilibrium = [_equilibrium_for_case(model, name, result) for name, result in analysis.get("cases", {}).items()]
    return {"items": items, "restraint_count": restraints, "equilibrium": equilibrium}


def _segments_cross(
    first_start: tuple[float, float], first_end: tuple[float, float], second_start: tuple[float, float], second_end: tuple[float, float]
) -> bool:
    def cross(origin: tuple[float, float], first: tuple[float, float], second: tuple[float, float]) -> float:
        return (first[0] - origin[0]) * (second[1] - origin[1]) - (first[1] - origin[1]) * (second[0] - origin[0])

    first_a = cross(first_start, first_end, second_start)
    first_b = cross(first_start, first_end, second_end)
    second_a = cross(second_start, second_end, first_start)
    second_b = cross(second_start, second_end, first_end)
    return first_a * first_b < 0.0 and second_a * second_b < 0.0


def _equilibrium_for_case(model: FrameModel, case_name: str, result: Mapping[str, Any]) -> dict[str, Any]:
    force_x = force_y = moment = 0.0
    nodes = {node.id: node for node in model.nodes}
    for load in model.nodal_loads:
        if load.lcase != case_name:
            continue
        node = nodes[load.node]
        force_x += load.fx
        force_y += load.fy
        moment += load.mz + node.x * load.fy - node.y * load.fx
    for element in model.elements:
        for load in _distributed_loads(model, element, {case_name: 1.0}):
            node_i = nodes[element.n1]
            node_j = nodes[element.n2]
            angle = math.atan2(node_j.y - node_i.y, node_j.x - node_i.x)
            length = math.hypot(node_j.x - node_i.x, node_j.y - node_i.y)
            qx1, qx2 = float(load["qx1"]), float(load["qx2"])
            qy1, qy2 = float(load["qy1"]), float(load["qy2"])
            local_x_total = length * (qx1 + qx2) / 2.0
            local_y_total = length * (qy1 + qy2) / 2.0
            local_x_first = length**2 * (qx1 + 2.0 * qx2) / 6.0
            local_y_first = length**2 * (qy1 + 2.0 * qy2) / 6.0
            cosine, sine = math.cos(angle), math.sin(angle)
            global_x_total = cosine * local_x_total - sine * local_y_total
            global_y_total = sine * local_x_total + cosine * local_y_total
            global_x_first = cosine * local_x_first - sine * local_y_first
            global_y_first = sine * local_x_first + cosine * local_y_first
            force_x += global_x_total
            force_y += global_y_total
            moment += node_i.x * global_y_total - node_i.y * global_x_total + cosine * global_y_first - sine * global_x_first
        for load in _point_loads(model, element, {case_name: 1.0}):
            node_i = nodes[element.n1]
            node_j = nodes[element.n2]
            angle = math.atan2(node_j.y - node_i.y, node_j.x - node_i.x)
            cosine, sine = math.cos(angle), math.sin(angle)
            px, py, mz = float(load["px_kg"]), float(load["py_kg"]), float(load["mz_kg_m"])
            global_x = cosine * px - sine * py
            global_y = sine * px + cosine * py
            x = node_i.x + cosine * float(load["x_m"])
            y = node_i.y + sine * float(load["x_m"])
            force_x += global_x
            force_y += global_y
            moment += mz + x * global_y - y * global_x
    reaction_x = sum(float(node["fx"]) for node in result.get("nodes", []))
    reaction_y = sum(float(node["fy"]) for node in result.get("nodes", []))
    reaction_moment = sum(float(node["mz"]) + nodes[node["id"]].x * float(node["fy"]) - nodes[node["id"]].y * float(node["fx"]) for node in result.get("nodes", []))
    residual = {"fx_kg": reaction_x + force_x, "fy_kg": reaction_y + force_y, "mz_kg_m": reaction_moment + moment}
    scale = max(1.0, abs(force_x), abs(force_y), abs(moment))
    return {
        "load_case": case_name,
        "external": {"fx_kg": force_x, "fy_kg": force_y, "mz_kg_m": moment},
        "reactions": {"fx_kg": reaction_x, "fy_kg": reaction_y, "mz_kg_m": reaction_moment},
        "residual": residual,
        "ok": max(abs(value) for value in residual.values()) <= scale * 1.0e-7,
    }
