import ccxt
import pandas as pd
from core import config


class UpbitService:
    def __init__(self) -> None:
        self.exchange = ccxt.upbit({
            "enableRateLimit": True,
            "timeout": 15000,
        })

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

    def get_dynamic_universe(self, top_n: int) -> list[str]:
        tickers = self.exchange.fetch_tickers()
        rows: list[tuple[str, float]] = []

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
        return [s for s, _ in rows[:top_n]]

    def fetch_ohlcv_df(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        unified = self._to_upbit_symbol(symbol)
        ohlcv = self.exchange.fetch_ohlcv(unified, timeframe=timeframe, limit=limit)
        if not ohlcv:
            raise ValueError(f"OHLCV 없음: {unified} {timeframe}")
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna().reset_index(drop=True)
        if df.empty:
            raise ValueError(f"유효한 OHLCV 없음: {unified} {timeframe}")
        return df
