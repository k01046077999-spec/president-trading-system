# 대통령매매법 코인 검색기 v1.1

이 프로젝트는 PDF 매매법의 핵심 뼈대를 FastAPI 기반 검색기로 옮긴 버전이다.

## 이번 보강판에서 추가된 것
- 구조 기반 손절/익절을 계산하고 **표현은 퍼센트**로 통일
- 1시간봉 기준 다이버전스 강도 점수 추가
- 피벗 간격 점수 추가
- 스윙 구조 선명도/노이즈 점수 추가
- 현재가가 진입구간 밖이면 `watch`, 진입구간 안이면 `ready`로 분리
- 손절폭이 너무 크거나 너무 작으면 제외
- 롱은 저항 여유, 숏은 지지 여유를 각각 필터링
- 1차/2차/3차 목표 퍼센트와 RR 출력
- `warnings` 필드로 약점도 같이 노출

## API
- `GET /health`
- `GET /scan/main`
- `GET /scan/sub`
- `GET /scan/symbol/{symbol}?mode=main`

## 결과 구조 핵심
- `status`: `ready` 또는 `watch`
- `entry_reference_price`: 현재 진입 기준 가격
- `risk.stop_pct`: 구조 기반 손절 퍼센트
- `risk.tp1_pct`, `risk.tp2_pct`, `risk.tp3_pct`: 구조 기반 익절 퍼센트
- `signal`: 다이버전스/재확인 정보
- `market_context`: 거래량, 최근 급등, 레벨 여유, 구조 점수
- `warnings`: 신호의 약한 부분

## 로컬 실행
```bash
python -m venv .venv
source .venv/bin/activate  # windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## GitHub 업로드
```bash
git init
git add .
git commit -m "president trading system v1.1"
git branch -M main
git remote add origin https://github.com/<YOUR_ID>/president-trading-system.git
git push -u origin main
```

## Render 배포
- GitHub 저장소 연결
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## 커스텀 GPT 연결
1. Render 배포 완료
2. FastAPI의 OpenAPI 스키마 URL 확인: `/openapi.json`
3. 커스텀 GPT Action에 해당 스키마 연결
4. `GET /scan/main`, `GET /scan/sub`, `GET /scan/symbol/{symbol}` 호출

## 주의
이 버전도 아직 완성형은 아니다.
다만 이전 버전보다 아래는 분명히 강화됐다.
- 구조 기반 퍼센트형 리스크 출력
- 오탐 제거 점수체계 보강
- 진입 준비 상태와 대기 상태 분리
- 약점까지 같이 보여주는 결과 포맷
