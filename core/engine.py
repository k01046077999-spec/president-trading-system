import math
import time
import numpy as np
import pandas as pd
from core import config
from core.scoring import classify_signal
from services.upbit import UpbitService


class PresidentTradingEngine:
    def __init__(self) -> None:
        self.market = UpbitService()

    def _safe_float(self, value, default: float = 0.0) -> float:
        try:
            num = float(value)
            if math.isnan(num) or math.isinf(num):
                return default
            return num
        except Exception:
            return default

    def _sanitize_item(self, item: dict) -> dict:
        for key in ("stop_pct", "tp1_pct", "tp2_pct", "rr"):
            if key in item and item[key] is not None:
                item[key] = self._safe_float(item[key], 0.0)
        for key in ("warnings", "rejected_by", "errors"):
            item[key] = [str(x) for x in item.get(key, []) if x is not None]
        if item.get("reason_summary") is None:
            item["reason_summary"] = ""
        if item.get("message") is None:
            item["message"] = ""
        return item

    def _rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)
        avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def _ema(self, series: pd.Series, span: int) -> pd.Series:
        return series.ewm(span=span, adjust=False).mean()

    def _atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        prev_close = close.shift(1)
        tr = pd.concat([
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean().bfill()

    def _find_pivot_lows(self, series: pd.Series) -> list[int]:
        vals = series.astype(float).values
        lb = config.PIVOT_LOOKBACK
        if len(vals) < (lb * 2 + 8):
            return []
        pivot_idx = []
        for i in range(lb, len(vals) - lb):
            window = vals[i - lb:i + lb + 1]
            if vals[i] == np.min(window):
                if pivot_idx and i - pivot_idx[-1] < config.PIVOT_MIN_GAP:
                    if vals[i] < vals[pivot_idx[-1]]:
                        pivot_idx[-1] = i
                    continue
                pivot_idx.append(i)
        return pivot_idx

    def _find_recent_divergence_setup(self, lows: pd.Series, rsi: pd.Series):
        pivots = self._find_pivot_lows(lows)
        if len(pivots) < 2:
            return None

        for end in range(len(pivots) - 1, 0, -1):
            i2 = pivots[end]
            for start in range(end - 1, -1, -1):
                i1 = pivots[start]
                gap = i2 - i1
                if gap < config.PIVOT_MIN_GAP:
                    continue
                if gap > config.PIVOT_MAX_GAP:
                    break

                p1 = self._safe_float(lows.iloc[i1], 0.0)
                p2 = self._safe_float(lows.iloc[i2], 0.0)
                if p1 <= 0:
                    continue
                undercut_pct = ((p1 - p2) / p1) * 100
                r1 = self._safe_float(rsi.iloc[i1], 50.0)
                r2 = self._safe_float(rsi.iloc[i2], 50.0)
                rsi_gap = r2 - r1
                price_div = p2 < p1 and undercut_pct <= config.MAX_SECOND_LOW_UNDERCUT_PCT
                rsi_div = rsi_gap >= config.MIN_RSI_DIVERGENCE_GAP
                if not (price_div and rsi_div):
                    continue

                chain_ok = False
                chain_anchor = None
                if start >= 1:
                    for prev in range(start - 1, -1, -1):
                        i0 = pivots[prev]
                        if i2 - i0 < config.MIN_THREE_POINT_SPAN:
                            continue
                        p0 = self._safe_float(lows.iloc[i0], 0.0)
                        r0 = self._safe_float(rsi.iloc[i0], 50.0)
                        if p1 <= p0 and r1 >= r0 and r2 >= r1:
                            chain_ok = True
                            chain_anchor = i0
                            break

                return {
                    "pivot_indices": [idx for idx in (chain_anchor, i1, i2) if idx is not None],
                    "i1": i1,
                    "i2": i2,
                    "price_div": price_div,
                    "rsi_div": rsi_div,
                    "rsi_gap": round(rsi_gap, 2),
                    "undercut_pct": round(undercut_pct, 2),
                    "chain_ok": chain_ok,
                    "p1": p1,
                    "p2": p2,
                    "r1": r1,
                    "r2": r2,
                }
        return None

    def _fib_levels(self, high: float, low: float):
        diff = high - low
        return {
            "fib_0618": high - diff * 0.618,
            "fib_0786": high - diff * 0.786,
            "fib_1": low,
            "swing_pct": ((high / low) - 1) * 100 if low > 0 else 0.0,
        }

    def _build_pdf_fib_context(self, df_1h: pd.DataFrame, stage1: dict):
        high_1h = df_1h["high"].astype(float)
        low_1h = df_1h["low"].astype(float)
        close_1h = df_1h["close"].astype(float)

        i2 = int(stage1["pivot_indices"][-1])
        pivot_low = self._safe_float(stage1["pivot_low_2"], 0.0)
        if pivot_low <= 0:
            return None

        post_pivot_high = self._safe_float(high_1h.iloc[i2:].max(), 0.0)
        post_pivot_high_idx = int(high_1h.iloc[i2:].idxmax()) if len(high_1h.iloc[i2:]) else i2
        if post_pivot_high <= pivot_low:
            return None

        fib = self._fib_levels(post_pivot_high, pivot_low)
        current = self._safe_float(close_1h.iloc[-1], 0.0)
        fib_low = fib["fib_0786"] * (1 - config.FIB_TOLERANCE)
        fib_high = fib["fib_0618"] * (1 + config.FIB_TOLERANCE)
        fib_ok = fib_low <= current <= fib_high and fib["swing_pct"] >= config.FIB_MIN_MOVE_PCT

        return {
            "anchor_low": pivot_low,
            "anchor_high": post_pivot_high,
            "anchor_high_idx": post_pivot_high_idx,
            "fib": fib,
            "fib_ok": fib_ok,
            "fib_low": fib_low,
            "fib_high": fib_high,
        }

    def _stage1_check(self, df_1h: pd.DataFrame):
        close = df_1h["close"].astype(float)
        low = df_1h["low"].astype(float)
        volume = df_1h["volume"].astype(float)
        rsi = self._rsi(close)

        div = self._find_recent_divergence_setup(low, rsi)
        if not div:
            return {"passed": False, "score": 0.0, "reason": "no_valid_divergence"}

        i2 = div["i2"]
        current = self._safe_float(close.iloc[-1], 0.0)
        pivot_low = self._safe_float(low.iloc[i2], 0.0)
        bounce_from_low_pct = ((current - pivot_low) / pivot_low) * 100 if pivot_low else 999.0
        oversold_rsi = min(div["r1"], div["r2"])
        oversold_ok = oversold_rsi <= config.RSI_OVERSOLD_MAX
        deep_oversold = oversold_rsi <= config.RSI_DEEP_OVERSOLD_MAX
        not_chasing = bounce_from_low_pct <= config.MAX_BOUNCE_FROM_LOW_PCT

        recent_vol = self._safe_float(volume.tail(5).mean(), 0.0)
        prev_vol = self._safe_float(volume.iloc[max(0, len(volume) - 15):len(volume) - 5].mean(), 0.0)
        volume_improve = recent_vol >= prev_vol * 1.05 if prev_vol > 0 else False

        crash_20bar_pct = ((current / self._safe_float(close.iloc[-21], 1.0)) - 1) * 100 if len(close) >= 21 and self._safe_float(close.iloc[-21], 0.0) > 0 else 0.0
        crash_filter_ok = crash_20bar_pct > config.CRASH_FILTER_20BAR_PCT

        score = 0.0
        if div["price_div"] and div["rsi_div"]:
            score += 1.4
        if div["chain_ok"]:
            score += 0.5
        if deep_oversold:
            score += 0.45
        elif oversold_ok:
            score += 0.3
        if volume_improve:
            score += 0.2
        if not_chasing:
            score += 0.15

        passed = bool(div["price_div"] and div["rsi_div"] and oversold_ok and not_chasing and crash_filter_ok)

        return {
            "passed": passed,
            "score": round(score, 2),
            "price_div": div["price_div"],
            "rsi_div": div["rsi_div"],
            "rsi_gap": div["rsi_gap"],
            "chain_ok": div["chain_ok"],
            "oversold_ok": oversold_ok,
            "deep_oversold": deep_oversold,
            "volume_improve": volume_improve,
            "not_chasing": not_chasing,
            "crash_filter_ok": crash_filter_ok,
            "crash_20bar_pct": round(crash_20bar_pct, 2),
            "bounce_from_low_pct": round(bounce_from_low_pct, 2),
            "pivot_indices": div["pivot_indices"],
            "pivot_low_2": div["p2"],
            "pivot_low_1": div["p1"],
            "rsi_lowest": round(oversold_rsi, 2),
        }

    def _stage2_analyze(self, symbol: str, mode: str):
        df_1h = self.market.fetch_ohlcv_df(symbol, "1h", 240)
        stage1 = self._stage1_check(df_1h)
        if not stage1["passed"]:
            return {
                "passed": False,
                "symbol": self.market.display_symbol(symbol),
                "state": "watch",
                "message": "1단계 조건 미충족",
                "warnings": [],
                "rejected_by": ["stage1_fail"],
                "errors": [],
                "reason_summary": "",
            }

        fib_ctx = self._build_pdf_fib_context(df_1h, stage1)
        if not fib_ctx:
            return {
                "passed": False,
                "symbol": self.market.display_symbol(symbol),
                "state": "watch",
                "message": "피보나치 기준점 불충분",
                "warnings": [],
                "rejected_by": ["fib_anchor_fail"],
                "errors": [],
                "reason_summary": "",
            }

        close_1h = df_1h["close"].astype(float)
        high_1h = df_1h["high"].astype(float)
        low_1h = df_1h["low"].astype(float)
        open_1h = df_1h["open"].astype(float)
        volume_1h = df_1h["volume"].astype(float)
        ema20_1h = self._ema(close_1h, 20)
        atr_1h = self._atr(df_1h, config.ATR_PERIOD)
        current = self._safe_float(close_1h.iloc[-1], 0.0)

        fib = fib_ctx["fib"]
        fib_ok = fib_ctx["fib_ok"]
        ema_reclaim_ok = current >= self._safe_float(ema20_1h.iloc[-1], current)
        if len(high_1h) > config.MICRO_BREAKOUT_LOOKBACK:
            breakout_ref = self._safe_float(high_1h.iloc[-(config.MICRO_BREAKOUT_LOOKBACK + 1):-1].max(), current)
        else:
            breakout_ref = self._safe_float(high_1h.iloc[-2], current) if len(high_1h) >= 2 else current
        breakout_ok = current > breakout_ref
        recent_vol_avg = self._safe_float(volume_1h.iloc[-6:-1].mean(), 0.0) if len(volume_1h) >= 6 else self._safe_float(volume_1h.iloc[:-1].mean(), 0.0)
        volume_ok = self._safe_float(volume_1h.iloc[-1], 0.0) >= recent_vol_avg * config.VOLUME_SURGE_MULTIPLIER if recent_vol_avg > 0 else False
        green_candle_ok = current > self._safe_float(open_1h.iloc[-1], current)

        # PDF 취지대로 1시간봉 구조를 잡고, 작은 분봉으로 진입 디테일 확인
        df_15m = self.market.fetch_ohlcv_df(symbol, "15m", 220)
        close_15m = df_15m["close"].astype(float)
        high_15m = df_15m["high"].astype(float)
        open_15m = df_15m["open"].astype(float)
        volume_15m = df_15m["volume"].astype(float)
        ema20_15m = self._ema(close_15m, 20)
        micro_breakout_15m = self._safe_float(high_15m.iloc[-(config.MICRO_BREAKOUT_LOOKBACK_15M + 1):-1].max(), close_15m.iloc[-1]) if len(high_15m) > config.MICRO_BREAKOUT_LOOKBACK_15M else self._safe_float(high_15m.iloc[-2], close_15m.iloc[-1])
        ema_reclaim_15m_ok = self._safe_float(close_15m.iloc[-1], 0.0) >= self._safe_float(ema20_15m.iloc[-1], 0.0)
        breakout_15m_ok = self._safe_float(close_15m.iloc[-1], 0.0) > micro_breakout_15m
        recent_vol_15m = self._safe_float(volume_15m.iloc[-9:-1].mean(), 0.0) if len(volume_15m) >= 9 else self._safe_float(volume_15m.iloc[:-1].mean(), 0.0)
        volume_15m_ok = self._safe_float(volume_15m.iloc[-1], 0.0) >= recent_vol_15m * 1.15 if recent_vol_15m > 0 else False
        green_15m_ok = self._safe_float(close_15m.iloc[-1], 0.0) > self._safe_float(open_15m.iloc[-1], 0.0)

        entry_ok = all([
            fib_ok,
            ema_reclaim_ok,
            breakout_ok,
            volume_ok,
            green_candle_ok,
            ema_reclaim_15m_ok,
            breakout_15m_ok,
            green_15m_ok,
        ])

        stop_base = fib["fib_1"] * (1 - config.STOP_BUFFER_PCT / 100)
        stop_price = min(
            stop_base,
            self._safe_float(stage1["pivot_low_2"], current) - self._safe_float(atr_1h.iloc[-1], 0.0) * config.ATR_STOP_BUFFER,
        )
        recent_resistance = fib_ctx["anchor_high"]
        tp1 = max(recent_resistance, current)
        tp2 = current + (current - stop_price) * 2.0

        stop_pct = round(((stop_price - current) / current) * 100, 2) if current > 0 else 0.0
        tp1_pct = round(((tp1 - current) / current) * 100, 2) if current > 0 else 0.0
        tp2_pct = round(((tp2 - current) / current) * 100, 2) if current > 0 else 0.0
        risk = abs(stop_pct) if stop_pct != 0 else 999.0
        rr = round((max(tp1_pct, 0.0) / risk), 2) if risk > 0 else 0.0

        passed, state, warnings, rejected_by = classify_signal(
            mode=mode,
            stage1_score=self._safe_float(stage1["score"], 0.0),
            oversold_ok=bool(stage1["oversold_ok"]),
            fib_ok=fib_ok,
            divergence_ok=bool(stage1["price_div"] and stage1["rsi_div"]),
            divergence_chain_ok=bool(stage1["chain_ok"]),
            volume_ok=volume_ok and volume_15m_ok,
            breakout_ok=breakout_ok and breakout_15m_ok,
            ema_reclaim_ok=ema_reclaim_ok and ema_reclaim_15m_ok,
            rr=rr,
        )

        if mode == "main" and not entry_ok and "volume_confirm_fail" not in rejected_by and "micro_breakout_fail" not in rejected_by and "ema_reclaim_fail" not in rejected_by:
            rejected_by.append("entry_not_confirmed")
            passed = False
            state = "watch"

        if not green_15m_ok:
            warnings.append("15m_green_candle_fail")

        reason = [
            f"업비트 KRW 마켓",
            f"1시간봉 RSI 다이버전스(+{stage1['rsi_gap']})",
            f"RSI 과매도({stage1['rsi_lowest']})",
        ]
        if stage1["chain_ok"]:
            reason.append("3포인트 다이버전스 연계")
        if fib_ok:
            reason.append("Fib 0.618~0.786 구간")
        reason.append(f"피보나치1 손절 기준({round(stop_pct, 2)}%)")
        if ema_reclaim_ok:
            reason.append("1시간봉 20EMA 회복")
        if breakout_ok:
            reason.append("1시간봉 미세고점 돌파")
        if volume_ok:
            reason.append("1시간봉 거래량 증가")
        if ema_reclaim_15m_ok and breakout_15m_ok:
            reason.append("15분봉 진입확인")

        message = "진입 가능 구조" if passed and mode == "main" else ("관찰 후보" if passed else "조건 미충족")

        return self._sanitize_item({
            "passed": passed,
            "symbol": self.market.display_symbol(symbol),
            "state": state,
            "direction": "long",
            "stop_pct": stop_pct,
            "tp1_pct": tp1_pct,
            "tp2_pct": tp2_pct,
            "rr": rr,
            "message": message,
            "warnings": warnings,
            "rejected_by": rejected_by,
            "errors": [],
            "reason_summary": ", ".join(reason) if reason else "구조 불충분",
        })

    def analyze_symbol(self, symbol: str, mode: str = "main"):
        try:
            sym = self.market._to_upbit_symbol(symbol)
            return self._stage2_analyze(sym, mode)
        except Exception as e:
            return self._sanitize_item({
                "passed": False,
                "symbol": symbol,
                "state": "watch",
                "message": "개별 심볼 분석 실패",
                "warnings": [],
                "rejected_by": [],
                "errors": [f"{type(e).__name__}: {e}"],
                "reason_summary": "",
            })

    def scan(self, mode: str = "main", limit: int = 10):
        started = time.time()
        errors = []
        items = []

        try:
            universe_top_n = config.UNIVERSE_TOP_N_MAIN if mode == "main" else config.UNIVERSE_TOP_N_SUB
            stage1_max = config.STAGE1_MAX_MAIN if mode == "main" else config.STAGE1_MAX_SUB
            stage2_max = config.STAGE2_MAX_MAIN if mode == "main" else config.STAGE2_MAX_SUB

            universe = self.market.get_dynamic_universe(top_n=universe_top_n)
            stage1_candidates = []

            for symbol in universe:
                if len(stage1_candidates) >= stage1_max:
                    break
                try:
                    df_1h = self.market.fetch_ohlcv_df(symbol, "1h", 200)
                    stage1 = self._stage1_check(df_1h)
                    if stage1["passed"]:
                        stage1_candidates.append(symbol)
                except Exception as e:
                    errors.append(f"{symbol}: {type(e).__name__}: {e}")

            for symbol in stage1_candidates[:stage2_max]:
                try:
                    result = self._stage2_analyze(symbol, mode)
                    if result["passed"]:
                        items.append(result)
                    elif mode == "sub" and result["state"] == "watch" and not result["errors"]:
                        items.append(result)
                except Exception as e:
                    errors.append(f"{symbol}: {type(e).__name__}: {e}")

            items.sort(key=lambda x: (x.get("state") != "ready", -(x.get("rr") or 0)))
            items = [self._sanitize_item(x) for x in items[:limit]]

            status = "partial" if errors else "ok"
            message = f"현재 {mode} 조건을 만족하는 종목이 없습니다." if len(items) == 0 else f"현재 {mode} 조건 후보 {len(items)}개"

            return {
                "status": status,
                "mode": mode,
                "count": len(items),
                "candidate_pool": len(universe),
                "stage1_checked": min(len(universe), stage1_max),
                "stage2_checked": min(len(stage1_candidates), stage2_max),
                "scan_seconds": round(time.time() - started, 2),
                "stopped_reason": None,
                "items": items,
                "message": message,
                "errors": [str(e) for e in errors[:20]],
            }
        except Exception as e:
            return {
                "status": "partial",
                "mode": mode,
                "count": 0,
                "candidate_pool": 0,
                "stage1_checked": 0,
                "stage2_checked": 0,
                "scan_seconds": round(time.time() - started, 2),
                "stopped_reason": "scan_exception",
                "items": [],
                "message": f"{mode} 스캔 실패",
                "errors": [f"{type(e).__name__}: {e}"],
            }
