"""Built-in, analysis-ready frame examples for learning the desktop workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class FrameExample:
    key: str
    title: str
    description: str
    build_model: Callable[[], dict[str, Any]]
    result_selection: str = "case:DL"
    diagram_mode: str = "m_kg_m"
    view_mode: str = "results"

    def model(self) -> dict[str, Any]:
        return self.build_model()


def _model(
    name: str,
    description: str,
    nodes: list[dict[str, Any]],
    elements: list[dict[str, Any]],
    loadcases: list[str],
    loadcombos: list[dict[str, Any]],
    nloads: list[dict[str, Any]],
    eloads: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "projectInfo": {
            "name": name,
            "project": "GO Struct built-in examples",
            "company": "",
            "engineer": "",
            "location": "",
            "units": "legacy_kg_m",
            "description": description,
        },
        "settings": {"include_self_weight": False},
        "nodes": nodes,
        "sections": [
            {"id": 1, "e": 2.0e9, "a": 1000.0, "i": 1000000.0, "density": 0.0},
            {"id": 2, "e": 2.0e9, "a": 1400.0, "i": 2200000.0, "density": 0.0},
        ],
        "elements": elements,
        "loadcases": loadcases,
        "loadcombos": loadcombos,
        "nloads": nloads,
        "eloads": eloads,
    }


def _cantilever_point_actions() -> dict[str, Any]:
    return _model(
        "Cantilever | Point Force and Moment",
        "Fixed cantilever with a member point force and point moment. Inspect V, M, and deflection.",
        [{"id": 1, "x": 0.0, "y": 0.0, "support": "Fixed"}, {"id": 2, "x": 5.0, "y": 0.0, "support": "Free"}],
        [{"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"}],
        ["DL"],
        [{"name": "Service", "factors": {"DL": 1.0}}],
        [],
        [
            {"elem": 1, "lcase": "DL", "type": "Point Force", "dir": "Local Y", "x_m": 3.0, "p": -15.0},
            {"elem": 1, "lcase": "DL", "type": "Point Moment", "x_m": 4.2, "m": 18.0},
        ],
    )


def _simply_supported_triangular_load() -> dict[str, Any]:
    return _model(
        "Simply Supported | Triangular Load",
        "Pinned and roller supports under a triangular distributed load. Use FBD to inspect reactions.",
        [{"id": 1, "x": 0.0, "y": 0.0, "support": "Pinned"}, {"id": 2, "x": 8.0, "y": 0.0, "support": "RollerX"}],
        [{"id": 1, "n1": 1, "n2": 2, "sec": 2, "release": "Rigid-Rigid"}],
        ["DL"],
        [{"name": "Service", "factors": {"DL": 1.0}}],
        [],
        [{"elem": 1, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": 0.0, "w2": -12.0}],
    )


def _portal_frame_combinations() -> dict[str, Any]:
    return _model(
        "Portal Frame | Load Combinations",
        "Rigid portal frame with dead, live, and wind cases. Compare Service and ULS combinations.",
        [
            {"id": 1, "x": 0.0, "y": 0.0, "support": "Fixed"},
            {"id": 2, "x": 8.0, "y": 0.0, "support": "Fixed"},
            {"id": 3, "x": 0.0, "y": 5.0, "support": "Free"},
            {"id": 4, "x": 8.0, "y": 5.0, "support": "Free"},
        ],
        [
            {"id": 1, "n1": 1, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 2, "n1": 2, "n2": 4, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 3, "n1": 3, "n2": 4, "sec": 2, "release": "Rigid-Rigid"},
        ],
        ["DL", "LL", "WL"],
        [
            {"name": "Service", "factors": {"DL": 1.0, "LL": 1.0, "WL": 0.7}},
            {"name": "ULS", "factors": {"DL": 1.2, "LL": 1.6, "WL": 1.0}},
        ],
        [{"node": 4, "lcase": "WL", "fx": 14.0, "fy": 0.0, "mz": 0.0}],
        [
            {"elem": 3, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -18.0, "w2": -18.0},
            {"elem": 3, "lcase": "LL", "type": "Point Force", "dir": "Global Y", "x_m": 4.0, "p": -20.0},
        ],
    )


def _released_beam() -> dict[str, Any]:
    return _model(
        "Released Beam | Fixed to Pin",
        "Propped beam with a Rigid-Pin member release. Compare the released end moment with the rigid case.",
        [{"id": 1, "x": 0.0, "y": 0.0, "support": "Fixed"}, {"id": 2, "x": 6.0, "y": 0.0, "support": "RollerX"}],
        [{"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Pin"}],
        ["DL"],
        [{"name": "Service", "factors": {"DL": 1.0}}],
        [],
        [{"elem": 1, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -10.0, "w2": -10.0}],
    )


def _reaction_check() -> dict[str, Any]:
    return _model(
        "Reaction Check | Two-span Beam",
        "Two-span continuous beam for checking support reactions and equilibrium in the FBD view.",
        [
            {"id": 1, "x": 0.0, "y": 0.0, "support": "Pinned"},
            {"id": 2, "x": 4.0, "y": 0.0, "support": "Free"},
            {"id": 3, "x": 8.0, "y": 0.0, "support": "RollerX"},
        ],
        [
            {"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 2, "n1": 2, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
        ],
        ["DL", "LL"],
        [{"name": "Service", "factors": {"DL": 1.0, "LL": 1.0}}],
        [{"node": 2, "lcase": "LL", "fx": 0.0, "fy": -16.0, "mz": 0.0}],
        [
            {"elem": 1, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -6.0, "w2": -6.0},
            {"elem": 2, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -12.0, "w2": -12.0},
        ],
    )


FRAME_EXAMPLES: tuple[FrameExample, ...] = (
    FrameExample("cantilever_point_actions", "1. Cantilever: Point Force + Moment", "Point force and point moment on a fixed cantilever.", _cantilever_point_actions, "case:DL", "all"),
    FrameExample("simply_supported_triangular", "2. Simply Supported: Triangular Load", "Triangular member load with pinned and roller reactions.", _simply_supported_triangular_load, "case:DL", "m_kg_m"),
    FrameExample("portal_combinations", "3. Portal Frame: Load Combinations", "DL, LL, and WL compared in Service and ULS combinations.", _portal_frame_combinations, "combo:ULS", "all"),
    FrameExample("released_beam", "4. Released Beam: Fixed to Pin", "Rigid-Pin release under a distributed load.", _released_beam, "case:DL", "m_kg_m"),
    FrameExample("reaction_check", "5. Reaction Check: Two-span Beam", "FBD opens directly to inspect applied loads, reactions, and equilibrium.", _reaction_check, "combo:Service", "none", "fbd"),
)
