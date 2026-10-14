#!/bin/bash
# EGM 켬 재처리 레인을 **작업 스케줄러에서** 시작한다 (2026-10-15).
#
# 왜: 레인을 Claude 세션의 백그라운드 셸로 띄우면 세션이 끝날 때 같이 죽는다
# (10-15 01:59 — L2 가 장 중간에 죽고 L1 재개 감시도 죽어 5시간 멈춤). 스케줄러가 띄운
# 프로세스는 세션과 무관하게 돈다.
#
# 등록(한 번): 작업 「S1_EGM_L1」·「S1_EGM_L2」, 트리거 없음(필요할 때 시작), 실행 시간 제한 없음.
#   동작 = powershell.exe -NoProfile -WindowStyle Hidden -Command
#          "& 'C:\Program Files\Git\bin\bash.exe' -l /f/06_SAR_system/S1/scripts/egm_lane_sched.sh L1"
# 시작:  powershell -Command "Start-ScheduledTask -TaskName S1_EGM_L1"
# 멈춤:  레인 bash(명령줄에 run_egm_queue.sh L1)를 줄 경계에서 끝낸다 — 창 운영 절차 그대로.
#
# -l 로 띄워야 ~/.bash_profile 의 conda 초기화가 읽힌다(레인이 conda run 을 쓴다).
cd /f/06_SAR_system/S1 || exit 1
lane=$1
x=10G
[ "$lane" = L1 ] && x=13G
echo "$(date '+%m-%d %H:%M:%S') $lane start via Task Scheduler (GPT_XMX=$x)" >> temp/logs/_pause_L2.log
export GPT_XMX=$x
exec bash scripts/run_egm_queue.sh "$lane" >> "temp/logs/_sched_$lane.out" 2>&1
