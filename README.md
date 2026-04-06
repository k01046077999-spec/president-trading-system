# President Trading System v1.9.1 Final Fixed

안정화 수정본.

## 핵심 수정
- `/scan/main`, `/scan/sub`를 캐시 기반으로 변경해서 GPT/브라우저 호출 안정화
- 실시간 강제 스캔은 `/scan/live/main`, `/scan/live/sub`로 분리
- 백그라운드 갱신 실패 시 500 대신 stale 캐시/partial 응답 반환
- NaN / Infinity / null 문제 방지용 sanitize 추가
- 스캔 범위 소폭 축소로 Render 타임아웃 가능성 감소

## 권장 GPT 연결 엔드포인트
- `/health`
- `/gpt/main`
- `/gpt/sub`

## 브라우저 확인용
- `/scan/main`
- `/scan/sub`
- `/scan/live/main`
- `/scan/live/sub`
