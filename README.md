# 대통령매매법 v2.0.1

이번 파일은 **비어 있지 않은 실제 배포용 프로젝트 ZIP**입니다.

## 포함 기능
- `/health`
- `/scan/main`
- `/scan/pre_main`
- `/scan/sub`
- `/gpt/main`
- `/gpt/pre_main`
- `/gpt/sub`
- `/refresh/main`
- `/refresh/pre_main`
- `/refresh/sub`

## 핵심 구조
- `main`: 실제 진입 확정용
- `pre_main`: 돌파 직전 감시용
- `sub`: PDF 핵심 조건 후보군

## 적용 방법
1. ZIP 압축 해제
2. GitHub 기존 프로젝트 파일을 이 내용으로 덮어쓰기
3. Render 재배포
4. 아래 순서로 확인
   - `/health`
   - `/scan/pre_main`
   - `/scan/main`
   - `/scan/sub`
