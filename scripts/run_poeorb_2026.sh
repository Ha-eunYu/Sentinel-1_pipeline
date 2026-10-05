#!/usr/bin/env bash
# 2026-07/08 POEORB 재처리 — 한 레인(배치 하나)을 순서대로 돌린다 (2026-10-05)
#
#   bash scripts/run_poeorb_2026.sh <레인이름> <월> <우선ID,...> <나머지ID,...>
#
# 출력은 E: 로 간다 — downloads/rtc_grd_frost_vh_poeorb_2026 은
# E:\06_SAR_system_archive\rtc_grd_frost_vh_poeorb_2026 을 가리키는 junction 이다
# (F: 여유 부족, DOWNLOADS_LAYOUT_KR.md 의 junction 관례).
#
# ⚠ 레인 두 개를 **같은 순간에** 띄우지 말 것 — conda run 이 같은
#   __conda_tmp_*.txt 를 잡으려다 한쪽이 시작도 못 하고 죽는다(2026-10-05 실측).
set -u
cd "$(dirname "$0")/.."
lane=$1; month=$2; first=$3; rest=${4:-}
log=temp/logs/rtc_poeorb_2026_${lane}.log
common=(--pol VH --out-dir downloads/rtc_grd_frost_vh_poeorb_2026 --out-tag _vh
        --dem downloads/dem_basin/korea_peninsula_cop30.tif --gpt-c 7G)

for ids in "$first" "$rest"; do
    [ -z "$ids" ] && continue
    echo "=== $(date '+%F %T') 시작: --month $month --only $ids" >> "$log"
    conda run --no-capture-output -n s1_snappy python -u -m s1.tools.preprocess.batch_grd_rtc_frost \
        --month "$month" --only "$ids" "${common[@]}" >> "$log" 2>&1
    echo "=== $(date '+%F %T') 종료(exit $?)" >> "$log"
done
echo "LANE_${lane}_DONE" >> "$log"
