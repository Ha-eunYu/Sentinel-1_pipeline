# -*- coding: utf-8 -*-
"""WAMIS 월자료(mn_mndata)로 8월 평균 저수위의 다년 순위 — 2025 가 '평년'이었나.

    conda run -n s1_snappy python -m s1.tools.wamis.wamis_august_climatology          # 보고서 8곳, 8월
    conda run -n s1_snappy python -m s1.tools.wamis.wamis_august_climatology --all    # 전국 댐, 7·8월 + 권역 요약

월자료는 연도 범위를 넓게 주면 앞쪽이 잘려 온다(2006~ 요청에 2017-01 부터 118행).
그래서 연도 구간을 나눠 받는다. 필드: obsymd(YYYYMM) · avwl(월평균 수위) 등.

``--all`` (2026-10-14): mn_dammain 목록 + DELISTED(성덕·동복) 전부를 7·8월로 순위 낸다 →
``data/wamis_rank_jul_aug.csv``. 권역 요약은 **조정지 댐을 뺀다**(수위를 일정하게 묶어 두는 댐이라
가뭄 신호가 아니다). API 가 2017 이전을 주지 않아 순위는 사실상 10년(2017~2026) 기준이다.

🔴 2026-10-15 사용자 정정 — **순위로 가뭄 권역을 판정하지 않는다.** 댐마다 **자기 10년 기록**과 비교한다
(2026 값의 10년 중앙값 대비, 10년 최저인지, 더 낮았던 해). 그 판단용 두 모드:

    ... wamis_august_climatology --monthly    # 전국 댐 7·8월 월평균 수위 → data/wamis_monthly_jul_aug.csv
    ... wamis_august_climatology --levels     # 그 CSV 로 댐별 10년 기록 대비 + 권역별 「자기 중앙값 아래」 개수
"""
import argparse
import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from s1.wamis.client import rows  # noqa: E402
from s1.wamis.dams import DELISTED, fetch_dams  # noqa: E402

DAMS = {"안동호": "2001110", "임하호": "2002110", "밀양호": "2021110", "영천호": "2012210",
        "성덕저수지": "2002111", "운문호": "2021210", "옥정호": "4001110", "평림호": "5002201"}
# 권역 요약 묶음 — mn_dammain 의 bbsnnm 값. 주암역조정지는 bbsnnm 이 비어 섬진강에 넣는다.
GROUPS = {"한강": ("한강", "한강동해"), "금강": ("금강", "만경 · 동진"),
          "낙동강·동남": ("낙동강", "형산강", "태화강", "회야 · 수영", "낙동강동해", "낙동강남해"),
          "섬진강": ("섬진강", "섬진강남해", ""), "영산강·탐진": ("영산강", "탐진강")}
OUT = ROOT / "data" / "wamis_rank_jul_aug.csv"
MONTHLY_OUT = ROOT / "data" / "wamis_monthly_jul_aug.csv"


def monthly(cd: str, months: tuple[str, ...], spans=((2001, 2008), (2009, 2016), (2017, 2026))) -> dict:
    """{(연, 'MM'): 월평균 수위} — months 에 든 달만."""
    out = {}
    for y0, y1 in spans:
        for r in rows("wkd", "mn_mndata", {"damcd": cd, "startyear": str(y0), "endyear": str(y1)}):
            ym = str(r.get("obsymd", ""))
            if len(ym) == 6 and ym[4:] in months and r.get("avwl") not in (None, "", "-"):
                out[(int(ym[:4]), ym[4:])] = float(r["avwl"])
    return out


def rank_of(vals: dict[int, float], y: int) -> int | None:
    """낮은 쪽부터 몇 번째 (1 = 최저)."""
    srt = sorted(vals.values())
    return srt.index(vals[y]) + 1 if y in vals else None


def report8() -> None:
    for name, cd in DAMS.items():
        aug = {y: v for (y, m), v in monthly(cd, ("08",)).items()}
        if not aug:
            print(name, "자료 없음"); continue
        yrs, vals = sorted(aug), sorted(aug.values())
        print(f"{name:6s} {yrs[0]}~{yrs[-1]} ({len(yrs)}년)  8월 평균수위 중앙값 {vals[len(vals)//2]:.2f}  "
              f"2025={aug.get(2025, float('nan')):.2f} (낮은순 {rank_of(aug, 2025)}위)  "
              f"2026={aug.get(2026, float('nan')):.2f} (낮은순 {rank_of(aug, 2026)}위)")


def report_all() -> None:
    have = set()
    table = []
    for d in [*fetch_dams(), *DELISTED]:
        if d.damcd in have:
            continue
        have.add(d.damcd)
        mon = monthly(d.damcd, ("07", "08"), spans=((2009, 2016), (2017, 2026)))
        row = {"권역": d.bbsnnm or "", "댐": d.damnm, "코드": d.damcd, "관리": d.mggvnm or ""}
        for m in ("07", "08"):
            vals = {y: v for (y, mm), v in mon.items() if mm == m}
            row |= {f"{int(m)}월_년수": len(vals), f"{int(m)}월_2025순위": rank_of(vals, 2025),
                    f"{int(m)}월_2026순위": rank_of(vals, 2026)}
        table.append(row)
        print(row, flush=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader(); w.writerows(table)
    print(f"-> {OUT.relative_to(ROOT)}\n\n권역 요약 (조정지 제외, 낮은 순 1 = 최저)")
    for g, keys in GROUPS.items():
        rs = [r for r in table if r["권역"] in keys and "조정지" not in r["댐"] and "(조)" not in r["댐"]]
        for m in ("7월", "8월"):
            a25 = [r[f"{m}_2025순위"] for r in rs if r[f"{m}_2025순위"]]
            a26 = [r[f"{m}_2026순위"] for r in rs if r[f"{m}_2026순위"]]
            print(f"  {g:8s} {m} n={len(rs):2d}  2025 중앙 {statistics.median(a25):4.1f} (≤3위 {sum(x <= 3 for x in a25):2d})"
                  f"   2026 중앙 {statistics.median(a26):4.1f} (≤3위 {sum(x <= 3 for x in a26):2d})")


def export_monthly() -> None:
    """전국 댐(mn_dammain + DELISTED) 7·8월 월평균 수위를 그대로 남긴다 — 판단은 --levels 가 한다."""
    have, table = set(), []
    for d in [*fetch_dams(), *DELISTED]:
        if d.damcd in have:
            continue
        have.add(d.damcd)
        mon = monthly(d.damcd, ("07", "08"), spans=((2009, 2016), (2017, 2026)))
        for (y, mm), v in sorted(mon.items()):
            table.append({"권역": d.bbsnnm or "", "댐": d.damnm, "코드": d.damcd, "관리": d.mggvnm or "",
                          "연": y, "월": int(mm), "월평균수위_m": v})
        print(d.damnm, len(mon), flush=True)
    with open(MONTHLY_OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader(); w.writerows(table)
    print(f"-> {MONTHLY_OUT.relative_to(ROOT)} ({len(have)}곳)")


def report_levels(year: int = 2026) -> None:
    """댐마다 자기 10년(2017~) 기록과 비교 — 다른 댐과 견주지 않는다. 조정지 제외."""
    with open(MONTHLY_OUT, encoding="utf-8-sig") as fh:
        rs = [r for r in csv.DictReader(fh) if "조정지" not in r["댐"] and int(r["연"]) >= 2017]
    by = {}
    for r in rs:
        by.setdefault((r["권역"], r["댐"], int(r["월"])), {})[int(r["연"])] = float(r["월평균수위_m"])
    summ = {}
    for m in (7, 8):
        print(f"\n== {m}월 {year} — 자기 10년 기록 대비 (중앙값 = 표준 중앙값)")
        for (g, nm, mm), s in by.items():
            if mm != m or year not in s:
                continue
            med = statistics.median(s.values())
            lower = sorted(y for y, v in s.items() if v < s[year])
            a = s[year] - med
            a25 = s[year - 1] - med if year - 1 in s else float("nan")
            where = (f"{len(s)}년 최저" if not lower else "중앙값 위" if a > 0.005 else
                     "·".join(map(str, lower)) + "년 다음으로 낮음" if len(lower) <= 2 else "중앙값 아래")
            print(f"  {g or '-':8s} {nm:8s} n={len(s):2d}  {year} {a:+7.2f} m  {where:22s}  {year - 1} {a25:+7.2f} m")
            key = next((k for k, v in GROUPS.items() if g in v), g)
            t = summ.setdefault((m, key), [0, 0, 0])
            t[0] += 1; t[1] += a < -0.005; t[2] += not lower
    print("\n권역 묶음별 — 자기 중앙값 아래 / 자기 기록 최저 / 전체")
    for (m, key), (n, below, lowest) in sorted(summ.items()):
        print(f"  {m}월 {key:8s} 아래 {below:2d} · 최저 {lowest:2d} / {n:2d}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="전국 댐 7·8월 순위 + 권역 요약 → data/wamis_rank_jul_aug.csv")
    ap.add_argument("--monthly", action="store_true", help="전국 댐 7·8월 월평균 수위 → data/wamis_monthly_jul_aug.csv")
    ap.add_argument("--levels", action="store_true", help="그 CSV 로 댐별 자기 10년 기록 대비 요약")
    a = ap.parse_args()
    (export_monthly if a.monthly else report_levels if a.levels else report_all if a.all else report8)()
