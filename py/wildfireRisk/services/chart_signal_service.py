"""
Helpers for chart-oriented derived signals.
Keeps API layer thin by moving computation logic out of app.py.
"""

from __future__ import annotations

import math
from typing import Optional


def summarize_rent_trajectory(zillow_overlay: dict) -> dict:
    if not zillow_overlay or not zillow_overlay.get("found"):
        return {"available": False}

    ts = zillow_overlay.get("timeseries", {})
    if not ts or len(ts) < 2:
        return {"available": False}

    years = sorted(ts.keys())
    max_year = max(years)
    min_year = min(years)
    current_value = ts[max_year]

    recent_start = str(int(max_year) - 5)
    recent_years = [y for y in years if y >= recent_start]

    pct_change_5yr = None
    trend_label = "insufficient data"
    if len(recent_years) >= 2:
        start_val = ts[recent_years[0]]
        if start_val:
            pct_change_5yr = round((current_value - start_val) / start_val * 100, 1)
            if pct_change_5yr > 20:
                trend_label = "strong growth"
            elif pct_change_5yr > 5:
                trend_label = "moderate growth"
            elif pct_change_5yr > -5:
                trend_label = "flat"
            else:
                trend_label = "declining"

    return {
        "available": True,
        "current_value": round(current_value, 1),
        "pct_change_5yr": pct_change_5yr,
        "trend_label": trend_label,
        "year_range": f"{min_year}-{max_year}",
    }


def _pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - x_mean) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - y_mean) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def summarize_cross_signals(
    fire_history: dict,
    zhvi: dict,
    zillow_overlay: dict,
) -> dict:
    if not fire_history.get("found") or not fire_history.get("fires"):
        return {"available": False}

    # One fire-distance value per year: closest recorded fire in that year.
    fire_by_year: dict[int, float] = {}
    for fire in fire_history.get("fires", []):
        year = fire.get("year")
        dist = fire.get("distance_miles")
        if year is None or dist is None:
            continue
        if year not in fire_by_year or dist < fire_by_year[year]:
            fire_by_year[year] = float(dist)

    if len(fire_by_year) < 3:
        return {"available": False}

    fire_series = {str(y): v for y, v in fire_by_year.items()}
    home_series = zhvi.get("timeseries", {}) if zhvi.get("found") else {}
    rent_series = zillow_overlay.get("timeseries", {}) if zillow_overlay.get("found") else {}

    home_years = sorted(set(fire_series).intersection(home_series))
    rent_years = sorted(set(fire_series).intersection(rent_series))

    home_corr = None
    if len(home_years) >= 3:
        home_corr = _pearson(
            [fire_series[y] for y in home_years],
            [float(home_series[y]) for y in home_years],
        )

    rent_corr = None
    if len(rent_years) >= 3:
        rent_corr = _pearson(
            [fire_series[y] for y in rent_years],
            [float(rent_series[y]) for y in rent_years],
        )

    return {
        "available": True,
        "home_overlap_years": len(home_years),
        "rent_overlap_years": len(rent_years),
        "home_fire_distance_corr": round(home_corr, 3) if home_corr is not None else None,
        "rent_fire_distance_corr": round(rent_corr, 3) if rent_corr is not None else None,
    }
