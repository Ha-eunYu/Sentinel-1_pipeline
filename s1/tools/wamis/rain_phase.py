# -*- coding: utf-8 -*-
"""관측(날짜 × 궤도)마다 **촬영 직전 5일 강우** — 모든 일자 비교의 해석용 주석 (2026-10-12).

왜
--
2026-10-06 결정(REVIEW_20261005 §2-6)으로 1:1 쌍 대신 **상대궤도의 모든 일자**를 양쪽 해에서
비교한다. 2025 의 젖은 영상은 걸러내지 않고 비교 대상으로 쓰되, **어느 관측이 비 직후였는지**
그림·표에 표시하기로 했다. 이 도구가 그 주석을 만든다.

무엇을 재나
-----------
- 관측 = ``downloads/water_otsu_vh/vrt/mosaic_{날짜}_o{절대궤도}.vrt`` 중 **원본이 살아 있는 것**.
  날짜가 같아도 궤도가 다르면 다른 관측이다(20250805·20250811·20260714 는 하루에 두 궤도).
- 강우 = WAMIS 댐유역 일강우 ``rf``(담수호 21곳). **UTC 촬영일 포함 직전 5일 합**(§2-6 과 같은 정의).
  하강(KST 익일 06시대)은 창이 촬영 6시간 전에 끝나고, 상승(KST 18시대)은 촬영 뒤 6시간이 섞인다.
- **그 관측이 실제로 덮은 저수지만** 센다 — 저수지 좌표 주변 3×3 화소에 값이 있으면 덮었다.
- 권역 = 댐코드 첫 자리(1 한강 · 2 낙동강 · 3 금강 · 4 섬진강 · 5 영산강). 권역 값은 덮은 댐의 중앙값.
- 태그: 권역 중앙값 **50 mm 이상이면 ``wet``**(§2-6 의 기준 — 임의값이다).

입력 강우 CSV 는 ``collect_dam_level --preset reservoirs --mode daily`` 산출이다
(2026-10-12: ``dam_daily_20250626_20250901.csv`` · ``dam_daily_20260626_20260901.csv``).

    python -m s1.tools.wamis.rain_phase            # data/rain_phase_5d{,_dam}.csv + 표 출력
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from s1.core.paths import DATA_DIR, WAMIS_DIR                      # noqa: E402
from s1.tools.audit.poeorb_inventory import orbit_offsets         # noqa: E402
from s1.wamis import dams as damlib                                # noqa: E402

VRT_DIR = ROOT / "downloads" / "water_otsu_vh" / "vrt"
RAIN_CSVS = ("dam_daily_20250626_20250901.csv", "dam_daily_20260626_20260901.csv")
OUT_BASIN = DATA_DIR / "rain_phase_5d.csv"
OUT_DAM = DATA_DIR / "rain_phase_5d_dam.csv"
DAYS = 5
WET_MM = 50.0
BASINS = {"1": "한강", "3": "금강", "2": "낙동강", "4": "섬진강", "5": "영산강"}   # 표 열 순서
VRT_NAME = re.compile(r"mosaic_(\d{8})_o(\d{6})\.vrt$")
SRC = re.compile(r'<SourceFilename relativeToVRT="(\d)">([^<]+)</SourceFilename>')
SCENE = re.compile(r"(S1[A-D])_IW_GRDH_\w{4}_(\d{8}T\d{6})_")


def observations() -> list[dict]:
    """살아 있는 VRT 마다 (날짜, 절대궤도, 상대궤도, 방향, 위성, 촬영시각, 경로)."""
    off = orbit_offsets()
    out = []
    for p in sorted(VRT_DIR.glob("mosaic_*.vrt")):
        d, ab = VRT_NAME.search(p.name).groups()
        srcs = [(p.parent / s) if r == "1" else Path(s)
                for r, s in SRC.findall(p.read_text(encoding="utf-8", errors="ignore"))]
        if not srcs or not all(s.exists() for s in srcs):
            print(f"  건너뜀(원본 없음) {p.name}", file=sys.stderr)
            continue
        scenes = [SCENE.search(s.name).groups() for s in srcs]
        sats = sorted({s for s, _ in scenes})
        t0 = min(datetime.strptime(t, "%Y%m%dT%H%M%S") for _, t in scenes)
        rel = (int(ab) - off[(sats[0][-1], d[:4])]) % 175
        out.append({"date": d, "orbit": ab, "rel": rel,
                    "dir": "A" if t0.hour < 15 else "D",       # 상승 UTC 09시대, 하강 21시대
                    "sat": "·".join(sats), "utc": t0.strftime("%H:%M"), "vrt": p})
    return out


def load_rain() -> tuple[dict[str, dict[str, float | None]], dict[str, str]]:
    """damcd -> {YYYYMMDD: rf 또는 None(빈 값)}, damcd -> damnm."""
    rf: dict[str, dict[str, float | None]] = defaultdict(dict)
    names: dict[str, str] = {}
    for fn in RAIN_CSVS:
        with open(Path(WAMIS_DIR) / fn, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                names[r["damcd"]] = r["damnm"]
                v = (r.get("rf") or "").strip()
                rf[r["damcd"]][r["obsymd"]] = float(v) if v else None
    return rf, names


def lake_dams(names: dict[str, str]) -> list[tuple[str, str, float, float]]:
    """담수호 21곳 -> (호수, damcd, lon, lat). 이름 해석은 강우 CSV 의 댐 목록 + DELISTED 로(네트워크 없이)."""
    idx = damlib.build_index([damlib.Dam(cd, nm, None, None, None) for cd, nm in names.items()])
    with open(ROOT / "reservoir_points.json", encoding="utf-8") as fh:
        lakes = json.load(fh)["lakes"]
    out = []
    for lake, v in lakes.items():
        d = damlib.resolve(lake, idx)
        if d is None:
            raise SystemExit(f"[중단] {lake} 를 강우 CSV 의 댐에 못 붙였다")
        out.append((lake, d.damcd, v["lon"], v["lat"]))
    return out


def covered(ds, lon: float, lat: float) -> bool:
    """좌표 주변 3×3 화소에 유효값이 있나."""
    row, col = ds.index(lon, lat)
    a = ds.read(1, window=Window(col - 1, row - 1, 3, 3), boundless=True, masked=True)
    return bool(np.isfinite(a.filled(np.nan)).any())


def rain5(series: dict[str, float | None], date: str) -> tuple[float | None, int]:
    """date 포함 직전 DAYS 일 합, 빈 날 수. 다 비면 None."""
    d0 = datetime.strptime(date, "%Y%m%d")
    vals = [series.get((d0 - timedelta(days=k)).strftime("%Y%m%d")) for k in range(DAYS)]
    got = [v for v in vals if v is not None]
    return (sum(got) if got else None), DAYS - len(got)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    rf, names = load_rain()
    lakes = lake_dams(names)
    obs = observations()

    dam_rows, basin_rows = [], []
    for o in obs:
        per_basin: dict[str, list[float]] = defaultdict(list)
        with rasterio.open(o["vrt"]) as ds:
            for lake, cd, lon, lat in lakes:
                cov = covered(ds, lon, lat)
                mm, miss = rain5(rf.get(cd, {}), o["date"])
                b = BASINS[cd[0]]
                dam_rows.append({"date": o["date"], "orbit": o["orbit"], "rel": o["rel"], "dir": o["dir"],
                                 "lake": lake, "damcd": cd, "basin": b, "covered": int(cov),
                                 "rf5_mm": "" if mm is None else round(mm, 1), "days_missing": miss})
                if cov and mm is not None:
                    per_basin[b].append(mm)
        row = {k: o[k] for k in ("date", "orbit", "rel", "dir", "sat", "utc")}
        for b in BASINS.values():
            v = per_basin.get(b)
            row[b] = "" if not v else round(statistics.median(v), 1)
            row[f"{b}_n"] = len(v or [])
        row["wet"] = "·".join(b for b in BASINS.values() if row[b] != "" and row[b] >= WET_MM)
        basin_rows.append(row)

    for path, rows in ((OUT_DAM, dam_rows), (OUT_BASIN, basin_rows)):
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"-> {path.relative_to(ROOT)}  ({len(rows)}행)")

    gaps = sorted({(r["lake"], r["days_missing"]) for r in dam_rows if r["days_missing"]})
    if gaps:
        print("강우 빈 날이 있는 호수(관측 창 기준, 최대): "
              + " · ".join(f"{k}{max(m for l, m in gaps if l == k)}일" for k in sorted({l for l, _ in gaps})))

    # 문서용 표 — (상대궤도, 날짜) 순. 굵게 = 50 mm 이상, 괄호 = 덮은 댐 수.
    print("\n| 상대궤도 | 촬영일(UTC) | 궤도 | 위성 | " + " | ".join(BASINS.values()) + " | wet |")
    print("| --- | --- | --- | --- | " + " | ".join("--:" for _ in BASINS) + " | --- |")
    for r in sorted(basin_rows, key=lambda r: (r["rel"], r["date"])):
        cells = []
        for b in BASINS.values():
            v, n = r[b], r[f"{b}_n"]
            cells.append("—" if v == "" else (f"**{v:.0f}**" if v >= WET_MM else f"{v:.0f}") + f" ({n})")
        d = r["date"]
        print(f"| {r['dir']}{r['rel']} | {d[:4]}-{d[4:6]}-{d[6:]} | o{r['orbit']} | {r['sat']} | "
              + " | ".join(cells) + f" | {r['wet'] or '-'} |")


if __name__ == "__main__":
    main()
