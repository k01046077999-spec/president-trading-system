from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from app.schemas import HealthResponse, ScanItem, ScanResponse
from core.engine import PresidentTradingEngine

APP_VERSION = "1.4.1"
BASE_URL = "https://president-trading-system-1.onrender.com"

app = FastAPI(
    title="대통령매매법 API",
    version=APP_VERSION,
    servers=[{"url": BASE_URL}],
)
engine = PresidentTradingEngine()


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="헬스체크",
    response_description="API 상태 확인",
)
def health() -> HealthResponse:
    return HealthResponse(status="ok", system="president-trading-system", version=APP_VERSION)


@app.get(
    "/scan/main",
    response_model=ScanResponse,
    response_model_exclude_none=True,
    summary="메인 스캔",
    response_description="대통령매매법 메인 조건 스캔 결과",
)
def scan_main(limit: int = Query(default=10, ge=1, le=30, description="반환할 최대 종목 수")) -> JSONResponse:
    result = engine.scan(mode="main", limit=limit)
    code = 200 if result["status"] in {"ok", "partial"} else 500
    return JSONResponse(content=result, status_code=code)


@app.get(
    "/scan/sub",
    response_model=ScanResponse,
    response_model_exclude_none=True,
    summary="서브 스캔",
    response_description="대통령매매법 서브 조건 스캔 결과",
)
def scan_sub(limit: int = Query(default=12, ge=1, le=40, description="반환할 최대 종목 수")) -> JSONResponse:
    result = engine.scan(mode="sub", limit=limit)
    code = 200 if result["status"] in {"ok", "partial"} else 500
    return JSONResponse(content=result, status_code=code)


@app.get(
    "/scan/symbol/{symbol}",
    response_model=ScanItem,
    response_model_exclude_none=True,
    summary="개별 심볼 분석",
    response_description="특정 심볼에 대한 대통령매매법 분석 결과",
)
def scan_symbol(symbol: str, mode: str = Query(default="main", pattern="^(main|sub)$", description="스캔 모드")) -> JSONResponse:
    result = engine.analyze_symbol(symbol.upper(), mode=mode)
    code = 200 if result.get("status") in {"ok", "partial"} else 500
    return JSONResponse(content=result, status_code=code)
