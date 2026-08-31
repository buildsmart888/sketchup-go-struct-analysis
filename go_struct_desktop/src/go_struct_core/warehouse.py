"""Parametric, SI-unit warehouse domain model for preliminary 3D studies.

This module intentionally has no UI or solver imports.  It is a new project
format and does not alter the legacy GOFrame/GOTruss JSON contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import radians, tan
from typing import Any, Mapping

from .errors import ModelValidationError


def _number(source: Mapping[str, Any], key: str, default: float) -> float:
    value = source.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"{key} must be a number")
    return float(value)


def _text(source: Mapping[str, Any], key: str, default: str) -> str:
    value = source.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text")
    return value


@dataclass(frozen=True)
class Section3D:
    """A steel section in SI base units (Pa, m2, m4, m3, kg/m3)."""

    id: str
    area_m2: float
    iy_m4: float
    iz_m4: float
    j_m4: float
    zy_m3: float
    zz_m3: float
    e_pa: float = 200_000_000_000.0
    g_pa: float = 76_900_000_000.0
    fy_pa: float = 250_000_000.0
    density_kg_m3: float = 7_850.0

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], path: str) -> "Section3D":
        try:
            section = cls(
                id=_text(raw, "id", path),
                area_m2=_number(raw, "area_m2", 0.0),
                iy_m4=_number(raw, "iy_m4", 0.0),
                iz_m4=_number(raw, "iz_m4", 0.0),
                j_m4=_number(raw, "j_m4", 0.0),
                zy_m3=_number(raw, "zy_m3", 0.0),
                zz_m3=_number(raw, "zz_m3", 0.0),
                e_pa=_number(raw, "e_pa", 200_000_000_000.0),
                g_pa=_number(raw, "g_pa", 76_900_000_000.0),
                fy_pa=_number(raw, "fy_pa", 250_000_000.0),
                density_kg_m3=_number(raw, "density_kg_m3", 7_850.0),
            )
        except (TypeError, ValueError) as exc:
            raise ModelValidationError([f"{path}: {exc}"]) from exc
        if min(section.area_m2, section.iy_m4, section.iz_m4, section.j_m4, section.zy_m3, section.zz_m3, section.e_pa, section.g_pa, section.fy_pa) <= 0:
            raise ModelValidationError([f"{path} requires positive A, Iy, Iz, J, Zy, Zz, E, G, and Fy"])
        if section.density_kg_m3 < 0:
            raise ModelValidationError([f"{path}.density_kg_m3 cannot be negative"])
        return section

    def to_dict(self) -> dict[str, float | str]:
        return {
            "id": self.id,
            "area_m2": self.area_m2,
            "iy_m4": self.iy_m4,
            "iz_m4": self.iz_m4,
            "j_m4": self.j_m4,
            "zy_m3": self.zy_m3,
            "zz_m3": self.zz_m3,
            "e_pa": self.e_pa,
            "g_pa": self.g_pa,
            "fy_pa": self.fy_pa,
            "density_kg_m3": self.density_kg_m3,
        }


@dataclass(frozen=True)
class Node3D:
    id: int
    x_m: float
    y_m: float
    z_m: float
    support: str = "Free"

    def to_dict(self) -> dict[str, float | int | str]:
        return {"id": self.id, "x_m": self.x_m, "y_m": self.y_m, "z_m": self.z_m, "support": self.support}


@dataclass(frozen=True)
class Member3D:
    id: int
    i: int
    j: int
    section: str
    group: str
    kind: str = "frame"

    def to_dict(self) -> dict[str, int | str]:
        return {"id": self.id, "i": self.i, "j": self.j, "section": self.section, "group": self.group, "kind": self.kind}


@dataclass(frozen=True)
class NodalLoad3D:
    node: int
    case: str
    fx_kn: float = 0.0
    fy_kn: float = 0.0
    fz_kn: float = 0.0
    mx_kn_m: float = 0.0
    my_kn_m: float = 0.0
    mz_kn_m: float = 0.0

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "node": self.node,
            "case": self.case,
            "fx_kn": self.fx_kn,
            "fy_kn": self.fy_kn,
            "fz_kn": self.fz_kn,
            "mx_kn_m": self.mx_kn_m,
            "my_kn_m": self.my_kn_m,
            "mz_kn_m": self.mz_kn_m,
        }


@dataclass(frozen=True)
class LoadCombination3D:
    name: str
    factors: Mapping[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "factors": dict(self.factors)}


@dataclass(frozen=True)
class WarehouseGeometry:
    width_m: float = 20.0
    length_m: float = 30.0
    bay_count: int = 3
    eave_height_m: float = 6.0
    roof_slope_deg: float = 10.0
    truss_depth_m: float = 1.5
    overhang_m: float = 0.6
    panel_count: int = 8
    min_clear_height_m: float = 6.0
    topology: str = "warren"

    @property
    def bay_spacing_m(self) -> float:
        return self.length_m / self.bay_count

    @property
    def ridge_height_m(self) -> float:
        # Eave height remains the clear-height datum.  A deeper truss raises
        # its interior top chord while preserving the eave/column connection.
        return self.eave_height_m + tan(radians(self.roof_slope_deg)) * self.width_m / 2.0 + self.truss_depth_m

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "WarehouseGeometry":
        geometry = cls(
            width_m=_number(raw, "width_m", 20.0),
            length_m=_number(raw, "length_m", 30.0),
            bay_count=int(_number(raw, "bay_count", 3)),
            eave_height_m=_number(raw, "eave_height_m", 6.0),
            roof_slope_deg=_number(raw, "roof_slope_deg", 10.0),
            truss_depth_m=_number(raw, "truss_depth_m", 1.5),
            overhang_m=_number(raw, "overhang_m", 0.6),
            panel_count=int(_number(raw, "panel_count", 8)),
            min_clear_height_m=_number(raw, "min_clear_height_m", 6.0),
            topology=_text(raw, "topology", "warren").lower(),
        )
        errors: list[str] = []
        if geometry.width_m <= 0 or geometry.length_m <= 0:
            errors.append("warehouse width_m and length_m must be positive")
        if geometry.bay_count < 1:
            errors.append("warehouse bay_count must be at least 1")
        if geometry.panel_count < 2 or geometry.panel_count % 2:
            errors.append("warehouse panel_count must be an even integer of at least 2")
        if geometry.eave_height_m <= 0 or geometry.min_clear_height_m <= 0:
            errors.append("warehouse eave/minimum clear height must be positive")
        if not 0.1 <= geometry.roof_slope_deg <= 60.0:
            errors.append("warehouse roof_slope_deg must be between 0.1 and 60")
        if geometry.truss_depth_m <= 0 or geometry.overhang_m < 0:
            errors.append("warehouse truss_depth_m must be positive and overhang_m cannot be negative")
        if geometry.topology not in {"warren", "pratt", "howe", "pitched"}:
            errors.append("warehouse topology must be warren, pratt, howe, or pitched")
        if errors:
            raise ModelValidationError(errors)
        return geometry

    def to_dict(self) -> dict[str, Any]:
        return {
            "width_m": self.width_m,
            "length_m": self.length_m,
            "bay_count": self.bay_count,
            "bay_spacing_m": self.bay_spacing_m,
            "eave_height_m": self.eave_height_m,
            "ridge_height_m": self.ridge_height_m,
            "roof_slope_deg": self.roof_slope_deg,
            "truss_depth_m": self.truss_depth_m,
            "overhang_m": self.overhang_m,
            "panel_count": self.panel_count,
            "min_clear_height_m": self.min_clear_height_m,
            "topology": self.topology,
        }


@dataclass(frozen=True)
class WarehouseLoads:
    roof_dead_kn_m2: float = 0.25
    roof_live_kn_m2: float = 0.50
    wind_roof_kn_m2: float = 0.80
    wind_wall_kn_m2: float = 0.80
    include_self_weight: bool = True

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "WarehouseLoads":
        loads = cls(
            roof_dead_kn_m2=_number(raw, "roof_dead_kn_m2", 0.25),
            roof_live_kn_m2=_number(raw, "roof_live_kn_m2", 0.50),
            wind_roof_kn_m2=_number(raw, "wind_roof_kn_m2", 0.80),
            wind_wall_kn_m2=_number(raw, "wind_wall_kn_m2", 0.80),
            include_self_weight=raw.get("include_self_weight", True) is True,
        )
        if min(loads.roof_dead_kn_m2, loads.roof_live_kn_m2, loads.wind_roof_kn_m2, loads.wind_wall_kn_m2) < 0:
            raise ModelValidationError(["warehouse load intensities cannot be negative"])
        return loads

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "roof_dead_kn_m2": self.roof_dead_kn_m2,
            "roof_live_kn_m2": self.roof_live_kn_m2,
            "wind_roof_kn_m2": self.wind_roof_kn_m2,
            "wind_wall_kn_m2": self.wind_wall_kn_m2,
            "include_self_weight": self.include_self_weight,
        }


def default_sections() -> tuple[Section3D, ...]:
    """Conservative starter sections; users can replace them with a catalog."""
    return (
        Section3D("column", 0.0120, 1.60e-4, 5.50e-5, 2.00e-5, 9.0e-4, 4.5e-4),
        Section3D("chord", 0.0080, 8.00e-5, 3.50e-5, 1.20e-5, 5.5e-4, 3.0e-4),
        Section3D("web", 0.0035, 1.20e-5, 1.20e-5, 4.00e-6, 1.3e-4, 1.3e-4),
        Section3D("purlin", 0.0030, 9.00e-6, 2.00e-5, 3.00e-6, 1.1e-4, 1.8e-4),
        Section3D("bracing", 0.0020, 3.00e-6, 3.00e-6, 1.00e-6, 5.0e-5, 5.0e-5),
        Section3D("ground_beam", 0.0060, 4.00e-5, 2.00e-5, 8.00e-6, 3.2e-4, 2.0e-4),
    )


@dataclass(frozen=True)
class WarehouseProject:
    """Validated, serializable warehouse project in SI units."""

    geometry: WarehouseGeometry
    sections: tuple[Section3D, ...] = field(default_factory=default_sections)
    loads: WarehouseLoads = field(default_factory=WarehouseLoads)
    project_info: Mapping[str, Any] = field(default_factory=dict)
    combinations: tuple[LoadCombination3D, ...] = field(default_factory=tuple)

    @classmethod
    def default(cls) -> "WarehouseProject":
        return cls(
            geometry=WarehouseGeometry(),
            project_info={
                "name": "20 x 30 m Preliminary Warehouse",
                "analysisType": "Warehouse3D",
                "units": "kn_m",
                "disclaimer": "Preliminary design — requires licensed engineer review.",
            },
            combinations=default_combinations(),
        )

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "WarehouseProject":
        geometry = WarehouseGeometry.from_dict(_mapping(raw.get("geometry", {}), "geometry"))
        raw_sections = raw.get("sections", [item.to_dict() for item in default_sections()])
        if not isinstance(raw_sections, list):
            raise ModelValidationError(["sections must be an array"])
        sections = tuple(Section3D.from_dict(_mapping(value, f"sections[{index}]"), f"sections[{index}]") for index, value in enumerate(raw_sections))
        ids = [item.id for item in sections]
        if len(ids) != len(set(ids)):
            raise ModelValidationError(["section ids must be unique"])
        loads = WarehouseLoads.from_dict(_mapping(raw.get("loads", {}), "loads"))
        project_info = dict(_mapping(raw.get("projectInfo", {}), "projectInfo"))
        project_info.setdefault("analysisType", "Warehouse3D")
        project_info.setdefault("units", "kn_m")
        project_info.setdefault("disclaimer", "Preliminary design — requires licensed engineer review.")
        raw_combos = raw.get("load_combinations", [item.to_dict() for item in default_combinations()])
        if not isinstance(raw_combos, list):
            raise ModelValidationError(["load_combinations must be an array"])
        combos: list[LoadCombination3D] = []
        for index, value in enumerate(raw_combos):
            item = _mapping(value, f"load_combinations[{index}]")
            factors = item.get("factors", {})
            if not isinstance(factors, Mapping):
                raise ModelValidationError([f"load_combinations[{index}].factors must be an object"])
            combos.append(LoadCombination3D(_text(item, "name", f"Combo {index + 1}"), {str(key): float(factor) for key, factor in factors.items()}))
        names = [item.name for item in combos]
        if len(names) != len(set(names)):
            raise ModelValidationError(["load combination names must be unique"])
        return cls(geometry=geometry, sections=sections, loads=loads, project_info=project_info, combinations=tuple(combos))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "projectInfo": dict(self.project_info),
            "geometry": self.geometry.to_dict(),
            "sections": [section.to_dict() for section in self.sections],
            "loads": self.loads.to_dict(),
            "load_combinations": [combo.to_dict() for combo in self.combinations],
        }


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ModelValidationError([f"{path} must be an object"])
    return value


def default_combinations() -> tuple[LoadCombination3D, ...]:
    return (
        LoadCombination3D("Service", {"DL": 1.0, "LL": 1.0, "WXP": 0.7, "WYP": 0.7}),
        LoadCombination3D("ULS Gravity", {"DL": 1.2, "LL": 1.6}),
        LoadCombination3D("ULS Wind +X", {"DL": 1.2, "WXP": 1.0}),
        LoadCombination3D("ULS Wind -X", {"DL": 1.2, "WXN": 1.0}),
        LoadCombination3D("ULS Wind +Y", {"DL": 1.2, "WYP": 1.0}),
        LoadCombination3D("ULS Wind -Y", {"DL": 1.2, "WYN": 1.0}),
    )


@dataclass(frozen=True)
class GeneratedWarehouse:
    project: WarehouseProject
    nodes: tuple[Node3D, ...]
    members: tuple[Member3D, ...]
    loads: tuple[NodalLoad3D, ...]
    conceptual_items: Mapping[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project.to_dict(),
            "nodes": [node.to_dict() for node in self.nodes],
            "members": [member.to_dict() for member in self.members],
            "loads": [load.to_dict() for load in self.loads],
            "conceptual_items": dict(self.conceptual_items),
        }


class _Builder:
    def __init__(self) -> None:
        self.nodes: list[Node3D] = []
        self.members: list[Member3D] = []
        self._next_node = 1
        self._next_member = 1
        self._member_pairs: set[frozenset[int]] = set()

    def node(self, x: float, y: float, z: float, support: str = "Free") -> int:
        node_id = self._next_node
        self._next_node += 1
        self.nodes.append(Node3D(node_id, x, y, z, support))
        return node_id

    def member(self, i: int, j: int, section: str, group: str, kind: str = "frame") -> None:
        pair = frozenset((i, j))
        if i == j or pair in self._member_pairs:
            return
        self._member_pairs.add(pair)
        self.members.append(Member3D(self._next_member, i, j, section, group, kind))
        self._next_member += 1


def _truss_web_layout(topology: str, panel_count: int) -> tuple[tuple[str, int, str, int], ...]:
    """Return the web layout for one pitched transverse truss.

    Each tuple is ``(first_chord, first_index, second_chord, second_index)``.
    The outer top and bottom chord nodes coincide at the eaves, so Pratt and
    Howe deliberately leave their outermost cells without a duplicate chord
    member.  This preserves the conventional diagonal direction while keeping
    the generated model free of zero-length and duplicate members.
    """
    items: list[tuple[str, int, str, int]] = [
        ("bottom", index, "top", index) for index in range(1, panel_count)
    ]

    def add(first: str, first_index: int, second: str, second_index: int) -> None:
        items.append((first, first_index, second, second_index))

    midpoint = panel_count // 2
    if topology == "warren":
        # Alternating diagonals form the Warren zig-zag, rather than every
        # diagonal leaning in the same direction.
        for panel in range(panel_count):
            if panel % 2 == 0:
                add("bottom", panel, "top", panel + 1)
            else:
                add("top", panel, "bottom", panel + 1)
    elif topology == "pratt":
        # Diagonals slope down toward the ridge/centre from both sides.
        for panel in range(1, midpoint):
            add("top", panel, "bottom", panel + 1)
        for panel in range(midpoint, panel_count - 1):
            add("top", panel + 1, "bottom", panel)
    elif topology == "howe":
        # Howe is the reverse of Pratt: diagonals slope away from centre.
        for panel in range(1, midpoint):
            add("bottom", panel, "top", panel + 1)
        for panel in range(midpoint, panel_count - 1):
            add("bottom", panel + 1, "top", panel)
    else:  # ``pitched``: a symmetric Fink / pitched W-web, not a ridge fan.
        for panel in range(panel_count):
            mirrored_panel = panel if panel < midpoint else panel_count - 1 - panel
            if panel < midpoint:
                if mirrored_panel % 2 == 0:
                    add("bottom", panel, "top", panel + 1)
                else:
                    add("top", panel, "bottom", panel + 1)
            elif mirrored_panel % 2 == 0:
                add("bottom", panel + 1, "top", panel)
            else:
                add("top", panel + 1, "bottom", panel)
    return tuple(items)


def generate_warehouse(project: WarehouseProject | Mapping[str, Any]) -> GeneratedWarehouse:
    """Generate the complete preliminary building skeleton and equivalent nodal loads."""
    model = project if isinstance(project, WarehouseProject) else WarehouseProject.from_dict(project)
    geometry = model.geometry
    section_ids = {item.id for item in model.sections}
    required = {"column", "chord", "web", "purlin", "bracing", "ground_beam"}
    missing = sorted(required - section_ids)
    if missing:
        raise ModelValidationError([f"warehouse sections missing required ids: {', '.join(missing)}"])
    builder = _Builder()
    frame_nodes: list[dict[str, list[int]]] = []
    half_width = geometry.width_m / 2.0
    panel_width = geometry.width_m / geometry.panel_count

    for frame_index in range(geometry.bay_count + 1):
        x = frame_index * geometry.bay_spacing_m
        bottom: list[int] = []
        top: list[int] = []
        columns: list[int] = []
        for panel in range(geometry.panel_count + 1):
            y = -half_width + panel * panel_width
            bottom_node = builder.node(x, y, geometry.eave_height_m)
            bottom.append(bottom_node)
            rise = tan(radians(geometry.roof_slope_deg)) * geometry.width_m / 2.0
            profile = 1.0 - abs(2.0 * panel / geometry.panel_count - 1.0)
            z_top = geometry.eave_height_m + (rise + geometry.truss_depth_m) * profile
            top.append(bottom_node if panel in {0, geometry.panel_count} else builder.node(x, y, z_top))
        left_base = builder.node(x, -half_width, 0.0, "Fixed")
        right_base = builder.node(x, half_width, 0.0, "Fixed")
        columns.extend((left_base, right_base))
        builder.member(left_base, bottom[0], "column", "column")
        builder.member(right_base, bottom[-1], "column", "column")
        for panel in range(geometry.panel_count):
            builder.member(bottom[panel], bottom[panel + 1], "chord", "bottom_chord")
            builder.member(top[panel], top[panel + 1], "chord", "top_chord")
        for first_chord, first_index, second_chord, second_index in _truss_web_layout(geometry.topology, geometry.panel_count):
            first = bottom[first_index] if first_chord == "bottom" else top[first_index]
            second = bottom[second_index] if second_chord == "bottom" else top[second_index]
            builder.member(first, second, "web", "web", "truss")
        frame_nodes.append({"bottom": bottom, "top": top, "bases": columns})

    for frame_index in range(geometry.bay_count):
        current, following = frame_nodes[frame_index], frame_nodes[frame_index + 1]
        for panel in range(geometry.panel_count + 1):
            builder.member(current["top"][panel], following["top"][panel], "purlin", "purlin")
            builder.member(current["bottom"][panel], following["bottom"][panel], "purlin", "bottom_tie")
        for end in (0, -1):
            builder.member(current["bases"][0 if end == 0 else 1], following["bases"][0 if end == 0 else 1], "ground_beam", "ground_beam")
        if frame_index in {0, geometry.bay_count - 1}:
            # Roof-plane and wall X-bracing in the end bays.  Both diagonals
            # are retained in this preliminary generator to avoid assigning a
            # one-way tension-only assumption to an elastic truss member.
            builder.member(current["top"][0], following["top"][-1], "bracing", "roof_bracing", "truss")
            builder.member(current["top"][-1], following["top"][0], "bracing", "roof_bracing", "truss")
            builder.member(current["bases"][0], following["bottom"][0], "bracing", "wall_bracing", "truss")
            builder.member(current["bottom"][0], following["bases"][0], "bracing", "wall_bracing", "truss")
            builder.member(current["bases"][1], following["bottom"][-1], "bracing", "wall_bracing", "truss")
            builder.member(current["bottom"][-1], following["bases"][1], "bracing", "wall_bracing", "truss")

    loads = _warehouse_loads(model, frame_nodes)
    conceptual_items = {
        "column_bases": 2 * (geometry.bay_count + 1),
        "truss_panel_points": (geometry.bay_count + 1) * (geometry.panel_count + 1),
        "foundation_positions": 2 * (geometry.bay_count + 1),
        "connection_nodes": len(builder.nodes),
    }
    return GeneratedWarehouse(model, tuple(builder.nodes), tuple(builder.members), tuple(loads), conceptual_items)


def _warehouse_loads(project: WarehouseProject, frame_nodes: list[dict[str, list[int]]]) -> list[NodalLoad3D]:
    geometry, input_loads = project.geometry, project.loads
    panel_width = geometry.width_m / geometry.panel_count
    loads: list[NodalLoad3D] = []
    average_height = (geometry.eave_height_m + geometry.ridge_height_m) / 2.0
    for frame_index, frame in enumerate(frame_nodes):
        tributary_length = geometry.bay_spacing_m * (0.5 if frame_index in {0, geometry.bay_count} else 1.0)
        for panel, node in enumerate(frame["top"]):
            tributary_width = panel_width * (0.5 if panel in {0, geometry.panel_count} else 1.0)
            area = tributary_width * tributary_length
            loads.append(NodalLoad3D(node, "DL", fz_kn=-input_loads.roof_dead_kn_m2 * area))
            loads.append(NodalLoad3D(node, "LL", fz_kn=-input_loads.roof_live_kn_m2 * area))
            wind_x = input_loads.wind_wall_kn_m2 * geometry.width_m * average_height / len(frame["top"])
            wind_y = input_loads.wind_wall_kn_m2 * geometry.length_m * geometry.eave_height_m / ((geometry.bay_count + 1) * len(frame["top"]))
            loads.extend((
                NodalLoad3D(node, "WXP", fx_kn=wind_x), NodalLoad3D(node, "WXN", fx_kn=-wind_x),
                NodalLoad3D(node, "WYP", fy_kn=wind_y), NodalLoad3D(node, "WYN", fy_kn=-wind_y),
            ))
    return loads
