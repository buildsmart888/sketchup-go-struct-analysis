"""Project display units layered over GOFrame's legacy kg/m solver contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitSystem:
    key: str
    label: str
    force_factor: float
    length_factor: float
    force_unit: str
    length_unit: str

    @property
    def moment_factor(self) -> float:
        return self.force_factor * self.length_factor

    @property
    def distributed_factor(self) -> float:
        return self.force_factor / self.length_factor

    def force(self, value_kg: float) -> float:
        return value_kg * self.force_factor

    def length(self, value_m: float) -> float:
        return value_m * self.length_factor

    def moment(self, value_kg_m: float) -> float:
        return value_kg_m * self.moment_factor

    def distributed(self, value_kg_m: float) -> float:
        return value_kg_m * self.distributed_factor

    def force_label(self) -> str:
        return self.force_unit

    def moment_label(self) -> str:
        return f"{self.force_unit}-{self.length_unit}"

    def distributed_label(self) -> str:
        return f"{self.force_unit}/{self.length_unit}"


UNIT_SYSTEMS: dict[str, UnitSystem] = {
    "legacy_kg_m": UnitSystem("legacy_kg_m", "Legacy kg-m", 1.0, 1.0, "kg", "m"),
    "kn_m": UnitSystem("kn_m", "Metric kN-m", 0.00980665, 1.0, "kN", "m"),
    "n_mm": UnitSystem("n_mm", "SI N-mm", 9.80665, 1000.0, "N", "mm"),
    "tf_m": UnitSystem("tf_m", "Metric tf-m", 0.001, 1.0, "tf", "m"),
}


def get_unit_system(key: str | None) -> UnitSystem:
    return UNIT_SYSTEMS.get(str(key), UNIT_SYSTEMS["legacy_kg_m"])
