from fastapi import FastAPI, Query

from app.schemas import HealthResponse, ScanItem, ScanResponse
from core.config import APP_VERSION, BASE_URL
from core.engine import PresidentTradingEngine

app = FastAPI(
    title="대통령매매법 API",
    version=APP_VERSION,
    servers=[{"url": BASE_URL}],
)

engine = PresidentTradingEngine()


@app.get("/health", response_model=HealthResponse, summary="헬스체크")
def health() -> HealthResponse:
    return HealthResponse(version=APP_VERSION)


@app.get("/scan/main", response_model=ScanResponse, response_model_exclude_none=True, summary="메인 스캔")
def scan_main(limit: int = Query(default=10, ge=1, le=30, description="반환할 최대 종목 수")):
    return engine.scan(mode="main", limit=limit)


@app.get("/scan/sub", response_model=ScanResponse, response_model_exclude_none=True, summary="서브 스캔")
def scan_sub(limit: int = Query(default=14, ge=1, le=40, description="반환할 최대 종목 수")):
    return engine.scan(mode="sub", limit=limit)


@app.get("/scan/symbol/{symbol}", response_model=ScanItem, response_model_exclude_none=True, summary="개별 심볼 분석")
def scan_symbol(symbol: str, mode: str = Query(default="main", pattern="^(main|sub)$", description="스캔 모드")):
    return engine.analyze_symbol(symbol.upper(), mode=mode)
