from __future__ import annotations

from typing import Dict, List, Optional

import ccxt
import pandas as pd


MAIN_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT",
    "ADAUSDT", "LINKUSDT", "AVAXUSDT", "TRXUSDT", "DOTUSDT", "BCHUSDT",
]

SUB_SYMBOLS = MAIN_SYMBOLS + [
    "APTUSDT", "NEARUSDT", "TONUSDT", "SUIUSDT", "ETCUSDT", "ATOMUSDT",
    "ARBUSDT", "OPUSDT", "FILUSDT", "INJUSDT", "SEIUSDT", "TIAUSDT",
]


class BinanceService:
    def __init__(self) -> None:
        self.exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}, "timeout": 15000})
        self._ohlcv_cache: Dict[str, pd.DataFrame] = {}

    def candidate_symbols(self, mode: str = "main", limit: Optional[int] = None) -> List[str]:
        symbols = MAIN_SYMBOLS if mode == "main" else SUB_SYMBOLS
        return symbols[:limit] if limit else list(symbols)

    def ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 220) -> pd.DataFrame:
        market_symbol = symbol if "/" in symbol else f"{symbol[:-4]}/USDT" if symbol.endswith("USDT") else symbol
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
