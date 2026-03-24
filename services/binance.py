from __future__ import annotations

from typing import Dict, List
import ccxt


class BinanceService:
    def __init__(self) -> None:
        self.exchange = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
            "timeout": 20000,
        })

    def fetch_tickers(self) -> Dict:
        return self.exchange.fetch_tickers()

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[List[float]]:
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
