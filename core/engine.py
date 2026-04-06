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

    def _find_two_recent_lows(self, series: pd.Series):
        vals = series.astype(float).values
        lb = config.PIVOT_LOOKBACK
        if len(vals) < (lb * 2 + 8):
            return None
        pivot_idx = []
        for i in range(lb, len(vals) - lb):
            window = vals[i - lb:i + lb + 1]
            if vals[i] == np.min(window):
                if pivot_idx and i - pivot_idx[-1] < config.PIVOT_MIN_GAP:
                    if vals[i] < vals[pivot_idx[-1]]:
                        pivot_idx[-1] = i
                    continue
                pivot_idx.append(i)
        if len(pivot_idx) < 2:
            return None
        for i in range(len(pivot_idx) - 2, -1, -1):
            a, b = pivot_idx[i], pivot_idx[-1]
            gap = b - a
            if config.PIVOT_MIN_GAP <= gap <= config.PIVOT_MAX_GAP:
                return a, b
        return None

    def _stage1_check(self, df_1h: pd.DataFrame):
        close = df_1h["close"].astype(float)
        low = df_1h["low"].astype(float)
        vol = df_1h["volume"].astype(float)
        rsi = self._rsi(close)
        ema20 = self._ema(close, 20)

        lows = self._find_two_recent_lows(low)
        if not lows:
            return {"passed": False, "score": 0.0, "reason": "no_pivots"}

        i1, i2 = lows
        p1 = float(low.iloc[i1])
        p2 = float(low.iloc[i2])
        r1 = float(rsi.iloc[i1])
        r2 = float(rsi.iloc[i2])
        current = float(close.iloc[-1])

        undercut_pct = ((p1 - p2) / p1) * 100 if p1 else 0.0
        bounce_from_low_pct = ((current - p2) / p2) * 100 if p2 else 999.0
        price_div = p2 < p1 and undercut_pct <= config.MAX_SECOND_LOW_UNDERCUT_PCT
        rsi_div_gap = r2 - r1
        rsi_div = rsi_div_gap >= config.MIN_RSI_DIV_GAP
        vol_recent = vol.tail(8).mean()
        vol_prev = vol.iloc[max(0, len(vol) - 24):len(vol) - 8].mean()
        vol_improve = vol_recent >= vol_prev * 1.05 if vol_prev > 0 else False
        rsi_zone = r2 <= 38
        reclaim_ema20 = current >= float(ema20.iloc[-1])
        not_chasing = bounce_from_low_pct <= config.MAX_BOUNCE_FROM_LOW_PCT

        score = 0.0
        if price_div and rsi_div:
            score += 1.75
        if rsi_zone:
            score += 0.45
        if vol_improve:
            score += 0.35
        if reclaim_ema20:
            score += 0.25
        if not_chasing:
            score += 0.2

        return {
            "passed": score >= 1.75 and price_div and rsi_div and not_chasing,
            "score": score,
            "price_div": price_div,
            "rsi_div": rsi_div,
            "rsi_div_gap": round(rsi_div_gap, 2),
            "vol_improve": vol_improve,
            "rsi_zone": rsi_zone,
            "reclaim_ema20": reclaim_ema20,
            "not_chasing": not_chasing,
            "rsi_last": float(rsi.iloc[-1]),
            "pivot_1": i1,
            "pivot_2": i2,
            "pivot_low_1": p1,
            "pivot_low_2": p2,
        }

    def _fib_levels(self, high: float, low: float):
        diff = high - low
        return {
            "fib_0618": high - diff * 0.618,
            "fib_0786": high - diff * 0.786,
            "fib_1": low,
        }

    def _stage2_analyze(self, symbol: str, mode: str):
        df_1h = self.binance.fetch_ohlcv_df(symbol, "1h", 240)
        stage1 = self._stage1_check(df_1h)
        if not stage1["passed"]:
            return {
                "passed": False,
                "symbol": symbol,
                "state": "watch",
                "message": "1단계 조건 미충족",
                "warnings": [],
                "rejected_by": ["stage1_fail"],
                "errors": [],
            }

        df_30m = self.binance.fetch_ohlcv_df(symbol, "30m", 240)
        df_4h = self.binance.fetch_ohlcv_df(symbol, "4h", 180)

        close_1h = df_1h["close"].astype(float)
        high_1h = df_1h["high"].astype(float)
        low_1h = df_1h["low"].astype(float)
        atr_1h = self._atr(df_1h, config.ATR_PERIOD)
        ema20_1h = self._ema(close_1h, 20)
        current = float(close_1h.iloc[-1])
        recent_high = float(high_1h.tail(72).max())
        recent_low = float(low_1h.tail(72).min())
        fib = self._fib_levels(recent_high, recent_low)

        fib_ok = fib["fib_0786"] <= current <= fib["fib_0618"]
        structural_stop = min(stage1["pivot_low_2"], recent_low)
        atr_buffer = float(atr_1h.iloc[-1]) * config.ATR_STOP_BUFFER
        stop_price = structural_stop - atr_buffer
        tp1 = recent_high
        tp2 = recent_high + (recent_high - recent_low) * 0.5

        stop_pct = round(((stop_price - current) / current) * 100, 2)
        tp1_pct = round(((tp1 - current) / current) * 100, 2)
        tp2_pct = round(((tp2 - current) / current) * 100, 2)

        risk = abs(stop_pct) if stop_pct != 0 else 999.0
        rr = round((tp1_pct / risk), 2) if risk > 0 else 0.0

        close_30m = df_30m["close"].astype(float)
        close_4h = df_4h["close"].astype(float)
        rsi_30m = self._rsi(close_30m)
        rsi_4h = self._rsi(close_4h)
        ema50_4h = self._ema(close_4h, 50)
        ema200_4h = self._ema(close_4h, 200)

        trend_ok = bool(
            close_4h.iloc[-1] >= ema200_4h.iloc[-1] * 0.94
            and ema50_4h.iloc[-1] >= ema50_4h.iloc[-4]
            and rsi_4h.iloc[-1] >= 40
        )

        last_open = float(df_1h["open"].astype(float).iloc[-1])
        last_close = float(close_1h.iloc[-1])
        prev_close = float(close_1h.iloc[-2])
        entry_ok = bool(last_close >= ema20_1h.iloc[-1] and last_close > last_open and last_close >= prev_close)

        div_strength = 0.55
        lows_30m = self._find_two_recent_lows(df_30m["low"].astype(float))
        if lows_30m:
            j1, j2 = lows_30m
            if df_30m["low"].iloc[j2] < df_30m["low"].iloc[j1] and rsi_30m.iloc[j2] > rsi_30m.iloc[j1] + 2:
                div_strength += 0.25
        if rsi_4h.iloc[-1] >= rsi_4h.iloc[-3] and rsi_4h.iloc[-1] <= 50:
            div_strength += 0.2
        if trend_ok:
            div_strength += 0.1

        passed, state, warnings, rejected_by = classify_signal(
            mode=mode,
            stage1_score=float(stage1["score"]),
            fib_ok=fib_ok,
            rr=rr,
            divergence_strength=div_strength,
            trend_ok=trend_ok,
            entry_ok=entry_ok,
        )

        reason = []
        if stage1["price_div"] and stage1["rsi_div"]:
            reason.append(f"1시간봉 저가 기준 RSI 다이버전스(+{stage1['rsi_div_gap']})")
        if stage1.get("reclaim_ema20"):
            reason.append("1시간봉 20EMA 회복")
        if fib_ok:
            reason.append("Fib 0.618~0.786 구간")
        if trend_ok:
            reason.append("4시간봉 추세 필터 통과")
        if entry_ok:
            reason.append("직전 캔들 진입 확인")

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
            "errors": errors,
        }
