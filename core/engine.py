import time
import numpy as np
import pandas as pd
from core import config
from core.scoring import classify_signal
from services.binance import BinanceService


class PresidentTradingEngine:
    def __init__(self) -> None:
        self.binance = BinanceService()

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

                p1 = float(lows.iloc[i1])
                p2 = float(lows.iloc[i2])
                if p1 <= 0:
                    continue
                undercut_pct = ((p1 - p2) / p1) * 100
                r1 = float(rsi.iloc[i1])
                r2 = float(rsi.iloc[i2])
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
                        p0 = float(lows.iloc[i0])
                        r0 = float(rsi.iloc[i0])
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
        current = float(close.iloc[-1])
        pivot_low = float(low.iloc[i2])
        bounce_from_low_pct = ((current - pivot_low) / pivot_low) * 100 if pivot_low else 999.0
        oversold_rsi = min(div["r1"], div["r2"])
        oversold_ok = oversold_rsi <= config.RSI_OVERSOLD_MAX
        deep_oversold = oversold_rsi <= config.RSI_DEEP_OVERSOLD_MAX
        not_chasing = bounce_from_low_pct <= config.MAX_BOUNCE_FROM_LOW_PCT

        recent_vol = volume.tail(5).mean()
        prev_vol = volume.iloc[max(0, len(volume) - 15):len(volume) - 5].mean()
        volume_improve = recent_vol >= prev_vol * 1.05 if prev_vol > 0 else False

        crash_20bar_pct = ((current / float(close.iloc[-21])) - 1) * 100 if len(close) >= 21 and float(close.iloc[-21]) > 0 else 0.0
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
        df_1h = self.binance.fetch_ohlcv_df(symbol, "1h", 240)
        stage1 = self._stage1_check(df_1h)
        if not stage1["passed"]:
            return {
                "passed": False,
                "symbol": symbol.replace("/", ""),
                "state": "watch",
                "message": "1단계 조건 미충족",
                "warnings": [],
                "rejected_by": ["stage1_fail"],
                "errors": [],
            }

        close_1h = df_1h["close"].astype(float)
        high_1h = df_1h["high"].astype(float)
        low_1h = df_1h["low"].astype(float)
        open_1h = df_1h["open"].astype(float)
        volume_1h = df_1h["volume"].astype(float)
        ema20_1h = self._ema(close_1h, 20)
        atr_1h = self._atr(df_1h, config.ATR_PERIOD)
        current = float(close_1h.iloc[-1])

        anchor_high = float(high_1h.tail(config.FIB_ANCHOR_LOOKBACK).max())
        anchor_low = float(low_1h.tail(config.FIB_ANCHOR_LOOKBACK).min())
        fib = self._fib_levels(anchor_high, anchor_low)
        fib_low = fib["fib_0786"] * (1 - config.FIB_TOLERANCE)
        fib_high = fib["fib_0618"] * (1 + config.FIB_TOLERANCE)
        fib_ok = fib_low <= current <= fib_high

        ema_reclaim_ok = current >= float(ema20_1h.iloc[-1])
        breakout_ref = float(high_1h.iloc[-(config.MICRO_BREAKOUT_LOOKBACK + 1):-1].max()) if len(high_1h) > config.MICRO_BREAKOUT_LOOKBACK else float(high_1h.iloc[-2])
        breakout_ok = current > breakout_ref
        recent_vol_avg = float(volume_1h.iloc[-6:-1].mean()) if len(volume_1h) >= 6 else float(volume_1h.iloc[:-1].mean())
        volume_ok = float(volume_1h.iloc[-1]) >= recent_vol_avg * config.VOLUME_SURGE_MULTIPLIER if recent_vol_avg > 0 else False
        green_candle_ok = current > float(open_1h.iloc[-1])
        entry_ok = ema_reclaim_ok and breakout_ok and volume_ok and green_candle_ok

        structural_stop = min(float(stage1["pivot_low_2"]), anchor_low)
        stop_price = structural_stop - float(atr_1h.iloc[-1]) * config.ATR_STOP_BUFFER
        recent_resistance = breakout_ref
        tp1 = max(recent_resistance, current)
        tp2 = current + (current - stop_price) * 2.0

        stop_pct = round(((stop_price - current) / current) * 100, 2)
        tp1_pct = round(((tp1 - current) / current) * 100, 2)
        tp2_pct = round(((tp2 - current) / current) * 100, 2)
        risk = abs(stop_pct) if stop_pct != 0 else 999.0
        rr = round((max(tp1_pct, 0.0) / risk), 2) if risk > 0 else 0.0

        passed, state, warnings, rejected_by = classify_signal(
            mode=mode,
            stage1_score=float(stage1["score"]),
            oversold_ok=bool(stage1["oversold_ok"]),
            fib_ok=fib_ok,
            divergence_ok=bool(stage1["price_div"] and stage1["rsi_div"]),
            divergence_chain_ok=bool(stage1["chain_ok"]),
            volume_ok=volume_ok,
            breakout_ok=breakout_ok,
            ema_reclaim_ok=ema_reclaim_ok,
            rr=rr,
        )

        if mode == "main" and not entry_ok and "volume_confirm_fail" not in rejected_by and "micro_breakout_fail" not in rejected_by and "ema_reclaim_fail" not in rejected_by:
            rejected_by.append("entry_not_confirmed")
            passed = False
            state = "watch"

        reason = [
            f"1시간봉 저가 기준 RSI 다이버전스(+{stage1['rsi_gap']})",
            f"RSI 과매도({stage1['rsi_lowest']})",
        ]
        if stage1["chain_ok"]:
            reason.append("3포인트 다이버전스 연계")
        if fib_ok:
            reason.append("Fib 0.618~0.786 구간")
        if ema_reclaim_ok:
            reason.append("1시간봉 20EMA 회복")
        if breakout_ok:
            reason.append("직전 미세고점 돌파")
        if volume_ok:
            reason.append("거래량 증가 확인")

        message = "진입 가능 구조" if passed and mode == "main" else ("관찰 후보" if passed else "조건 미충족")

        return {
            "passed": passed,
            "symbol": symbol.replace("/", ""),
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
        }

    def analyze_symbol(self, symbol: str, mode: str = "main"):
        try:
            sym = symbol if "/" in symbol else symbol.replace("USDT", "/USDT")
            return self._stage2_analyze(sym, mode)
        except Exception as e:
            return {
                "passed": False,
                "symbol": symbol,
                "state": "watch",
                "message": "개별 심볼 분석 실패",
                "warnings": [],
                "rejected_by": [],
                "errors": [f"{type(e).__name__}: {e}"],
            }

    def scan(self, mode: str = "main", limit: int = 10):
        started = time.time()
        errors = []
        items = []

        universe_top_n = config.UNIVERSE_TOP_N_MAIN if mode == "main" else config.UNIVERSE_TOP_N_SUB
        stage1_max = config.STAGE1_MAX_MAIN if mode == "main" else config.STAGE1_MAX_SUB
        stage2_max = config.STAGE2_MAX_MAIN if mode == "main" else config.STAGE2_MAX_SUB

        universe = self.binance.get_dynamic_universe(top_n=universe_top_n)
        stage1_candidates = []

        for symbol in universe:
            if len(stage1_candidates) >= stage1_max:
                break
            try:
                df_1h = self.binance.fetch_ohlcv_df(symbol, "1h", 200)
                stage1 = self._stage1_check(df_1h)
                if stage1["passed"]:
                    stage1_candidates.append(symbol)
            except Exception as e:
                errors.append(f"{symbol}: {type(e).__name__}: {e}")

        for symbol in stage1_candidates[:stage2_max]:
            result = self._stage2_analyze(symbol, mode)
            if result["passed"]:
                items.append(result)
            elif mode == "sub" and result["state"] == "watch" and not result["errors"]:
                items.append(result)

        items.sort(key=lambda x: (x.get("state") != "ready", -(x.get("rr") or 0)))
        items = items[:limit]

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
            "errors": errors[:20],
        }
