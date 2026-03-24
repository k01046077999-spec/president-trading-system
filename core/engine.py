from __future__ import annotations

import math
import time
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from core.config import APP_VERSION, MAIN_PROFILE, SUB_PROFILE, ScanProfile
from services.binance import BinanceService


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(method="bfill").fillna(50.0)

def _df(ohlcv: List[List[float]]) -> pd.DataFrame:
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["volume"] = df["volume"].astype(float)
    df["rsi"] = _rsi(df["close"])
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema60"] = df["close"].ewm(span=60, adjust=False).mean()
    return df

def _quote_volume_1h(df: pd.DataFrame, bars: int = 24) -> float:
    t = df.tail(bars)
    return float((t["close"] * t["volume"]).sum())

def _recent_pivots(series: pd.Series, left: int = 3, right: int = 3, kind: str = "low") -> List[int]:
    vals = series.values
    pivots = []
    for i in range(left, len(vals) - right):
        window = vals[i-left:i+right+1]
        center = vals[i]
        if kind == "low":
            if np.nanmin(window) == center and np.sum(window == center) == 1:
                pivots.append(i)
        else:
            if np.nanmax(window) == center and np.sum(window == center) == 1:
                pivots.append(i)
    return pivots[-8:]

def _bullish_divergence(df: pd.DataFrame) -> Tuple[bool, bool, List[str]]:
    lows = _recent_pivots(df["low"], kind="low")
    reasons = []
    if len(lows) < 2:
        return False, False, reasons
    i1, i2 = lows[-2], lows[-1]
    p1, p2 = float(df["low"].iloc[i1]), float(df["low"].iloc[i2])
    r1, r2 = float(df["rsi"].iloc[i1]), float(df["rsi"].iloc[i2])
    basic = p2 < p1 and r2 > r1
    linked = False
    if len(lows) >= 3:
        i0 = lows[-3]
        p0 = float(df["low"].iloc[i0]); r0 = float(df["rsi"].iloc[i0])
        linked = (p2 <= p1 <= p0) and (r2 >= r1 >= r0)
    if basic:
        reasons.append("상승 다이버전스")
    if linked:
        reasons.append("연계 다이버전스")
    return basic, linked, reasons

def _fib_metrics(df: pd.DataFrame) -> Dict[str, float]:
    lows = _recent_pivots(df["low"], kind="low")
    highs = _recent_pivots(df["high"], kind="high")
    if not lows or not highs:
        raise ValueError("스윙 부족")
    low_i = lows[-1]
    high_i = None
    for h in reversed(highs):
        if h < low_i:
            high_i = h
            break
    if high_i is None:
        # fallback: use rolling high before last 12 bars
        high_i = int(df["high"].iloc[:-12].idxmax())
    high = float(df["high"].iloc[high_i])
    low = float(df["low"].iloc[low_i])
    if high <= low:
        raise ValueError("스윙 고저 비정상")
    current = float(df["close"].iloc[-1])
    diff = high - low
    fib_618 = high - diff * 0.618
    fib_786 = high - diff * 0.786
    fib_1 = low
    return {
        "high": high, "low": low, "current": current,
        "fib_618": fib_618, "fib_786": fib_786, "fib_1": fib_1,
        "in_zone": float(fib_786 <= current <= fib_618),
    }

def _stage1_quick_symbol(symbol: str, svc: BinanceService, profile: ScanProfile) -> Dict:
    df = _df(svc.fetch_ohlcv(symbol, "1h", limit=180))
    qv = _quote_volume_1h(df, 24)
    last = float(df["close"].iloc[-1])
    rsi = float(df["rsi"].iloc[-1])
    low20 = float(df["low"].tail(20).min())
    high20 = float(df["high"].tail(20).max())
    range_pct = 0.0 if low20 <= 0 else (high20 - low20) / low20 * 100
    volume_ratio = float(df["volume"].tail(5).mean() / max(df["volume"].tail(20).mean(), 1e-9))
    basic_div, linked_div, div_reasons = _bullish_divergence(df)

    score = 0.0
    reasons, warnings, rejected_by = [], [], []

    if qv >= profile.min_quote_volume:
        score += 1.0
        reasons.append("최소 거래대금 통과")
    else:
        rejected_by.append("quote_volume_low")

    if profile.stage1_rsi_low <= rsi <= profile.stage1_rsi_high:
        score += 1.0
        reasons.append("RSI 선별 통과")
    else:
        rejected_by.append("rsi_out_of_range")

    if last > float(df["ema20"].iloc[-1]) or float(df["ema20"].iloc[-1]) > float(df["ema60"].iloc[-1]):
        score += 0.5
        reasons.append("단기 구조 훼손 아님")

    if volume_ratio >= 1.05:
        score += 0.5
        reasons.append("거래량 최근 개선")
    else:
        warnings.append("거래량 개선 약함")

    if range_pct > 35:
        warnings.append("단기 변동성 과열 가능")
    else:
        score += 0.5

    if basic_div:
        score += 1.0
        reasons.extend(div_reasons)
    if linked_div:
        score += 1.5

    passed = score >= profile.stage1_score_min and "quote_volume_low" not in rejected_by

    return {
        "symbol": symbol.replace("/", ""),
        "symbol_ccxt": symbol,
        "passed": passed,
        "stage1_score": round(score, 2),
        "reasons": reasons,
        "warnings": warnings,
        "rejected_by": rejected_by,
        "last": round(last, 8),
        "quote_volume_24h_est": round(qv, 2),
        "rsi": round(rsi, 2),
    }

def _precise_symbol(symbol_ccxt: str, mode: str, svc: BinanceService) -> Dict:
    df1 = _df(svc.fetch_ohlcv(symbol_ccxt, "1h", limit=220))
    df30 = _df(svc.fetch_ohlcv(symbol_ccxt, "30m", limit=220))
    df4 = _df(svc.fetch_ohlcv(symbol_ccxt, "4h", limit=220))

    reasons, warnings, rejected_by, downgraded_by = [], [], [], []
    basic1, linked1, div1 = _bullish_divergence(df1)
    basic30, linked30, div30 = _bullish_divergence(df30)
    basic4, linked4, div4 = _bullish_divergence(df4)

    fib = _fib_metrics(df1)
    current = fib["current"]
    stop = fib["fib_1"]
    stop_pct = ((stop - current) / current) * 100

    score = 0.0
    if basic1:
        score += 2.0; reasons.append("1시간봉 상승 다이버전스")
    else:
        rejected_by.append("divergence_1h_missing")

    if linked1:
        score += 2.0; reasons.append("1시간봉 연계 다이버전스")
    if basic30:
        score += 1.0; reasons.append("30분봉 재확인")
    if linked30:
        score += 1.0; reasons.append("30분봉 연계")
    if basic4:
        score += 0.5; reasons.append("4시간봉 보조 확인")

    if fib["in_zone"] == 1.0:
        score += 2.0; reasons.append("Fib 0.618~0.786 구간")
    else:
        downgraded_by.append("fib_zone_miss")

    if -12.0 <= stop_pct <= -1.0:
        score += 1.0
    else:
        rejected_by.append("stop_range_invalid")

    # targets by simple structure
    high = fib["high"]; diff = high - stop
    tp1 = current + diff * 0.382
    tp2 = current + diff * 0.618
    tp3 = current + diff * 1.0
    tp1_pct = ((tp1 - current) / current) * 100
    tp2_pct = ((tp2 - current) / current) * 100
    tp3_pct = ((tp3 - current) / current) * 100

    rr1 = abs(tp1_pct / stop_pct) if stop_pct < 0 else None
    rr2 = abs(tp2_pct / stop_pct) if stop_pct < 0 else None
    rr3 = abs(tp3_pct / stop_pct) if stop_pct < 0 else None

    if rr1 is not None and rr1 >= 1.3:
        score += 1.0; reasons.append("손익비 1차 기준 통과")
    else:
        downgraded_by.append("rr1_low")

    state = "watch"
    passed = False
    if mode == "main":
        if score >= MAIN_PROFILE.final_score_min and not rejected_by:
            state = "ready"; passed = True
        elif score >= max(MAIN_PROFILE.final_score_min - 1.5, 4.5) and MAIN_PROFILE.allow_watch:
            state = "watch"
        else:
            state = "reject"
    else:
        if score >= SUB_PROFILE.final_score_min and not rejected_by:
            state = "ready"; passed = True
        elif score >= max(SUB_PROFILE.final_score_min - 1.0, 3.0):
            state = "watch"
        else:
            state = "reject"

    if not passed and state != "watch":
        msg = f"현재 {mode} 조건 미충족"
    elif state == "watch":
        msg = f"현재 {mode} 관찰 후보"
    else:
        msg = f"현재 {mode} 진입 후보"

    return {
        "symbol": symbol_ccxt.replace("/", ""),
        "mode": mode,
        "passed": passed,
        "state": state,
        "direction": "long",
        "score": round(score, 2),
        "entry_reference_price": round(current, 8),
        "stop_pct": round(stop_pct, 2),
        "tp1_pct": round(tp1_pct, 2),
        "tp2_pct": round(tp2_pct, 2),
        "tp3_pct": round(tp3_pct, 2),
        "rr1": round(rr1, 2) if rr1 is not None else None,
        "rr2": round(rr2, 2) if rr2 is not None else None,
        "rr3": round(rr3, 2) if rr3 is not None else None,
        "message": msg,
        "reasons": reasons,
        "warnings": warnings,
        "rejected_by": rejected_by,
        "downgraded_by": downgraded_by,
    }

class PresidentTradingEngine:
    def __init__(self) -> None:
        self.svc = BinanceService()

    def _profile(self, mode: str) -> ScanProfile:
        return MAIN_PROFILE if mode == "main" else SUB_PROFILE

    def analyze_symbol(self, symbol: str, mode: str = "main") -> Dict:
        if "/" not in symbol:
            symbol = symbol.replace("USDT", "/USDT")
        try:
            return _precise_symbol(symbol, mode=mode, svc=self.svc)
        except Exception as e:
            return {
                "symbol": symbol.replace("/", ""),
                "mode": mode,
                "passed": False,
                "state": "reject",
                "direction": "neutral",
                "score": 0.0,
                "message": f"심볼 분석 실패: {e}",
                "warnings": [],
                "reasons": [],
                "rejected_by": [],
                "downgraded_by": [],
            }

    def scan(self, mode: str = "main", limit: int = 10) -> Dict:
        profile = self._profile(mode)
        started = time.time()
        errors: List[str] = []
        stopped_reason = None

        universe = self.svc.fetch_dynamic_universe(
            pool_size=profile.pool_size,
            min_quote_volume=profile.min_quote_volume
        )

        stage1 = []
        for idx, symbol in enumerate(universe, start=1):
            if time.time() - started > profile.time_budget_sec * 0.45:
                stopped_reason = "stage1_time_budget_exceeded"
                break
            if len(stage1) >= profile.stage1_limit:
                stopped_reason = stopped_reason or "stage1_limit_reached"
                break
            try:
                s1 = _stage1_quick_symbol(symbol, self.svc, profile)
                if s1["passed"]:
                    stage1.append(s1)
            except Exception as e:
                errors.append(f"{symbol}: {type(e).__name__}: {e}")

        stage1.sort(key=lambda x: (x["stage1_score"], x["quote_volume_24h_est"]), reverse=True)
        shortlisted = stage1[: profile.stage2_limit]

        items = []
        for s1 in shortlisted:
            if time.time() - started > profile.time_budget_sec:
                stopped_reason = stopped_reason or "time_budget_exceeded"
                break
            try:
                item = _precise_symbol(s1["symbol_ccxt"], mode=mode, svc=self.svc)
                # carry forward quick reasons
                item["warnings"] = list(dict.fromkeys(item["warnings"] + s1["warnings"]))
                if item["passed"] or (profile.allow_watch and item["state"] == "watch"):
                    items.append(item)
            except Exception as e:
                errors.append(f"{s1['symbol']}: {type(e).__name__}: {e}")

        items.sort(key=lambda x: (x["state"] == "ready", x["score"], x.get("rr1") or 0), reverse=True)
        items = items[:limit]

        status = "partial" if errors or stopped_reason else "ok"
        msg = (
            f"현재 {mode} 조건을 만족하는 종목이 없습니다."
            if not items
            else f"현재 {mode} 후보 {len(items)}개 포착"
        )
        if stopped_reason == "time_budget_exceeded":
            msg += " 빠른 응답을 위해 시간 예산 내에서 스캔을 중단했습니다."
        elif stopped_reason and stopped_reason.startswith("stage1_"):
            msg += " 전체 후보군 선별 중 제한에 도달했습니다."

        return {
            "status": status,
            "mode": mode,
            "count": len(items),
            "candidate_pool": len(universe),
            "stage1_checked": min(len(universe), len(stage1) + len(errors)),
            "stage2_checked": len(shortlisted),
            "scan_seconds": round(time.time() - started, 2),
            "stopped_reason": stopped_reason,
            "items": items,
            "message": msg,
            "errors": errors[:20],
        }
