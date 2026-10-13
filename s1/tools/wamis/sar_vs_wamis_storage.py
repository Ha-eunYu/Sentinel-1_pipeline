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
    python -m s1.tools.wamis.sar_vs_wamis_storage --sens-csv <gee>/output/reservoir_km2_d134_sens.csv  # 8월 D134 민감도 4쌍

산출: ``experiments/swot_wamis/sar_vs_wamis_{tag}.csv``.

성덕(2002111)·동복은 2026-10 현재 mn_dammain 목록에서 빠졌지만 코드로는 자료가
나온다. 그래서 이름 해석(dams.resolve)을 거치지 않고 코드를 직접 준다.
"""
from __future__ import annotations

import argparse
import csv
import functools
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

# 8월 DESC134 S1C↔S1C 민감도 4쌍 (2026-10-12 사용자 결정 — REVIEW_20261005 §2-6 재결정 박스).
# 대상은 D134 가 4일 모두 덮는 보고서 저수지뿐(밀양·영천·성덕·운문은 못 덮는다).
# 4일 모두 UTC 21:30 → KST 익일 06:30 → 06시(위 B군 7월과 같은 규칙).
# gee 산출 output/reservoir_km2_d134_sens.csv — 열 이름 `2025-08-11_DESC134`.
SENS_LAKES = ("안동호", "임하호", "옥정호", "평림호")
SENS_PAIRS = (("20250811", "20260813"), ("20250811", "20260825"),
              ("20250823", "20260813"), ("20250823", "20260825"))
SENS_REL, SENS_HOUR, SENS_SHIFT = "DESC134", 6, 1


# 각 쌍 날짜의 상대궤도 — v11 의 by-orbit CSV 는 열이 `2025-07-25_ASC54` 처럼 궤도를 붙인다(gee 10-13).
ORBIT_OF = {"20250725": "ASC54", "20260715": "ASC54", "20250806": "ASC54", "20260802": "ASC54",
            "20250718": "DESC134", "20260720": "DESC134", "20250811": "ASC127", "20260807": "ASC127"}


def sar_from_csv(path: Path) -> dict[str, tuple[float | None, ...]]:
    """gee reservoir_series CSV -> {저수지: (DATES 순 4개 km² 또는 None)}.

    열 이름은 날짜 단위(`YYYY-MM-DD`, v9·v10)와 궤도 단위(`YYYY-MM-DD_ASC54`, v11 --by-orbit) 둘 다 읽는다.
    궤도 단위가 있으면 그쪽을 먼저 본다 — 하루 두 궤도인 날(0811 등)에 엉뚱한 궤도를 집지 않게.
    """
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = {r["저수지"]: r for r in csv.DictReader(fh)}
    out = {}
    for name, (_, grp) in DAMS.items():
        r = rows.get(name, {})
        vals = []
        for d in DATES[grp]:
            iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            v = (r.get(f"{iso}_{ORBIT_OF[d]}") or r.get(iso) or "").strip()
            vals.append(float(v) if v else None)
        out[name] = tuple(vals)
    return out


def sens_from_csv(path: Path) -> dict[str, dict[str, float | None]]:
    """민감도 CSV -> {저수지: {YYYYMMDD: km² 또는 None}} (열 `YYYY-MM-DD_DESC134`)."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = {r["저수지"]: r for r in csv.DictReader(fh)}
    days = sorted({d for p in SENS_PAIRS for d in p})
    out = {}
    for name in SENS_LAKES:
        r = rows.get(name, {})
        out[name] = {}
        for d in days:
            v = (r.get(f"{d[:4]}-{d[4:6]}-{d[6:]}_{SENS_REL}") or "").strip()
            out[name][d] = float(v) if v else None
    return out


@functools.lru_cache(maxsize=None)
def at(damcd: str, day: str, hour: int) -> dict:
    """그 댐의 그날 시자료 중 hour 시 행(없으면 마지막 행). 같은 (댐, 날, 시) 는 한 번만 묻는다."""
    time.sleep(0.3)
    f = series.hourly(damcd, day, day)
    hh = f"{day}{hour:02d}"
    return next((x for x in f.rows if str(x.get("obsdh", "")).startswith(hh)), None) \
        or (f.rows[-1] if f.rows else {})


def kst_day(d: str, shift: int) -> str:
    return (datetime.strptime(d, "%Y%m%d") + timedelta(days=shift)).strftime("%Y%m%d")


def compare(name: str, lab: str, r0: dict, r1: dict, a0: float | None, a1: float | None) -> list:
    """한 쌍의 SAR 면적 변화 ↔ WAMIS 저수량 변화 한 줄."""
    v0, v1 = r0.get("rsqty"), r1.get("rsqty")
    ok = a0 and a1
    dA = a1 / a0 - 1 if ok else None
    dV = v1 / v0 - 1 if v0 and v1 else None
    k = math.log(v1 / v0) / math.log(a1 / a0) if ok and v0 and v1 and a1 != a0 else None
    return [name, lab, r0.get("obsdh"), r1.get("obsdh"), r0.get("rwl"), r1.get("rwl"),
            round(r1["rwl"] - r0["rwl"], 2) if r0.get("rwl") and r1.get("rwl") else None,
            r0.get("rsrt"), r1.get("rsrt"), round(dA * 100, 1) if dA is not None else None,
            round(dV * 100, 1) if dV is not None else None, round(k, 2) if k else None]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sar-csv", type=Path, help="gee reservoir_series --csv 산출 (없으면 v9 보고서 값)")
    ap.add_argument("--sens-csv", type=Path,
                    help="8월 DESC134 민감도 4쌍 CSV(gee reservoir_km2_d134_sens.csv) — 이 모드만 돈다")
    ap.add_argument("--tag", help="산출 파일 꼬리표 (기본: v9 또는 CSV 이름)")
    ap.add_argument("--dry-run", action="store_true", help="WAMIS 를 부르지 않고 SAR 면적·변화율만 찍는다")
    a = ap.parse_args()

    out = [["저수지", "월", "t0", "t1", "rwl0", "rwl1", "dh_m", "rsrt0", "rsrt1",
            "SAR_dA_pct", "WAMIS_dV_pct", "k_eff"]]
    if a.sens_csv:
        sens = sens_from_csv(a.sens_csv)
        tag = a.tag or a.sens_csv.stem
        print(f"민감도 4쌍 ({SENS_REL}) SAR 면적: {a.sens_csv}")
        for name in SENS_LAKES:
            cd = DAMS[name][0]
            for d0, d1 in SENS_PAIRS:
                a0, a1 = sens[name][d0], sens[name][d1]
                lab = f"8월 D134 {d0[4:]}→{d1[4:]}"
                if a.dry_run:
                    pct = f"{(a1 / a0 - 1) * 100:+.1f}%" if a0 and a1 else "- (면적 없음)"
                    print(f"  {name:6s} {lab}  {a0} → {a1}  {pct}")
                    continue
                row = compare(name, lab, at(cd, kst_day(d0, SENS_SHIFT), SENS_HOUR),
                              at(cd, kst_day(d1, SENS_SHIFT), SENS_HOUR), a0, a1)
                out.append(row)
                print(row, flush=True)
        if not a.dry_run:
            write(out, tag)
        return

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

    for name, (cd, grp) in DAMS.items():
        vals = [at(cd, kst_day(d, SHIFT[grp][i]), HOUR[grp][i]) for i, d in enumerate(DATES[grp])]
        a_ = sar[name]
        for i0, i1, lab in [(0, 1, "7월"), (2, 3, "8월")]:
            row = compare(name, lab, vals[i0], vals[i1], a_[i0], a_[i1])
            out.append(row)
            print(row, flush=True)
    write(out, tag)


def write(out: list[list], tag: str) -> None:
    dest = ROOT / "experiments" / "swot_wamis" / f"sar_vs_wamis_{tag}.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8-sig") as fh:
        csv.writer(fh).writerows(out)
    print(f"-> {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
