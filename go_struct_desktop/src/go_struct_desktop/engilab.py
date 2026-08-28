"""Importer for text-based EngiLab Frame.2D .fr2d models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


KGF_PER_KN = 1000.0 / 9.80665
KPA_PER_KSI = 6.894757e6
KILONEWTON_PER_KIP = 4.448221615
METRES_PER_FOOT = 0.3048
CM2_PER_IN2 = 6.4516
CM4_PER_IN4 = 41.62314256


class EngiLabImportError(ValueError):
    """Raised when a .fr2d text file cannot be translated into a frame model."""


@dataclass(frozen=True)
class EngiLabImport:
    model: dict[str, Any]
    source_path: Path
    warnings: tuple[str, ...] = ()


def installed_examples_directory() -> Path:
    return Path(r"C:\Program Files (x86)\EngiLab\EngiLab Frame.2D 2022 Lite\Examples")


def installed_example_files() -> tuple[Path, ...]:
    directory = installed_examples_directory()
    if not directory.is_dir():
        return ()
    return tuple(sorted(directory.glob("*.fr2d"), key=lambda path: path.name.lower()))


def import_engilab_frame(path: str | Path) -> EngiLabImport:
    source_path = Path(path)
    try:
        sections = _sections(source_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EngiLabImportError(f"Could not read {source_path.name}: {exc}") from exc
    required = {"UNITS", "MATERIALS", "SECTIONS", "NODES", "CONSTRAINTS", "ELEMENTS", "NODAL_LOADS", "ELEMENTAL_LOADS"}
    missing = sorted(required - sections.keys())
    if missing:
        raise EngiLabImportError(f"{source_path.name} is missing sections: {', '.join(missing)}")

    unit_kind = _unit_kind(sections["UNITS"])
    materials = _materials(sections["MATERIALS"])
    source_sections = _source_sections(sections["SECTIONS"])
    nodes = _nodes(sections["NODES"], unit_kind)
    warnings = _constraints(sections["CONSTRAINTS"], nodes)
    springs = _count(sections.get("SPRINGS", "0"), "springs")
    if springs:
        warnings.append(f"{springs} translational spring(s) were omitted because spring analysis is not available yet.")
    elements, converted_sections = _elements(sections["ELEMENTS"], materials, source_sections, unit_kind)
    load_factor, length_factor = _load_factors(unit_kind)
    nodal_loads = _nodal_loads(sections["NODAL_LOADS"], load_factor, length_factor)
    element_loads = _element_loads(sections["ELEMENTAL_LOADS"], load_factor, length_factor)
    project_info = {
        "name": f"EngiLab | {source_path.stem}",
        "project": "Imported EngiLab Frame.2D model",
        "company": "",
        "engineer": "",
        "location": "",
        "units": "kn_m",
        "source": "Imported from EngiLab Frame.2D .fr2d",
        "sourceFile": source_path.name,
        "sourceUnitSystem": unit_kind,
    }
    if warnings:
        project_info["importWarnings"] = list(warnings)
    return EngiLabImport(
        {
            "projectInfo": project_info,
            "settings": {"include_self_weight": False},
            "nodes": list(nodes.values()),
            "sections": converted_sections,
            "elements": elements,
            "loadcases": ["DL"],
            "loadcombos": [{"name": "Service", "factors": {"DL": 1.0}}],
            "nloads": nodal_loads,
            "eloads": element_loads,
        },
        source_path,
        tuple(warnings),
    )


def _sections(text: str) -> dict[str, str]:
    markers = list(re.finditer(r"^\*([A-Z_]+)\s*$", text, re.MULTILINE))
    if not markers or markers[0].group(1) != "ENGILAB":
        raise EngiLabImportError("This is not an EngiLab Frame.2D text file.")
    return {
        marker.group(1): text[marker.end() : markers[index + 1].start() if index + 1 < len(markers) else len(text)].strip()
        for index, marker in enumerate(markers)
    }


def _rows(content: str, label: str) -> list[list[str]]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        raise EngiLabImportError(f"{label} is empty.")
    try:
        count = int(lines[0])
    except ValueError as exc:
        raise EngiLabImportError(f"{label} count is invalid.") from exc
    values = lines[1:]
    if len(values) < count:
        raise EngiLabImportError(f"{label} has fewer rows than declared.")
    return [line.split() for line in values[-count:]]


def _count(content: str, label: str) -> int:
    rows = [line.strip() for line in content.splitlines() if line.strip()]
    if not rows:
        return 0
    try:
        return int(rows[0])
    except ValueError as exc:
        raise EngiLabImportError(f"{label} count is invalid.") from exc


def _unit_kind(content: str) -> str:
    if re.search(r"^Coordinates\s+m\s", content, re.MULTILINE):
        return "metric"
    if re.search(r"^Coordinates\s+ft\s", content, re.MULTILINE):
        return "us"
    return "consistent"


def _materials(content: str) -> dict[int, float]:
    rows = _rows(content, "materials")
    try:
        return {int(row[0]): float(row[1]) for row in rows}
    except (IndexError, ValueError) as exc:
        raise EngiLabImportError("Material rows must contain an id and elastic modulus.") from exc


def _source_sections(content: str) -> dict[int, tuple[float, float]]:
    rows = _rows(content, "sections")
    try:
        return {index + 1: (float(row[1]), float(row[2])) for index, row in enumerate(rows)}
    except (IndexError, ValueError) as exc:
        raise EngiLabImportError("Section rows must contain area and inertia.") from exc


def _nodes(content: str, unit_kind: str) -> dict[int, dict[str, Any]]:
    scale = METRES_PER_FOOT if unit_kind == "us" else 1.0
    try:
        return {
            int(row[0]): {"id": int(row[0]), "x": float(row[1]) * scale, "y": float(row[2]) * scale, "support": "Free"}
            for row in _rows(content, "nodes")
        }
    except (IndexError, ValueError) as exc:
        raise EngiLabImportError("Node rows must contain id, x, and y.") from exc


def _constraints(content: str, nodes: dict[int, dict[str, Any]]) -> list[str]:
    support_by_flags = {(1, 1, 1): "Fixed", (1, 1, 0): "Pinned", (0, 1, 0): "RollerX", (1, 0, 0): "RollerY"}
    warnings: list[str] = []
    for row in _rows(content, "constraints"):
        try:
            node_id, x_fixed, y_fixed, rotation_fixed = (int(value) for value in row[:4])
        except (ValueError, IndexError) as exc:
            raise EngiLabImportError("Constraint rows must contain node and three restraint flags.") from exc
        if node_id not in nodes:
            raise EngiLabImportError(f"Constraint references missing node {node_id}.")
        support = support_by_flags.get((x_fixed, y_fixed, rotation_fixed))
        if support is None:
            warnings.append(f"Constraint at node {node_id} could not be represented exactly and was imported as Free.")
            continue
        nodes[node_id]["support"] = support
    return warnings


def _elements(
    content: str,
    materials: dict[int, float],
    source_sections: dict[int, tuple[float, float]],
    unit_kind: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    release_by_flags = {(0, 0): "Rigid-Rigid", (1, 0): "Pin-Rigid", (0, 1): "Rigid-Pin", (1, 1): "Pin-Pin"}
    section_keys: list[tuple[int, int]] = []
    raw_elements: list[list[int]] = []
    for row in _rows(content, "elements"):
        try:
            values = [int(value) for value in row]
            material_id, section_id = values[1], values[2]
            if material_id not in materials or section_id not in source_sections:
                raise EngiLabImportError("An element references an undefined material or section.")
            key = (material_id, section_id)
            if key not in section_keys:
                section_keys.append(key)
            raw_elements.append(values)
        except (IndexError, ValueError) as exc:
            raise EngiLabImportError("Element rows are invalid.") from exc
    converted_sections = [_convert_section(index + 1, materials[key[0]], *source_sections[key[1]], unit_kind) for index, key in enumerate(section_keys)]
    elements: list[dict[str, Any]] = []
    for values in raw_elements:
        release = release_by_flags.get((values[-2], values[-1]))
        if release is None:
            raise EngiLabImportError(f"Element {values[0]} has an unsupported release definition.")
        elements.append(
            {
                "id": values[0],
                "n1": values[3],
                "n2": values[4],
                "sec": section_keys.index((values[1], values[2])) + 1,
                "release": release,
            }
        )
    return elements, converted_sections


def _convert_section(section_id: int, modulus: float, area: float, inertia: float, unit_kind: str) -> dict[str, Any]:
    if unit_kind == "metric":
        elastic_modulus, converted_area, converted_inertia = modulus * 1.0e9 / 9.80665, area, inertia
    elif unit_kind == "us":
        elastic_modulus = modulus * KPA_PER_KSI / 9.80665
        converted_area, converted_inertia = area * CM2_PER_IN2, inertia * CM4_PER_IN4
    else:
        elastic_modulus = modulus * 1000.0 / 9.80665
        converted_area, converted_inertia = area * 1.0e4, inertia * 1.0e8
    return {"id": section_id, "e": elastic_modulus, "a": converted_area, "i": converted_inertia, "density": 0.0}


def _load_factors(unit_kind: str) -> tuple[float, float]:
    if unit_kind == "us":
        return KILONEWTON_PER_KIP * KGF_PER_KN, METRES_PER_FOOT
    return KGF_PER_KN, 1.0


def _nodal_loads(content: str, load_factor: float, length_factor: float) -> list[dict[str, Any]]:
    try:
        return [
            {
                "node": int(row[0]),
                "lcase": "DL",
                "fx": float(row[1]) * load_factor,
                "fy": float(row[2]) * load_factor,
                "mz": float(row[3]) * load_factor * length_factor,
            }
            for row in _rows(content, "nodal loads")
        ]
    except (IndexError, ValueError) as exc:
        raise EngiLabImportError("Nodal load rows are invalid.") from exc


def _element_loads(content: str, load_factor: float, length_factor: float) -> list[dict[str, Any]]:
    try:
        return [
            {
                "elem": int(row[0]),
                "lcase": "DL",
                "type": "Distributed",
                "dir": "Local Y",
                "w1": float(row[-2]) * load_factor / length_factor,
                "w2": float(row[-1]) * load_factor / length_factor,
            }
            for row in _rows(content, "element loads")
        ]
    except (IndexError, ValueError) as exc:
        raise EngiLabImportError("Element load rows are invalid.") from exc
