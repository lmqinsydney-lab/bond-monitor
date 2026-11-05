from __future__ import annotations

from copy import deepcopy


# 当前画像来自 2026 年三季度公开报告。它们是版本化的透明代理，不是实时持仓。
# 新报告自动发现与 PDF 解析会在后续版本替换这些种子画像；失败时继续保留本版本。
FUND_PROFILES: dict[str, dict[str, object]] = {
    "006985": {
        "name": "兴全恒裕债券A",
        "manager": "兴证全球基金",
        "report_period_end": "2026-09-30",
        "published_at": "2026-10-27",
        "source_url": "https://pdf.dfcfw.com/pdf/H2_AN202610271831007827_1.pdf",
        "source_note": "兴全恒裕债券型证券投资基金 2026 年第 3 季度报告",
        "bond_exposure_pct": 110.86,
        "leverage_proxy": 1.1086,
        "profile_confidence": "high",
        "holdings_summary": "债券仓位约 110.86%；按季报品种归类，信用债约 104.25%，利率债约 3.01%。",
        "bond_composition": {
            "credit": {"label": "信用债", "weight_pct": 104.25},
            "rate": {"label": "利率债", "weight_pct": 3.01},
            "other": {"label": "其他债券", "weight_pct": 3.60},
        },
        "bond_category_details": [
            {"name": "国家债券", "classification": "rate", "weight_pct": 0.95},
            {"name": "政策性金融债", "classification": "rate", "weight_pct": 2.06},
            {"name": "商业银行等金融债（不含政策性金融债）", "classification": "credit", "weight_pct": 58.88},
            {"name": "企业债券", "classification": "credit", "weight_pct": 26.80},
            {"name": "企业短期融资券", "classification": "credit", "weight_pct": 0.05},
            {"name": "中期票据", "classification": "credit", "weight_pct": 12.61},
            {"name": "同业存单", "classification": "credit", "weight_pct": 5.91},
            {"name": "季报归为其他的债券", "classification": "other", "weight_pct": 3.60},
        ],
        "top_holdings": [
            {"name": "22农行二级资本债02B", "type": "bank_t2", "classification": "credit", "weight_pct": 2.46},
            {"name": "22中行二级资本债02B", "type": "bank_t2", "classification": "credit", "weight_pct": 2.45},
            {"name": "22建设银行二级02", "type": "bank_t2", "classification": "credit", "weight_pct": 2.35},
            {"name": "17国开10", "type": "policy_bank", "classification": "rate", "weight_pct": 1.98},
            {"name": "22工行二级资本债03B", "type": "bank_t2", "classification": "credit", "weight_pct": 1.88},
        ],
        "component_weights": {"rate": 0.35, "credit": 0.5, "funding": 0.15},
        "metric_weights": {
            "rate": {"cdb_yield_5": 0.75, "cdb_yield_10": 0.25},
            "credit": {"spread_t2_cdb_5": 0.7, "spread_t2_cdb_3": 0.3},
            "funding": {"dr007": 1.0},
        },
    },
    "007744": {
        "name": "长盛安逸纯债A",
        "manager": "长盛基金",
        "report_period_end": "2026-09-30",
        "published_at": "2026-10-27",
        "source_url": "https://pdf.dfcfw.com/pdf/H2_AN202610271830976989_1.pdf",
        "source_note": "长盛安逸纯债债券型证券投资基金 2026 年第 3 季度报告",
        "bond_exposure_pct": 108.22,
        "leverage_proxy": 1.0822,
        "profile_confidence": "high",
        "holdings_summary": "债券仓位约 108.22%；按季报品种归类，信用债约 95.26%，利率债约 10.03%。",
        "bond_composition": {
            "credit": {"label": "信用债", "weight_pct": 95.26},
            "rate": {"label": "利率债", "weight_pct": 10.03},
            "other": {"label": "其他债券", "weight_pct": 2.93},
        },
        "bond_category_details": [
            {"name": "政策性金融债", "classification": "rate", "weight_pct": 10.03},
            {"name": "商业银行等金融债（不含政策性金融债）", "classification": "credit", "weight_pct": 21.20},
            {"name": "企业债券", "classification": "credit", "weight_pct": 5.39},
            {"name": "中期票据", "classification": "credit", "weight_pct": 66.25},
            {"name": "同业存单", "classification": "credit", "weight_pct": 2.43},
            {"name": "季报归为其他的债券", "classification": "other", "weight_pct": 2.93},
        ],
        "top_holdings": [
            {"name": "26交通银行CD170", "type": "bank_cd", "classification": "credit", "weight_pct": 2.43},
            {"name": "24国开05", "type": "policy_bank", "classification": "rate", "weight_pct": 2.23},
            {"name": "26民生银行二级资本债01", "type": "bank_t2", "classification": "credit", "weight_pct": 2.10},
            {"name": "25工行二级资本债01BC", "type": "bank_t2", "classification": "credit", "weight_pct": 1.77},
            {"name": "24进出10", "type": "policy_bank", "classification": "rate", "weight_pct": 1.75},
        ],
        "component_weights": {"rate": 0.35, "credit": 0.5, "funding": 0.15},
        "metric_weights": {
            "rate": {"cdb_yield_5": 0.65, "cdb_yield_10": 0.35},
            "credit": {
                "spread_mtm_cdb_3": 0.5,
                "spread_t2_cdb_5": 0.35,
                "spread_perp_cdb_5": 0.15,
            },
            "funding": {"dr007": 1.0},
        },
    },
    "012591": {
        "name": "广发添财180天滚动持有债券A",
        "manager": "广发基金",
        "report_period_end": "2026-09-30",
        "published_at": "2026-10-27",
        "source_url": "https://pdf.dfcfw.com/pdf/H2_AN202610271830977393_1.pdf",
        "source_note": "广发添财 180 天滚动持有债券型证券投资基金 2026 年第 3 季度报告",
        "bond_exposure_pct": 97.52,
        "leverage_proxy": 0.9752,
        "profile_confidence": "high",
        "holdings_summary": "债券仓位约 97.52%；按季报品种归类，信用债约 90.45%，利率债约 5.69%。",
        "bond_composition": {
            "credit": {"label": "信用债", "weight_pct": 90.45},
            "rate": {"label": "利率债", "weight_pct": 5.69},
            "other": {"label": "其他债券", "weight_pct": 1.38},
        },
        "bond_category_details": [
            {"name": "国家债券", "classification": "rate", "weight_pct": 0.36},
            {"name": "政策性金融债", "classification": "rate", "weight_pct": 5.33},
            {"name": "商业银行等金融债（不含政策性金融债）", "classification": "credit", "weight_pct": 10.12},
            {"name": "企业债券", "classification": "credit", "weight_pct": 14.13},
            {"name": "企业短期融资券", "classification": "credit", "weight_pct": 38.85},
            {"name": "中期票据", "classification": "credit", "weight_pct": 27.35},
            {"name": "季报归为其他的债券", "classification": "other", "weight_pct": 1.38},
        ],
        "top_holdings": [
            {"name": "26物产中大SCP003", "type": "short_credit", "classification": "credit", "weight_pct": 4.97},
            {"name": "26农发01", "type": "policy_bank", "classification": "rate", "weight_pct": 3.67},
            {"name": "26国泰海通CP002", "type": "short_credit", "classification": "credit", "weight_pct": 3.32},
            {"name": "26中交一公SCP009", "type": "short_credit", "classification": "credit", "weight_pct": 3.31},
            {"name": "23青港01", "type": "enterprise", "classification": "credit", "weight_pct": 3.04},
        ],
        "component_weights": {"rate": 0.25, "credit": 0.6, "funding": 0.15},
        "metric_weights": {
            "rate": {"cdb_yield_1": 0.55, "cdb_yield_3": 0.45},
            "credit": {"spread_mtm_cdb_1": 0.6, "spread_mtm_cdb_3": 0.4},
            "funding": {"dr007": 1.0},
        },
    },
}


def current_profiles() -> list[dict[str, object]]:
    return [deepcopy(FUND_PROFILES[code]) | {"code": code} for code in FUND_PROFILES]

