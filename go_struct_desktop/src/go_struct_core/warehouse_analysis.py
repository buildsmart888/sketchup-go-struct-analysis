"""Linear-elastic 3D space-frame analysis for generated warehouse models.

The native backend is deliberately small, deterministic, and independently
testable.  ``OpenSeesPyBackend`` is an optional integration point; deployments
may select it after its binary dependency has been qualified for their Python
and operating-system combination.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Any, Mapping, Protocol

import numpy as np

from .errors import ModelValidationError
from .warehouse import GeneratedWarehouse, Member3D, Section3D, WarehouseProject, generate_warehouse


class AnalysisBackend3D(Protocol):
    name: str

    def analyze(self, model: GeneratedWarehouse) -> dict[str, Any]: ...


@dataclass(frozen=True)
class _ElementState:
    member: Member3D
    section: Section3D
    dofs: tuple[int, ...]
    length_m: float
    transform: np.ndarray
    local_stiffness: np.ndarray


def _local_axes(first: np.ndarray, second: np.ndarray) -> tuple[float, np.ndarray]:
    x_axis = second - first
    length = float(np.linalg.norm(x_axis))
    if length <= 1.0e-9:
        raise ValueError("member has zero length")
    x_axis /= length
    reference = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(x_axis, reference))) > 0.95:
        reference = np.array([0.0, 1.0, 0.0])
    y_axis = np.cross(reference, x_axis)
    y_axis /= np.linalg.norm(y_axis)
    z_axis = np.cross(x_axis, y_axis)
    return length, np.vstack((x_axis, y_axis, z_axis))


def _block_transform(rotation: np.ndarray) -> np.ndarray:
    result = np.zeros((12, 12), dtype=float)
    for offset in (0, 3, 6, 9):
        result[offset : offset + 3, offset : offset + 3] = rotation
    return result


def _frame_stiffness(section: Section3D, length: float, kind: str) -> np.ndarray:
    stiffness = np.zeros((12, 12), dtype=float)
    if kind == "truss":
        value = section.e_pa * section.area_m2 / length
        stiffness[0, 0] = stiffness[6, 6] = value
        stiffness[0, 6] = stiffness[6, 0] = -value
        return stiffness
    ea = section.e_pa * section.area_m2 / length
    gj = section.g_pa * section.j_m4 / length
    eiy_l3 = section.e_pa * section.iy_m4 / length**3
    eiz_l3 = section.e_pa * section.iz_m4 / length**3
    eiy_l2 = section.e_pa * section.iy_m4 / length**2
    eiz_l2 = section.e_pa * section.iz_m4 / length**2
    eiy_l = section.e_pa * section.iy_m4 / length
    eiz_l = section.e_pa * section.iz_m4 / length
    stiffness[0, 0] = stiffness[6, 6] = ea
    stiffness[0, 6] = stiffness[6, 0] = -ea
    stiffness[3, 3] = stiffness[9, 9] = gj
    stiffness[3, 9] = stiffness[9, 3] = -gj
    # Local v / rz bending uses Iz.
    values_z = ((1, 1, 12 * eiz_l3), (1, 5, 6 * eiz_l2), (1, 7, -12 * eiz_l3), (1, 11, 6 * eiz_l2),
                (5, 5, 4 * eiz_l), (5, 7, -6 * eiz_l2), (5, 11, 2 * eiz_l),
                (7, 7, 12 * eiz_l3), (7, 11, -6 * eiz_l2), (11, 11, 4 * eiz_l))
    # Local w / ry bending uses Iy.
    values_y = ((2, 2, 12 * eiy_l3), (2, 4, -6 * eiy_l2), (2, 8, -12 * eiy_l3), (2, 10, -6 * eiy_l2),
                (4, 4, 4 * eiy_l), (4, 8, 6 * eiy_l2), (4, 10, 2 * eiy_l),
                (8, 8, 12 * eiy_l3), (8, 10, 6 * eiy_l2), (10, 10, 4 * eiy_l))
    for first, second, value in values_z + values_y:
        stiffness[first, second] = value
        stiffness[second, first] = value
    return stiffness


def _support_dofs(support: str, start: int) -> set[int]:
    if support == "Fixed":
        return set(range(start, start + 6))
    if support == "Pinned":
        return {start, start + 1, start + 2}
    if support == "RollerX":
        return {start + 1, start + 2}
    if support == "RollerY":
        return {start, start + 2}
    if support == "RollerZ":
        return {start, start + 1}
    return set()


def _combine_case_result(cases: Mapping[str, Mapping[str, Any]], factors: Mapping[str, float]) -> dict[str, Any]:
    first = next(iter(cases.values()))
    nodes = []
    for index, source in enumerate(first["nodes"]):
        item = {"id": source["id"], "x_m": source["x_m"], "y_m": source["y_m"], "z_m": source["z_m"], "displacements": [0.0] * 6, "reactions_kn": [0.0] * 6}
        for case_name, factor in factors.items():
            candidate = cases.get(case_name)
            if candidate is None:
                continue
            for component in range(6):
                item["displacements"][component] += candidate["nodes"][index]["displacements"][component] * factor
                item["reactions_kn"][component] += candidate["nodes"][index]["reactions_kn"][component] * factor
        nodes.append(item)
    members = []
    for index, source in enumerate(first["members"]):
        item = {"id": source["id"], "group": source["group"], "kind": source["kind"], "length_m": source["length_m"], "axial_tension_kn": 0.0, "local_end_forces_kn": [0.0] * 12}
        for case_name, factor in factors.items():
            candidate = cases.get(case_name)
            if candidate is None:
                continue
            item["axial_tension_kn"] += candidate["members"][index]["axial_tension_kn"] * factor
            for component in range(12):
                item["local_end_forces_kn"][component] += candidate["members"][index]["local_end_forces_kn"][component] * factor
        members.append(item)
    return {"nodes": nodes, "members": members}


class NativeLinear3DBackend:
    """Direct-stiffness 3D backend for first-order preliminary analysis."""

    name = "native_linear_3d"

    def analyze(self, model: GeneratedWarehouse) -> dict[str, Any]:
        try:
            return self._analyze(model)
        except (ValueError, np.linalg.LinAlgError) as exc:
            return {"ok": False, "backend": self.name, "error": str(exc)}

    def _analyze(self, model: GeneratedWarehouse) -> dict[str, Any]:
        node_index = {node.id: index for index, node in enumerate(model.nodes)}
        sections = {section.id: section for section in model.project.sections}
        total_dofs = len(model.nodes) * 6
        stiffness = np.zeros((total_dofs, total_dofs), dtype=float)
        states: list[_ElementState] = []
        truss_rotation_nodes: set[int] = set()
        frame_rotation_nodes: set[int] = set()
        for member in model.members:
            first, second = model.nodes[node_index[member.i]], model.nodes[node_index[member.j]]
            length, rotation = _local_axes(np.array([first.x_m, first.y_m, first.z_m]), np.array([second.x_m, second.y_m, second.z_m]))
            section = sections[member.section]
            transform = _block_transform(rotation)
            local_stiffness = _frame_stiffness(section, length, member.kind)
            dofs = tuple(range(node_index[member.i] * 6, node_index[member.i] * 6 + 6)) + tuple(range(node_index[member.j] * 6, node_index[member.j] * 6 + 6))
            stiffness[np.ix_(dofs, dofs)] += transform.T @ local_stiffness @ transform
            states.append(_ElementState(member, section, dofs, length, transform, local_stiffness))
            (truss_rotation_nodes if member.kind == "truss" else frame_rotation_nodes).update((member.i, member.j))
        fixed: set[int] = set()
        for index, node in enumerate(model.nodes):
            fixed.update(_support_dofs(node.support, index * 6))
            if node.id in truss_rotation_nodes and node.id not in frame_rotation_nodes:
                fixed.update((index * 6 + 3, index * 6 + 4, index * 6 + 5))
        free = tuple(index for index in range(total_dofs) if index not in fixed)
        if not fixed:
            raise ValueError("Warehouse has no support restraints")
        reduced = stiffness[np.ix_(free, free)]
        if free and np.linalg.matrix_rank(reduced) < len(free):
            raise ValueError("Matrix singular. Warehouse may be unstable or insufficiently braced")
        force_by_case = self._load_vectors(model, node_index, states)
        cases: dict[str, dict[str, Any]] = {}
        for name, force in force_by_case.items():
            displacements = np.zeros(total_dofs, dtype=float)
            if free:
                displacements[list(free)] = np.linalg.solve(reduced, force[list(free)])
            reactions = stiffness @ displacements - force
            cases[name] = self._result_for_vector(model, states, displacements, reactions)
        combos = {combo.name: _combine_case_result(cases, combo.factors) for combo in model.project.combinations}
        envelope = self._envelope(combos)
        return {
            "ok": True,
            "backend": self.name,
            "analysisType": "Warehouse3D",
            "cases": cases,
            "combos": combos,
            "envelope": envelope,
            "model_summary": {"nodes": len(model.nodes), "members": len(model.members), "dofs": total_dofs, "free_dofs": len(free)},
            "steps": ["Assembled 3D space-frame stiffness", f"Nodes: {len(model.nodes)}, members: {len(model.members)}", f"Load cases: {len(cases)}, combinations: {len(combos)}", "First-order linear analysis complete"],
        }

    def _load_vectors(self, model: GeneratedWarehouse, node_index: Mapping[int, int], states: list[_ElementState]) -> dict[str, np.ndarray]:
        names = {"DL", "LL", "WXP", "WXN", "WYP", "WYN"}
        names.update(load.case for load in model.loads)
        force_by_case = {name: np.zeros(len(model.nodes) * 6, dtype=float) for name in names}
        for load in model.loads:
            target = force_by_case.setdefault(load.case, np.zeros(len(model.nodes) * 6, dtype=float))
            offset = node_index[load.node] * 6
            # Stiffness is assembled in N/m and N-m; public warehouse loads are kN and kN-m.
            target[offset : offset + 6] += 1000.0 * np.array((load.fx_kn, load.fy_kn, load.fz_kn, load.mx_kn_m, load.my_kn_m, load.mz_kn_m))
        if model.project.loads.include_self_weight:
            target = force_by_case["DL"]
            for state in states:
                weight_kn = state.section.density_kg_m3 * state.section.area_m2 * state.length_m * 9.80665 / 1000.0
                target[state.dofs[2]] -= weight_kn * 1000.0 / 2.0
                target[state.dofs[8]] -= weight_kn * 1000.0 / 2.0
        return force_by_case

    def _result_for_vector(self, model: GeneratedWarehouse, states: list[_ElementState], displacements: np.ndarray, reactions: np.ndarray) -> dict[str, Any]:
        nodes = []
        for index, node in enumerate(model.nodes):
            offset = index * 6
            nodes.append({"id": node.id, "x_m": node.x_m, "y_m": node.y_m, "z_m": node.z_m, "displacements": [float(value) for value in displacements[offset : offset + 6]], "reactions_kn": [float(value / 1000.0) for value in reactions[offset : offset + 6]]})
        members = []
        for state in states:
            local_displacements = state.transform @ displacements[list(state.dofs)]
            local_force = state.local_stiffness @ local_displacements
            axial = state.section.e_pa * state.section.area_m2 / state.length_m * (local_displacements[6] - local_displacements[0]) / 1000.0
            members.append({"id": state.member.id, "group": state.member.group, "kind": state.member.kind, "length_m": state.length_m, "axial_tension_kn": float(axial), "local_end_forces_kn": [float(value / 1000.0) for value in local_force]})
        return {"nodes": nodes, "members": members}

    def _envelope(self, combos: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        if not combos:
            return {"nodes": [], "members": []}
        result = _combine_case_result(combos, {next(iter(combos)): 1.0})
        for combo in list(combos.values())[1:]:
            for target, candidate in zip(result["nodes"], combo["nodes"], strict=True):
                for key in ("displacements", "reactions_kn"):
                    for index, value in enumerate(candidate[key]):
                        if abs(value) > abs(target[key][index]):
                            target[key][index] = value
            for target, candidate in zip(result["members"], combo["members"], strict=True):
                if abs(candidate["axial_tension_kn"]) > abs(target["axial_tension_kn"]):
                    target["axial_tension_kn"] = candidate["axial_tension_kn"]
                for index, value in enumerate(candidate["local_end_forces_kn"]):
                    if abs(value) > abs(target["local_end_forces_kn"][index]):
                        target["local_end_forces_kn"][index] = value
        return result


class OpenSeesPyBackend:
    """OpenSeesPy linear-elastic backend behind the shared Warehouse3D contract."""

    name = "openseespy"

    @staticmethod
    def available() -> bool:
        try:
            import openseespy.opensees  # noqa: F401
        except ImportError:
            return False
        return True

    def analyze(self, model: GeneratedWarehouse) -> dict[str, Any]:
        if not self.available():
            return {"ok": False, "backend": self.name, "error": "OpenSeesPy is not installed. Install go-struct-desktop[warehouse-opensees] or use native_linear_3d."}
        import openseespy.opensees as ops

        native = NativeLinear3DBackend()
        try:
            node_index = {node.id: index for index, node in enumerate(model.nodes)}
            sections = {section.id: section for section in model.project.sections}
            states: list[_ElementState] = []
            truss_rotation_nodes: set[int] = set()
            frame_rotation_nodes: set[int] = set()
            for member in model.members:
                first, second = model.nodes[node_index[member.i]], model.nodes[node_index[member.j]]
                length, rotation = _local_axes(np.array([first.x_m, first.y_m, first.z_m]), np.array([second.x_m, second.y_m, second.z_m]))
                section = sections[member.section]
                dofs = tuple(range(node_index[member.i] * 6, node_index[member.i] * 6 + 6)) + tuple(range(node_index[member.j] * 6, node_index[member.j] * 6 + 6))
                states.append(_ElementState(member, section, dofs, length, _block_transform(rotation), _frame_stiffness(section, length, member.kind)))
                (truss_rotation_nodes if member.kind == "truss" else frame_rotation_nodes).update((member.i, member.j))
            force_by_case = native._load_vectors(model, node_index, states)
            cases: dict[str, dict[str, Any]] = {}
            for case_index, (case_name, force) in enumerate(force_by_case.items(), 1):
                ops.wipe()
                ops.model("basic", "-ndm", 3, "-ndf", 6)
                for index, node in enumerate(model.nodes):
                    ops.node(node.id, node.x_m, node.y_m, node.z_m)
                    fixed = _support_dofs(node.support, index * 6)
                    if node.id in truss_rotation_nodes and node.id not in frame_rotation_nodes:
                        fixed.update((index * 6 + 3, index * 6 + 4, index * 6 + 5))
                    flags = [1 if index * 6 + component in fixed else 0 for component in range(6)]
                    if any(flags):
                        ops.fix(node.id, *flags)
                material_tags = {section_id: 200_000 + index for index, section_id in enumerate(sections, 1)}
                for section_id, section in sections.items():
                    ops.uniaxialMaterial("Elastic", material_tags[section_id], section.e_pa)
                for state in states:
                    local_z = state.transform[2, :3]
                    transform_tag = 100_000 + state.member.id
                    ops.geomTransf("Linear", transform_tag, float(local_z[0]), float(local_z[1]), float(local_z[2]))
                    if state.member.kind == "truss":
                        ops.element("truss", state.member.id, state.member.i, state.member.j, state.section.area_m2, material_tags[state.section.id])
                    else:
                        ops.element("elasticBeamColumn", state.member.id, state.member.i, state.member.j, state.section.area_m2, state.section.e_pa, state.section.g_pa, state.section.j_m4, state.section.iy_m4, state.section.iz_m4, transform_tag)
                ops.timeSeries("Linear", case_index)
                ops.pattern("Plain", case_index, case_index)
                for node in model.nodes:
                    offset = node_index[node.id] * 6
                    values = [float(value) for value in force[offset : offset + 6]]
                    if any(abs(value) > 1.0e-12 for value in values):
                        ops.load(node.id, *values)
                ops.system("BandSPD")
                ops.numberer("RCM")
                ops.constraints("Plain")
                ops.integrator("LoadControl", 1.0)
                ops.algorithm("Linear")
                ops.analysis("Static")
                if ops.analyze(1) != 0:
                    return {"ok": False, "backend": self.name, "error": f"OpenSeesPy failed to solve load case {case_name}"}
                ops.reactions()
                displacements = np.zeros(len(model.nodes) * 6, dtype=float)
                reactions = np.zeros(len(model.nodes) * 6, dtype=float)
                for node in model.nodes:
                    offset = node_index[node.id] * 6
                    displacements[offset : offset + 6] = ops.nodeDisp(node.id)
                    reactions[offset : offset + 6] = ops.nodeReaction(node.id)
                cases[case_name] = native._result_for_vector(model, states, displacements, reactions)
            combos = {combo.name: _combine_case_result(cases, combo.factors) for combo in model.project.combinations}
            return {"ok": True, "backend": self.name, "analysisType": "Warehouse3D", "cases": cases, "combos": combos, "envelope": native._envelope(combos), "model_summary": {"nodes": len(model.nodes), "members": len(model.members), "dofs": len(model.nodes) * 6}, "steps": ["Assembled OpenSeesPy 3D elastic beam-column model", f"Load cases: {len(cases)}, combinations: {len(combos)}", "First-order linear analysis complete"]}
        except Exception as exc:
            return {"ok": False, "backend": self.name, "error": str(exc)}
        finally:
            ops.wipe()


def analyze_warehouse_data(data: Mapping[str, Any] | WarehouseProject | GeneratedWarehouse, backend: AnalysisBackend3D | None = None) -> dict[str, Any]:
    """Analyze a warehouse project or a previously generated model."""
    try:
        generated = data if isinstance(data, GeneratedWarehouse) else generate_warehouse(data if isinstance(data, WarehouseProject) else WarehouseProject.from_dict(data))
        return (backend or NativeLinear3DBackend()).analyze(generated)
    except ModelValidationError as exc:
        return {"ok": False, "error": str(exc), "errors": exc.errors}
