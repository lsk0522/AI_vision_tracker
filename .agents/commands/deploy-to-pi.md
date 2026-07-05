---
name: deploy-to-pi
description: 로컬 환경(PC)에서 작업한 내용을 원격 라즈베리파이에 자동 배포하는 절차를 수행합니다.
---

# Deploy to Raspberry Pi

이 명령어(Skill)는 로컬 `main` 브랜치의 최신 코드를 라즈베리파이 쪽으로 넘기고 서버를 재시작하는 절차를 설명합니다.

## 실행 절차
1. 로컬에서 작업한 코드가 `main`에 모두 병합되었는지 확인합니다.
2. (선택) `git push origin main`으로 GitHub에 최신 코드를 업로드합니다.
3. 라즈베리파이 터미널에서 다음을 실행하여 코드를 동기화합니다:
   ```bash
   git pull origin main
   ```
4. 백그라운드 프로세스가 실행 중이라면 재시작합니다.
   ```bash
   ./start.sh
   ```
