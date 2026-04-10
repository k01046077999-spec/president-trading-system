# President Trading System v2.0.3 Upbit KRW Optimized

대통령매매법 업비트 KRW 마켓 v2.0.3 보완본.

## 이번 수정 핵심
- 업비트 KRW 기준 유지
- stage1 / stage2를 제한된 워커로 병렬화해 스캔 지연 축소
- 1차 검토 대상을 상위 유동성 종목으로 먼저 압축
- 메인 판정식을 단순 완화가 아니라 **확인 스택 3개 중 2개 충족** 방식으로 재배열
- 3포인트 다이버전스 연계는 메인에서 경고 요소로 유지하되 절대 탈락 조건으로 두지 않음
- 응답 reason_summary에 `확인스택 n/3` 추가

## 기대 효과
- scan_seconds 하락
- 메인 0개 빈도 일부 완화
- 서브는 감시리스트 성격 유지

## 권장 확인
- `/health`
- `/scan/main`
- `/scan/sub`
- `/scan/symbol/KRW-BTC?mode=main`
