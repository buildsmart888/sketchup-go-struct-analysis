"""Small, UI-independent helpers for sampled result contour rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class ContourRange:
    """Numeric range used by a canvas legend and its coloured sample bands."""

    minimum: float
    maximum: float

    @property
    def span(self) -> float:
        return max(self.maximum - self.minimum, 1.0e-12)


def stress_value(point: Mapping[str, Any]) -> float:
    """Return the governing signed elastic fibre stress at one sampled station."""

    top = float(point.get("stress_top_kg_cm2", 0.0))
    bottom = float(point.get("stress_bottom_kg_cm2", 0.0))
    return top if abs(top) >= abs(bottom) else bottom


def contour_range(
    members: list[Mapping[str, Any]],
    key: str,
    transform: Callable[[str, float], float] | None = None,
    *,
    signed: bool = True,
) -> ContourRange:
    """Find the exact global or member range without changing solver values."""

    transform = transform or (lambda _key, value: value)
    values = [
        transform(key, stress_value(point) if key == "stress_kg_cm2" else float(point.get(key, 0.0)))
        for member in members
        for point in member.get("points", [])
    ]
    if not values:
        return ContourRange(-1.0, 1.0) if signed else ContourRange(0.0, 1.0)
    if signed:
        maximum = max(max(abs(value) for value in values), 1.0e-12)
        return ContourRange(-maximum, maximum)
    minimum, maximum = min(values), max(values)
    if maximum - minimum <= 1.0e-12:
        maximum = minimum + 1.0
    return ContourRange(minimum, maximum)


def colour_stops(value: float, value_range: ContourRange, palette: str) -> tuple[int, int, int]:
    """Return an RGB colour for either a signed or sequential result convention."""

    if palette == "truss_axial":
        # This is intentionally a display-only convention. Solver values retain +N tension.
        if value > 1.0e-12:
            return 21, 128, 61
        if value < -1.0e-12:
            return 185, 28, 28
        return 71, 85, 105
    ratio = min(max((value - value_range.minimum) / value_range.span, 0.0), 1.0)
    if palette == "spectrum":
        stops = ((37, 99, 235), (6, 182, 212), (22, 163, 74), (234, 179, 8), (220, 38, 38))
        position = ratio * (len(stops) - 1)
        lower = min(int(position), len(stops) - 2)
        blend = position - lower
        first, second = stops[lower], stops[lower + 1]
    else:
        # A diverging palette makes sign unambiguous: blue is negative, red positive.
        if ratio <= 0.5:
            first, second, blend = (37, 99, 235), (248, 250, 252), ratio * 2.0
        else:
            first, second, blend = (248, 250, 252), (220, 38, 38), (ratio - 0.5) * 2.0
    return tuple(round(a + (b - a) * blend) for a, b in zip(first, second))
