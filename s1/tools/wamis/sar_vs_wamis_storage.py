# -*- coding: utf-8 -*-
"""보고서 SAR 저수지 면적 변화 ↔ WAMIS 공식 저수위·저수량 — 같은 촬영 시각으로.

2026_drought_map/REPORT_AUG_SAR_KR.md 표 1·표 2 의 8개 저수지·1:1 쌍을 그대로 쓴다.
WAMIS 시자료(mn_hrdata)에서 **SAR 촬영 시각에 가장 가까운 정시**를 고른다 —
상승궤도(A·B 8월)는 KST 18시대, 하강 134(B 7월)는 UTC 21시대 = **KST 익일 06시대**.

    conda run -n s1_snappy python -m s1.tools.wamis.sar_vs_wamis_storage

성덕(2002111)·동복은 2026-10 현재 mn_dammain 목록에서 빠졌지만 코드로는 자료가
나온다. 그래서 이름 해석(dams.resolve)을 거치지 않고 코드를 직접 준다.
"""
from __future__ import annotations

import csv
import math
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from s1.wamis import series  # noqa: E402

DAMS = {"안동호": ("2001110", "A"), "임하호": ("2002110", "A"), "밀양호": ("2021110", "A"),
        "영천호": ("2012210", "A"), "성덕저수지": ("2002111", "A"), "운문호": ("2021210", "A"),
        "옥정호": ("4001110", "B"), "평림호": ("5002201", "B")}
# 보고서 표 2 (km²): 2025-07, 2026-07, 2025-08(표 1 전), 2026-08(표 1 후)
SAR = {"안동호": (33.02, 28.70, 30.86, 27.37), "임하호": (11.43, 11.14, 10.96, 10.54),
       "밀양호": (1.61, 1.26, 1.47, 1.13), "영천호": (4.13, 3.80, 4.01, 3.62),
       "성덕저수지": (0.88, 0.64, 0.74, 0.56), "운문호": (4.69, 4.02, 4.50, 3.86),
       "옥정호": (14.21, 10.82, 14.67, 10.20), "평림호": (0.64, 0.62, 0.62, 0.60)}
DATES = {"A": ("20250725", "20260715", "20250806", "20260802"),
         "B": ("20250718", "20260720", "20250811", "20260807")}
HOUR = {"A": (18, 18, 18, 18), "B": (6, 6, 18, 18)}
SHIFT = {"A": (0, 0, 0, 0), "B": (1, 1, 0, 0)}   # DESC 134 는 KST 로 하루 넘어간다


def at(damcd: str, day: str, hour: int) -> dict:
    f = series.hourly(damcd, day, day)
    hh = f"{day}{hour:02d}"
    return next((x for x in f.rows if str(x.get("obsdh", "")).startswith(hh)), None) \
        or (f.rows[-1] if f.rows else {})


def main() -> None:
    out = [["저수지", "월", "t0", "t1", "rwl0", "rwl1", "dh_m", "rsrt0", "rsrt1",
            "SAR_dA_pct", "WAMIS_dV_pct", "k_eff"]]
    for name, (cd, grp) in DAMS.items():
        vals = []
        for i, d in enumerate(DATES[grp]):
            day = (datetime.strptime(d, "%Y%m%d") + timedelta(days=SHIFT[grp][i])).strftime("%Y%m%d")
            vals.append(at(cd, day, HOUR[grp][i]))
            time.sleep(0.3)
        a = SAR[name]
        for i0, i1, lab in [(0, 1, "7월"), (2, 3, "8월")]:
            r0, r1 = vals[i0], vals[i1]
            v0, v1 = r0.get("rsqty"), r1.get("rsqty")
            dA = a[i1] / a[i0] - 1
            dV = v1 / v0 - 1 if v0 and v1 else None
            k = math.log(v1 / v0) / math.log(a[i1] / a[i0]) if v0 and v1 else None
            row = [name, lab, r0.get("obsdh"), r1.get("obsdh"), r0.get("rwl"), r1.get("rwl"),
                   round(r1["rwl"] - r0["rwl"], 2) if r0.get("rwl") and r1.get("rwl") else None,
                   r0.get("rsrt"), r1.get("rsrt"), round(dA * 100, 1),
                   round(dV * 100, 1) if dV is not None else None, round(k, 2) if k else None]
            out.append(row)
            print(row, flush=True)
    with open(ROOT / "experiments" / "swot_wamis" / "sar_vs_wamis.csv", "w", newline="", encoding="utf-8-sig") as fh:
        csv.writer(fh).writerows(out)


if __name__ == "__main__":
    main()
