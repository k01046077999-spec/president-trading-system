from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Query

from app.schemas import HealthResponse, RefreshResponse, ScanItem, ScanResponse
from core.config import APP_VERSION, BASE_URL, REFRESH_EVERY_SECONDS, STALE_AFTER_SECONDS, STARTUP_WARMUP
from core.engine import PresidentTradingEngine
from storage.cache import CacheStore


engine = PresidentTradingEngine()
cache = CacheStore()
_refreshing = {"main": False, "sub": False}
_bg_tasks = []


def _age_seconds(refreshed_at: str | None) -> float | None:
    if not refreshed_at:
        return None
    try:
        dt = datetime.fromisoformat(refreshed_at.replace("Z", "+00:00"))
        return round((datetime.now(timezone.utc) - dt).total_seconds(), 2)
    except Exception:
        return None


async def _refresh_mode(mode: str) -> None:
    if _refreshing.get(mode):
        return
    _refreshing[mode] = True
    try:
        result = await asyncio.to_thread(engine.scan, mode, 10 if mode == "main" else 15)
        result["refreshed_at"] = datetime.now(timezone.utc).isoformat()
        cache.set(mode, result)
    finally:
        _refreshing[mode] = False


async def _scheduler(mode: str) -> None:
    if STARTUP_WARMUP:
        await _refresh_mode(mode)
    while True:
        await asyncio.sleep(REFRESH_EVERY_SECONDS)
        await _refresh_mode(mode)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bg_tasks.extend([
        asyncio.create_task(_scheduler("main")),
        asyncio.create_task(_scheduler("sub")),
    ])
    yield
    for task in _bg_tasks:
        task.cancel()


app = FastAPI(
    title="대통령매매법 API",
    version=APP_VERSION,
    servers=[{"url": BASE_URL}],
    lifespan=lifespan,
)


def _snapshot(mode: str) -> dict:
    snap = cache.get(mode)
    if not snap:
        if not _refreshing[mode]:
            asyncio.create_task(_refresh_mode(mode))
        return {
            "status": "refreshing",
            "mode": mode,
            "count": 0,
            "candidate_pool": 0,
            "stage1_checked": 0,
            "stage2_checked": 0,
            "refreshed_at": None,
            "age_seconds": None,
            "cache_status": "empty",
            "items": [],
            "message": "초기 스캔 중입니다. 잠시 후 다시 확인하세요.",
            "errors": [],
        }
    age = _age_seconds(snap.get("refreshed_at"))
    out = {**snap, "age_seconds": age, "cache_status": "fresh" if age is not None and age <= STALE_AFTER_SECONDS else "stale"}
    if out["cache_status"] == "stale" and not _refreshing[mode]:
        asyncio.create_task(_refresh_mode(mode))
        out["message"] = (out.get("message") or "") + " (기존 캐시를 보여주며 백그라운드 갱신 중)"
    return out


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(version=APP_VERSION)


@app.get("/scan/main", response_model=ScanResponse, response_model_exclude_none=True)
def scan_main() -> ScanResponse:
    return ScanResponse(**_snapshot("main"))


@app.get("/scan/sub", response_model=ScanResponse, response_model_exclude_none=True)
def scan_sub() -> ScanResponse:
    return ScanResponse(**_snapshot("sub"))


@app.get("/gpt/main", response_model=ScanResponse, response_model_exclude_none=True)
def gpt_main() -> ScanResponse:
    return ScanResponse(**_snapshot("main"))


@app.get("/gpt/sub", response_model=ScanResponse, response_model_exclude_none=True)
def gpt_sub() -> ScanResponse:
    return ScanResponse(**_snapshot("sub"))


@app.post("/refresh/{mode}", response_model=RefreshResponse)
async def refresh(mode: str) -> RefreshResponse:
    mode = mode.lower()
    if mode not in {"main", "sub"}:
        return RefreshResponse(status="error", mode="main", message="mode must be main or sub")
    asyncio.create_task(_refresh_mode(mode))
    return RefreshResponse(status="ok", mode=mode, message=f"{mode} refresh started")


@app.get("/scan/symbol/{symbol}", response_model=ScanItem, response_model_exclude_none=True)
def scan_symbol(symbol: str, mode: str = Query(default="main", pattern="^(main|sub)$")) -> ScanItem:
    result = engine.analyze_symbol(symbol.upper(), mode=mode)
    return ScanItem(**result)
