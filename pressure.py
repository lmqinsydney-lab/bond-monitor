from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


FORMULA_VERSION = "1.0"


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return min(high, max(low, value))


def standard_pressure(change_1d_bp: float, change_5d_bp: float) -> float:
    value = 50 + 50 * (0.4 * change_1d_bp / 3 + 0.6 * change_5d_bp / 8)
    return round(clamp(value), 2)


def pressure_band(score: float | None) -> str:
    if score is None:
        return "insufficient"
    if score <= 35:
        return "low"
    if score <= 64:
        return "watch"
    return "high"


@dataclass(frozen=True)
class WeightedResult:
    score: float | None
    band: str
    missing_weight: float
    used_weights: dict[str, float]
    confidence_adjustment: str


def weighted_pressure(
    scores: Mapping[str, float | None],
    weights: Mapping[str, float],
    *,
    max_missing_weight: float = 0.2,
) -> WeightedResult:
    total = sum(max(0.0, float(weight)) for weight in weights.values())
    if total <= 0:
        raise ValueError("weights must sum to a positive value")
    normalized = {name: max(0.0, float(weight)) / total for name, weight in weights.items()}
    missing = sum(weight for name, weight in normalized.items() if scores.get(name) is None)
    if missing > max_missing_weight + 1e-12:
        return WeightedResult(None, "insufficient", round(missing, 6), {}, "unavailable")
    available_total = 1 - missing
    used = {
        name: weight / available_total
        for name, weight in normalized.items()
        if scores.get(name) is not None
    }
    score = sum(float(scores[name]) * weight for name, weight in used.items())
    confidence = "lowered" if missing > 0 else "unchanged"
    rounded = round(score, 2)
    return WeightedResult(rounded, pressure_band(rounded), round(missing, 6), used, confidence)

