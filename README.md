# President Trading System v2.0.0 Upbit KRW

대통령매매법 업비트 KRW 마켓 최종 보완본.

## 이번 수정 핵심
- 바이낸스 USDT 기준을 **업비트 KRW 마켓 기준**으로 전면 변경
- 심볼 표기를 `KRW-BTC` 형태로 통일
- 1시간봉 구조 탐지 후 **15분봉 진입확인**을 추가
- 피보나치 기준을 최근 120봉 전체 범위가 아니라 **다이버전스 이후 최근 상승 스윙** 기준으로 재구성
- 손절 기준을 PDF 취지대로 **피보나치 1 이탈 무효** 중심으로 재정렬
- Upbit 특성에 맞게 거래대금 필터/유니버스 크기 재조정
- 기존 캐시 기반 `/scan/main`, `/scan/sub`, `/gpt/main`, `/gpt/sub` 구조 유지

## PDF 반영 로직
- 1시간봉 중심
- RSI 상승 다이버전스 우선
- 3포인트 다이버전스 연계 우대
- Fib 0.618 ~ 0.786 구간 확인
- Fib 1 이탈 시 무효 처리 성격의 손절 계산
- 작은 분봉(15분봉)으로 진입 디테일 확인

## 권장 GPT 연결 엔드포인트
- `/health`
- `/gpt/main`
- `/gpt/sub`

## 브라우저 확인용
- `/scan/main`
- `/scan/sub`
- `/scan/live/main`
- `/scan/live/sub`
- `/scan/symbol/KRW-BTC?mode=main`
- `/scan/symbol/BTC?mode=sub`
