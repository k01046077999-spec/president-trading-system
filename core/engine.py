from __future__ import annotations

import time
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

    def _approx_quote_volume_usdt(self, df: pd.DataFrame, bars: int = 24) -> float:
        if df.empty:
            return 0.0
        seg = df.tail(bars)
        return float((seg["close"] * seg["volume"]).sum())

    def _level_gap_pct(self, df: pd.DataFrame, reference_price: float, side: str) -> float:
        lookback = df.tail(50)
        if lookback.empty or reference_price <= 0:
            return 0.0
        if side == "long":
            resistance = float(lookback["high"].max())
            return (resistance - reference_price) / reference_price * 100
        support = float(lookback["low"].min())
        return (reference_price - support) / reference_price * 100

    def _build_no_signal_response(self, symbol: str, mode: str, message: str, *, warnings: Optional[List[str]] = None) -> Dict:
        return {
            "status": "ok",
            "symbol": symbol,
            "mode": mode,
            "passed": False,
            "state": "no_signal",
            "message": message,
            "warnings": warnings or [],
            "errors": [],
        }

    def _build_symbol_error(self, symbol: str, mode: str, exc: Exception) -> Dict:
        return {
            "status": "partial",
            "symbol": symbol,
            "mode": mode,
            "passed": False,
            "state": "error",
            "message": "심볼 분석 실패",
            "warnings": [],
            "errors": [f"{symbol}: {type(exc).__name__}: {str(exc)}"],
        }

    def _load_1h_context(self, symbol: str, cfg: ScanConfig):
        df_1h = self._prepare(self.service.ohlcv(symbol, "1h", cfg.lookback_bars), cfg.rsi_period)
        div_1h = best_divergence(df_1h, pivot_window=cfg.pivot_window, min_spacing=cfg.min_pivot_spacing)
        if not div_1h:
            return df_1h, None, None, None, None
        side = div_1h["side"]
        swing = build_swing_from_divergence(div_1h, df_1h, structure_lookback_bars=cfg.structure_lookback_bars)
        if not swing:
            return df_1h, div_1h, side, None, None
        current_price = float(df_1h["close"].iloc[-1])
        levels = build_fib_levels(swing["swing_low"], swing["swing_high"], side=side)
        zone = fib_zone_status(current_price, levels, cfg.fib_zone_low, cfg.fib_zone_high, side)
        return df_1h, div_1h, side, swing, {"levels": levels, "zone": zone, "current_price": current_price}

    def analyze_symbol(self, symbol: str, mode: str = "main") -> Dict:
        try:
            cfg = ScanConfig(mode=mode)
            df_1h, div_1h, side, swing, ctx = self._load_1h_context(symbol, cfg)
            if not div_1h:
                return self._build_no_signal_response(symbol, mode, "1시간봉 유효 다이버전스 없음")
            if not swing or not ctx:
                return self._build_no_signal_response(symbol, mode, "스윙 계산 실패")

            current_price = float(ctx["current_price"])
            levels = ctx["levels"]
            zone = ctx["zone"]
            entry_reference = float(zone["preferred_entry"])
            trades = trade_levels(entry_reference, levels, side)

            vol_ratio = volume_ratio(df_1h["volume"])
            pump_pct = recent_pump_pct(df_1h["close"], bars=12)
            level_gap = self._level_gap_pct(df_1h, entry_reference, side)
            structure = swing_cleanliness(df_1h, swing["start_idx"], swing["end_idx"], side)
            approx_quote_volume = self._approx_quote_volume_usdt(df_1h)

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

            confirm_30m = None
            confirm_4h = None
            prefilter_ok = (
                div_1h.get("linked") or div_1h.get("regular")
            ) and structure["score"] >= max(1, cfg.min_structure_score - 1) and approx_quote_volume >= cfg.min_quote_volume_usdt * 0.7

            if prefilter_ok:
                try:
                    df_30m = self._prepare(self.service.ohlcv(symbol, "30m", min(180, cfg.lookback_bars)), cfg.rsi_period)
                    confirm_30m = (
                        detect_bullish_divergence(df_30m, cfg.pivot_window, cfg.min_pivot_spacing)
                        if side == "long"
                        else detect_bearish_divergence(df_30m, cfg.pivot_window, cfg.min_pivot_spacing)
                    )
                except Exception:
                    confirm_30m = None

                if mode == "main" and (zone["in_zone"] or trades["rr1"] >= cfg.min_reward_risk):
                    try:
                        df_4h = self._prepare(self.service.ohlcv(symbol, "4h", 160), cfg.rsi_period)
                        confirm_4h = (
                            detect_bullish_divergence(df_4h, cfg.pivot_window, cfg.min_pivot_spacing)
                            if side == "long"
                            else detect_bearish_divergence(df_4h, cfg.pivot_window, cfg.min_pivot_spacing)
                        )
                    except Exception:
                        confirm_4h = None

            if confirm_30m:
                quality["score"] += 1
                quality["reasons"].append("30분봉 재확인")
            else:
                quality["warnings"].append("30분봉 재확인 없음")
                if mode == "main":
                    quality["downgrade_reasons"].append("30분봉 재확인 없음")

            if confirm_4h and confirm_4h.get("regular"):
                quality["score"] += 0.5
                quality["reasons"].append("4시간봉 보조확인")

            stop_abs = abs(trades["stop_pct"])
            stop_ok = cfg.min_stop_pct <= stop_abs <= cfg.max_stop_pct
            rr_ok = trades["rr1"] >= cfg.min_reward_risk
            liquidity_ok = approx_quote_volume >= cfg.min_quote_volume_usdt
            pump_ok = pump_pct <= cfg.max_recent_pump_pct
            level_gap_ok = level_gap >= (cfg.resistance_buffer_pct if side == "long" else cfg.support_buffer_pct)
            structure_ok = structure["score"] >= cfg.min_structure_score

            hard_fail_reasons = list(quality["hard_fail_reasons"])
            downgrade_reasons = list(dict.fromkeys(quality["downgrade_reasons"]))
            filter_fail_reasons: List[str] = []

            if not stop_ok:
                filter_fail_reasons.append("손절폭 기준 이탈")
            if not rr_ok:
                filter_fail_reasons.append("손익비 기준 미달")
            if not liquidity_ok:
                filter_fail_reasons.append("유동성 기준 미달")
            if not pump_ok:
                filter_fail_reasons.append("최근 급등으로 제외")
            if not level_gap_ok:
                filter_fail_reasons.append("반대 레벨 여유 부족")
            if not structure_ok:
                filter_fail_reasons.append("구조 점수 기준 미달")

            passed = all([
                quality["passed"],
                stop_ok,
                rr_ok,
                liquidity_ok,
                pump_ok,
                level_gap_ok,
                structure_ok,
            ])

            status_label = "ready" if zone["in_zone"] else "watch"
            trade_plan = "즉시 검토" if zone["in_zone"] else "진입구간 대기"
            state = "candidate" if passed else ("watch" if status_label == "watch" else "filtered")
            overall_status = "ok"
            message = "조건 충족" if passed else ("현재 조건 미충족" if filter_fail_reasons or downgrade_reasons else "관찰 후보")

            return {
                "status": overall_status,
                "symbol": symbol,
                "mode": mode,
                "side": side,
                "status_label": status_label,
                "state": state,
                "trade_plan": trade_plan,
                "passed": passed,
                "score": round(float(quality["score"]), 2),
                "message": message,
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
                    "quote_volume_usdt": round(float(approx_quote_volume), 2),
                    "structure_score": structure["score"],
                    "structure_noise_ratio": structure["noise_ratio"],
                    "structure_bars": structure["bars"],
                },
                "reasons": quality["reasons"],
                "warnings": quality["warnings"],
                "rejected_by": filter_fail_reasons + hard_fail_reasons,
                "downgraded_by": downgrade_reasons,
                "errors": [],
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
        except Exception as exc:  # pragma: no cover
            return self._build_symbol_error(symbol, mode, exc)

    def scan(self, mode: str = "main", limit: int = 10) -> Dict:
        cfg = ScanConfig(mode=mode)
        started_at = time.monotonic()
        symbols = self.service.candidate_symbols(mode=mode, limit=cfg.candidate_pool)
        candidates: List[Dict] = []
        errors: List[str] = []
        analyzed = 0
        stopped_reason = "completed"

        for symbol in symbols:
            elapsed = time.monotonic() - started_at
            if analyzed >= cfg.max_processed_symbols:
                stopped_reason = "max_processed_symbols"
                break
            if elapsed >= cfg.max_scan_seconds:
                stopped_reason = "time_budget_exceeded"
                break

            result = self.analyze_symbol(symbol, mode=mode)
            analyzed += 1
            if result.get("errors"):
                errors.extend(result["errors"])
            if result.get("passed"):
                candidates.append(result)

        candidates.sort(
            key=lambda x: (
                x.get("status_label") == "ready",
                x.get("score", 0),
                x.get("risk", {}).get("rr1", 0),
                x.get("risk", {}).get("tp1_pct", 0),
            ),
            reverse=True,
        )
        items = candidates[:limit]

        status = "partial" if errors or stopped_reason != "completed" else "ok"
        if items:
            message = f"{mode} 조건 충족 종목 {len(items)}개"
        else:
            message = f"현재 {mode} 조건을 만족하는 종목이 없습니다."
        if stopped_reason == "time_budget_exceeded":
            message += " 빠른 응답을 위해 시간 예산 내에서 스캔을 중단했습니다."
        elif stopped_reason == "max_processed_symbols":
            message += " 안정성을 위해 최대 스캔 심볼 수에서 중단했습니다."

        return {
            "status": status,
            "mode": mode,
            "count": len(items),
            "candidate_pool": len(symbols),
            "scanned": analyzed,
            "stopped_reason": stopped_reason,
            "scan_seconds": round(time.monotonic() - started_at, 2),
            "items": items,
            "message": message,
            "errors": errors[:20],
        }
