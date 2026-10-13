# -*- coding: utf-8 -*-
"""호소 폴리곤을 동서로 밀어 **폴리곤 안 수체 면적이 최대가 되는 이동량**을 잰다 (2026-10-13, ISSUES #26 판정 ②).

`geoloc_shift`(두 영상끼리 맞대기)와 짝을 이루는 **절대 기준** 검사다 — 국가기본도 호소 폴리곤(TN_LKMH, 만수위
경계)을 기준으로, 영상 속 물이 폴리곤보다 어느 쪽에 있는지 본다. 위치가 맞으면 최대 지점이 0 열이어야 한다.

- 수체: 폴리곤 외곽 + 0.01° 창 안에서 Otsu 임계(창마다)로 가른다.
- 이동: 폴리곤 마스크를 영상 격자에서 열(경도 화소, 한국 위도에서 약 8 m) 단위로 ±R 만큼 민다.
- 음수 = 폴리곤을 **서쪽**으로 밀 때 최대 = 영상 속 물이 **서쪽**에 있다(= 영상이 서쪽으로 밀렸다).

2026-10-12 시험(2026-07-14 376D 상승 · B126 하강): v10(EGM 끔) 상승 −4 · 하강 +6 → EGM 켬 −1 · +1.
gee-61 이 같은 방식(EPSG:5179 10 m)으로 안동·임하·옥정 상승 4건 모두 −4 를 얻었다.

geopandas·shapely 가 필요해 s1_snappy 가 아니라 **sar-gee** 환경으로 돌린다.

    conda run --no-capture-output -n sar-gee python -m s1.tools.audit.polygon_shift A.tif [B.tif ...] [--lakes 옥정호 평림호] [--radius 8]
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pyogrio
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds

LAKES = Path(r"F:\06_SAR_system\gee\V-world_수자원\국가기본도_호소\TN_LKMH.shp")
DEFAULT = ["옥정호", "평림호", "장성호", "주암호", "합천호", "동복호", "담양호", "나주호", "진양호",
           "안동호", "임하호", "대청호", "용담호", "충주호", "소양호"]
PAD = 0.01      # 폴리곤 외곽 여유(도)


def otsu(x: np.ndarray) -> float:
    h, e = np.histogram(x, bins=256)
    c = (e[:-1] + e[1:]) / 2
    w = np.cumsum(h)
    m = np.cumsum(h * c)
    w1 = w[-1] - w
    ok = (w > 0) & (w1 > 0)
    sb = np.zeros_like(c)
    sb[ok] = (m[-1] * w[ok] / w[-1] - m[ok]) ** 2 / (w[ok] * w1[ok])
    return float(c[np.argmax(sb)])


def load(names: list[str]) -> dict:
    g = pyogrio.read_dataframe(LAKES)
    g["geometry"] = g.geometry.make_valid()
    g["nm"] = g["LKMH_NM"].astype(str).str.strip()
    out = {}
    for n in names:
        s = g[g["nm"] == n]
        if not s.empty:                           # 동명이 있으면 가장 큰 것
            s = s.assign(a=s.geometry.area).sort_values("a", ascending=False)
            out[n] = gpd.GeoSeries([s.iloc[0].geometry], crs=g.crs).to_crs("EPSG:4326").iloc[0]
    return out


def peak(path: str, geom, r: int) -> tuple[int, float, float] | None:
    """(최대 지점 열, 0 열 대비 면적 증가율, 임계 dB). 덮지 않으면 None."""
    with rasterio.open(path) as ds:
        b = geom.bounds
        win = from_bounds(b[0] - PAD, b[1] - PAD, b[2] + PAD, b[3] + PAD, ds.transform).round_offsets().round_lengths()
        a = ds.read(1, window=win, boundless=True, masked=True).astype("float32").filled(np.nan)
        a[a == 0] = np.nan
        if np.isnan(a).mean() > 0.3:
            return None
        mask = rasterize([(geom, 1)], out_shape=a.shape, transform=ds.window_transform(win),
                         fill=0, dtype="uint8").astype(bool)
    thr = otsu(a[np.isfinite(a)])
    water = np.isfinite(a) & (np.nan_to_num(a, nan=0.0) < thr)
    areas = [(water & np.roll(mask, dx, 1)).sum() for dx in range(-r, r + 1)]
    k = int(np.argmax(areas)) - r
    return k, areas[k + r] / max(areas[r], 1) - 1, thr


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rasters", nargs="+", help="RTC tif 또는 모자이크 VRT (EPSG:4326, dB)")
    ap.add_argument("--lakes", nargs="+", default=DEFAULT)
    ap.add_argument("--radius", type=int, default=8)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    lakes = load(a.lakes)
    print("폴리곤:", ", ".join(lakes))
    for path in a.rasters:
        ks = []
        print(f"\n== {Path(path).name}")
        for n, geom in lakes.items():
            res = peak(path, geom, a.radius)
            if res is None:
                continue
            k, gain, thr = res
            ks.append(k)
            print(f"  {n:4s} 최대 지점 {k:+d} 열   0 열 대비 면적 +{gain * 100:.1f}%   임계 {thr:.1f} dB")
        if ks:
            print(f"  → 저수지 {len(ks)}곳 중앙값 {statistics.median(ks):+.1f} 열 · 범위 {min(ks):+d}~{max(ks):+d}")


if __name__ == "__main__":
    main()
