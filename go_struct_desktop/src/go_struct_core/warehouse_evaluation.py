"""Preliminary checks and auditable cost estimates for Warehouse3D.

These checks are explicit engineering screens, not a national design code.
Every result includes its assumptions so callers cannot confuse it with a
construction-ready connection or foundation design.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt
from typing import Any, Mapping

from .warehouse import GeneratedWarehouse


@dataclass(frozen=True)
class PreliminaryLimits:
    max_displacement_ratio: float = 1.0 / 240.0
    max_drift_ratio: float = 1.0 / 200.0
    max_slenderness: float = 200.0
    effective_length_factor: float = 1.0

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "PreliminaryLimits":
        raw = raw or {}
        return cls(
            max_displacement_ratio=float(raw.get("max_displacement_ratio", 1.0 / 240.0)),
            max_drift_ratio=float(raw.get("max_drift_ratio", 1.0 / 200.0)),
            max_slenderness=float(raw.get("max_slenderness", 200.0)),
            effective_length_factor=float(raw.get("effective_length_factor", 1.0)),
        )


@dataclass(frozen=True)
class CostCatalog:
    steel_thb_per_kg: float = 42.0
    fabrication_thb_per_kg: float = 18.0
    erection_thb_per_kg: float = 10.0
    coating_thb_per_kg: float = 6.0
    waste_fraction: float = 0.05
    connection_thb_each: float = 4_000.0
    foundation_thb_each: float = 15_000.0
    reaction_allowance_thb_per_kn: float = 12.0

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "CostCatalog":
        raw = raw or {}
        return cls(**{key: float(raw.get(key, value)) for key, value in cls().__dict__.items()})

    def to_dict(self) -> dict[str, float]:
        return dict(self.__dict__)


def preliminary_checks(model: GeneratedWarehouse, analysis: Mapping[str, Any], limits: PreliminaryLimits | Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Screen member demand, buckling, slenderness and global movement."""
    if not analysis.get("ok"):
        return {"feasible": False, "utilization": float("inf"), "reasons": [str(analysis.get("error", "analysis failed"))], "members": [], "assumptions": _assumptions(PreliminaryLimits.from_dict(None))}
    used_limits = limits if isinstance(limits, PreliminaryLimits) else PreliminaryLimits.from_dict(limits)
    sections = {item.id: item for item in model.project.sections}
    member_by_id = {item.id: item for item in model.members}
    node_by_id = {item.id: item for item in model.nodes}
    result_sets: dict[str, Mapping[str, Any]] = dict(analysis.get("combos", {}))
    if not result_sets:
        result_sets = {"Envelope": analysis.get("envelope", {})}
    governing: dict[int, dict[str, Any]] = {}
    for combo_name, result in result_sets.items():
        for item in result.get("members", []):
            member = member_by_id[int(item["id"])]
            section = sections[member.section]
            length = float(item["length_m"])
            r_min = sqrt(min(section.iy_m4, section.iz_m4) / section.area_m2)
            slenderness = used_limits.effective_length_factor * length / r_min
            axial_kn = float(item["axial_tension_kn"])
            tension_capacity_kn = section.fy_pa * section.area_m2 / 1000.0
            euler_kn = pi**2 * section.e_pa * min(section.iy_m4, section.iz_m4) / (used_limits.effective_length_factor * length) ** 2 / 1000.0
            compression_capacity_kn = min(tension_capacity_kn, euler_kn)
            local = [abs(float(value)) for value in item["local_end_forces_kn"]]
            my_kn_m = max(local[4], local[10])
            mz_kn_m = max(local[5], local[11])
            my_capacity_kn_m = section.fy_pa * section.zy_m3 / 1000.0
            mz_capacity_kn_m = section.fy_pa * section.zz_m3 / 1000.0
            axial_capacity = tension_capacity_kn if axial_kn >= 0 else compression_capacity_kn
            axial_utilization = abs(axial_kn) / axial_capacity if axial_capacity else float("inf")
            bending_utilization = my_kn_m / my_capacity_kn_m + mz_kn_m / mz_capacity_kn_m
            utilization = axial_utilization + bending_utilization if member.kind == "frame" else axial_utilization
            utilization = max(utilization, slenderness / used_limits.max_slenderness)
            candidate = {
                "id": member.id,
                "group": member.group,
                "combo": combo_name,
                "axial_tension_kn": axial_kn,
                "tension_capacity_kn": tension_capacity_kn,
                "compression_capacity_kn": compression_capacity_kn,
                "slenderness": slenderness,
                "axial_utilization": axial_utilization,
                "bending_utilization": bending_utilization if member.kind == "frame" else 0.0,
                "slenderness_utilization": slenderness / used_limits.max_slenderness,
                "check_expression": "|N|/Nt + My/My,Rd + Mz/Mz,Rd" if member.kind == "frame" else "|N|/Nc,t",
                "utilization": utilization,
            }
            if member.id not in governing or utilization > governing[member.id]["utilization"]:
                governing[member.id] = candidate
    max_displacement = 0.0
    max_drift = 0.0
    for result in result_sets.values():
        for node in result.get("nodes", []):
            displacement = node["displacements"]
            max_displacement = max(max_displacement, sqrt(sum(float(component) ** 2 for component in displacement[:3])))
            reference = node_by_id[int(node["id"])]
            if reference.z_m > 1.0e-9:
                max_drift = max(max_drift, sqrt(float(displacement[0]) ** 2 + float(displacement[1]) ** 2) / reference.z_m)
    span = max(model.project.geometry.width_m, model.project.geometry.bay_spacing_m)
    allowable_displacement = span * used_limits.max_displacement_ratio
    displacement_utilization = max_displacement / allowable_displacement if allowable_displacement else float("inf")
    drift_utilization = max_drift / used_limits.max_drift_ratio if used_limits.max_drift_ratio else float("inf")
    clearance_utilization = model.project.geometry.min_clear_height_m / model.project.geometry.eave_height_m
    member_results = sorted(governing.values(), key=lambda value: value["utilization"], reverse=True)
    utilization = max([displacement_utilization, drift_utilization, clearance_utilization, *(item["utilization"] for item in member_results)] or [0.0])
    reasons = []
    if clearance_utilization > 1.0:
        reasons.append("eave height is below the configured minimum clear height")
    if displacement_utilization > 1.0:
        reasons.append("maximum translation exceeds the configured preliminary limit")
    if drift_utilization > 1.0:
        reasons.append("maximum drift exceeds the configured preliminary limit")
    if any(item["utilization"] > 1.0 for item in member_results):
        reasons.append("at least one member exceeds a preliminary stress, buckling, or slenderness screen")
    return {
        "feasible": utilization <= 1.0,
        "utilization": utilization,
        "max_displacement_m": max_displacement,
        "max_drift_ratio": max_drift,
        "members": member_results,
        "reasons": reasons,
        "assumptions": _assumptions(used_limits),
    }


def warehouse_equilibrium(model: GeneratedWarehouse, analysis: Mapping[str, Any]) -> dict[str, Any]:
    """Audit force and moment balance for each solved case and combination.

    Values retain the warehouse SI presentation units: kN and kN-m.  The
    self-weight vector is reconstructed exactly as the native backend applies
    it, so the audit remains meaningful when it is included in DL.
    """
    node_by_id = {node.id: node for node in model.nodes}
    case_actions: dict[str, dict[int, list[float]]] = {}
    for load in model.loads:
        values = case_actions.setdefault(load.case, {}).setdefault(load.node, [0.0] * 6)
        for index, value in enumerate((load.fx_kn, load.fy_kn, load.fz_kn, load.mx_kn_m, load.my_kn_m, load.mz_kn_m)):
            values[index] += value
    if model.project.loads.include_self_weight:
        sections = {section.id: section for section in model.project.sections}
        for member in model.members:
            first, second = node_by_id[member.i], node_by_id[member.j]
            length = sqrt((first.x_m - second.x_m) ** 2 + (first.y_m - second.y_m) ** 2 + (first.z_m - second.z_m) ** 2)
            weight_kn = sections[member.section].density_kg_m3 * sections[member.section].area_m2 * length * 9.80665 / 1000.0
            for node_id in (member.i, member.j):
                case_actions.setdefault("DL", {}).setdefault(node_id, [0.0] * 6)[2] -= weight_kn / 2.0

    factors_by_name = {name: {name: 1.0} for name in analysis.get("cases", {})}
    factors_by_name.update({combo.name: dict(combo.factors) for combo in model.project.combinations})
    result_sets = {**analysis.get("cases", {}), **analysis.get("combos", {})}
    rows = []
    for name, result in result_sets.items():
        factors = factors_by_name.get(name, {name: 1.0})
        applied = _resultant_from_actions(node_by_id, case_actions, factors)
        reactions = _resultant_from_reactions(node_by_id, result.get("nodes", []))
        residual = [applied[index] + reactions[index] for index in range(6)]
        rows.append({"name": name, "applied": applied, "reactions": reactions, "residual": residual, "max_residual": max(abs(value) for value in residual), "balanced": max(abs(value) for value in residual) < 1.0e-5})
    distribution = {case: {"nodes": len(nodes), "force_kn": [sum(values[index] for values in nodes.values()) for index in range(3)]} for case, nodes in case_actions.items()}
    return {"sets": rows, "load_distribution": distribution, "assumptions": ["Force and moment balance is reported about the global origin.", "Self weight is included in DL when enabled and distributed equally to each member end."]}


def _resultant_from_actions(node_by_id: Mapping[int, Any], case_actions: Mapping[str, Mapping[int, list[float]]], factors: Mapping[str, float]) -> list[float]:
    resultant = [0.0] * 6
    for case, factor in factors.items():
        for node_id, values in case_actions.get(case, {}).items():
            node = node_by_id[node_id]
            force = [factor * value for value in values[:3]]
            resultant[0] += force[0]; resultant[1] += force[1]; resultant[2] += force[2]
            resultant[3] += factor * values[3] + node.y_m * force[2] - node.z_m * force[1]
            resultant[4] += factor * values[4] + node.z_m * force[0] - node.x_m * force[2]
            resultant[5] += factor * values[5] + node.x_m * force[1] - node.y_m * force[0]
    return resultant


def _resultant_from_reactions(node_by_id: Mapping[int, Any], nodes: list[Mapping[str, Any]]) -> list[float]:
    resultant = [0.0] * 6
    for item in nodes:
        node = node_by_id[int(item["id"])]
        values = [float(value) for value in item.get("reactions_kn", [0.0] * 6)]
        resultant[0] += values[0]; resultant[1] += values[1]; resultant[2] += values[2]
        resultant[3] += values[3] + node.y_m * values[2] - node.z_m * values[1]
        resultant[4] += values[4] + node.z_m * values[0] - node.x_m * values[2]
        resultant[5] += values[5] + node.x_m * values[1] - node.y_m * values[0]
    return resultant


def preliminary_cost(model: GeneratedWarehouse, analysis: Mapping[str, Any] | None = None, catalog: CostCatalog | Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return an auditable Thai-baht estimate including conceptual allowances."""
    used_catalog = catalog if isinstance(catalog, CostCatalog) else CostCatalog.from_dict(catalog)
    sections = {item.id: item for item in model.project.sections}
    node_by_id = {item.id: item for item in model.nodes}
    mass_by_group: dict[str, float] = {}
    total_mass = 0.0
    for member in model.members:
        first, second = node_by_id[member.i], node_by_id[member.j]
        length = sqrt((first.x_m - second.x_m) ** 2 + (first.y_m - second.y_m) ** 2 + (first.z_m - second.z_m) ** 2)
        mass = sections[member.section].density_kg_m3 * sections[member.section].area_m2 * length
        total_mass += mass
        mass_by_group[member.group] = mass_by_group.get(member.group, 0.0) + mass
    purchased_mass = total_mass * (1.0 + used_catalog.waste_fraction)
    reaction_sum = 0.0
    if analysis and analysis.get("ok"):
        envelope = analysis.get("envelope", {})
        reaction_sum = sum(abs(float(value)) for node in envelope.get("nodes", []) for value in node.get("reactions_kn", [])[:3])
    connection_count = int(model.conceptual_items.get("connection_nodes", 0))
    foundation_count = int(model.conceptual_items.get("foundation_positions", 0))
    breakdown = {
        "steel_material": purchased_mass * used_catalog.steel_thb_per_kg,
        "fabrication": purchased_mass * used_catalog.fabrication_thb_per_kg,
        "erection": purchased_mass * used_catalog.erection_thb_per_kg,
        "coating": purchased_mass * used_catalog.coating_thb_per_kg,
        "conceptual_connections": connection_count * used_catalog.connection_thb_each,
        "conceptual_foundations": foundation_count * used_catalog.foundation_thb_each + reaction_sum * used_catalog.reaction_allowance_thb_per_kn,
    }
    return {
        "currency": "THB",
        "steel_mass_kg": total_mass,
        "purchased_steel_mass_kg": purchased_mass,
        "mass_by_group_kg": mass_by_group,
        "breakdown_thb": breakdown,
        "total_thb": sum(breakdown.values()),
        "catalog": used_catalog.to_dict(),
        "assumptions": [
            "Connection, base plate, anchor, and foundation entries are conceptual allowances only.",
            "This estimate is not a contractor quotation and does not include tax, escalation, or site-specific soil works.",
        ],
    }


def _assumptions(limits: PreliminaryLimits) -> list[str]:
    return [
        "First-order linear-elastic analysis only; no P-Delta, seismic detailing, fatigue, fire, or nonlinear connection behaviour.",
        "Yield/Euler/slenderness screens are preliminary engineering checks, not a national design-code verification.",
        f"K={limits.effective_length_factor:g}, member slenderness limit={limits.max_slenderness:g}, displacement limit=L/{1.0 / limits.max_displacement_ratio:g}.",
    ]
