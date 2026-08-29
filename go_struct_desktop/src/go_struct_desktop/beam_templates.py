"""Pure, editable model templates for common one-dimensional beam systems."""

from __future__ import annotations

from collections.abc import Sequence
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
    return continuous_beam_from_spans([span_m] * span_count)


def continuous_beam_from_spans(span_lengths: Sequence[float]) -> dict[str, Any]:
    """Create a continuous beam with independent editable lengths for every span."""
    spans = [float(length) for length in span_lengths]
    if len(spans) < 2:
        raise ValueError("Continuous beam requires at least two spans")
    if any(length <= 0.0 for length in spans):
        raise ValueError("Continuous beam span lengths must be greater than zero")
    stations = [0.0]
    for length in spans:
        stations.append(stations[-1] + length)
    nodes = [
        {"id": index + 1, "x": station, "y": 0.0, "support": "Pinned" if index < len(spans) else "RollerX"}
        for index, station in enumerate(stations)
    ]
    elements = [{"id": index + 1, "n1": index + 1, "n2": index + 2, "sec": 1, "release": "Rigid-Rigid"} for index in range(len(spans))]
    return _base(f"Continuous Beam | {len(spans)} spans", nodes, elements)
