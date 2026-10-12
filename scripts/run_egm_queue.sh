#!/usr/bin/env bash
# EGM 켬 재처리 (ISSUES #26) — 공유 대기열 소비자 (2026-10-12, run_poeorb_queue.sh 에서 갈라짐)
#
#   WAIT_PIDS="<pid> ..." bash scripts/run_egm_queue.sh <레인이름>
#
# 대기열 파일 temp/egm_queue.txt 의 **맨 윗줄부터** 하나씩 꺼내 처리한다.
# 레인 두 개가 같은 파일을 나눠 먹으므로, 레인이 끝나는 시점과 상관없이
# **파일에 적힌 순서**가 지켜진다. 순서를 바꾸려면 파일을 고치면 된다
# (처리 중인 줄은 이미 빠져 있다 — temp/egm_queue_taken.txt 에 기록).
#
#   줄 형식: <월·날짜 접두사>|<ID,...>|<출력폴더 접미사 2025|2026>   # 주석
#     예) 20260825|CB51,4918|2026
#   '#' 로 시작하는 줄과 빈 줄은 건너뛴다.
#
# 출력: downloads/rtc_grd_frost_vh_egm_{2025,2026} (E: junction).
#   POEORB 판(run_poeorb_queue.sh)과 다른 것은 `--dem-egm` 하나뿐이다 — COP30 은 바다가 0 m 인
#   지오이드 정표고라 EGM 을 켜야 제자리에 놓인다(ISSUES #26). POEORB 판(EGM 끔)은 그대로 둔다.
# ⚠ 이 파일을 **실행 중에 고치지 말 것** — bash 는 스크립트를 진행하며 읽는다.
#   대기열 파일(txt)은 언제 고쳐도 된다.
#
# ⚠ 메모리: gpt.vmoptions 가 -Xmx22G 라 레인 2개면 gpt 둘이 최대 44 GB 를 노린다(RAM 32 GB).
#   2026-10-12 시험에서 gpt 둘(17 GB + 5 GB↑)에 가용 RAM 170 MB · 페이징 3,400/s 까지 갔다(10-07 BSOD 와 같은 조건).
#   그래서 레인마다 JVM 최대 힙을 GPT_XMX(기본 13G)로 묶는다 — _JAVA_OPTIONS 가 vmoptions 보다 나중에 적용된다.
#   로그에 "Picked up _JAVA_OPTIONS: -Xmx13G" 가 찍히는지 확인할 것.
set -u
cd "$(dirname "$0")/.."
export _JAVA_OPTIONS="-Xmx${GPT_XMX:-13G}"
lane=$1
log=temp/logs/rtc_egm_q_${lane}.log
queue=temp/egm_queue.txt
taken=temp/egm_queue_taken.txt
lock=temp/egm_queue.lock

if [ -n "${WAIT_PIDS:-}" ]; then
    echo "=== $(date '+%F %T') 대기: PID $WAIT_PIDS 종료" >> "$log"
    for p in $WAIT_PIDS; do
        while tasklist //FI "PID eq $p" 2>/dev/null | grep -qw "$p"; do sleep 60; done
    done
fi

pop() {   # 대기열 맨 위 유효 줄을 꺼내 stdout 으로. 없으면 빈 문자열
    until mkdir "$lock" 2>/dev/null; do sleep 2; done
    local line=""
    if [ -s "$queue" ]; then
        local n
        n=$(grep -n -v -E '^\s*(#|$)' "$queue" | head -1 | cut -d: -f1)
        if [ -n "$n" ]; then
            line=$(sed -n "${n}p" "$queue" | sed 's/#.*//; s/[[:space:]]*$//')
            sed -i "${n}d" "$queue"
            echo "$(date '+%F %T') $lane $line" >> "$taken"
        fi
    fi
    rmdir "$lock"
    printf '%s' "$line"
}

while :; do
    seg=$(pop)
    [ -z "$seg" ] && break
    IFS='|' read -r month ids year <<< "$seg"
    echo "=== $(date '+%F %T') 시작: --month $month --only $ids -> _$year (EGM 켬)" >> "$log"
    conda run --no-capture-output -n s1_snappy python -u -m s1.tools.preprocess.batch_grd_rtc_frost \
        --month "$month" --only "$ids" --pol VH \
        --out-dir "downloads/rtc_grd_frost_vh_egm_$year" --out-tag _vh \
        --dem downloads/dem_basin/korea_peninsula_cop30.tif --dem-egm --gpt-c 7G >> "$log" 2>&1
    echo "=== $(date '+%F %T') 종료(exit $?)" >> "$log"
    sleep 30   # 다른 레인과 conda run 시작 시각이 겹치지 않게
done
echo "LANE_egm_${lane}_DONE" >> "$log"
