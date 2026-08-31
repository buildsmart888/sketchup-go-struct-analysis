"""Typed, JSON-compatible models for the current GOFrame payload."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .errors import ModelValidationError


SUPPORT_TYPES = frozenset({"Free", "Fixed", "Pinned", "RollerX", "RollerY", "Spring"})
RELEASE_TYPES = frozenset({"Rigid-Rigid", "Pin-Rigid", "Rigid-Pin", "Pin-Pin"})
MEMBER_TYPES = frozenset({"Frame", "Truss"})
LOAD_DIRECTIONS = frozenset({"Local X", "Local Y", "Global X", "Global Y"})


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ModelValidationError([f"{path} must be an object"])
    return value


def _sequence(value: Any, path: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ModelValidationError([f"{path} must be an array"])
    return value


def _number(value: Any, path: str, default: float | None = None) -> float:
    if value is None and default is not None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ModelValidationError([f"{path} must be numeric"]) from exc


def _integer(value: Any, path: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ModelValidationError([f"{path} must be an integer"]) from exc


def _text(value: Any, path: str, default: str | None = None) -> str:
    if value is None and default is not None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ModelValidationError([f"{path} must be a non-empty string"])
    return value.strip()


@dataclass(frozen=True)
class FrameNode:
    id: int
    x: float
    y: float
    support: str = "Free"
    kx: float = 0.0
    ky: float = 0.0
    kr: float = 0.0

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], path: str) -> "FrameNode":
        support = _text(value.get("support"), f"{path}.support", "Free")
        return cls(
            id=_integer(value.get("id"), f"{path}.id"),
            x=_number(value.get("x"), f"{path}.x"),
            y=_number(value.get("y"), f"{path}.y"),
            support=support,
            kx=_number(value.get("kx"), f"{path}.kx", 0.0),
            ky=_number(value.get("ky"), f"{path}.ky", 0.0),
            kr=_number(value.get("kr"), f"{path}.kr", 0.0),
        )


@dataclass(frozen=True)
class FrameSection:
    id: int
    e: float
    a: float
    i: float
    density: float = 0.0
    name: str = ""
    material: str = ""
    depth_cm: float = 0.0
    width_cm: float = 0.0

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], path: str) -> "FrameSection":
        return cls(
            id=_integer(value.get("id"), f"{path}.id"),
            e=_number(value.get("e"), f"{path}.e"),
            a=_number(value.get("a"), f"{path}.a"),
            i=_number(value.get("i"), f"{path}.i"),
            density=_number(value.get("density"), f"{path}.density", 0.0),
            name=str(value.get("name", "")).strip(),
            material=str(value.get("material", "")).strip(),
            depth_cm=_number(value.get("depth_cm"), f"{path}.depth_cm", 0.0),
            width_cm=_number(value.get("width_cm"), f"{path}.width_cm", 0.0),
        )

    @property
    def area_m2(self) -> float:
        return self.a * 1.0e-4

    @property
    def inertia_m4(self) -> float:
        return self.i * 1.0e-8


@dataclass(frozen=True)
class FrameElement:
    id: int
    n1: int
    n2: int
    sec: int
    release: str = "Rigid-Rigid"
    member_type: str = "Frame"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], path: str) -> "FrameElement":
        raw_member_type = _text(value.get("memberType", value.get("member_type", "Frame")), f"{path}.memberType", "Frame")
        member_type = {"frame": "Frame", "truss": "Truss"}.get(raw_member_type.lower(), raw_member_type)
        return cls(
            id=_integer(value.get("id"), f"{path}.id"),
            n1=_integer(value.get("n1"), f"{path}.n1"),
            n2=_integer(value.get("n2"), f"{path}.n2"),
            sec=_integer(value.get("sec"), f"{path}.sec"),
            release=_text(value.get("release"), f"{path}.release", "Rigid-Rigid"),
            member_type=member_type,
        )


@dataclass(frozen=True)
class NodalLoad:
    node: int
    lcase: str
    fx: float = 0.0
    fy: float = 0.0
    mz: float = 0.0

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], path: str) -> "NodalLoad":
        return cls(
            node=_integer(value.get("node"), f"{path}.node"),
            lcase=_text(value.get("lcase"), f"{path}.lcase", "DL"),
            fx=_number(value.get("fx"), f"{path}.fx", 0.0),
            fy=_number(value.get("fy"), f"{path}.fy", 0.0),
            mz=_number(value.get("mz"), f"{path}.mz", 0.0),
        )


@dataclass(frozen=True)
class ElementLoad:
    elem: int
    lcase: str
    type: str
    direction: str
    w1: float = 0.0
    w2: float = 0.0
    x_m: float = 0.0
    p: float = 0.0
    m: float = 0.0
    x1_m: float = 0.0
    x2_m: float | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], path: str) -> "ElementLoad":
        w1 = _number(value.get("w1", value.get("w", 0.0)), f"{path}.w1")
        return cls(
            elem=_integer(value.get("elem"), f"{path}.elem"),
            lcase=_text(value.get("lcase"), f"{path}.lcase", "DL"),
            type=_text(value.get("type"), f"{path}.type", "Distributed"),
            direction=_text(value.get("dir"), f"{path}.dir", "Local Y"),
            w1=w1,
            w2=_number(value.get("w2", w1), f"{path}.w2"),
            x_m=_number(value.get("x_m", value.get("x", value.get("at", 0.0))), f"{path}.x_m"),
            p=_number(value.get("p", value.get("value", 0.0)), f"{path}.p"),
            m=_number(value.get("m", value.get("mz", value.get("value", 0.0))), f"{path}.m"),
            x1_m=_number(value.get("x1_m", value.get("start_x_m", 0.0)), f"{path}.x1_m", 0.0),
            x2_m=_number(value.get("x2_m", value.get("end_x_m")), f"{path}.x2_m") if value.get("x2_m", value.get("end_x_m")) is not None else None,
        )


@dataclass(frozen=True)
class LoadCombination:
    name: str
    factors: dict[str, float] = field(default_factory=dict)
    equation: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], path: str) -> "LoadCombination":
        raw_factors = value.get("factors", {})
        if not isinstance(raw_factors, Mapping):
            raise ModelValidationError([f"{path}.factors must be an object"])
        factors = {
            _text(key, f"{path}.factors key"): _number(raw, f"{path}.factors.{key}")
            for key, raw in raw_factors.items()
        }
        equation = value.get("eq")
        if equation is not None:
            equation = _text(equation, f"{path}.eq")
        return cls(name=_text(value.get("name"), f"{path}.name"), factors=factors, equation=equation)


@dataclass(frozen=True)
class FrameSettings:
    include_self_weight: bool = False
    display: dict[str, Any] = field(default_factory=dict)
    authoring: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FrameSettings":
        display = value.get("display", {})
        authoring = value.get("authoring", {})
        return cls(
            include_self_weight=value.get("include_self_weight") is True,
            display=dict(display) if isinstance(display, Mapping) else {},
            authoring=dict(authoring) if isinstance(authoring, Mapping) else {},
        )


@dataclass(frozen=True)
class FrameModel:
    """A validated view of the JSON emitted by the legacy GOFrame dialog."""

    nodes: tuple[FrameNode, ...]
    elements: tuple[FrameElement, ...]
    sections: tuple[FrameSection, ...]
    load_cases: tuple[str, ...]
    load_combinations: tuple[LoadCombination, ...]
    nodal_loads: tuple[NodalLoad, ...]
    element_loads: tuple[ElementLoad, ...]
    settings: FrameSettings
    project_info: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "FrameModel":
        data = _mapping(raw, "model")
        nodes = tuple(
            FrameNode.from_dict(_mapping(item, f"nodes[{index}]"), f"nodes[{index}]")
            for index, item in enumerate(_sequence(data.get("nodes", []), "nodes"))
        )
        elements = tuple(
            FrameElement.from_dict(_mapping(item, f"elements[{index}]"), f"elements[{index}]")
            for index, item in enumerate(_sequence(data.get("elements", []), "elements"))
        )
        sections = tuple(
            FrameSection.from_dict(_mapping(item, f"sections[{index}]"), f"sections[{index}]")
            for index, item in enumerate(_sequence(data.get("sections", []), "sections"))
        )
        raw_cases = data.get("loadcases", ["DL"])
        load_cases = tuple(_text(item, f"loadcases[{index}]") for index, item in enumerate(_sequence(raw_cases, "loadcases")))
        raw_combos = data.get("loadcombos", [{"name": "Comb 1", "eq": "1.0DL"}])
        load_combinations = tuple(
            LoadCombination.from_dict(_mapping(item, f"loadcombos[{index}]"), f"loadcombos[{index}]")
            for index, item in enumerate(_sequence(raw_combos, "loadcombos"))
        )
        nodal_loads = tuple(
            NodalLoad.from_dict(_mapping(item, f"nloads[{index}]"), f"nloads[{index}]")
            for index, item in enumerate(_sequence(data.get("nloads", []), "nloads"))
        )
        element_loads = tuple(
            ElementLoad.from_dict(_mapping(item, f"eloads[{index}]"), f"eloads[{index}]")
            for index, item in enumerate(_sequence(data.get("eloads", []), "eloads"))
        )
        settings = FrameSettings.from_dict(_mapping(data.get("settings", {}), "settings"))
        project_info = dict(_mapping(data.get("projectInfo", {}), "projectInfo"))
        model = cls(
            nodes=nodes,
            elements=elements,
            sections=sections,
            load_cases=load_cases,
            load_combinations=load_combinations,
            nodal_loads=nodal_loads,
            element_loads=element_loads,
            settings=settings,
            project_info=project_info,
        )
        model.validate()
        return model

    def validate(self) -> None:
        errors: list[str] = []
        if not self.nodes:
            errors.append("nodes must contain at least one node")
        if not self.elements:
            errors.append("elements must contain at least one element")
        if not self.sections:
            errors.append("sections must contain at least one section")

        node_ids = [node.id for node in self.nodes]
        element_ids = [element.id for element in self.elements]
        section_ids = [section.id for section in self.sections]
        combo_names = [combo.name for combo in self.load_combinations]
        for label, values in (("node", node_ids), ("element", element_ids), ("section", section_ids), ("load case", list(self.load_cases)), ("load combination", combo_names)):
            if len(values) != len(set(values)):
                errors.append(f"{label} identifiers must be unique")

        node_id_set = set(node_ids)
        element_id_set = set(element_ids)
        section_id_set = set(section_ids)
        load_case_set = set(self.load_cases)
        for node in self.nodes:
            if node.support not in SUPPORT_TYPES:
                errors.append(f"node {node.id} has unsupported support type {node.support!r}")
            if min(node.kx, node.ky, node.kr) < 0.0:
                errors.append(f"node {node.id} spring stiffness cannot be negative")
            if node.support == "Spring" and node.kx + node.ky + node.kr <= 0.0:
                errors.append(f"spring support at node {node.id} requires positive kx, ky, or kr")
        for section in self.sections:
            if section.e <= 0 or section.a <= 0 or section.i <= 0:
                errors.append(f"section {section.id} requires positive e, a, and i")
            if section.density < 0:
                errors.append(f"section {section.id} density cannot be negative")
            if section.depth_cm < 0 or section.width_cm < 0:
                errors.append(f"section {section.id} dimensions cannot be negative")
        for element in self.elements:
            if element.n1 not in node_id_set or element.n2 not in node_id_set:
                errors.append(f"element {element.id} references a missing node")
            if element.n1 == element.n2:
                errors.append(f"element {element.id} endpoints must differ")
            if element.sec not in section_id_set:
                errors.append(f"element {element.id} references a missing section")
            if element.release not in RELEASE_TYPES:
                errors.append(f"element {element.id} has unsupported release {element.release!r}")
            if element.member_type not in MEMBER_TYPES:
                errors.append(f"element {element.id} has unsupported memberType {element.member_type!r}")
            if element.member_type == "Truss" and element.release != "Rigid-Rigid":
                errors.append(f"truss member {element.id} cannot use a frame end release")
        for load in self.nodal_loads:
            if load.node not in node_id_set:
                errors.append(f"nodal load references missing node {load.node}")
            if load.lcase not in load_case_set:
                errors.append(f"nodal load references missing load case {load.lcase!r}")
        for load in self.element_loads:
            if load.elem not in element_id_set:
                errors.append(f"element load references missing element {load.elem}")
            if load.lcase not in load_case_set:
                errors.append(f"element load references missing load case {load.lcase!r}")
            if load.type not in {"Distributed", "Point Force", "Point Moment"}:
                errors.append(f"element load has unsupported type {load.type!r}")
            target_element = next((item for item in self.elements if item.id == load.elem), None)
            if target_element is not None and target_element.member_type == "Truss":
                errors.append(f"member loads on truss member {load.elem} are not supported; apply equivalent loads at nodes")
            if load.type != "Point Moment" and load.direction not in LOAD_DIRECTIONS:
                errors.append(f"element load has unsupported direction {load.direction!r}")
            if load.type in {"Point Force", "Point Moment"}:
                element = next((item for item in self.elements if item.id == load.elem), None)
                if element is not None:
                    node_i = next(node for node in self.nodes if node.id == element.n1)
                    node_j = next(node for node in self.nodes if node.id == element.n2)
                    length = math.hypot(node_j.x - node_i.x, node_j.y - node_i.y)
                    if load.x_m < 0.0 or load.x_m > length:
                        errors.append(f"element load on element {load.elem} requires x_m between 0 and {length:g} m")
            if load.type == "Distributed":
                element = next((item for item in self.elements if item.id == load.elem), None)
                if element is not None and load.x2_m is not None:
                    node_i = next(node for node in self.nodes if node.id == element.n1)
                    node_j = next(node for node in self.nodes if node.id == element.n2)
                    length = math.hypot(node_j.x - node_i.x, node_j.y - node_i.y)
                    if load.x1_m < -1.0e-9 or load.x2_m > length + 1.0e-9 or load.x2_m <= load.x1_m + 1.0e-9:
                        errors.append(f"distributed load on element {load.elem} requires 0 <= x1_m < x2_m <= {length:g} m")
        for combo in self.load_combinations:
            for load_case in combo.factors:
                if load_case not in load_case_set:
                    errors.append(f"load combination {combo.name!r} references missing load case {load_case!r}")
        if errors:
            raise ModelValidationError(errors)

    def to_dict(self) -> dict[str, Any]:
        """Return the current GOFrame JSON shape for GUI and bridge consumers."""

        return {
            "projectInfo": dict(self.project_info),
            "settings": {
                "include_self_weight": self.settings.include_self_weight,
                **({"display": dict(self.settings.display)} if self.settings.display else {}),
                **({"authoring": dict(self.settings.authoring)} if self.settings.authoring else {}),
            },
            "nodes": [
                {"id": node.id, "x": node.x, "y": node.y, "support": node.support, **({"kx": node.kx, "ky": node.ky, "kr": node.kr} if node.support == "Spring" else {})}
                for node in self.nodes
            ],
            "elements": [
                {
                    "id": element.id,
                    "n1": element.n1,
                    "n2": element.n2,
                    "sec": element.sec,
                    "release": element.release,
                    **({"memberType": element.member_type} if element.member_type != "Frame" else {}),
                }
                for element in self.elements
            ],
            "sections": [
                {
                    "id": section.id,
                    "e": section.e,
                    "a": section.a,
                    "i": section.i,
                    "density": section.density,
                    **({"name": section.name} if section.name else {}),
                    **({"material": section.material} if section.material else {}),
                    **({"depth_cm": section.depth_cm} if section.depth_cm > 0 else {}),
                    **({"width_cm": section.width_cm} if section.width_cm > 0 else {}),
                }
                for section in self.sections
            ],
            "loadcases": list(self.load_cases),
            "loadcombos": [
                {
                    "name": combination.name,
                    "factors": dict(combination.factors),
                    **({"eq": combination.equation} if combination.equation else {}),
                }
                for combination in self.load_combinations
            ],
            "nloads": [
                {"node": load.node, "lcase": load.lcase, "fx": load.fx, "fy": load.fy, "mz": load.mz}
                for load in self.nodal_loads
            ],
            "eloads": [
                (
                    {"elem": load.elem, "lcase": load.lcase, "dir": load.direction, "w1": load.w1, "w2": load.w2, **({"x1_m": load.x1_m, "x2_m": load.x2_m} if load.x2_m is not None else {})}
                    if load.type == "Distributed"
                    else {
                        "elem": load.elem,
                        "lcase": load.lcase,
                        "type": load.type,
                        "dir": load.direction,
                        "x_m": load.x_m,
                        **({"p": load.p} if load.type == "Point Force" else {"m": load.m}),
                    }
                )
                for load in self.element_loads
            ],
        }
