"""Built-in, analysis-ready frame examples for learning the desktop workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


KGF_PER_KN = 1000.0 / 9.80665
KGF_PER_GPA_M2 = 1.0e9 / 9.80665


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


def _engilab_metric_model(
    source_file: str,
    name: str,
    description: str,
    nodes: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    elements: list[dict[str, Any]],
    nloads_kn: list[dict[str, Any]],
    eloads_kn: list[dict[str, Any]],
) -> dict[str, Any]:
    """Adapt an EngiLab Metric sample without bundling its original .fr2d file."""
    model = _model(
        name,
        description,
        nodes,
        elements,
        ["DL"],
        [{"name": "Service", "factors": {"DL": 1.0}}],
        nloads_kn,
        eloads_kn,
    )
    model["projectInfo"].update(
        {
            "units": "kn_m",
            "source": "Adapted from an EngiLab Frame.2D 2022 Lite Metric example",
            "sourceFile": source_file,
        }
    )
    model["sections"] = [
        {
            "id": int(section["id"]),
            "e": float(section["e_gpa"]) * KGF_PER_GPA_M2,
            "a": float(section["a_cm2"]),
            "i": float(section["i_cm4"]),
            "density": 0.0,
        }
        for section in sections
    ]
    model["nloads"] = [
        {
            **load,
            "fx": float(load.get("fx", 0.0)) * KGF_PER_KN,
            "fy": float(load.get("fy", 0.0)) * KGF_PER_KN,
            "mz": float(load.get("mz", 0.0)) * KGF_PER_KN,
        }
        for load in nloads_kn
    ]
    converted_loads: list[dict[str, Any]] = []
    for load in eloads_kn:
        item = dict(load)
        for key in ("w1", "w2", "p", "m"):
            if key in item:
                item[key] = float(item[key]) * KGF_PER_KN
        converted_loads.append(item)
    model["eloads"] = converted_loads
    return model


def _engilab_cantilever_beam_1() -> dict[str, Any]:
    return _engilab_metric_model(
        "Cantilever Beam 1 [Metric].fr2d",
        "EngiLab Cantilever Beam 1",
        "Adapted Metric cantilever: point load at the intermediate node and UDL on both members.",
        [
            {"id": 1, "x": 0.0, "y": 0.0, "support": "Fixed"},
            {"id": 2, "x": 4.0, "y": 0.0, "support": "Free"},
            {"id": 3, "x": 2.0, "y": 0.0, "support": "Free"},
        ],
        [{"id": 1, "e_gpa": 210.0, "a_cm2": 72.73, "i_cm4": 16265.63}],
        [
            {"id": 1, "n1": 1, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 2, "n1": 3, "n2": 2, "sec": 1, "release": "Rigid-Rigid"},
        ],
        [{"node": 3, "lcase": "DL", "fx": 0.0, "fy": -35.0, "mz": 0.0}],
        [
            {"elem": 1, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -20.0, "w2": -20.0},
            {"elem": 2, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -20.0, "w2": -20.0},
        ],
    )


def _engilab_fixed_pinned_beam() -> dict[str, Any]:
    return _engilab_metric_model(
        "Fixed-Pinned Beam [Metric].fr2d",
        "EngiLab Fixed-Pinned Beam",
        "Adapted Metric propped beam with a fixed support, roller support, and uniform load.",
        [{"id": 1, "x": 2.0, "y": 0.0, "support": "Fixed"}, {"id": 2, "x": 10.0, "y": 0.0, "support": "RollerX"}],
        [{"id": 1, "e_gpa": 210.0, "a_cm2": 28.7, "i_cm4": 4961.0}],
        [{"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"}],
        [],
        [{"elem": 1, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -25.0, "w2": -25.0}],
    )


def _engilab_frame_2() -> dict[str, Any]:
    return _engilab_metric_model(
        "Frame 2 [Metric].fr2d",
        "EngiLab Frame 2 | Gable Frame",
        "Adapted Metric gable frame with a horizontal point load and two triangular roof loads.",
        [
            {"id": 1, "x": 0.0, "y": 0.0, "support": "Fixed"},
            {"id": 2, "x": 0.0, "y": 5.0, "support": "Free"},
            {"id": 3, "x": 8.0, "y": 8.0, "support": "Free"},
            {"id": 4, "x": 16.0, "y": 5.0, "support": "Free"},
            {"id": 5, "x": 16.0, "y": 0.0, "support": "Fixed"},
        ],
        [
            {"id": 1, "e_gpa": 29.0, "a_cm2": 2500.0, "i_cm4": 520833.0},
            {"id": 2, "e_gpa": 29.0, "a_cm2": 1500.0, "i_cm4": 312500.0},
        ],
        [
            {"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 2, "n1": 4, "n2": 5, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 3, "n1": 2, "n2": 3, "sec": 2, "release": "Rigid-Rigid"},
            {"id": 4, "n1": 3, "n2": 4, "sec": 2, "release": "Rigid-Rigid"},
        ],
        [{"node": 2, "lcase": "DL", "fx": 50.0, "fy": 0.0, "mz": 0.0}],
        [
            {"elem": 3, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -2.5, "w2": -5.0},
            {"elem": 4, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -5.0, "w2": -2.5},
        ],
    )


def _engilab_gerber_beam_1() -> dict[str, Any]:
    return _engilab_metric_model(
        "Gerber Beam 1 [Metric].fr2d",
        "EngiLab Gerber Beam 1",
        "Adapted Metric Gerber beam with an internal member-end release and three supports.",
        [
            {"id": 1, "x": 1.0, "y": 4.0, "support": "Pinned"},
            {"id": 2, "x": 2.5, "y": 4.0, "support": "Free"},
            {"id": 3, "x": 3.5, "y": 4.0, "support": "RollerX"},
            {"id": 4, "x": 6.0, "y": 4.0, "support": "RollerX"},
        ],
        [{"id": 1, "e_gpa": 210.0, "a_cm2": 20.7, "i_cm4": 1598.0}],
        [
            {"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Pin"},
            {"id": 2, "n1": 2, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 3, "n1": 3, "n2": 4, "sec": 1, "release": "Rigid-Rigid"},
        ],
        [],
        [
            {"elem": 1, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -10.0, "w2": -10.0},
            {"elem": 2, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -10.0, "w2": -10.0},
            {"elem": 3, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -10.0, "w2": -10.0},
        ],
    )


def _engilab_two_span_continuous_beam() -> dict[str, Any]:
    return _engilab_metric_model(
        "Two-Span Continuous Beam [Metric].fr2d",
        "EngiLab Two-Span Continuous Beam",
        "Adapted Metric two-span beam with a nodal point load, nodal moment, UDL, and support reactions.",
        [
            {"id": 1, "x": 4.0, "y": 0.0, "support": "Fixed"},
            {"id": 2, "x": 6.0, "y": 0.0, "support": "Free"},
            {"id": 3, "x": 7.0, "y": 0.0, "support": "Free"},
            {"id": 4, "x": 10.0, "y": 0.0, "support": "RollerX"},
            {"id": 5, "x": 13.0, "y": 0.0, "support": "Free"},
            {"id": 6, "x": 16.0, "y": 0.0, "support": "RollerX"},
        ],
        [{"id": 1, "e_gpa": 210.0, "a_cm2": 200.0, "i_cm4": 5000.0}],
        [
            {"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 2, "n1": 2, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 3, "n1": 3, "n2": 4, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 4, "n1": 4, "n2": 5, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 5, "n1": 5, "n2": 6, "sec": 1, "release": "Rigid-Rigid"},
        ],
        [
            {"node": 2, "lcase": "DL", "fx": 0.0, "fy": 0.0, "mz": -80.0},
            {"node": 3, "lcase": "DL", "fx": 0.0, "fy": -40.0, "mz": 0.0},
        ],
        [{"elem": 4, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -10.0, "w2": -10.0}],
    )


BUILT_IN_FRAME_EXAMPLES: tuple[FrameExample, ...] = (
    FrameExample("cantilever_point_actions", "1. Cantilever: Point Force + Moment", "Point force and point moment on a fixed cantilever.", _cantilever_point_actions, "case:DL", "all"),
    FrameExample("simply_supported_triangular", "2. Simply Supported: Triangular Load", "Triangular member load with pinned and roller reactions.", _simply_supported_triangular_load, "case:DL", "m_kg_m"),
    FrameExample("portal_combinations", "3. Portal Frame: Load Combinations", "DL, LL, and WL compared in Service and ULS combinations.", _portal_frame_combinations, "combo:ULS", "all"),
    FrameExample("released_beam", "4. Released Beam: Fixed to Pin", "Rigid-Pin release under a distributed load.", _released_beam, "case:DL", "m_kg_m"),
    FrameExample("reaction_check", "5. Reaction Check: Two-span Beam", "FBD opens directly to inspect applied loads, reactions, and equilibrium.", _reaction_check, "combo:Service", "none", "fbd"),
)

ENGILAB_REFERENCE_EXAMPLES: tuple[FrameExample, ...] = (
    FrameExample("engilab_cantilever_beam_1", "Cantilever Beam 1", "EngiLab Frame.2D Metric reference model.", _engilab_cantilever_beam_1, "case:DL", "all"),
    FrameExample("engilab_fixed_pinned_beam", "Fixed-Pinned Beam", "EngiLab Frame.2D Metric reference model.", _engilab_fixed_pinned_beam, "case:DL", "m_kg_m"),
    FrameExample("engilab_frame_2", "Frame 2: Gable Frame", "EngiLab Frame.2D Metric reference model.", _engilab_frame_2, "case:DL", "all"),
    FrameExample("engilab_gerber_beam_1", "Gerber Beam 1", "EngiLab Frame.2D Metric reference model.", _engilab_gerber_beam_1, "case:DL", "m_kg_m"),
    FrameExample("engilab_two_span_continuous_beam", "Two-Span Continuous Beam", "EngiLab Frame.2D Metric reference model.", _engilab_two_span_continuous_beam, "case:DL", "none", "fbd"),
)

FRAME_EXAMPLES = BUILT_IN_FRAME_EXAMPLES + ENGILAB_REFERENCE_EXAMPLES
