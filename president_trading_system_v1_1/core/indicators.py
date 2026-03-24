from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_gain = up.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = down.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    return result.fillna(50)


def volume_ratio(series: pd.Series, fast: int = 5, slow: int = 20) -> float:
    if len(series) < slow + 2:
        return 0.0
    fast_ma = series.tail(fast).mean()
    slow_ma = series.tail(slow).mean()
    if slow_ma == 0:
        return 0.0
    return float((fast_ma / slow_ma) - 1)


def recent_pump_pct(close: pd.Series, bars: int = 12) -> float:
    if len(close) < bars:
        return 0.0
    window = close.tail(bars)
    low = float(window.min())
    high = float(window.max())
    if low <= 0:
        return 0.0
    return (high - low) / low * 100
