# -*- coding: utf-8 -*-
"""WAMIS 월자료(mn_mndata)로 8월 평균 저수위의 다년 순위 — 2025 가 '평년'이었나.

    conda run -n s1_snappy python -m s1.tools.wamis.wamis_august_climatology

월자료는 연도 범위를 넓게 주면 앞쪽이 잘려 온다(2006~ 요청에 2017-01 부터 118행).
그래서 연도 구간을 나눠 받는다. 필드: obsymd(YYYYMM) · avwl(월평균 수위) 등.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from s1.wamis.client import rows  # noqa: E402

DAMS = {"안동호": "2001110", "임하호": "2002110", "밀양호": "2021110", "영천호": "2012210",
        "성덕저수지": "2002111", "운문호": "2021210", "옥정호": "4001110", "평림호": "5002201"}

for name, cd in DAMS.items():
    aug = {}
    for y0, y1 in [(2001, 2008), (2009, 2016), (2017, 2026)]:
        for r in rows("wkd", "mn_mndata", {"damcd": cd, "startyear": str(y0), "endyear": str(y1)}):
            ym = str(r.get("obsymd", ""))
            if ym.endswith("08") and r.get("avwl") not in (None, "", "-"):
                aug[int(ym[:4])] = float(r["avwl"])
    yrs = sorted(aug)
    if not yrs:
        print(name, "자료 없음"); continue
    vals = sorted(aug.values())
    def rank(y):  # 낮은 쪽부터 몇 번째 (1 = 최저)
        return vals.index(aug[y]) + 1 if y in aug else None
    print(f"{name:6s} {yrs[0]}~{yrs[-1]} ({len(yrs)}년)  8월 평균수위 중앙값 {vals[len(vals)//2]:.2f}  "
          f"2025={aug.get(2025, float('nan')):.2f} (낮은순 {rank(2025)}위)  "
          f"2026={aug.get(2026, float('nan')):.2f} (낮은순 {rank(2026)}위)")
