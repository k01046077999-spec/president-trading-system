from __future__ import annotations

from typing import Dict, Optional



def build_fib_levels(swing_low: float, swing_high: float, side: str) -> Dict[str, float]:
    diff = swing_high - swing_low
    if side == "long":
        return {
            "0": swing_high,
            "0.382": swing_high - diff * 0.382,
            "0.5": swing_high - diff * 0.5,
            "0.618": swing_high - diff * 0.618,
            "0.786": swing_high - diff * 0.786,
            "1": swing_low,
            "1.272": swing_high + diff * 0.272,
            "1.618": swing_high + diff * 0.618,
        }
    return {
        "0": swing_low,
        "0.382": swing_low + diff * 0.382,
        "0.5": swing_low + diff * 0.5,
        "0.618": swing_low + diff * 0.618,
        "0.786": swing_low + diff * 0.786,
        "1": swing_high,
        "1.272": swing_low - diff * 0.272,
        "1.618": swing_low - diff * 0.618,
    }



def _distance_pct(a: float, b: float) -> float:
    if a == 0:
        return 0.0
    return abs(a - b) / a * 100



def fib_zone_status(current_price: float, levels: Dict[str, float], low_ratio: float, high_ratio: float, side: str) -> Dict[str, object]:
    lo_key = str(low_ratio)
    hi_key = str(high_ratio)
    lower = min(levels[lo_key], levels[hi_key])
    upper = max(levels[lo_key], levels[hi_key])
    in_zone = lower <= current_price <= upper
    zone_mid = (lower + upper) / 2
    preferred_entry = current_price if in_zone else zone_mid
    return {
        "in_zone": in_zone,
        "zone_lower": lower,
        "zone_upper": upper,
        "zone_mid": zone_mid,
        "preferred_entry": preferred_entry,
        "distance_to_zone_pct": 0.0 if in_zone else _distance_pct(current_price, lower if current_price < lower else upper),
        "entry_status": "ready" if in_zone else "wait",
    }



def trade_levels(entry_price: float, levels: Dict[str, float], side: str) -> Dict[str, float]:
    stop_price = levels["1"]
    tp1 = levels["0"]
    tp2 = levels["1.272"]
    tp3 = levels["1.618"]

    if side == "long":
        stop_pct = (stop_price - entry_price) / entry_price * 100
        tp1_pct = (tp1 - entry_price) / entry_price * 100
        tp2_pct = (tp2 - entry_price) / entry_price * 100
        tp3_pct = (tp3 - entry_price) / entry_price * 100
    else:
        stop_pct = (entry_price - stop_price) / entry_price * 100
        tp1_pct = (entry_price - tp1) / entry_price * 100
        tp2_pct = (entry_price - tp2) / entry_price * 100
        tp3_pct = (entry_price - tp3) / entry_price * 100

    stop_abs = abs(stop_pct) if stop_pct != 0 else 0.0
    rr1 = abs(tp1_pct) / stop_abs if stop_abs else 0.0
    rr2 = abs(tp2_pct) / stop_abs if stop_abs else 0.0
    rr3 = abs(tp3_pct) / stop_abs if stop_abs else 0.0
    return {
        "stop_price": stop_price,
        "stop_pct": stop_pct,
        "tp1_price": tp1,
        "tp1_pct": tp1_pct,
        "tp2_price": tp2,
        "tp2_pct": tp2_pct,
        "tp3_price": tp3,
        "tp3_pct": tp3_pct,
        "rr1": rr1,
        "rr2": rr2,
        "rr3": rr3,
    }



def build_swing_from_divergence(divergence: Dict, df, structure_lookback_bars: int = 80) -> Optional[Dict[str, float]]:
    idxs = divergence["pivot_indexes"]
    side = divergence["side"]
    trigger_idx = idxs[-1]
    start_idx = max(0, trigger_idx - structure_lookback_bars)
    segment = df.iloc[start_idx : trigger_idx + 1]
    if segment.empty:
        return None

    if side == "long":
        swing_low = float(df["low"].iloc[trigger_idx])
        left_high = float(segment["high"].max())
        recent_high = float(df["high"].iloc[trigger_idx:].tail(30).max())
        swing_high = max(left_high, recent_high)
        if swing_high <= swing_low:
            return None
        return {"swing_low": swing_low, "swing_high": swing_high, "start_idx": start_idx, "end_idx": trigger_idx}

    swing_high = float(df["high"].iloc[trigger_idx])
    left_low = float(segment["low"].min())
    recent_low = float(df["low"].iloc[trigger_idx:].tail(30).min())
    swing_low = min(left_low, recent_low)
    if swing_high <= swing_low:
        return None
    return {"swing_low": swing_low, "swing_high": swing_high, "start_idx": start_idx, "end_idx": trigger_idx}
