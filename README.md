# President Trading System v2.0.2 Upbit KRW Optimized

대통령매매법 업비트 KRW 마켓 최적화 보완본.

## 이번 수정 핵심
- 업비트 KRW 기준 유지
- `fetch_tickers` URL 길이 문제를 청크 호출로 해결
- Universe / OHLCV 단기 캐시 추가로 main·sub 중복 호출 부담 축소
- stage1에서 읽은 1시간봉 데이터를 stage2에 재사용해 중복 네트워크 호출 축소
- 15분봉 조회 캔들 수 축소로 속도 개선
- 메인 조건 미세 완화
  - RSI 과매도 상한 30 → 31.5
  - 저점 반등 허용폭 10% → 11.5%
  - RR 하한 1.5 → 1.35
  - Fib 허용 오차 소폭 확대
- 응답 메시지에 ready/watch 개수와 상위 심볼 표시

## 권장 확인
- `/health`
- `/scan/main`
- `/scan/sub`
- `/scan/symbol/KRW-BTC?mode=main`
