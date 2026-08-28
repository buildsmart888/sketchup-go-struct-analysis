"""Pure, editable model templates for common one-dimensional beam systems."""

from __future__ import annotations

from typing import Any


def _base(name: str, nodes: list[dict[str, Any]], elements: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "projectInfo": {"name": name, "analysisType": "Beam", "units": "legacy_kg_m", "project": "", "company": "", "engineer": "", "location": ""},
        "settings": {"include_self_weight": False},
        "nodes": nodes,
        "sections": [{"id": 1, "e": 2.0e9, "a": 1000.0, "i": 1000000.0, "density": 0.0}],
        "elements": elements,
        "loadcases": ["DL"],
        "loadcombos": [{"name": "Service", "factors": {"DL": 1.0}}],
        "nloads": [],
        "eloads": [],
    }


def cantilever_template(span_m: float = 5.0) -> dict[str, Any]:
    return _base(
        "Cantilever Beam",
        [{"id": 1, "x": 0.0, "y": 0.0, "support": "Fixed"}, {"id": 2, "x": span_m, "y": 0.0, "support": "Free"}],
        [{"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"}],
    )


def simply_supported_template(span_m: float = 6.0) -> dict[str, Any]:
    return _base(
        "Simply Supported Beam",
        [{"id": 1, "x": 0.0, "y": 0.0, "support": "Pinned"}, {"id": 2, "x": span_m, "y": 0.0, "support": "RollerX"}],
        [{"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"}],
    )


def continuous_beam_template(span_count: int = 2, span_m: float = 5.0) -> dict[str, Any]:
    if span_count < 2:
        raise ValueError("Continuous beam requires at least two spans")
    nodes = [
        {"id": index + 1, "x": index * span_m, "y": 0.0, "support": "Pinned" if index == 0 else "RollerX" if index == span_count else "Free"}
        for index in range(span_count + 1)
    ]
    elements = [{"id": index + 1, "n1": index + 1, "n2": index + 2, "sec": 1, "release": "Rigid-Rigid"} for index in range(span_count)]
    return _base(f"Continuous Beam | {span_count} spans", nodes, elements)
