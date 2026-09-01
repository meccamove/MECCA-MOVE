MECCA MOVE AUTO COLLECTOR V1

- collector_lh.py: LH 청약플러스 임대주택 공고 목록을 순회하고 평면도 포함 공고만 누적합니다.
- 기존 verified_floorplans_cumulative.json 위에 중복 제거 후 추가합니다.
- GitHub Actions: 매일 자동 실행 + 수동 실행 가능.
- 평면도가 확인되지 않은 공고는 추가하지 않습니다.
- 주소/면적을 추출하지 못한 경우 '공식 공고 자료' 상태로만 저장하며 가짜 주소/주택형을 만들지 않습니다.

GitHub에 이 ZIP의 파일 구조 그대로 올리면 .github/workflows/collect-lh.yml이 자동수집을 담당합니다.
