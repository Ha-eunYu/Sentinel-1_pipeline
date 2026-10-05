#!/usr/bin/env bash
# POEORB 재처리 레인 — 구간(segment)을 순서대로 돈다 (2026-10-05)
#
#   bash scripts/run_poeorb_lane.sh <레인이름> <구간> [<구간> ...]
#   구간 = "<월접두사>|<ID,...>|<출력폴더 접미사 2025|2026>"
#     예) "202608|3B05,B10F|2026"   "20250823|669C|2025"
#
#   WAIT_FOR=<로그 한 줄> 을 주면 그 줄이 (줄 전체 일치로) 로그에 찍힐 때까지 기다린다
#   — 부분일치로 찾으면 자기 로그의 "대기: ..." 줄에 걸려 바로 출발한다
#   (동시 gpt 2개 규칙 — HANDOFF_20260826 §4.1).
#
# 출력은 E: 다 — downloads/rtc_grd_frost_vh_poeorb_{2025,2026} 은
# E:\06_SAR_system_archive\ 아래를 가리키는 junction 이다(DOWNLOADS_LAYOUT_KR.md).
#
# ⚠ 레인 두 개를 **같은 순간에** 띄우지 말 것 — conda run 이 같은
#   __conda_tmp_*.txt 를 잡으려다 한쪽이 시작도 못 하고 죽는다(2026-10-05 실측).
# ⚠ --only 는 4자리 ID 매칭이라 같은 ID 가 두 장일 수 있다(669C: 2025-08-21 · 08-23).
#   그럴 땐 월접두사 자리에 날짜 8자리를 준다(--month 는 접두사 일치).
set -u
cd "$(dirname "$0")/.."
lane=$1; shift
log=temp/logs/rtc_poeorb_${lane}.log

if [ -n "${WAIT_FOR:-}" ]; then
    echo "=== $(date '+%F %T') 대기: $WAIT_FOR" >> "$log"
    until grep -qxh "$WAIT_FOR" temp/logs/rtc_poeorb_*.log 2>/dev/null; do sleep 60; done
fi

for seg in "$@"; do
    IFS='|' read -r month ids year <<< "$seg"
    [ -z "$ids" ] && continue
    echo "=== $(date '+%F %T') 시작: --month $month --only $ids -> _$year" >> "$log"
    conda run --no-capture-output -n s1_snappy python -u -m s1.tools.preprocess.batch_grd_rtc_frost \
        --month "$month" --only "$ids" --pol VH \
        --out-dir "downloads/rtc_grd_frost_vh_poeorb_$year" --out-tag _vh \
        --dem downloads/dem_basin/korea_peninsula_cop30.tif --gpt-c 7G >> "$log" 2>&1
    echo "=== $(date '+%F %T') 종료(exit $?)" >> "$log"
    sleep 30   # 다른 레인과 conda run 시작 시각이 겹치지 않게
done
echo "LANE_${lane}_DONE" >> "$log"
