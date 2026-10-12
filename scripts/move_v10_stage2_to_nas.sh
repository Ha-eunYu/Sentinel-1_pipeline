#!/usr/bin/env bash
# 2단계(나머지 35장)의 v10 판(POEORB · EGM 끔)을 NAS 로 옮긴다 (2026-10-12, 사용자 결정 "NAS로 옮기기").
#
#   bash scripts/move_v10_stage2_to_nas.sh            # 복사 → 크기 대조 → 일치한 것만 로컬 삭제
#   DRY=1 bash scripts/move_v10_stage2_to_nas.sh      # 복사·대조만, 삭제 안 함
#
# 목록: temp/egm_stage2_v10_files.txt (F:\...\downloads\rtc_grd_frost_vh_poeorb_{2025,2026}\*.tif — E: junction)
# 대상: X:\02_Analysis\Sentinel-1_Drought\v10_poeorb_egmoff_20261012\{2025,2026}\
# 이유: E: 여유가 EGM 판 83장(약 206 GB)을 다 담지 못한다. 이 35장은 위치가 30~50 m 밀린 판(ISSUES #26)이고
#       포스터 비교에도 "밀린 판 ↔ 제자리 판" 대조에도 안 쓴다(대조는 포스터용 48장으로 한다). 원본 zip 이 있어 재생성 가능.
set -u
cd "$(dirname "$0")/.."
log=temp/logs/_move_v10_stage2_nas.log
dst_root='X:\02_Analysis\Sentinel-1_Drought\v10_poeorb_egmoff_20261012'
echo "=== $(date '+%F %T') 시작 (DRY=${DRY:-0})" >> "$log"
ok=0; bad=0
while IFS= read -r src; do
    src=${src%$'\r'}
    [ -z "$src" ] && continue
    name=$(basename "${src//\\//}")
    year=$(echo "$name" | grep -o '_20[0-9]\{2\}' | head -1 | tr -d _)
    sdir=$(dirname "${src//\\//}")
    ddir="$dst_root\\$year"
    robocopy "$(cygpath -w "$sdir")" "$ddir" "$name" //NP //NJH //NJS //R:2 //W:10 >> "$log" 2>&1
    s=$(stat -c %s "$sdir/$name" 2>/dev/null || echo -1)
    d=$(stat -c %s "$(cygpath -u "$ddir")/$name" 2>/dev/null || echo -2)
    if [ "$s" = "$d" ]; then
        ok=$((ok+1))
        if [ "${DRY:-0}" != "1" ]; then rm -f "$sdir/$name"; echo "삭제(대조 일치 $s B) $name" >> "$log"; fi
    else
        bad=$((bad+1)); echo "⚠ 불일치 — 로컬 유지: $name 로컬 $s / NAS $d" >> "$log"
    fi
done < "${LIST:-temp/egm_stage2_v10_files.txt}"
echo "=== $(date '+%F %T') 끝: 일치 $ok · 불일치 $bad" >> "$log"
echo "MOVE_DONE ok=$ok bad=$bad" >> "$log"
