# 대통령매매법 코인 검색기 v1.5

이번 버전은 **전체선별 -> 후보 정밀판정** 구조다.

## 핵심 변경점
- 거래대금 상위 코인 동적 유니버스 확보
- 1차 선별: 1시간봉 기반의 가벼운 필터로 넓게 훑기
- 2차 판정: shortlisted 후보만 30분봉/4시간봉/Fib/손익비 정밀 체크
- 전체 시장을 보되 서버가 죽지 않도록 시간 예산/단계별 제한을 병행
- OpenAPI 스키마 명시형 유지

## 엔드포인트
- `/health`
- `/scan/main`
- `/scan/sub`
- `/scan/symbol/{symbol}?mode=main`

## GPT 연결용
OpenAPI URL:
`https://president-trading-system-1.onrender.com/openapi.json`
