from __future__ import annotations

import math
from typing import Iterable


def correlation_strength(value: float) -> str:
    absolute = abs(value)
    if absolute < 0.2:
        return "very_weak"
    if absolute < 0.4:
        return "weak"
    if absolute < 0.6:
        return "moderate"
    if absolute < 0.8:
        return "strong"
    return "very_strong"


def pearson_result(
    pairs: Iterable[tuple[float, float]], *, min_samples: int = 20
) -> dict[str, object]:
    values = [
        (float(left), float(right))
        for left, right in pairs
        if math.isfinite(float(left)) and math.isfinite(float(right))
    ]
    count = len(values)
    if count < min_samples:
        return {"r": None, "samples": count, "strength": "insufficient", "direction": None}
    left_mean = sum(item[0] for item in values) / count
    right_mean = sum(item[1] for item in values) / count
    numerator = sum((left - left_mean) * (right - right_mean) for left, right in values)
    left_sum = sum((left - left_mean) ** 2 for left, _ in values)
    right_sum = sum((right - right_mean) ** 2 for _, right in values)
    denominator = math.sqrt(left_sum * right_sum)
    if denominator <= 1e-15:
        return {"r": None, "samples": count, "strength": "constant", "direction": None}
    value = max(-1.0, min(1.0, numerator / denominator))
    rounded = round(value, 4)
    direction = "positive" if rounded > 0 else "negative" if rounded < 0 else "flat"
    return {
        "r": rounded,
        "samples": count,
        "strength": correlation_strength(rounded),
        "direction": direction,
    }
