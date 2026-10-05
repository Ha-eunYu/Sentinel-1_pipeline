# -*- coding: utf-8 -*-
"""SWOT LakeSP 수면고(wse) ↔ WAMIS 저수위(rwl) 대조 — 담수호 21곳.

    F:\\envs\\gis_clean\\python.exe -m s1.tools.swot.swot_vs_wamis downloads/swot/lakesp_prior_20260801

geopandas 가 필요해 gis_clean 환경에서 돈다(s1_* 환경에는 없다).
WAMIS 는 일자료 CSV(collect_dam_level --mode daily)를 읽는다. SWOT 시각은 UTC 라
**KST 로 바꿔 날짜를 맞춘다** — 15:4xZ 패스는 KST 익일 00:4x 다.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "experiments" / "swot_wamis"
WAMIS_CSV = ROOT / "downloads" / "wamis" / "dam_daily_20250909_20260908.csv"

# reservoir_points.json 이름 -> WAMIS damnm (s1/wamis/dams.py 별칭표와 같은 대응)
ALIAS = {"장성호": "장성", "옥정호": "섬진강", "밀양호": "밀양", "운문호": "운문", "용담호": "용담",
         "안동호": "안동", "영천호": "영천", "주암호": "주암(본)", "파로호": "화천", "합천호": "합천",
         "임하호": "임하", "나주호": "나주", "소양호": "소양강", "대청호": "대청", "담양호": "담양",
         "충주호": "충주", "의암호": "의암", "진양호": "남강", "평림호": "평림", "동복호": "동복",
         "성덕저수지": "성덕"}
COLS = ["lake_id", "time_str", "wse", "wse_u", "area_total", "area_tot_u", "p_ref_area", "p_ref_wse",
        "quality_f", "partial_f", "dark_frac", "xovr_cal_q", "ds1_l", "ds1_q", "lake_name"]


def read_swot(zdir: Path) -> pd.DataFrame:
    pts = json.loads((ROOT / "reservoir_points.json").read_text(encoding="utf-8"))["lakes"]
    pg = gpd.GeoDataFrame({"name": list(pts)},
                          geometry=[Point(v["lon"], v["lat"]) for v in pts.values()], crs=4326).to_crs(5179)
    rows = []
    for z in sorted(glob.glob(str(zdir / "*.zip"))):
        g = gpd.read_file("zip://" + z.replace("\\", "/"))
        g = g.cx[126:130, 34:38.7]
        if g.empty:
            continue
        # 호수 중심점이 폴리곤 밖(가늘고 긴 호수)일 수 있어 3 km 안 최근접으로 붙인다
        j = gpd.sjoin_nearest(pg, g.to_crs(5179), how="inner", max_distance=3000, distance_col="d_m")
        rows.append(j[["name", "d_m"] + COLS])
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    zdir = ROOT / sys.argv[1] if len(sys.argv) > 1 else ROOT / "downloads/swot/lakesp_prior_20260801"
    HERE.mkdir(parents=True, exist_ok=True)
    s = read_swot(zdir)
    s.to_csv(HERE / "swot_c054.csv", index=False, encoding="utf-8-sig")

    w = pd.read_csv(WAMIS_CSV, encoding="utf-8-sig", dtype={"damcd": str, "obsymd": str})
    s["kst"] = pd.to_datetime(s["time_str"]).dt.tz_convert("Asia/Seoul")
    s["obsymd"] = s["kst"].dt.strftime("%Y%m%d")
    s["damnm"] = s["name"].map(ALIAS)
    m = s.merge(w[["damnm", "obsymd", "rwl"]], on=["damnm", "obsymd"], how="left")
    m["wse_minus_rwl"] = m["wse"] - m["rwl"]
    m.to_csv(HERE / "swot_vs_wamis_c054.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    print(m[["name", "kst", "wse", "rwl", "wse_minus_rwl", "quality_f", "partial_f", "area_total",
             "p_ref_area", "dark_frac"]].sort_values(["name", "kst"]).to_string(index=False))
    good = m[(m.quality_f <= 1) & (m.partial_f == 0)].dropna(subset=["wse_minus_rwl"])
    print(f"\nquality_f<=1 & partial_f==0: n={len(good)}, "
          f"|wse-rwl| 중앙값 {good['wse_minus_rwl'].abs().median():.3f} m")


if __name__ == "__main__":
    main()
