from __future__ import annotations

from typing import Dict, List, Optional

import ccxt
import pandas as pd


EXCLUDED_QUOTE_SUFFIXES = ("BUSD", "FDUSD", "USDC", "TUSD", "USDP")
EXCLUDED_BASE_TOKENS = {"USDT", "BUSD", "USDC", "FDUSD", "TUSD", "USDP", "DAI"}
EXCLUDED_NAME_PARTS = ("UP/USDT", "DOWN/USDT", "BULL/USDT", "BEAR/USDT")


class BinanceService:
    def __init__(self) -> None:
        self.exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}, "timeout": 15000})
        self._ohlcv_cache: Dict[str, pd.DataFrame] = {}
        self._tickers_cache: Optional[Dict] = None

    def _normalize_symbol(self, symbol: str) -> str:
        if "/" in symbol:
            return symbol
        return f"{symbol[:-4]}/USDT" if symbol.endswith("USDT") else symbol

    def _denormalize_symbol(self, market_symbol: str) -> str:
        return market_symbol.replace("/", "")

    def _is_supported_symbol(self, market_symbol: str) -> bool:
        if not market_symbol.endswith("/USDT"):
            return False
        if market_symbol.endswith(EXCLUDED_QUOTE_SUFFIXES):
            return False
        if any(part in market_symbol for part in EXCLUDED_NAME_PARTS):
            return False
        base = market_symbol.split("/")[0]
        if base in EXCLUDED_BASE_TOKENS:
            return False
        return True

    def fetch_tickers(self) -> Dict:
        if self._tickers_cache is None:
            self._tickers_cache = self.exchange.fetch_tickers()
        return self._tickers_cache

    def candidate_symbols(self, mode: str = "main", limit: Optional[int] = None) -> List[str]:
        tickers = self.fetch_tickers()
        ranked = []
        for market_symbol, data in tickers.items():
            try:
                if not self._is_supported_symbol(market_symbol):
                    continue
                market = self.exchange.markets.get(market_symbol, {})
                if market and (not market.get("active", True) or market.get("spot") is False):
                    continue
                quote_volume = float((data or {}).get("quoteVolume") or 0.0)
                if quote_volume <= 0:
                    continue
                last_price = float((data or {}).get("last") or 0.0)
                pct_change = abs(float((data or {}).get("percentage") or 0.0))
                ranked.append({
                    "symbol": self._denormalize_symbol(market_symbol),
                    "quote_volume": quote_volume,
                    "last_price": last_price,
                    "abs_change_pct": pct_change,
                })
            except Exception:
                continue

        ranked.sort(key=lambda x: (x["quote_volume"], -x["abs_change_pct"]), reverse=True)
        symbols = [item["symbol"] for item in ranked]
        return symbols[:limit] if limit else symbols

    def ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 220) -> pd.DataFrame:
        market_symbol = self._normalize_symbol(symbol)
        cache_key = f"{market_symbol}:{timeframe}:{limit}"
        if cache_key in self._ohlcv_cache:
            return self._ohlcv_cache[cache_key].copy()
        rows = self.exchange.fetch_ohlcv(market_symbol, timeframe=timeframe, limit=limit)
        if not rows:
            raise ValueError(f"OHLCV 없음: {market_symbol} {timeframe}")
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        self._ohlcv_cache[cache_key] = df
        return df.copy()
