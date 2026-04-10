import time
from threading import RLock

import ccxt
import pandas as pd

from core import config


class UpbitService:
    def __init__(self) -> None:
        self.exchange = ccxt.upbit({
            "enableRateLimit": True,
            "timeout": 15000,
        })
        self._lock = RLock()
        self._api_lock = RLock()
        self._last_api_ts = 0.0
        self._universe_cache: dict[int, tuple[float, list[str]]] = {}
        self._ohlcv_cache: dict[tuple[str, str, int], tuple[float, pd.DataFrame]] = {}

    def _to_upbit_symbol(self, symbol: str) -> str:
        s = (symbol or "").strip().upper()
        if not s:
            raise ValueError("빈 심볼")
        if "/KRW" in s:
            return s
        if s.startswith("KRW-"):
            base = s.split("-", 1)[1]
            return f"{base}/KRW"
        if s.endswith("KRW") and len(s) > 3:
            base = s[:-3].replace("-", "").replace("/", "")
            return f"{base}/KRW"
        s = s.replace("/", "").replace("-", "")
        return f"{s}/KRW"

    def display_symbol(self, symbol: str) -> str:
        unified = self._to_upbit_symbol(symbol)
        base = unified.split("/")[0]
        return f"KRW-{base}"

    def _sleep_for_rate_limit(self) -> None:
        with self._api_lock:
            now = time.time()
            wait_sec = config.API_MIN_INTERVAL_SEC - (now - self._last_api_ts)
            if wait_sec > 0:
                time.sleep(wait_sec)
            self._last_api_ts = time.time()

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return isinstance(exc, ccxt.RateLimitExceeded) or "429" in msg or "too many requests" in msg or "rate limit" in msg

    def _call_api(self, fn, *args, **kwargs):
        last_exc = None
        for attempt in range(config.API_RETRY_MAX + 1):
            try:
                self._sleep_for_rate_limit()
                return fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if not self._is_rate_limit_error(exc) or attempt >= config.API_RETRY_MAX:
                    raise
                backoff = config.API_BACKOFF_BASE_SEC * (attempt + 1)
                time.sleep(backoff)
        if last_exc:
            raise last_exc

    def _get_cached_universe(self, top_n: int) -> list[str] | None:
        with self._lock:
            cached = self._universe_cache.get(top_n)
            if not cached:
                return None
            ts, data = cached
            if time.time() - ts > config.UNIVERSE_CACHE_TTL_SEC:
                return None
            return list(data)

    def _set_cached_universe(self, top_n: int, symbols: list[str]) -> None:
        with self._lock:
            self._universe_cache[top_n] = (time.time(), list(symbols))

    def get_dynamic_universe(self, top_n: int) -> list[str]:
        cached = self._get_cached_universe(top_n)
        if cached is not None:
            return cached

        markets = self._call_api(self.exchange.load_markets)
        krw_symbols = [symbol for symbol, meta in markets.items() if symbol.endswith("/KRW") and meta.get("active") is not False]
        rows: list[tuple[str, float]] = []

        chunk_size = 60
        for start in range(0, len(krw_symbols), chunk_size):
            chunk = krw_symbols[start:start + chunk_size]
            tickers = self._call_api(self.exchange.fetch_tickers, chunk)

            for symbol, ticker in tickers.items():
                if not symbol.endswith("/KRW"):
                    continue
                if ticker.get("active") is False:
                    continue

                qv = ticker.get("quoteVolume")
                if not qv:
                    base_vol = ticker.get("baseVolume") or 0
                    last_price = ticker.get("last") or 0
                    try:
                        qv = float(base_vol) * float(last_price)
                    except Exception:
                        qv = 0
                if not qv:
                    qv = (((ticker.get("info") or {}).get("acc_trade_price_24h")) or 0)

                try:
                    qv = float(qv)
                except Exception:
                    qv = 0

                if qv < config.MIN_QUOTE_VOLUME_KRW:
                    continue

                rows.append((self._to_upbit_symbol(symbol), qv))

        rows.sort(key=lambda x: x[1], reverse=True)
        result = [s for s, _ in rows[:top_n]]
        self._set_cached_universe(top_n, result)
        return result

    def _get_cached_ohlcv(self, key: tuple[str, str, int]) -> pd.DataFrame | None:
        with self._lock:
            cached = self._ohlcv_cache.get(key)
            if not cached:
                return None
            ts, data = cached
            if time.time() - ts > config.OHLCV_CACHE_TTL_SEC:
                return None
            return data.copy()

    def _set_cached_ohlcv(self, key: tuple[str, str, int], df: pd.DataFrame) -> None:
        with self._lock:
            self._ohlcv_cache[key] = (time.time(), df.copy())

    def fetch_ohlcv_df(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        unified = self._to_upbit_symbol(symbol)
        key = (unified, timeframe, limit)
        cached = self._get_cached_ohlcv(key)
        if cached is not None:
            return cached

        ohlcv = self._call_api(self.exchange.fetch_ohlcv, unified, timeframe=timeframe, limit=limit)
        if not ohlcv:
            raise ValueError(f"OHLCV 없음: {unified} {timeframe}")
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna().reset_index(drop=True)
        if df.empty:
            raise ValueError(f"유효한 OHLCV 없음: {unified} {timeframe}")
        self._set_cached_ohlcv(key, df)
        return df.copy()
