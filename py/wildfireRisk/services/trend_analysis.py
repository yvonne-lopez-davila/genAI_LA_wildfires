"""
Trend analysis module.
Computes fire proximity trends, fire frequency, and home value trajectory
from fire history and ZHVI data already fetched by existing services.

Now also incorporates DOI non-renewal, FAIR Plan exposure, and DINS
destruction rate as additional composite risk signals.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Linear slope helper
# ---------------------------------------------------------------------------

def _linear_slope(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return None
    return numerator / denominator


# ---------------------------------------------------------------------------
# Fire proximity trend
# ---------------------------------------------------------------------------

def analyze_fire_proximity_trend(fires: List[Dict[str, Any]]) -> Dict[str, Any]:
    valid = [f for f in fires if f.get("distance_miles") is not None]
    if not valid:
        return {"trend_label": "insufficient data"}

    by_year: Dict[int, float] = {}
    for f in valid:
        yr = f["year"]
        dist = f["distance_miles"]
        if yr not in by_year or dist < by_year[yr]:
            by_year[yr] = dist

    years = sorted(by_year.keys())
    distances = [by_year[y] for y in years]
    slope = _linear_slope([float(y) for y in years], distances)

    if slope is None:
        trend_label = "insufficient data"
    elif slope < -0.3:
        trend_label = "increasing"
    elif slope > 0.3:
        trend_label = "decreasing"
    else:
        trend_label = "stable"

    closest = min(valid, key=lambda f: f["distance_miles"])
    max_year = max(years)
    recent_fires = [f for f in valid if f["year"] >= max_year - 5]
    recent_avg = (
        round(sum(f["distance_miles"] for f in recent_fires) / len(recent_fires), 1)
        if recent_fires else None
    )
    historical_avg = round(sum(f["distance_miles"] for f in valid) / len(valid), 1)

    return {
        "slope_miles_per_year": round(slope, 3) if slope is not None else None,
        "trend_label": trend_label,
        "closest_fire": closest,
        "recent_avg_distance_miles": recent_avg,
        "historical_avg_distance_miles": historical_avg,
        "years_with_fires": len(by_year),
    }


# ---------------------------------------------------------------------------
# Fire frequency
# ---------------------------------------------------------------------------

def analyze_fire_frequency(fires: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not fires:
        return {"trend_label": "insufficient data", "windows": {}}

    years = [f["year"] for f in fires]
    min_year, max_year = min(years), max(years)

    windows: Dict[str, int] = {}
    start = (min_year // 5) * 5
    while start <= max_year:
        end = start + 4
        label = f"{start}-{end}"
        count = sum(1 for y in years if start <= y <= end)
        if count > 0:
            windows[label] = count
        start += 5

    window_counts = list(windows.values())
    if len(window_counts) >= 2:
        recent = window_counts[-1]
        previous = window_counts[-2]
        if recent > previous * 1.3:
            freq_trend = "accelerating"
        elif recent < previous * 0.7:
            freq_trend = "declining"
        else:
            freq_trend = "stable"
    else:
        freq_trend = "insufficient data"

    return {
        "windows": windows,
        "trend_label": freq_trend,
        "total_fires": len(fires),
        "most_active_year": max(set(years), key=years.count),
    }


# ---------------------------------------------------------------------------
# Price trajectory
# ---------------------------------------------------------------------------

def analyze_price_trajectory(timeseries: Dict[str, float]) -> Dict[str, Any]:
    if not timeseries or len(timeseries) < 2:
        return {"trend_label": "insufficient data"}

    years = sorted(timeseries.keys())
    max_year, min_year = max(years), min(years)
    current_value = timeseries[max_year]
    oldest_value = timeseries[min_year]

    recent_start = str(int(max_year) - 5)
    recent_years = [y for y in years if y >= recent_start]

    if len(recent_years) >= 2:
        value_5yr_ago = timeseries[recent_years[0]]
        pct_change_5yr = round((current_value - value_5yr_ago) / value_5yr_ago * 100, 1)
        slope_5yr = _linear_slope(
            [float(y) for y in recent_years],
            [timeseries[y] for y in recent_years]
        )
    else:
        pct_change_5yr = None
        slope_5yr = None

    pct_change_total = round((current_value - oldest_value) / oldest_value * 100, 1)

    if pct_change_5yr is None:
        trend_label = "insufficient data"
    elif pct_change_5yr > 20:
        trend_label = "strong growth"
    elif pct_change_5yr > 5:
        trend_label = "moderate growth"
    elif pct_change_5yr > -5:
        trend_label = "flat"
    else:
        trend_label = "declining"

    return {
        "current_value": round(current_value),
        "pct_change_5yr": pct_change_5yr,
        "pct_change_total": pct_change_total,
        "trend_label": trend_label,
        "slope_per_year_5yr": round(slope_5yr) if slope_5yr else None,
        "year_range": f"{min_year}-{max_year}",
    }


# ---------------------------------------------------------------------------
# per-domain signal builders
# ---------------------------------------------------------------------------

def _signal(text: str, direction: str, severity: float = 0.0) -> Dict[str, Any]:
    return {"text": text, "direction": direction, "severity": round(severity, 3)}


def _build_doi_signal(doi: Dict[str, Any]):
    if not doi or not doi.get("found"):
        return None, False

    rate = doi.get("latest_nonrenewal_rate")
    trend = (doi.get("trend_label") or "").lower()
    rate_change = doi.get("rate_change_pp")
    year = doi.get("latest_year", "")

    try:
        rate = float(rate) if rate is not None else None
    except (ValueError, TypeError):
        rate = None

    try:
        rate_change = float(rate_change) if rate_change is not None else None
    except (ValueError, TypeError):
        rate_change = None

    high_absolute = rate is not None and rate > 8
    accelerating = (
        trend in ("worsening", "increasing")
        and rate_change is not None
        and rate_change > 2
    )
    is_risk = high_absolute or accelerating

    if rate is None:
        return _signal("Non-renewal data unavailable", "neutral", 0.0), False

    severity = min(float(rate) / 16.0, 1.0)
    rate_str = f"{rate}%"
    year_str = f" ({year})" if year else ""

    if high_absolute and accelerating:
        return _signal(
            f"Non-renewal rate {rate_str}{year_str}, rising (+{rate_change}pp)",
            "negative", severity
        ), True
    elif high_absolute:
        return _signal(
            f"Non-renewal rate {rate_str}{year_str} — elevated",
            "negative", severity
        ), True
    elif accelerating:
        return _signal(
            f"Non-renewal rate trending up (+{rate_change}pp → {rate_str})",
            "negative", severity
        ), True
    else:
        return _signal(
            f"Non-renewal rate {rate_str}{year_str} ({trend})",
            "neutral", severity
        ), False


def _build_fair_plan_signal(fair_plan: Dict[str, Any]):
    if not fair_plan or not fair_plan.get("found"):
        return None, False

    covered = fair_plan.get("covered_by_fair_plan", False)
    change = fair_plan.get("five_year_pct_change")
    zipcode = fair_plan.get("zipcode", "this ZIP")

    try:
        change = float(change) if change is not None else None
    except (ValueError, TypeError):
        change = None

    if not covered:
        return _signal(
            f"FAIR Plan: no current exposure in ZIP {zipcode}",
            "neutral", 0.0
        ), False

    if change is None:
        return _signal(
            f"FAIR Plan exposure present in ZIP {zipcode}",
            "neutral"
        ), False

    severity = min(max(float(change), 0) / 200.0, 1.0)
    change_str = f"{'+' if change > 0 else ''}{change:.0f}%"

    if change > 100:
        return _signal(
            f"FAIR Plan exposure {change_str} (5yr) — insurers exiting",
            "negative", severity
        ), True
    elif change > 30:
        return _signal(
            f"FAIR Plan exposure up {change_str} over 5 years",
            "neutral", severity
        ), False
    else:
        return _signal(
            f"FAIR Plan exposure stable ({change_str} / 5yr)",
            "positive", severity
        ), False


def _build_dins_signal(destruction_rate_pct: Optional[float]):
    if destruction_rate_pct is None:
        return None, False

    rate = round(float(destruction_rate_pct), 1)
    severity = min(float(destruction_rate_pct) / 100.0, 1.0)

    if rate > 60:
        return _signal(
            f"{rate}% of nearby structures destroyed in past fires",
            "negative", severity
        ), True
    elif rate > 30:
        return _signal(
            f"{rate}% nearby structural destruction rate",
            "neutral", severity
        ), False
    else:
        return _signal(
            f"Low nearby destruction rate ({rate}%)",
            "positive", severity
        ), False


# ---------------------------------------------------------------------------
# Composite signal
# ---------------------------------------------------------------------------

def compute_composite_signal(
    fire_proximity: Dict[str, Any],
    fire_frequency: Dict[str, Any],
    price_trajectory: Dict[str, Any],
    hazard_zone: str,
    doi: Optional[Dict[str, Any]] = None,
    fair_plan: Optional[Dict[str, Any]] = None,
    dins_destruction_rate: Optional[float] = None,
) -> Dict[str, Any]:

    signals = []
    risk_factors: List[bool] = []

    # Fire proximity trend
    prox_trend = fire_proximity.get("trend_label", "insufficient data")
    if prox_trend == "increasing":
        signals.append(_signal("Fires trending closer over time", "negative"))
        risk_factors.append(True)
    elif prox_trend == "decreasing":
        signals.append(_signal("Fires trending further away", "positive"))
        risk_factors.append(False)

    # Closest fire
    closest = fire_proximity.get("closest_fire")
    if closest:
        dist = closest["distance_miles"]
        direction = "negative" if dist < 5 else "neutral" if dist < 15 else "positive"
        severity = max(0.0, min(1.0, 1.0 - (dist / 30.0)))
        signals.append(_signal(
            f"Closest fire: {closest['fire_name']} ({closest['year']}, {dist} mi away)",
            direction, severity
        ))

    # Recent vs historical avg
    recent_avg = fire_proximity.get("recent_avg_distance_miles")
    hist_avg = fire_proximity.get("historical_avg_distance_miles")
    if recent_avg and hist_avg and recent_avg < hist_avg * 0.8:
        signals.append(_signal(
            f"Recent fires avg {recent_avg} mi — closer than historical {hist_avg} mi",
            "negative"
        ))
        risk_factors.append(True)
    elif recent_avg and hist_avg:
        risk_factors.append(False)

    # Fire frequency
    freq_trend = fire_frequency.get("trend_label", "insufficient data")
    total = fire_frequency.get("total_fires", 0)
    freq_severity = {"accelerating": 0.8, "stable": 0.3, "declining": 0.0,
                     "insufficient data": 0.2}.get(freq_trend, 0.2)

    if freq_trend == "accelerating":
        signals.append(_signal(
            f"Fire frequency accelerating ({total} nearby on record)",
            "negative", freq_severity
        ))
        risk_factors.append(True)
    elif freq_trend == "declining":
        signals.append(_signal(
            f"Fire frequency declining ({total} nearby on record)",
            "positive", freq_severity
        ))
        risk_factors.append(False)
    else:
        signals.append(_signal(
            f"{total} fires on record nearby",
            "neutral", freq_severity
        ))
        risk_factors.append(False)

    # Home value
    price_trend = price_trajectory.get("trend_label", "insufficient data")
    pct_5yr = price_trajectory.get("pct_change_5yr")
    current = price_trajectory.get("current_value")
    if current and pct_5yr is not None:
        direction = "neutral" if pct_5yr > 0 else "negative"
        severity = max(0.0, min(1.0, -pct_5yr / 30.0)) if pct_5yr < 0 else 0.1
        signals.append(_signal(
            f"Median home value ~${current:,} ({'+' if pct_5yr > 0 else ''}{pct_5yr}% / 5yr)",
            direction, severity
        ))

    # Hazard zone
    if hazard_zone and hazard_zone != "Unknown":
        direction = "negative" if hazard_zone in ("Very High", "High") else "neutral"
        zone_severity = {"Very High": 1.0, "High": 0.7,
                         "Moderate": 0.3, "Unknown": 0.0}.get(hazard_zone, 0.0)
        signals.append(_signal(
            f"State hazard zone: {hazard_zone}",
            direction, zone_severity
        ))
        risk_factors.append(hazard_zone in ("Very High", "High"))

    # Insurance and structural signals
    doi_signal, doi_risk = _build_doi_signal(doi)
    if doi_signal:
        signals.append(doi_signal)
        risk_factors.append(doi_risk)

    fair_signal, fair_risk = _build_fair_plan_signal(fair_plan)
    if fair_signal:
        signals.append(fair_signal)
        risk_factors.append(fair_risk)

    dins_signal, dins_risk = _build_dins_signal(dins_destruction_rate)
    if dins_signal:
        signals.append(dins_signal)
        risk_factors.append(dins_risk)

    # Score
    n_risk = sum(risk_factors)
    n_total = len(risk_factors)
    proportion = n_risk / n_total if n_total > 0 else 0

    if proportion >= 0.6:
        composite_label = "high and increasing risk"
    elif proportion >= 0.35:
        composite_label = "moderate to high risk"
    elif proportion > 0:
        composite_label = "moderate risk"
    else:
        composite_label = "lower risk based on available data"

    signals.sort(key=lambda s: s["severity"], reverse=True)

    return {
        "composite_label": composite_label,
        "signals": signals,
        "risk_factor_count": n_risk,
        "risk_factors_scored": n_total,
    }


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def analyze_trends(
    fire_history: Dict[str, Any],
    zhvi: Dict[str, Any],
    hazard_zone: str = "Unknown",
    doi: Optional[Dict[str, Any]] = None,
    fair_plan: Optional[Dict[str, Any]] = None,
    dins: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    fires = fire_history.get("fires", []) if fire_history.get("found") else []
    timeseries = zhvi.get("timeseries", {}) if zhvi.get("found") else {}

    fire_proximity = analyze_fire_proximity_trend(fires)
    fire_frequency = analyze_fire_frequency(fires)
    price_trajectory = analyze_price_trajectory(timeseries)

    dins_destruction_rate = None
    if dins and dins.get("found"):
        dins_destruction_rate = dins.get("damage_rates", {}).get("destruction_rate_pct")

    composite = compute_composite_signal(
        fire_proximity,
        fire_frequency,
        price_trajectory,
        hazard_zone,
        doi=doi,
        fair_plan=fair_plan,
        dins_destruction_rate=dins_destruction_rate,
    )

    return {
        "fire_proximity": fire_proximity,
        "fire_frequency": fire_frequency,
        "price_trajectory": price_trajectory,
        "composite": composite,
    }