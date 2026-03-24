from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from core.swings import find_pivot_highs, find_pivot_lows, pivot_spacing_score



def _extreme_score(value: float, bullish: bool) -> int:
    if bullish:
        if value <= 30:
            return 2
        if value <= 40:
            return 1
        return 0
    if value >= 70:
        return 2
    if value >= 60:
        return 1
    return 0



def _price_rsi_strength(price_a: float, price_b: float, rsi_a: float, rsi_b: float) -> float:
    price_change = abs(price_b - price_a) / max(abs(price_a), 1e-9)
    rsi_change = abs(rsi_b - rsi_a) / 100.0
    return round(price_change + rsi_change, 4)



def detect_bullish_divergence(df: pd.DataFrame, pivot_window: int = 3, min_spacing: int = 4) -> Optional[Dict]:
    lows = find_pivot_lows(df["low"], window=pivot_window)
    if len(lows) < 2:
        return None

    recent = lows[-3:]
    low_series = df["low"].reset_index(drop=True)
    close = df["close"].reset_index(drop=True)
    rsi = df["rsi"].reset_index(drop=True)

    p1, p2 = recent[-2], recent[-1]
    if p2 - p1 < min_spacing:
        return None

    regular = low_series.iloc[p2] < low_series.iloc[p1] and rsi.iloc[p2] > rsi.iloc[p1]

    linked = False
    if len(recent) == 3:
        p0 = recent[0]
        linked = (
            (p1 - p0) >= min_spacing
            and low_series.iloc[p2] <= low_series.iloc[p1] <= low_series.iloc[p0]
            and rsi.iloc[p2] >= rsi.iloc[p1] >= rsi.iloc[p0]
        )

    if not regular and not linked:
        return None

    strength = _price_rsi_strength(float(low_series.iloc[p1]), float(low_series.iloc[p2]), float(rsi.iloc[p1]), float(rsi.iloc[p2]))
    return {
        "side": "long",
        "pivot_indexes": recent,
        "regular": regular,
        "linked": linked,
        "trigger_index": p2,
        "trigger_price": float(close.iloc[p2]),
        "pivot_low": float(low_series.iloc[p2]),
        "rsi_at_trigger": float(rsi.iloc[p2]),
        "extreme_score": _extreme_score(float(rsi.iloc[p2]), bullish=True),
        "spacing_score": pivot_spacing_score(recent),
        "strength": strength,
    }



def detect_bearish_divergence(df: pd.DataFrame, pivot_window: int = 3, min_spacing: int = 4) -> Optional[Dict]:
    highs = find_pivot_highs(df["high"], window=pivot_window)
    if len(highs) < 2:
        return None

    recent = highs[-3:]
    high_series = df["high"].reset_index(drop=True)
    close = df["close"].reset_index(drop=True)
    rsi = df["rsi"].reset_index(drop=True)

    p1, p2 = recent[-2], recent[-1]
    if p2 - p1 < min_spacing:
        return None

    regular = high_series.iloc[p2] > high_series.iloc[p1] and rsi.iloc[p2] < rsi.iloc[p1]

    linked = False
    if len(recent) == 3:
        p0 = recent[0]
        linked = (
            (p1 - p0) >= min_spacing
            and high_series.iloc[p2] >= high_series.iloc[p1] >= high_series.iloc[p0]
            and rsi.iloc[p2] <= rsi.iloc[p1] <= rsi.iloc[p0]
        )

    if not regular and not linked:
        return None

    strength = _price_rsi_strength(float(high_series.iloc[p1]), float(high_series.iloc[p2]), float(rsi.iloc[p1]), float(rsi.iloc[p2]))
    return {
        "side": "short",
        "pivot_indexes": recent,
        "regular": regular,
        "linked": linked,
        "trigger_index": p2,
        "trigger_price": float(close.iloc[p2]),
        "pivot_high": float(high_series.iloc[p2]),
        "rsi_at_trigger": float(rsi.iloc[p2]),
        "extreme_score": _extreme_score(float(rsi.iloc[p2]), bullish=False),
        "spacing_score": pivot_spacing_score(recent),
        "strength": strength,
    }



def best_divergence(df: pd.DataFrame, pivot_window: int = 3, min_spacing: int = 4) -> Optional[Dict]:
    bull = detect_bullish_divergence(df, pivot_window=pivot_window, min_spacing=min_spacing)
    bear = detect_bearish_divergence(df, pivot_window=pivot_window, min_spacing=min_spacing)
    candidates: List[Dict] = [x for x in [bull, bear] if x]
    if not candidates:
        return None
    candidates.sort(
        key=lambda x: (x["linked"], x["extreme_score"], x["spacing_score"], x["strength"], x["trigger_index"]),
        reverse=True,
    )
    return candidates[0]
