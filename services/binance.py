from __future__ import annotations

import ccxt
import math
from typing import Dict, List

from core.config import EXCLUDED_EXACT, EXCLUDED_KEYWORDS

class BinanceService:
    def __init__(self) -> None:
        self.exchange = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })

    def fetch_dynamic_universe(self, pool_size: int, min_quote_volume: float) -> List[str]:
        tickers = self.exchange.fetch_tickers()
        ranked = []
        for symbol, t in tickers.items():
            if not symbol.endswith("/USDT"):
                continue
            if symbol in EXCLUDED_EXACT:
                continue
            base = symbol.split("/")[0]
            if any(k in base for k in EXCLUDED_KEYWORDS):
                continue
            qv = float(t.get("quoteVolume") or 0.0)
            close = float(t.get("last") or t.get("close") or 0.0)
            if qv < min_quote_volume or close <= 0:
                continue
            ranked.append((symbol, qv))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in ranked[:pool_size]]

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 220) -> List[List[float]]:
        data = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not data or len(data) < 80:
            raise ValueError(f"OHLCV 부족: {symbol} {timeframe}")
        return data
