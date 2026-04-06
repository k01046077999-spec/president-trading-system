import ccxt
import pandas as pd
from core import config


class BinanceService:
    def __init__(self) -> None:
        self.exchange = ccxt.binance({
            "enableRateLimit": True,
            "timeout": 15000,
            "options": {"defaultType": "spot"},
        })

    def get_dynamic_universe(self, top_n: int) -> list[str]:
        tickers = self.exchange.fetch_tickers()
        rows = []
        for symbol, ticker in tickers.items():
            if not symbol.endswith("/USDT"):
                continue
            if any(symbol.endswith(sfx) for sfx in config.EXCLUDED_SUFFIXES):
                continue
            if any(key in symbol for key in config.EXCLUDED_SYMBOL_KEYWORDS):
                continue
            qv = ticker.get("quoteVolume") or 0
            try:
                qv = float(qv)
            except Exception:
                qv = 0
            if not qv or qv < config.MIN_QUOTE_VOLUME:
                continue
            rows.append((symbol, qv))
        rows.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in rows[:top_n]]

    def fetch_ohlcv_df(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not ohlcv:
            raise ValueError(f"OHLCV 없음: {symbol} {timeframe}")
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna().reset_index(drop=True)
        if df.empty:
            raise ValueError(f"유효한 OHLCV 없음: {symbol} {timeframe}")
        return df
