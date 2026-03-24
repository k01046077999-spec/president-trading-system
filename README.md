# 대통령매매법 코인 검색기 v1.3 경량화판

이번 버전은 **Render free/Starter에서 빠르게 응답하도록 경량화**한 운영판이다.

## 핵심 변경
- 메인/서브 모두 **전체 코인 완전탐색 제거**
- 메인: 상위 유동성 12개만 스캔
- 서브: 상위 유동성 24개만 스캔
- 전 종목 3타임프레임 동시 조회 제거
- **1시간봉 선필터 통과 종목만** 30분/4시간 추가 확인
- `ticker()` 제거, 최근 24개 1시간봉 기준 **근사 quote volume** 사용
- 심볼별 실패는 skip하고 `errors`에만 기록
- 0건일 때도 항상 정상 JSON 반환

## API
- `GET /health`
- `GET /scan/main`
- `GET /scan/sub`
- `GET /scan/symbol/{symbol}?mode=main`

## 실행
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Render
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## 기대 효과
- `/scan/main`, `/scan/sub` 502/500 빈도 감소
- GPT Action 호출 안정성 향상
- 메인은 빠른 응답 우선, 서브는 약간 넓은 탐색
