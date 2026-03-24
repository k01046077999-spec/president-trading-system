from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator

from core import config
from services.binance import BinanceService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


class PresidentTradingEngine:
    def __init__(self) -> None:
        self.client = BinanceService()

    def scan(self, mode: str, limit: int = 10) -> Dict[str, Any]:
        candidate_pool = config.MAIN_CANDIDATE_POOL if mode == "main" else config.SUB_CANDIDATE_POOL
        stage2_max = config.MAIN_STAGE2_MAX if mode == "main" else config.SUB_STAGE2_MAX
        min_quote = config.MIN_QUOTE_VOLUME_MAIN if mode == "main" else config.MIN_QUOTE_VOLUME_SUB

        tickers = self.client.fetch_tickers()
        universe = self._build_universe(tickers, candidate_pool, min_quote)

        stage1_pass: List[Tuple[str, float, Dict[str, Any]]] = []
        errors: List[str] = []

        for symbol, quote_volume in universe:
            try:
                candles = self.client.fetch_ohlcv(symbol, "1h", config.OHLCV_LIMIT_1H)
                stage1 = self._stage1_screen(candles, mode=mode)
                if stage1["passed"]:
                    stage1_pass.append((symbol, stage1["priority"], {"quote_volume": quote_volume, **stage1}))
            except Exception as exc:
                errors.append(f"{symbol}: {type(exc).__name__}: {exc}")

        stage1_pass.sort(key=lambda x: x[1], reverse=True)
        stage2_symbols = stage1_pass[:stage2_max]

        items: List[Dict[str, Any]] = []
        for symbol, _, meta in stage2_symbols:
            try:
                item = self._stage2_analyze(symbol, mode=mode, stage1_meta=meta)
                if item["state"] != "rejected":
                    items.append(item)
            except Exception as exc:
                errors.append(f"{symbol}: {type(exc).__name__}: {exc}")

        items.sort(key=lambda x: (0 if x["state"] == "ready" else 1, -x["score"]))
        items = items[:limit]

        status = "partial" if errors else "ok"
        message = (
            f"현재 {mode} 조건을 만족하는 종목이 없습니다."
            if not items
            else f"현재 {mode} 조건을 만족하는 종목 {len(items)}개입니다."
        )
        return {
            "status": status,
            "mode": mode,
            "count": len(items),
            "candidate_pool": len(universe),
            "stage1_checked": len(universe),
            "stage2_checked": len(stage2_symbols),
            "items": items,
            "message": message,
            "errors": errors[:20],
        }

    def analyze_symbol(self, symbol: str, mode: str) -> Dict[str, Any]:
        return self._stage2_analyze(symbol.replace("USDT","/USDT") if "/" not in symbol else symbol, mode, {})

    def _build_universe(self, tickers: Dict[str, Any], top_n: int, min_quote: float) -> List[Tuple[str, float]]:
        rows: List[Tuple[str, float]] = []
        for symbol, data in tickers.items():
            if not symbol.endswith("/USDT"):
                continue
            if symbol in config.EXCLUDED_EXACT:
                continue
            if any(symbol.endswith(suffix) for suffix in config.EXCLUDED_SUFFIXES):
                continue
            quote_volume = float(data.get("quoteVolume") or 0.0)
            if quote_volume < min_quote:
                continue
            rows.append((symbol, quote_volume))
        rows.sort(key=lambda x: x[1], reverse=True)
        return rows[:top_n]

    def _to_df(self, candles: List[List[float]]) -> pd.DataFrame:
        if not candles:
            raise ValueError("OHLCV empty")
        df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume"])
        df["rsi"] = RSIIndicator(close=df["close"], window=14).rsi()
        df["vol_ma20"] = df["volume"].rolling(20).mean()
        return df.dropna().reset_index(drop=True)

    def _stage1_screen(self, candles: List[List[float]], mode: str) -> Dict[str, Any]:
        df = self._to_df(candles)
        if len(df) < 60:
            return {"passed": False, "priority": -1.0}

        close = df["close"]
        low = df["low"]
        vol = df["volume"]
        rsi = df["rsi"]

        recent = df.iloc[-24:]
        current_rsi = float(rsi.iloc[-1])
        rsi_low = float(rsi.iloc[-12:-1].min())
        price_now = float(close.iloc[-1])
        prior_price_low = float(low.iloc[-18:-4].min())
        recent_price_low = float(low.iloc[-4:].min())
        vol_now = float(vol.iloc[-1])
        vol_ma = float(df["vol_ma20"].iloc[-1])

        # 대충이라도 bullish 구조 선별: RSI 개선 + 저점 재방문/미세 LL + 거래량
        divergence_hint = current_rsi > rsi_low and recent_price_low <= prior_price_low * 1.01
        rsi_recovery = 28 <= current_rsi <= (56 if mode == "sub" else 50)
        volume_ok = vol_now >= vol_ma * (0.9 if mode == "sub" else 1.0)
        non_overextended = price_now <= float(close.iloc[-24:].max()) * (0.97 if mode == "main" else 0.99)

        passed = divergence_hint and rsi_recovery and volume_ok and non_overextended
        priority = (
            (current_rsi - rsi_low) * 1.5
            + (1.0 if volume_ok else -1.0)
            + (1.0 if non_overextended else -2.0)
        )
        return {
            "passed": bool(passed),
            "priority": float(priority),
            "current_rsi": current_rsi,
            "divergence_hint": divergence_hint,
            "volume_ok": volume_ok,
        }

    def _stage2_analyze(self, symbol: str, mode: str, stage1_meta: Dict[str, Any]) -> Dict[str, Any]:
        df1h = self._to_df(self.client.fetch_ohlcv(symbol, "1h", config.OHLCV_LIMIT_1H))
        df30 = self._to_df(self.client.fetch_ohlcv(symbol, "30m", config.OHLCV_LIMIT_30M))
        df4h = self._to_df(self.client.fetch_ohlcv(symbol, "4h", config.OHLCV_LIMIT_4H))

        price = float(df1h["close"].iloc[-1])
        swing_low = float(df1h["low"].iloc[-30:].min())
        swing_high = float(df1h["high"].iloc[-30:].max())
        if swing_high <= swing_low:
            raise ValueError("invalid swing")

        # fib
        diff = swing_high - swing_low
        fib_618 = swing_high - diff * 0.618
        fib_786 = swing_high - diff * 0.786
        stop_price = swing_low * 0.995
        tp1 = fib_618 + diff * 0.25
        tp2 = swing_high * 1.01

        stop_pct = round((stop_price - price) / price * 100, 2)
        tp1_pct = round((tp1 - price) / price * 100, 2)
        tp2_pct = round((tp2 - price) / price * 100, 2)
        rr1 = round(abs(tp1_pct / stop_pct), 2) if stop_pct < 0 else None
        rr2 = round(abs(tp2_pct / stop_pct), 2) if stop_pct < 0 else None

        in_fib = min(fib_618, fib_786) <= price <= max(fib_618, fib_786)
        rsi1h = float(df1h["rsi"].iloc[-1])
        rsi30 = float(df30["rsi"].iloc[-1])
        rsi4h = float(df4h["rsi"].iloc[-1])

        score = 0.0
        reasons = []
        warnings = []
        rejected_by = []
        downgraded_by = []

        if stage1_meta.get("divergence_hint"):
            score += 2.0
            reasons.append("1시간봉 다이버전스 힌트")
        if 30 <= rsi1h <= 52:
            score += 1.5
            reasons.append("1시간봉 RSI 위치 양호")
        if 30 <= rsi30 <= 58:
            score += 1.0
            reasons.append("30분봉 재확인")
        if 35 <= rsi4h <= 60:
            score += 0.5
            reasons.append("4시간봉 보조 확인")
        if in_fib:
            score += 2.0
            reasons.append("Fib 0.618~0.786 구간")
        else:
            rejected_by.append("fib_zone_fail")
        if stop_pct < -12:
            downgraded_by.append("stop_too_wide")
            warnings.append("손절폭 큼")
            score -= 1.0
        if rr1 is not None and rr1 < (1.2 if mode == "sub" else 1.4):
            downgraded_by.append("rr1_low")
            warnings.append("손익비 낮음")
            score -= 1.0

        ready_threshold = 5.0 if mode == "main" else 4.0
        watch_threshold = 3.0 if mode == "main" else 2.5

        if rejected_by and mode == "main":
            state = "rejected"
        elif score >= ready_threshold:
            state = "ready"
        elif score >= watch_threshold:
            state = "watch"
        else:
            state = "rejected"

        if not reasons:
            reasons.append("구조상 강한 근거 부족")

        item = {
            "symbol": symbol.replace("/", ""),
            "state": state,
            "direction": "long",
            "stop_pct": stop_pct,
            "tp1_pct": tp1_pct,
            "tp2_pct": tp2_pct,
            "rr1": rr1,
            "rr2": rr2,
            "score": round(score, 2),
            "reason_summary": ", ".join(reasons[:3]),
            "warnings": warnings,
            "rejected_by": rejected_by,
            "downgraded_by": downgraded_by,
        }
        return item
