from __future__ import annotations

from typing import Dict, List

import pandas as pd



def find_pivot_lows(series: pd.Series, window: int = 3) -> List[int]:
    idxs: List[int] = []
    vals = series.reset_index(drop=True)
    for i in range(window, len(vals) - window):
        current = vals.iloc[i]
        left = vals.iloc[i - window:i]
        right = vals.iloc[i + 1:i + 1 + window]
        if current <= left.min() and current <= right.min():
            idxs.append(i)
    return idxs



def find_pivot_highs(series: pd.Series, window: int = 3) -> List[int]:
    idxs: List[int] = []
    vals = series.reset_index(drop=True)
    for i in range(window, len(vals) - window):
        current = vals.iloc[i]
        left = vals.iloc[i - window:i]
        right = vals.iloc[i + 1:i + 1 + window]
        if current >= left.max() and current >= right.max():
            idxs.append(i)
    return idxs



def pivot_spacing_score(indexes: List[int]) -> int:
    if len(indexes) < 2:
        return 0
    gaps = [b - a for a, b in zip(indexes[:-1], indexes[1:])]
    if min(gaps) >= 6:
        return 2
    if min(gaps) >= 3:
        return 1
    return 0



def swing_cleanliness(df: pd.DataFrame, start_idx: int, end_idx: int, side: str) -> Dict[str, float]:
    if end_idx <= start_idx:
        return {"score": 0, "noise_ratio": 1.0, "bars": 0}

    segment = df.iloc[start_idx : end_idx + 1].copy()
    bars = len(segment)
    if bars < 5:
        return {"score": 0, "noise_ratio": 1.0, "bars": bars}

    total_range = float(segment["high"].max() - segment["low"].min())
    body_sum = float((segment["close"] - segment["open"]).abs().sum())
    if total_range <= 0:
        return {"score": 0, "noise_ratio": 1.0, "bars": bars}

    noise_ratio = body_sum / (bars * total_range)

    if side == "long":
        path_ok = float(segment["low"].iloc[-1]) <= float(segment["low"].median())
    else:
        path_ok = float(segment["high"].iloc[-1]) >= float(segment["high"].median())

    score = 0
    if noise_ratio <= 0.18:
        score += 2
    elif noise_ratio <= 0.28:
        score += 1
    if path_ok:
        score += 1

    return {"score": score, "noise_ratio": round(noise_ratio, 4), "bars": bars}
