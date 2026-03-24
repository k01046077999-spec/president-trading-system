# 대통령매매법 코인 검색기 v1.6

## 핵심 구조
- 요청 시 풀스캔하지 않음
- 백그라운드에서 main/sub 결과를 주기적으로 갱신
- API는 최신 캐시 스냅샷만 즉시 반환
- GPT는 `/gpt/main`, `/gpt/sub` 사용 권장

## 장점
- 요청 시 timeout/502 가능성 감소
- 전체 선별 -> 후보 정밀판정 구조 유지
- 무거운 분석과 빠른 응답 분리

## 엔드포인트
- `GET /health`
- `GET /scan/main`
- `GET /scan/sub`
- `GET /gpt/main`
- `GET /gpt/sub`
- `GET /scan/symbol/{symbol}?mode=main`
- `POST /refresh/main`
- `POST /refresh/sub`

## 응답 해석
- `status=ok` 정상
- `status=partial` 일부 심볼 오류가 있었지만 결과 사용 가능
- `status=refreshing` 초기 스캔 또는 캐시 갱신 대기
- `cache_status=fresh|stale|empty`
