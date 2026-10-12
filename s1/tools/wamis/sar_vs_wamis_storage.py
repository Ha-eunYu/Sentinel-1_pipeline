# -*- coding: utf-8 -*-
"""보고서 SAR 저수지 면적 변화 ↔ WAMIS 공식 저수위·저수량 — 같은 촬영 시각으로.

2026_drought_map/REPORT_AUG_SAR_KR.md 표 1·표 2 의 8개 저수지·1:1 쌍을 그대로 쓴다.
WAMIS 시자료(mn_hrdata)에서 **SAR 촬영 시각에 가장 가까운 정시**를 고른다 —
상승궤도(A·B 8월)는 KST 18시대, 하강 134(B 7월)는 UTC 21시대 = **KST 익일 06시대**.

SAR 면적은 어디서 오나 (2026-10-12)
----------------------------------
- 기본: **v9** — 보고서 표 1·2 값(아래 ``SAR_V9``). = gee ``output/reservoir_km2_1to1.csv``
  를 소수 둘째 자리로 반올림한 것(안동 33.016 · 28.699 · 30.855 · 27.372 로 확인).
- ``--sar-csv``: gee ``kwater/reservoir_series.py --csv`` 산출(행 = 저수지, 열 = ``YYYY-MM-DD``).
  **v10 이 나오면 그 파일을 주고 다시 돌린다** — 포스터의 "SAR 면적 변화는 저수량 변화의
  하한" 주장을 POEORB 판으로 다시 확인하는 것이 목적이다(REVIEW_20261005 §2-1).
  열이 날짜 단위라 하루 두 궤도인 날은 gee ``CANON`` 쪽 궤도다 — 여기 쓰는 8개 날짜 중엔
  20250811(ASC127, 8월 B군이 쓰는 쪽)뿐이라 문제없다.

    python -m s1.tools.wamis.sar_vs_wamis_storage                         # v9
    python -m s1.tools.wamis.sar_vs_wamis_storage --sar-csv <gee>/output/reservoir_km2_v10.csv --tag v10
    python -m s1.tools.wamis.sar_vs_wamis_storage --sar-csv ... --dry-run  # WAMIS 없이 면적만

산출: ``experiments/swot_wamis/sar_vs_wamis_{tag}.csv``.

성덕(2002111)·동복은 2026-10 현재 mn_dammain 목록에서 빠졌지만 코드로는 자료가
나온다. 그래서 이름 해석(dams.resolve)을 거치지 않고 코드를 직접 준다.
"""
from __future__ import annotations

import argparse
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
SAR_V9 = {"안동호": (33.02, 28.70, 30.86, 27.37), "임하호": (11.43, 11.14, 10.96, 10.54),
          "밀양호": (1.61, 1.26, 1.47, 1.13), "영천호": (4.13, 3.80, 4.01, 3.62),
          "성덕저수지": (0.88, 0.64, 0.74, 0.56), "운문호": (4.69, 4.02, 4.50, 3.86),
          "옥정호": (14.21, 10.82, 14.67, 10.20), "평림호": (0.64, 0.62, 0.62, 0.60)}
DATES = {"A": ("20250725", "20260715", "20250806", "20260802"),
         "B": ("20250718", "20260720", "20250811", "20260807")}
HOUR = {"A": (18, 18, 18, 18), "B": (6, 6, 18, 18)}
SHIFT = {"A": (0, 0, 0, 0), "B": (1, 1, 0, 0)}   # DESC 134 는 KST 로 하루 넘어간다


def sar_from_csv(path: Path) -> dict[str, tuple[float | None, ...]]:
    """gee reservoir_series CSV -> {저수지: (DATES 순 4개 km² 또는 None)}."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = {r["저수지"]: r for r in csv.DictReader(fh)}
    out = {}
    for name, (_, grp) in DAMS.items():
        r = rows.get(name, {})
        vals = []
        for d in DATES[grp]:
            v = (r.get(f"{d[:4]}-{d[4:6]}-{d[6:]}") or "").strip()
            vals.append(float(v) if v else None)
        out[name] = tuple(vals)
    return out


def at(damcd: str, day: str, hour: int) -> dict:
    f = series.hourly(damcd, day, day)
    hh = f"{day}{hour:02d}"
    return next((x for x in f.rows if str(x.get("obsdh", "")).startswith(hh)), None) \
        or (f.rows[-1] if f.rows else {})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sar-csv", type=Path, help="gee reservoir_series --csv 산출 (없으면 v9 보고서 값)")
    ap.add_argument("--tag", help="산출 파일 꼬리표 (기본: v9 또는 CSV 이름)")
    ap.add_argument("--dry-run", action="store_true", help="WAMIS 를 부르지 않고 SAR 면적·변화율만 찍는다")
    a = ap.parse_args()

    sar = sar_from_csv(a.sar_csv) if a.sar_csv else SAR_V9
    tag = a.tag or (a.sar_csv.stem if a.sar_csv else "v9")
    print(f"SAR 면적: {a.sar_csv or 'v9 (보고서 표 1·2)'}")
    missing = [f"{n} {DATES[DAMS[n][1]][i]}" for n, v in sar.items() for i, x in enumerate(v) if x is None]
    if missing:
        print(f"⚠ 면적 없음(그 쌍은 비운다): {', '.join(missing)}")

    if a.dry_run:
        for name, v in sar.items():
            pct = [f"{(v[i1] / v[i0] - 1) * 100:+.1f}%" if v[i0] and v[i1] else "-" for i0, i1 in ((0, 1), (2, 3))]
            print(f"  {name:6s} {v}  7월 {pct[0]}  8월 {pct[1]}")
        return

    out = [["저수지", "월", "t0", "t1", "rwl0", "rwl1", "dh_m", "rsrt0", "rsrt1",
            "SAR_dA_pct", "WAMIS_dV_pct", "k_eff"]]
    for name, (cd, grp) in DAMS.items():
        vals = []
        for i, d in enumerate(DATES[grp]):
            day = (datetime.strptime(d, "%Y%m%d") + timedelta(days=SHIFT[grp][i])).strftime("%Y%m%d")
            vals.append(at(cd, day, HOUR[grp][i]))
            time.sleep(0.3)
        a_ = sar[name]
        for i0, i1, lab in [(0, 1, "7월"), (2, 3, "8월")]:
            r0, r1 = vals[i0], vals[i1]
            v0, v1 = r0.get("rsqty"), r1.get("rsqty")
            ok = a_[i0] and a_[i1]
            dA = a_[i1] / a_[i0] - 1 if ok else None
            dV = v1 / v0 - 1 if v0 and v1 else None
            k = math.log(v1 / v0) / math.log(a_[i1] / a_[i0]) if ok and v0 and v1 and a_[i1] != a_[i0] else None
            row = [name, lab, r0.get("obsdh"), r1.get("obsdh"), r0.get("rwl"), r1.get("rwl"),
                   round(r1["rwl"] - r0["rwl"], 2) if r0.get("rwl") and r1.get("rwl") else None,
                   r0.get("rsrt"), r1.get("rsrt"), round(dA * 100, 1) if dA is not None else None,
                   round(dV * 100, 1) if dV is not None else None, round(k, 2) if k else None]
            out.append(row)
            print(row, flush=True)
    dest = ROOT / "experiments" / "swot_wamis" / f"sar_vs_wamis_{tag}.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8-sig") as fh:
        csv.writer(fh).writerows(out)
    print(f"-> {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
