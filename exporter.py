from __future__ import annotations

import csv
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from fund_profiles import current_profiles
from correlation import pearson_result
from pressure import FORMULA_VERSION, standard_pressure, weighted_pressure
from storage import database, get_state, preferred_fund_nav_series, preferred_series


SERIES = {
    **{f"cgb_yield_{tenor}": ("cgb_yield", float(tenor), "") for tenor in (1, 3, 5, 10)},
    **{f"cdb_yield_{tenor}": ("cdb_yield", float(tenor), "") for tenor in (1, 3, 5, 10)},
    **{f"bank_t2_yield_{tenor}": ("bank_t2_yield", float(tenor), "AAA-") for tenor in (1, 3, 5)},
    **{f"mtm_aaa_yield_{tenor}": ("mtm_aaa_yield", float(tenor), "AAA") for tenor in (1, 3, 5)},
    "dr007": ("dr007", 7 / 365, ""),
    "r007": ("r007", 7 / 365, ""),
    "bank_perp_yield_5": ("bank_perp_yield", 5.0, "AAA-"),
}


LABELS = {
    "cgb_yield_1": "国债 1Y",
    "cgb_yield_3": "国债 3Y",
    "cgb_yield_5": "国债 5Y",
    "cgb_yield_10": "国债 10Y",
    "cdb_yield_1": "国开债 1Y",
    "cdb_yield_3": "国开债 3Y",
    "cdb_yield_5": "国开债 5Y",
    "cdb_yield_10": "国开债 10Y",
    "bank_t2_yield_1": "二级资本债 AAA- 1Y",
    "bank_t2_yield_3": "二级资本债 AAA- 3Y",
    "bank_t2_yield_5": "二级资本债 AAA- 5Y",
    "mtm_aaa_yield_1": "中短期票据 AAA 1Y",
    "mtm_aaa_yield_3": "中短期票据 AAA 3Y",
    "mtm_aaa_yield_5": "中短期票据 AAA 5Y",
    "bank_perp_yield_5": "银行永续债 AAA- 5Y（行权）",
    "spread_perp_cdb_5": "银行永续债 − 国开债 5Y",
    "dr007": "DR007",
    "r007": "R007",
}


def _enrich(
    points: list[dict[str, object]], *, change_scale: float = 100.0
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for index, row in enumerate(points):
        value = float(row["value"])
        change_1d = (
            (value - float(points[index - 1]["value"])) * change_scale
            if index >= 1
            else None
        )
        change_5d = (
            (value - float(points[index - 5]["value"])) * change_scale
            if index >= 5
            else None
        )
        enriched.append(
            {
                "date": row["observation_date"],
                "value": round(value, 6),
                "change_1d_bp": round(change_1d, 4) if change_1d is not None else None,
                "change_5d_bp": round(change_5d, 4) if change_5d is not None else None,
                "source": row["source"],
                "source_tier": row["source_tier"],
                "source_url": row["source_url"],
                "quality": row["quality"],
            }
        )
    return enriched


def _spread(
    left: list[dict[str, object]], right: list[dict[str, object]], label: str
) -> list[dict[str, object]]:
    left_by_date = {item["date"]: item for item in left}
    right_by_date = {item["date"]: item for item in right}
    raw: list[dict[str, object]] = []
    for date in sorted(set(left_by_date) & set(right_by_date)):
        a, b = left_by_date[date], right_by_date[date]
        raw.append(
            {
                "observation_date": date,
                "value": (float(a["value"]) - float(b["value"])) * 100,
                "source": f"{a['source']} − {b['source']}",
                "source_tier": "official" if a["source_tier"] == b["source_tier"] == "official" else "fallback",
                "source_url": a["source_url"],
                "quality": "derived",
            }
        )
    # Spread values are already expressed in basis points, so their daily and
    # five-day changes must not be multiplied by 100 again.
    points = _enrich(raw, change_scale=1.0)
    for point in points:
        point["unit"] = "bp"
        point["label"] = label
    return points


def _latest_pressure(points: list[dict[str, object]]) -> float | None:
    if not points:
        return None
    point = points[-1]
    if point.get("change_1d_bp") is None or point.get("change_5d_bp") is None:
        return None
    return standard_pressure(float(point["change_1d_bp"]), float(point["change_5d_bp"]))


def _fund_results(
    profiles: Iterable[dict[str, object]], all_series: dict[str, list[dict[str, object]]]
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    score_by_metric = {key: _latest_pressure(points) for key, points in all_series.items()}
    for profile in profiles:
        components: dict[str, object] = {}
        component_scores: dict[str, float | None] = {}
        for component, weights in profile["metric_weights"].items():
            result = weighted_pressure(score_by_metric, weights)
            component_scores[component] = result.score
            components[component] = {
                "score": result.score,
                "band": result.band,
                "missing_weight": result.missing_weight,
                "confidence_adjustment": result.confidence_adjustment,
                "weights": weights,
                "used_weights": result.used_weights,
                "metrics": {
                    key: {
                        "score": score_by_metric.get(key),
                        "latest": all_series.get(key, [])[-1] if all_series.get(key) else None,
                    }
                    for key in weights
                },
            }
        overall = weighted_pressure(component_scores, profile["component_weights"])
        confidence = str(profile["profile_confidence"])
        if any(item["confidence_adjustment"] == "lowered" for item in components.values()):
            confidence = "medium" if confidence == "high" else "low"
        if overall.score is None:
            confidence = "low"
        output.append(
            {
                **profile,
                "formula_version": FORMULA_VERSION,
                "score": overall.score,
                "band": overall.band,
                "confidence": confidence,
                "components": components,
                "calculation": {
                    "component_weights": profile["component_weights"],
                    "used_component_weights": overall.used_weights,
                    "missing_weight": overall.missing_weight,
                },
            }
        )
    return output


def _profile_metric_keys(profile: dict[str, object]) -> list[str]:
    output: list[str] = []
    for weights in profile["metric_weights"].values():
        for key in weights:
            if key not in output:
                output.append(key)
    return output


def _correlation_ranges(
    nav_points: list[dict[str, object]],
    metric_points: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    metric_by_date = {point["date"]: point for point in metric_points}
    pairs = [
        (
            str(nav["date"]),
            float(nav["daily_return_pct"]),
            float(metric_by_date[nav["date"]]["change_1d_bp"]),
        )
        for nav in nav_points
        if nav.get("daily_return_pct") is not None
        and nav["date"] in metric_by_date
        and metric_by_date[nav["date"]].get("change_1d_bp") is not None
    ]
    latest = date.fromisoformat(str(nav_points[-1]["date"])) if nav_points else None
    output: dict[str, dict[str, object]] = {}
    for key, size in (("20", 20), ("60", 60), ("120", 120)):
        selected = pairs[-size:]
        output[key] = pearson_result(
            [(fund_return, metric_change) for _, fund_return, metric_change in selected]
        )
    year_pairs = (
        [
            item
            for item in pairs
            if date.fromisoformat(item[0]) >= latest - timedelta(days=365)
        ]
        if latest
        else []
    )
    output["365"] = pearson_result(
        [(fund_return, metric_change) for _, fund_return, metric_change in year_pairs]
    )
    output["all"] = pearson_result(
        [(fund_return, metric_change) for _, fund_return, metric_change in pairs]
    )
    return output


def _fund_nav_comparisons(
    profiles: Iterable[dict[str, object]],
    nav_by_code: dict[str, list[dict[str, object]]],
    all_series: dict[str, list[dict[str, object]]],
) -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    for profile in profiles:
        code = str(profile["code"])
        nav_points = [
            {
                "date": row["nav_date"],
                "unit_nav": row["unit_nav"],
                "cumulative_nav": row["cumulative_nav"],
                "daily_return_pct": row["daily_return_pct"],
                "source": row["source"],
                "source_tier": row["source_tier"],
                "source_url": row["source_url"],
                "quality": row["quality"],
            }
            for row in nav_by_code.get(code, [])
        ]
        metric_keys = _profile_metric_keys(profile)
        output[code] = {
            "code": code,
            "name": profile["name"],
            "profile_period_end": profile["report_period_end"],
            "profile_confidence": profile["profile_confidence"],
            "metric_keys": metric_keys,
            "nav_points": nav_points,
            "latest_nav_date": nav_points[-1]["date"] if nav_points else None,
            "correlations": {
                range_key: {
                    metric_key: _correlation_ranges(
                        nav_points, all_series.get(metric_key, [])
                    )[range_key]
                    for metric_key in metric_keys
                }
                for range_key in ("20", "60", "120", "365", "all")
            },
        }
    return output


def export_dashboard(
    *,
    db_path: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, object]:
    web_data = Path(output_dir) if output_dir else Path(__file__).resolve().parent / "web" / "data"
    web_data.mkdir(parents=True, exist_ok=True)
    with database(db_path) as conn:
        series = {
            key: _enrich(preferred_series(conn, metric, tenor=tenor, rating=rating))
            for key, (metric, tenor, rating) in SERIES.items()
        }
        for points in series.values():
            for point in points:
                point.setdefault("unit", "percent")

        for tenor in (1, 3, 5):
            series[f"spread_t2_cdb_{tenor}"] = _spread(
                series[f"bank_t2_yield_{tenor}"],
                series[f"cdb_yield_{tenor}"],
                f"二级资本债 − 国开债 {tenor}Y",
            )
            series[f"spread_mtm_cdb_{tenor}"] = _spread(
                series[f"mtm_aaa_yield_{tenor}"],
                series[f"cdb_yield_{tenor}"],
                f"AAA 中票 − 国开债 {tenor}Y",
            )
        series["spread_perp_cdb_5"] = _spread(
            series["bank_perp_yield_5"], series["cdb_yield_5"], "银行永续债 − 国开债 5Y"
        )
        if series["r007"] and series["dr007"]:
            series["spread_r_dr"] = _spread(series["r007"], series["dr007"], "R007 − DR007")
        else:
            series["spread_r_dr"] = []

        dates = [point["date"] for points in series.values() for point in points]
        latest_date = max(dates) if dates else None
        update_status = get_state(conn, "update_status", {"state": "never"})

        profiles = current_profiles()
        nav_by_code = {
            str(profile["code"]): preferred_fund_nav_series(conn, str(profile["code"]))
            for profile in profiles
        }

    overview_keys = [
        "cgb_yield_10",
        "cdb_yield_5",
        "bank_t2_yield_5",
        "spread_t2_cdb_5",
        "dr007",
    ]
    dashboard = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "latest_data_date": latest_date,
            "update_status": update_status,
            "formula_version": FORMULA_VERSION,
        },
        "overview": [
            {
                "key": key,
                "label": LABELS.get(key, series[key][-1].get("label", key) if series[key] else key),
                "latest": series[key][-1] if series[key] else None,
            }
            for key in overview_keys
        ],
        "series": {
            key: {
                "label": LABELS.get(key, points[-1].get("label", key) if points else key),
                "unit": points[-1].get("unit", "percent") if points else "percent",
                "points": points,
            }
            for key, points in series.items()
        },
        "funds": _fund_results(profiles, series),
        "fund_nav_comparison": _fund_nav_comparisons(profiles, nav_by_code, series),
        "quality": {
            "missing_required": [
                key for key in ("bank_perp_yield_5", "r007") if not series[key]
            ],
            "notes": [
                "银行永续债官方行权曲线自 2026-07-27 起由上海清算所发布，适配器尚待完成时保留为空。",
                "中国货币网公开模块已接入 DR007 加权利率；R007 不会用 FDR007 冒充。",
                "基金压力是公开季报画像代理，不是实时净值估算。",
            ],
        },
    }
    json_path = web_data / "dashboard.json"
    json_path.write_text(json.dumps(dashboard, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    _write_csv(web_data / "market-history.csv", dashboard["series"])
    return dashboard


def _write_csv(path: Path, series: dict[str, dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["指标代码", "指标名称", "日期", "数值", "单位", "单日变化BP", "5日变化BP", "来源", "来源等级", "质量"]
        )
        for key, payload in series.items():
            for point in payload["points"]:
                writer.writerow(
                    [
                        key,
                        payload["label"],
                        point["date"],
                        point["value"],
                        payload["unit"],
                        point.get("change_1d_bp"),
                        point.get("change_5d_bp"),
                        point["source"],
                        point["source_tier"],
                        point["quality"],
                    ]
                )
