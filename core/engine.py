from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from core.config import ScanConfig
from core.divergence import best_divergence, detect_bearish_divergence, detect_bullish_divergence
from core.fibonacci import build_fib_levels, build_swing_from_divergence, fib_zone_status, trade_levels
from core.indicators import recent_pump_pct, rsi, volume_ratio
from core.scoring import score_candidate
from core.swings import swing_cleanliness
from services.binance import BinanceService


class PresidentTradingEngine:
    def __init__(self, service: Optional[BinanceService] = None) -> None:
        self.service = service or BinanceService()

    def _prepare(self, df: pd.DataFrame, rsi_period: int) -> pd.DataFrame:
        out = df.copy()
        out["rsi"] = rsi(out["close"], period=rsi_period)
        return out

    def _level_gap_pct(self, df: pd.DataFrame, reference_price: float, side: str) -> float:
        lookback = df.tail(60)
        if side == "long":
            resistance = float(lookback["high"].max())
            return (resistance - reference_price) / reference_price * 100
        support = float(lookback["low"].min())
        return (reference_price - support) / reference_price * 100

    def analyze_symbol(self, symbol: str, mode: str = "main") -> Dict:
        cfg = ScanConfig(mode=mode)
        df_1h = self._prepare(self.service.ohlcv(symbol, "1h", cfg.lookback_bars), cfg.rsi_period)
        df_30m = self._prepare(self.service.ohlcv(symbol, "30m", cfg.lookback_bars), cfg.rsi_period)
        df_4h = self._prepare(self.service.ohlcv(symbol, "4h", cfg.lookback_bars), cfg.rsi_period)

        div_1h = best_divergence(df_1h, pivot_window=cfg.pivot_window, min_spacing=cfg.min_pivot_spacing)
        if not div_1h:
            return {"symbol": symbol, "passed": False, "reason": "1시간봉 유효 다이버전스 없음"}

        side = div_1h["side"]
        confirm_30m = (
            detect_bullish_divergence(df_30m, cfg.pivot_window, cfg.min_pivot_spacing)
            if side == "long"
            else detect_bearish_divergence(df_30m, cfg.pivot_window, cfg.min_pivot_spacing)
        )
        confirm_4h = (
            detect_bullish_divergence(df_4h, cfg.pivot_window, cfg.min_pivot_spacing)
            if side == "long"
            else detect_bearish_divergence(df_4h, cfg.pivot_window, cfg.min_pivot_spacing)
        )

        swing = build_swing_from_divergence(div_1h, df_1h, structure_lookback_bars=cfg.structure_lookback_bars)
        if not swing:
            return {"symbol": symbol, "passed": False, "reason": "스윙 계산 실패"}

        current_price = float(df_1h["close"].iloc[-1])
        levels = build_fib_levels(swing["swing_low"], swing["swing_high"], side=side)
        zone = fib_zone_status(current_price, levels, cfg.fib_zone_low, cfg.fib_zone_high, side)
        entry_reference = float(zone["preferred_entry"])
        trades = trade_levels(entry_reference, levels, side)

        vol_ratio = volume_ratio(df_1h["volume"])
        pump_pct = recent_pump_pct(df_1h["close"], bars=12)
        level_gap = self._level_gap_pct(df_1h, entry_reference, side)
        structure = swing_cleanliness(df_1h, swing["start_idx"], swing["end_idx"], side)

        quality = score_candidate(
            divergence=div_1h,
            zone=zone,
            volume_ratio_value=vol_ratio,
            recent_pump=0 if pump_pct <= cfg.max_recent_pump_pct else pump_pct,
            level_gap_pct=level_gap,
            rr1=trades["rr1"],
            structure_score=structure["score"],
            mode=mode,
        )

        if confirm_30m:
            quality["score"] += 1
            quality["reasons"].append("30분봉 재확인")
        else:
            quality["warnings"].append("30분봉 재확인 없음")

        if confirm_4h and confirm_4h.get("regular"):
            quality["score"] += 1
            quality["reasons"].append("4시간봉 보조확인")

        ticker = self.service.ticker(symbol)
        stop_abs = abs(trades["stop_pct"])
        stop_ok = cfg.min_stop_pct <= stop_abs <= cfg.max_stop_pct
        rr_ok = trades["rr1"] >= cfg.min_reward_risk
        liquidity_ok = ticker.get("quoteVolume", 0) >= cfg.min_quote_volume_usdt
        pump_ok = pump_pct <= cfg.max_recent_pump_pct
        level_gap_ok = level_gap >= (cfg.resistance_buffer_pct if side == "long" else cfg.support_buffer_pct)
        structure_ok = structure["score"] >= cfg.min_structure_score

        passed = all([
            quality["passed"],
            stop_ok,
            rr_ok,
            liquidity_ok,
            pump_ok,
            level_gap_ok,
            structure_ok,
        ])

        status = "ready" if zone["in_zone"] else "watch"
        trade_plan = "즉시 검토" if zone["in_zone"] else "진입구간 대기"

        return {
            "symbol": symbol,
            "mode": mode,
            "side": side,
            "status": status,
            "trade_plan": trade_plan,
            "passed": passed,
            "score": quality["score"],
            "current_price": round(current_price, 6),
            "entry_reference_price": round(entry_reference, 6),
            "entry_zone": {
                "lower": round(zone["zone_lower"], 6),
                "upper": round(zone["zone_upper"], 6),
                "mid": round(zone["zone_mid"], 6),
                "distance_to_zone_pct": round(zone["distance_to_zone_pct"], 2),
                "in_zone": zone["in_zone"],
            },
            "risk": {
                "stop_price": round(trades["stop_price"], 6),
                "stop_pct": round(trades["stop_pct"], 2),
                "tp1_price": round(trades["tp1_price"], 6),
                "tp1_pct": round(trades["tp1_pct"], 2),
                "tp2_price": round(trades["tp2_price"], 6),
                "tp2_pct": round(trades["tp2_pct"], 2),
                "tp3_price": round(trades["tp3_price"], 6),
                "tp3_pct": round(trades["tp3_pct"], 2),
                "rr1": round(trades["rr1"], 2),
                "rr2": round(trades["rr2"], 2),
                "rr3": round(trades["rr3"], 2),
            },
            "signal": {
                "linked_divergence": div_1h.get("linked", False),
                "regular_divergence": div_1h.get("regular", False),
                "rsi_at_trigger": round(div_1h.get("rsi_at_trigger", 0.0), 2),
                "divergence_strength": div_1h.get("strength", 0.0),
                "pivot_spacing_score": div_1h.get("spacing_score", 0),
                "confirm_30m": bool(confirm_30m),
                "confirm_4h": bool(confirm_4h),
            },
            "market_context": {
                "volume_ratio": round(vol_ratio, 3),
                "recent_pump_pct": round(pump_pct, 2),
                "level_gap_pct": round(level_gap, 2),
                "quote_volume_usdt": round(float(ticker.get("quoteVolume", 0) or 0), 2),
                "structure_score": structure["score"],
                "structure_noise_ratio": structure["noise_ratio"],
                "structure_bars": structure["bars"],
            },
            "reasons": quality["reasons"],
            "warnings": quality["warnings"],
            "filters": {
                "stop_ok": stop_ok,
                "rr_ok": rr_ok,
                "liquidity_ok": liquidity_ok,
                "pump_ok": pump_ok,
                "level_gap_ok": level_gap_ok,
                "structure_ok": structure_ok,
            },
            "fib_levels": {k: round(v, 6) for k, v in levels.items()},
        }

    def scan(self, mode: str = "main", limit: int = 15) -> List[Dict]:
        symbols = self.service.usdt_symbols(limit=80)
        results: List[Dict] = []
        for symbol in symbols:
            try:
                result = self.analyze_symbol(symbol, mode=mode)
                if result.get("passed"):
                    results.append(result)
            except Exception as exc:  # pragma: no cover
                results.append({"symbol": symbol, "passed": False, "reason": str(exc)})
        winners = [r for r in results if r.get("passed")]
        winners.sort(
            key=lambda x: (
                x.get("status") == "ready",
                x.get("score", 0),
                x.get("risk", {}).get("rr1", 0),
                x.get("risk", {}).get("tp1_pct", 0),
            ),
            reverse=True,
        )
        return winners[:limit]
