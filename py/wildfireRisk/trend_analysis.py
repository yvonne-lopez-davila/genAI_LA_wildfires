"""
Trend analysis module.
Computes fire proximity trends, fire frequency, and home value trajectory
from fire history and ZHVI data already fetched by existing services.

Inputs:
    - fire_history: output of fire_history_service.get_nearby_fires()
    - zhvi: output of zhvi_service.get_home_value_timeseries()

Output:
    - trend metrics dict ready to pass into extra_context for LLM or display directly
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Fire proximity trend
# ---------------------------------------------------------------------------

def _linear_slope(xs: List[float], ys: List[float]) -> Optional[float]:
    """
    Simple linear regression slope (rise/run).
    Returns None if insufficient data.
    """
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


def analyze_fire_proximity_trend(fires: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute whether fires are getting closer over time.

    Returns:
        slope_miles_per_year: negative = fires getting closer, positive = moving away
        trend_label: "increasing" | "decreasing" | "stable" | "insufficient data"
        closest_fire: the single closest fire on record
        recent_avg_distance: average distance of fires in last 5 years
        historical_avg_distance: average distance of all fires
    """
    valid = [f for f in fires if f.get("distance_miles") is not None]

    if not valid:
        return {"trend_label": "insufficient data"}

    # One entry per year — use closest fire per year for trend
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
        trend_label = "increasing"   # fires getting closer each year
    elif slope > 0.3:
        trend_label = "decreasing"   # fires moving further away
    else:
        trend_label = "stable"

    # Closest fire overall
    closest = min(valid, key=lambda f: f["distance_miles"])

    # Recent vs historical avg distance
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
# Fire frequency analysis
# ---------------------------------------------------------------------------

def analyze_fire_frequency(fires: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute fire frequency by 5-year window.
    Tells you if fire activity is accelerating over time.
    """
    if not fires:
        return {"trend_label": "insufficient data", "windows": {}}

    years = [f["year"] for f in fires]
    min_year = min(years)
    max_year = max(years)

    # Build 5-year windows
    windows: Dict[str, int] = {}
    start = (min_year // 5) * 5
    while start <= max_year:
        end = start + 4
        label = f"{start}-{end}"
        count = sum(1 for y in years if start <= y <= end)
        if count > 0:
            windows[label] = count
        start += 5

    # Compare most recent full window to previous
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
# ZHVI price trajectory
# ---------------------------------------------------------------------------

def analyze_price_trajectory(timeseries: Dict[str, float]) -> Dict[str, Any]:
    """
    Compute price trend from ZHVI timeseries.
    Focuses on last 5 years for near-term trajectory.
    """
    if not timeseries or len(timeseries) < 2:
        return {"trend_label": "insufficient data"}

    years = sorted(timeseries.keys())
    max_year = max(years)
    min_year = min(years)

    current_value = timeseries[max_year]
    oldest_value = timeseries[min_year]

    # 5-year trend
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

    # Overall trend
    pct_change_total = round((current_value - oldest_value) / oldest_value * 100, 1)

    # Label recent trajectory
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
# Composite risk signal
# ---------------------------------------------------------------------------

def compute_composite_signal(
    fire_proximity: Dict[str, Any],
    fire_frequency: Dict[str, Any],
    price_trajectory: Dict[str, Any],
    hazard_zone: str,
) -> Dict[str, Any]:

    signals = []

    def signal(text, direction):
        # direction: "negative" | "positive" | "neutral"
        return {"text": text, "direction": direction}

    prox_trend = fire_proximity.get("trend_label", "insufficient data")
    if prox_trend == "increasing":
        signals.append(signal("fires are trending closer over time", "negative"))
    elif prox_trend == "decreasing":
        signals.append(signal("fires have been trending further away over time", "positive"))

    closest = fire_proximity.get("closest_fire")
    if closest:
        dist = closest['distance_miles']
        direction = "negative" if dist < 5 else "neutral" if dist < 15 else "positive"
        signals.append(signal(
            f"closest recorded fire was {closest['fire_name']} "
            f"({closest['year']}, {closest['distance_miles']} miles away)",
            direction
        ))

    recent_avg = fire_proximity.get("recent_avg_distance_miles")
    hist_avg = fire_proximity.get("historical_avg_distance_miles")
    if recent_avg and hist_avg and recent_avg < hist_avg * 0.8:
        signals.append(signal(
            f"recent fires (last 5 years) have averaged {recent_avg} miles away, "
            f"closer than the historical average of {hist_avg} miles",
            "negative"
        ))

    freq_trend = fire_frequency.get("trend_label", "insufficient data")
    total = fire_frequency.get("total_fires", 0)
    if freq_trend == "accelerating":
        signals.append(signal(f"fire frequency is accelerating ({total} fires on record nearby)", "negative"))
    elif freq_trend == "declining":
        signals.append(signal(f"fire frequency has been declining recently ({total} fires on record)", "positive"))
    else:
        signals.append(signal(f"{total} fires on record within search radius", "neutral"))

    price_trend = price_trajectory.get("trend_label", "insufficient data")
    pct_5yr = price_trajectory.get("pct_change_5yr")
    current = price_trajectory.get("current_value")
    if current and pct_5yr is not None:
        direction = "neutral" if pct_5yr > 0 else "negative"
        signals.append(signal(
            f"current median home value ~${current:,}, "
            f"{'+' if pct_5yr > 0 else ''}{pct_5yr}% over last 5 years ({price_trend})",
            direction
        ))

    if hazard_zone and hazard_zone != "Unknown":
        direction = "negative" if hazard_zone in ("Very High", "High") else "neutral"
        signals.append(signal(f"official state hazard classification: {hazard_zone}", direction))

    risk_factors = sum([
        prox_trend == "increasing",
        freq_trend == "accelerating",
        hazard_zone in ("Very High", "High"),
        recent_avg is not None and recent_avg < 10,
    ])

    if risk_factors >= 3:
        composite_label = "high and increasing risk"
    elif risk_factors >= 2:
        composite_label = "moderate to high risk"
    elif risk_factors >= 1:
        composite_label = "moderate risk"
    else:
        composite_label = "lower risk based on available data"

    return {
        "composite_label": composite_label,
        "signals": signals,
        "risk_factor_count": risk_factors,
    }

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_trends(
    fire_history: Dict[str, Any],
    zhvi: Dict[str, Any],
    hazard_zone: str = "Unknown",
) -> Dict[str, Any]:
    """
    Main function — takes outputs of existing services and returns full trend analysis.

    Args:
        fire_history: output of get_nearby_fires()
        zhvi: output of get_home_value_timeseries()
        hazard_zone: string from fire_hazard_service

    Returns:
        Full trend analysis dict including composite signal
    """
    fires = fire_history.get("fires", []) if fire_history.get("found") else []
    timeseries = zhvi.get("timeseries", {}) if zhvi.get("found") else {}

    fire_proximity = analyze_fire_proximity_trend(fires)
    fire_frequency = analyze_fire_frequency(fires)
    price_trajectory = analyze_price_trajectory(timeseries)
    composite = compute_composite_signal(
        fire_proximity, fire_frequency, price_trajectory, hazard_zone
    )

    return {
        "fire_proximity": fire_proximity,
        "fire_frequency": fire_frequency,
        "price_trajectory": price_trajectory,
        "composite": composite,
    }


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Mock data matching real service output shapes
    mock_fire_history = {
        "found": True,
        "fires": [
            {"fire_name": "Topanga", "year": 2005, "acres": 23396, "distance_miles": 10.3},
            {"fire_name": "Corral", "year": 2007, "acres": 4708, "distance_miles": 8.9},
            {"fire_name": "Woolsey", "year": 2018, "acres": 89551, "distance_miles": 11.7},
            {"fire_name": "Getty", "year": 2019, "acres": 553, "distance_miles": 6.6},
            {"fire_name": "Palisades", "year": 2021, "acres": 1203, "distance_miles": 1.7},
            {"fire_name": "Palisades", "year": 2025, "acres": 23449, "distance_miles": 2.0},
        ]
    }
    mock_zhvi = {
        "found": True,
        "timeseries": {
            "2000": 380000, "2005": 750000, "2010": 620000,
            "2015": 800000, "2020": 1050000, "2024": 1420000,
        }
    }

    result = analyze_trends(mock_fire_history, mock_zhvi, hazard_zone="Very High")

    import json
    print(json.dumps(result, indent=2))