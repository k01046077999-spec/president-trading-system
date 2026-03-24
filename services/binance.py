from __future__ import annotations

from typing import List

import ccxt
import pandas as pd


class BinanceService:
    def __init__(self) -> None:
        self.exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})
        self._markets = None

    def _load_markets(self):
        if self._markets is None:
            self._markets = self.exchange.load_markets()
        return self._markets

    def usdt_symbols(self, limit: int = 60) -> List[str]:
        markets = self._load_markets()
        symbols = []
        for symbol, market in markets.items():
            if not market.get("spot"):
                continue
            if market.get("active") is False:
                continue
            if symbol.endswith("/USDT"):
                symbols.append(symbol.replace("/", ""))
        symbols.sort()
        return symbols[:limit]

    def ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 220) -> pd.DataFrame:
        market_symbol = symbol if "/" in symbol else f"{symbol[:-4]}/USDT" if symbol.endswith("USDT") else symbol
        rows = self.exchange.fetch_ohlcv(market_symbol, timeframe=timeframe, limit=limit)
        if not rows:
            raise ValueError(f"OHLCV 없음: {market_symbol} {timeframe}")
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df

    def ticker(self, symbol: str) -> dict:
        market_symbol = symbol if "/" in symbol else f"{symbol[:-4]}/USDT" if symbol.endswith("USDT") else symbol
        return self.exchange.fetch_ticker(market_symbol)
