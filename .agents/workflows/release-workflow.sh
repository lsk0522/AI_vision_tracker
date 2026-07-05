#!/bin/bash
# 전체 릴리즈 프로세스를 자동화하는 워크플로우 스크립트

echo "=== AI Vision Tracker Release Workflow ==="

# 1. 버전 범프 확인
read -p "Enter new version (e.g., v1.5.0): " version

# 2. 브랜치 병합
git checkout main
git pull origin main
git merge dev -m "Merge dev into main for release $version"

# 3. 태그 생성 및 푸시
git tag -a $version -m "Release $version"
git push origin main --tags

echo "Release $version deployed successfully!"
git checkout dev
