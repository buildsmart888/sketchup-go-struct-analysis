from __future__ import annotations

import math

import pytest

from go_struct_core import (
    GeneratedWarehouse,
    LoadCombination3D,
    Member3D,
    NodalLoad3D,
    OpenSeesPyBackend,
    Node3D,
    OptimizationSettings,
    Section3D,
    WarehouseOptimizer,
    WarehouseProject,
    WarehouseLoads,
    analyze_warehouse_data,
    candidate_hash,
    generate_warehouse,
    preliminary_checks,
    preliminary_cost,
    warehouse_equilibrium,
)
from go_struct_core.warehouse import _truss_web_layout


def test_warehouse_schema_round_trip_and_all_topologies_generate() -> None:
    for topology in ("warren", "pratt", "howe", "pitched"):
        raw = WarehouseProject.default().to_dict()
        raw["geometry"].update({"topology": topology, "bay_count": 2, "panel_count": 6})
        project = WarehouseProject.from_dict(raw)
        generated = generate_warehouse(project)
        assert WarehouseProject.from_dict(project.to_dict()).geometry.topology == topology
        assert generated.nodes
        assert generated.members
        assert len({node.id for node in generated.nodes}) == len(generated.nodes)
        assert all(member.i != member.j for member in generated.members)
        assert len({frozenset((member.i, member.j)) for member in generated.members}) == len(generated.members)


def test_truss_web_patterns_use_correct_diagonal_direction_and_never_fan_to_ridge() -> None:
    warren = _truss_web_layout("warren", 8)
    warren_diagonals = [item for item in warren if item[1] != item[3]]
    assert warren_diagonals == [
        ("bottom", 0, "top", 1), ("top", 1, "bottom", 2), ("bottom", 2, "top", 3), ("top", 3, "bottom", 4),
        ("bottom", 4, "top", 5), ("top", 5, "bottom", 6), ("bottom", 6, "top", 7), ("top", 7, "bottom", 8),
    ]
    pratt = _truss_web_layout("pratt", 8)
    howe = _truss_web_layout("howe", 8)
    # On the left half, Pratt falls toward centre and Howe rises away from it.
    assert ("top", 1, "bottom", 2) in pratt
    assert ("bottom", 1, "top", 2) in howe
    # The pitched/Fink layout is mirrored W-web: it does not make a fan by
    # connecting every bottom node to the ridge.
    pitched = _truss_web_layout("pitched", 8)
    ridge = 4
    assert sum(1 for item in pitched if (item[0] == "top" and item[1] == ridge) or (item[2] == "top" and item[3] == ridge)) <= 3


def test_roof_equivalent_loads_preserve_horizontal_plan_resultant() -> None:
    project = WarehouseProject.default()
    generated = generate_warehouse(project)
    total_dead = sum(load.fz_kn for load in generated.loads if load.case == "DL")
    total_live = sum(load.fz_kn for load in generated.loads if load.case == "LL")
    area = project.geometry.width_m * project.geometry.length_m
    assert total_dead == pytest.approx(-area * project.loads.roof_dead_kn_m2)
    assert total_live == pytest.approx(-area * project.loads.roof_live_kn_m2)


def test_truss_depth_changes_top_chord_geometry_without_reducing_clear_height() -> None:
    shallow_raw = WarehouseProject.default().to_dict()
    deep_raw = WarehouseProject.default().to_dict()
    shallow_raw["geometry"]["truss_depth_m"] = 1.0
    deep_raw["geometry"]["truss_depth_m"] = 2.0
    shallow = generate_warehouse(WarehouseProject.from_dict(shallow_raw))
    deep = generate_warehouse(WarehouseProject.from_dict(deep_raw))
    shallow_top = max(node.z_m for node in shallow.nodes)
    deep_top = max(node.z_m for node in deep.nodes)
    assert deep_top - shallow_top == pytest.approx(1.0)
    assert min(node.z_m for node in deep.nodes if node.z_m > 0.0) == pytest.approx(WarehouseProject.from_dict(deep_raw).geometry.eave_height_m)


def test_native_3d_cantilever_matches_closed_form_deflection_and_reaction() -> None:
    section = Section3D("test", area_m2=0.02, iy_m4=8.0e-5, iz_m4=8.0e-5, j_m4=1.0e-5, zy_m3=8.0e-4, zz_m3=8.0e-4)
    project = WarehouseProject(geometry=WarehouseProject.default().geometry, sections=(section,), loads=WarehouseLoads(include_self_weight=False), combinations=(LoadCombination3D("Service", {"DL": 1.0}),))
    generated = GeneratedWarehouse(
        project,
        (Node3D(1, 0.0, 0.0, 0.0, "Fixed"), Node3D(2, 3.0, 0.0, 0.0)),
        (Member3D(1, 1, 2, "test", "test", "frame"),),
        (NodalLoad3D(2, "DL", fz_kn=-10.0),),
        {},
    )
    result = analyze_warehouse_data(generated)
    assert result["ok"]
    expected_deflection = -10_000.0 * 3.0**3 / (3.0 * section.e_pa * section.iy_m4)
    node_two = result["cases"]["DL"]["nodes"][1]
    node_one = result["cases"]["DL"]["nodes"][0]
    assert node_two["displacements"][2] == pytest.approx(expected_deflection)
    assert node_one["reactions_kn"][2] == pytest.approx(10.0)


def test_generated_warehouse_analyzes_and_cost_and_checks_are_auditable() -> None:
    generated = generate_warehouse(WarehouseProject.default())
    result = analyze_warehouse_data(generated)
    checks = preliminary_checks(generated, result)
    cost = preliminary_cost(generated, result)
    assert result["ok"]
    assert result["model_summary"]["dofs"] == len(generated.nodes) * 6
    assert math.isfinite(checks["utilization"])
    assert cost["steel_mass_kg"] > 0
    assert cost["total_thb"] > cost["breakdown_thb"]["steel_material"]
    assert "conceptual_foundations" in cost["breakdown_thb"]


def test_warehouse_equilibrium_reports_force_and_moment_balance_and_load_trace() -> None:
    generated = generate_warehouse(WarehouseProject.default())
    audit = warehouse_equilibrium(generated, analyze_warehouse_data(generated))
    assert audit["sets"]
    assert all(item["balanced"] for item in audit["sets"])
    assert audit["load_distribution"]["DL"]["nodes"] > 0
    assert audit["load_distribution"]["WXP"]["force_kn"][0] > 0.0


@pytest.mark.skipif(not OpenSeesPyBackend.available(), reason="OpenSeesPy optional backend is not installed")
def test_openseespy_matches_native_first_order_warehouse_displacements() -> None:
    generated = generate_warehouse(WarehouseProject.default())
    native = analyze_warehouse_data(generated)
    opensees = analyze_warehouse_data(generated, OpenSeesPyBackend())
    assert native["ok"] and opensees["ok"]
    native_max = max(abs(value) for node in native["cases"]["DL"]["nodes"] for value in node["displacements"])
    opensees_max = max(abs(value) for node in opensees["cases"]["DL"]["nodes"] for value in node["displacements"])
    assert opensees_max == pytest.approx(native_max)


def test_optimizer_cache_and_seed_are_deterministic() -> None:
    project = WarehouseProject.default()
    first = WarehouseOptimizer(project)
    result_a = first.run(OptimizationSettings(population_size=4, generations=0, seed=123))
    result_b = WarehouseOptimizer(project).run(OptimizationSettings(population_size=4, generations=0, seed=123))
    assert [item["id"] for item in result_a["population"]] == [item["id"] for item in result_b["population"]]
    candidate = result_a["population"][0]["candidate"]
    from go_struct_core import WarehouseCandidate

    repeated = WarehouseCandidate(**candidate)
    evaluation = first.evaluate(repeated)
    assert evaluation["cache_hit"]
    assert evaluation["id"] == candidate_hash(repeated, project)
