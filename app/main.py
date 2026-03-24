from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from core.engine import PresidentTradingEngine

APP_VERSION = "1.2.0"
BASE_URL = "https://president-trading-system-1.onrender.com"

app = FastAPI(
    title="대통령매매법 API",
    version=APP_VERSION,
    servers=[{"url": BASE_URL}],
)
engine = PresidentTradingEngine()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "system": "president-trading-system", "version": APP_VERSION}


@app.get("/scan/main")
def scan_main(limit: int = Query(default=10, ge=1, le=50)) -> JSONResponse:
    result = engine.scan(mode="main", limit=limit)
    code = 200 if result["status"] in {"ok", "partial"} else 500
    return JSONResponse(content=result, status_code=code)


@app.get("/scan/sub")
def scan_sub(limit: int = Query(default=10, ge=1, le=50)) -> JSONResponse:
    result = engine.scan(mode="sub", limit=limit)
    code = 200 if result["status"] in {"ok", "partial"} else 500
    return JSONResponse(content=result, status_code=code)


@app.get("/scan/symbol/{symbol}")
def scan_symbol(symbol: str, mode: str = Query(default="main", pattern="^(main|sub)$")) -> JSONResponse:
    result = engine.analyze_symbol(symbol.upper(), mode=mode)
    code = 200 if result.get("status") in {"ok", "partial"} else 500
    return JSONResponse(content=result, status_code=code)
