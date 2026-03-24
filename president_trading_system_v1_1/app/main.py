from __future__ import annotations

from fastapi import FastAPI, Query

from core.engine import PresidentTradingEngine

app = FastAPI(title="대통령매매법 API", version="1.1.0")
engine = PresidentTradingEngine()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "system": "president-trading-system", "version": "1.1.0"}


@app.get("/scan/main")
def scan_main(limit: int = Query(default=10, ge=1, le=50)) -> dict:
    return {"mode": "main", "items": engine.scan(mode="main", limit=limit)}


@app.get("/scan/sub")
def scan_sub(limit: int = Query(default=10, ge=1, le=50)) -> dict:
    return {"mode": "sub", "items": engine.scan(mode="sub", limit=limit)}


@app.get("/scan/symbol/{symbol}")
def scan_symbol(symbol: str, mode: str = Query(default="main", pattern="^(main|sub)$")) -> dict:
    return engine.analyze_symbol(symbol.upper(), mode=mode)
