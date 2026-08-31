"""Deterministic mixed-variable Pareto optimization for Warehouse3D."""

from __future__ import annotations

import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .warehouse import WarehouseProject, generate_warehouse
from .warehouse_analysis import analyze_warehouse_data
from .warehouse_evaluation import CostCatalog, PreliminaryLimits, preliminary_checks, preliminary_cost


@dataclass(frozen=True)
class WarehouseCandidate:
    topology: str
    bay_count: int
    panel_count: int
    truss_depth_m: float
    roof_slope_deg: float
    column_scale: float
    chord_scale: float
    web_scale: float

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class OptimizationSettings:
    population_size: int = 24
    generations: int = 12
    seed: int = 11
    workers: int = 1
    engine: str = "pymoo"


def candidate_hash(candidate: WarehouseCandidate, project: WarehouseProject) -> str:
    payload = {"candidate": candidate.to_dict(), "project": project.to_dict()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]


class WarehouseOptimizer:
    """Small NSGA-II-style optimizer with cache, cancellation and progress hooks."""

    def __init__(self, project: WarehouseProject | Mapping[str, Any], limits: PreliminaryLimits | Mapping[str, Any] | None = None, catalog: CostCatalog | Mapping[str, Any] | None = None) -> None:
        self.project = project if isinstance(project, WarehouseProject) else WarehouseProject.from_dict(project)
        self.limits = limits if isinstance(limits, PreliminaryLimits) else PreliminaryLimits.from_dict(limits)
        self.catalog = catalog if isinstance(catalog, CostCatalog) else CostCatalog.from_dict(catalog)
        self.cache: dict[str, dict[str, Any]] = {}

    def evaluate(self, candidate: WarehouseCandidate) -> dict[str, Any]:
        key = candidate_hash(candidate, self.project)
        if key in self.cache:
            return {**self.cache[key], "cache_hit": True}
        raw = self.project.to_dict()
        raw_geometry = raw["geometry"]
        raw_geometry.update({
            "topology": candidate.topology,
            "bay_count": candidate.bay_count,
            "panel_count": candidate.panel_count,
            "truss_depth_m": candidate.truss_depth_m,
            "roof_slope_deg": candidate.roof_slope_deg,
        })
        for section in raw["sections"]:
            scale = candidate.column_scale if section["id"] == "column" else candidate.chord_scale if section["id"] == "chord" else candidate.web_scale if section["id"] in {"web", "bracing"} else 1.0
            for property_name in ("area_m2", "iy_m4", "iz_m4", "j_m4", "zy_m3", "zz_m3"):
                section[property_name] *= scale
        try:
            model = WarehouseProject.from_dict(raw)
            generated = generate_warehouse(model)
            analysis = analyze_warehouse_data(generated)
            checks = preliminary_checks(generated, analysis, self.limits)
            cost = preliminary_cost(generated, analysis, self.catalog)
            result = {
                "id": key,
                "candidate": candidate.to_dict(),
                "feasible": checks["feasible"],
                "objectives": [cost["total_thb"], cost["steel_mass_kg"], checks["utilization"]],
                "cost": cost,
                "checks": checks,
                "analysis_summary": analysis.get("model_summary", {}),
                "analysis_error": analysis.get("error"),
                "cache_hit": False,
            }
        except Exception as exc:  # Candidate failures must be represented, not abort the run.
            result = {"id": key, "candidate": candidate.to_dict(), "feasible": False, "objectives": [float("inf")] * 3, "cost": {}, "checks": {"utilization": float("inf"), "reasons": [str(exc)]}, "analysis_summary": {}, "analysis_error": str(exc), "cache_hit": False}
        self.cache[key] = result
        return result

    def run(self, settings: OptimizationSettings | None = None, on_progress: Callable[[dict[str, Any]], None] | None = None, cancelled: Callable[[], bool] | None = None) -> dict[str, Any]:
        settings = settings or OptimizationSettings()
        if settings.engine == "pymoo":
            try:
                return self._run_pymoo(settings, on_progress, cancelled)
            except ImportError:
                pass
        return self._run_native(settings, on_progress, cancelled)

    def _run_native(self, settings: OptimizationSettings, on_progress: Callable[[dict[str, Any]], None] | None, cancelled: Callable[[], bool] | None) -> dict[str, Any]:
        rng = random.Random(settings.seed)
        population = [self._random_candidate(rng) for _ in range(settings.population_size)]
        history: list[dict[str, Any]] = []
        for generation in range(settings.generations + 1):
            evaluated = self._evaluate_many(population, settings.workers)
            fronts = _non_dominated_fronts(evaluated)
            pareto = fronts[0] if fronts else []
            feasible = [item for item in evaluated if item["feasible"]]
            snapshot = {"generation": generation, "evaluated": len(evaluated), "feasible": len(feasible), "pareto": len(pareto), "best_cost_thb": min((item["objectives"][0] for item in feasible), default=None)}
            history.append(snapshot)
            if on_progress:
                on_progress(snapshot)
            if generation == settings.generations or (cancelled and cancelled()):
                return {"ok": True, "cancelled": bool(cancelled and cancelled()), "seed": settings.seed, "evaluations": len(self.cache), "pareto": pareto, "population": evaluated, "history": history}
            population = self._next_generation(population, evaluated, rng, settings.population_size)
        raise AssertionError("unreachable")

    def _run_pymoo(self, settings: OptimizationSettings, on_progress: Callable[[dict[str, Any]], None] | None, cancelled: Callable[[], bool] | None) -> dict[str, Any]:
        """Run the requested mixed-variable NSGA-II engine when pymoo is available."""
        from pymoo.algorithms.moo.nsga2 import RankAndCrowdingSurvival
        from pymoo.core.mixed import MixedVariableGA
        from pymoo.core.problem import ElementwiseProblem
        from pymoo.core.variable import Choice, Integer, Real
        from pymoo.optimize import minimize

        owner = self

        class Problem(ElementwiseProblem):
            def __init__(self) -> None:
                super().__init__(
                    vars={
                        "topology": Choice(options=["warren", "pratt", "howe", "pitched"]),
                        "bay_count": Integer(bounds=(2, 6)),
                        "panel_count": Choice(options=[4, 6, 8, 10, 12]),
                        "truss_depth_m": Real(bounds=(0.8, 3.5)),
                        "roof_slope_deg": Real(bounds=(5.0, 20.0)),
                        "column_scale": Choice(options=[0.8, 1.0, 1.25, 1.5]),
                        "chord_scale": Choice(options=[0.8, 1.0, 1.25, 1.5]),
                        "web_scale": Choice(options=[0.8, 1.0, 1.25]),
                    },
                    n_obj=3,
                    n_ieq_constr=1,
                )

            def _evaluate(self, values: Mapping[str, Any], out: dict[str, Any], *args: Any, **kwargs: Any) -> None:
                candidate = WarehouseCandidate(
                    topology=str(values["topology"]), bay_count=int(values["bay_count"]), panel_count=int(values["panel_count"]),
                    truss_depth_m=float(values["truss_depth_m"]), roof_slope_deg=float(values["roof_slope_deg"]),
                    column_scale=float(values["column_scale"]), chord_scale=float(values["chord_scale"]), web_scale=float(values["web_scale"]),
                )
                result = owner.evaluate(candidate)
                out["F"] = result["objectives"]
                out["G"] = [float(result["checks"].get("utilization", float("inf"))) - 1.0]

        # pymoo's numeric duplicate eliminator cannot compare mapping-backed mixed variables.
        # Candidate hashing below still records duplicate evaluations deterministically.
        algorithm = MixedVariableGA(pop_size=settings.population_size, survival=RankAndCrowdingSurvival())
        result = minimize(Problem(), algorithm, ("n_gen", settings.generations + 1), seed=settings.seed, verbose=False)
        if cancelled and cancelled():
            return {"ok": True, "cancelled": True, "engine": "pymoo", "seed": settings.seed, "evaluations": len(self.cache), "pareto": [], "population": [], "history": []}
        population: list[dict[str, Any]] = []
        for values in result.pop.get("X"):
            candidate = WarehouseCandidate(
                topology=str(values["topology"]), bay_count=int(values["bay_count"]), panel_count=int(values["panel_count"]),
                truss_depth_m=float(values["truss_depth_m"]), roof_slope_deg=float(values["roof_slope_deg"]),
                column_scale=float(values["column_scale"]), chord_scale=float(values["chord_scale"]), web_scale=float(values["web_scale"]),
            )
            population.append(self.evaluate(candidate))
        pareto = _non_dominated_fronts(population)[0] if population else []
        snapshot = {"generation": settings.generations, "evaluated": len(population), "feasible": sum(item["feasible"] for item in population), "pareto": len(pareto), "best_cost_thb": min((item["objectives"][0] for item in population if item["feasible"]), default=None)}
        if on_progress:
            on_progress(snapshot)
        return {"ok": True, "cancelled": False, "engine": "pymoo", "seed": settings.seed, "evaluations": len(self.cache), "pareto": pareto, "population": population, "history": [snapshot]}

    def _evaluate_many(self, candidates: list[WarehouseCandidate], workers: int) -> list[dict[str, Any]]:
        if workers <= 1:
            return [self.evaluate(candidate) for candidate in candidates]
        with ThreadPoolExecutor(max_workers=workers) as executor:
            return list(executor.map(self.evaluate, candidates))

    def _random_candidate(self, rng: random.Random) -> WarehouseCandidate:
        return WarehouseCandidate(
            topology=rng.choice(("warren", "pratt", "howe", "pitched")),
            bay_count=rng.randint(2, 6),
            panel_count=rng.choice((4, 6, 8, 10, 12)),
            truss_depth_m=round(rng.uniform(0.8, 3.5), 3),
            roof_slope_deg=round(rng.uniform(5.0, 20.0), 3),
            column_scale=rng.choice((0.8, 1.0, 1.25, 1.5)),
            chord_scale=rng.choice((0.8, 1.0, 1.25, 1.5)),
            web_scale=rng.choice((0.8, 1.0, 1.25)),
        )

    def _next_generation(self, population: list[WarehouseCandidate], evaluated: list[dict[str, Any]], rng: random.Random, size: int) -> list[WarehouseCandidate]:
        ranked = _rank_and_crowding(evaluated)
        lookup = {item["id"]: candidate for item, candidate in zip(evaluated, population, strict=True)}
        children: list[WarehouseCandidate] = []
        while len(children) < size:
            parent_a = lookup[_tournament(ranked, rng)["id"]]
            parent_b = lookup[_tournament(ranked, rng)["id"]]
            children.append(self._mutate(self._crossover(parent_a, parent_b, rng), rng))
        combined = evaluated + self._evaluate_many(children, 1)
        combined_candidates = population + children
        selected = _environmental_selection(combined, size)
        candidate_by_id = {item["id"]: candidate for item, candidate in zip(combined, combined_candidates, strict=True)}
        return [candidate_by_id[item["id"]] for item in selected]

    def _crossover(self, first: WarehouseCandidate, second: WarehouseCandidate, rng: random.Random) -> WarehouseCandidate:
        values = {}
        for name in first.__dataclass_fields__:
            values[name] = getattr(first if rng.random() < 0.5 else second, name)
        return WarehouseCandidate(**values)

    def _mutate(self, candidate: WarehouseCandidate, rng: random.Random) -> WarehouseCandidate:
        values = candidate.to_dict()
        if rng.random() < 0.25:
            values["topology"] = rng.choice(("warren", "pratt", "howe", "pitched"))
        if rng.random() < 0.25:
            values["bay_count"] = max(2, min(6, values["bay_count"] + rng.choice((-1, 1))))
        if rng.random() < 0.25:
            values["panel_count"] = rng.choice((4, 6, 8, 10, 12))
        for name, low, high in (("truss_depth_m", 0.8, 3.5), ("roof_slope_deg", 5.0, 20.0)):
            if rng.random() < 0.3:
                values[name] = round(max(low, min(high, values[name] + rng.uniform(-0.4, 0.4))), 3)
        for name, choices in (("column_scale", (0.8, 1.0, 1.25, 1.5)), ("chord_scale", (0.8, 1.0, 1.25, 1.5)), ("web_scale", (0.8, 1.0, 1.25))):
            if rng.random() < 0.25:
                values[name] = rng.choice(choices)
        return WarehouseCandidate(**values)


def _dominates(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    if first["feasible"] != second["feasible"]:
        return bool(first["feasible"])
    if not first["feasible"]:
        return float(first["objectives"][2]) < float(second["objectives"][2])
    values_a, values_b = first["objectives"], second["objectives"]
    return all(a <= b for a, b in zip(values_a, values_b, strict=True)) and any(a < b for a, b in zip(values_a, values_b, strict=True))


def _non_dominated_fronts(items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    remaining = list(items)
    fronts: list[list[dict[str, Any]]] = []
    while remaining:
        front = [item for item in remaining if not any(_dominates(other, item) for other in remaining if other is not item)]
        fronts.append(front)
        front_ids = {item["id"] for item in front}
        remaining = [item for item in remaining if item["id"] not in front_ids]
    return fronts


def _rank_and_crowding(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for rank, front in enumerate(_non_dominated_fronts(items)):
        for item, crowding in zip(front, _crowding(front), strict=True):
            ranked.append({**item, "rank": rank, "crowding": crowding})
    return ranked


def _crowding(front: list[dict[str, Any]]) -> list[float]:
    values = [0.0] * len(front)
    if len(front) <= 2:
        return [float("inf")] * len(front)
    for objective in range(3):
        order = sorted(range(len(front)), key=lambda index: front[index]["objectives"][objective])
        values[order[0]] = values[order[-1]] = float("inf")
        low, high = front[order[0]]["objectives"][objective], front[order[-1]]["objectives"][objective]
        if high == low or not (abs(high) < float("inf")):
            continue
        for position in range(1, len(order) - 1):
            values[order[position]] += (front[order[position + 1]]["objectives"][objective] - front[order[position - 1]]["objectives"][objective]) / (high - low)
    return values


def _tournament(items: list[dict[str, Any]], rng: random.Random) -> dict[str, Any]:
    first, second = rng.sample(items, 2)
    return min((first, second), key=lambda item: (item["rank"], -item["crowding"]))


def _environmental_selection(items: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    for front in _non_dominated_fronts(items):
        if len(chosen) + len(front) <= size:
            chosen.extend(front)
        else:
            crowding = _crowding(front)
            order = sorted(range(len(front)), key=lambda index: crowding[index], reverse=True)
            chosen.extend(front[index] for index in order[: size - len(chosen)])
            break
    return chosen
