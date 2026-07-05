---
name: fix-issue
description: 터미널이나 웹에서 발생한 에러 로그, 혹은 GitHub 이슈를 분석하여 코드를 자동으로 수정합니다.
---

# 자동 이슈 수정 가이드

## 작업 절차
1. 발생한 오류 메시지의 원본 문자열을 그대로 수집합니다.
2. `grep_search` 등을 통해 에러가 발생한 파일과 줄 번호를 찾습니다.
3. 수정 계획(Implementation Plan)을 작성하여 사용자에게 보여줍니다.
4. 사용자가 승인하면 `replace_file_content`로 코드를 수정하고, 수정한 브랜치(`dev`)에 `git push` 합니다.
