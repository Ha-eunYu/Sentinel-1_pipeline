# -*- coding: utf-8 -*-
"""두 RTC(또는 모자이크 VRT)의 **위치 어긋남**을 담수호 수체 마스크로 잰다 (2026-10-12).

왜
--
2026-10-12 에 외부 DEM(`korea_peninsula_cop30`)을 **EGM 끔**으로 쓴 RTC 가 레인지 방향으로
30~50 m 밀려 있는 것을 찾았다. 그 DEM 은 바다가 0.00 m 인 **지오이드(EGM2008) 정표고**인데,
EGM 을 끄면 SNAP 이 타원체고로 읽어 지형이 지오이드고(한국 약 25~28 m)만큼 낮게 들어간다.
높이가 낮으면 영상이 **센서 쪽으로** 밀린다(상승 = 서쪽, 하강 = 동쪽).

이 도구는 그 어긋남을 숫자 하나로 잰다. 담수호 좌표 주변 창(기본 반경 0.05° ≈ 5 km)에서
두 영상의 수체 마스크(VH dB < 임계)를 만들고, B 를 ±R 화소 옮겨 IoU 가 최대가 되는 (dx, dy) 를 찾는다.

- **같은 날 상승 ↔ 하강**(예: 2026-07-14 A127 ↔ D134): 위치가 맞으면 0, EGM 끔이면 7~10 화소.
- **같은 씬 두 판**(예: EGM 끔 ↔ EGM 켬, 자동캐시 DEM ↔ 외부 DEM): 처리 차이에 의한 이동만 남는다.

dx > 0 은 "B 를 동쪽으로 옮겨야 A 와 맞는다"(= B 가 A 보다 서쪽에 있다). 화소는 입력 격자(10 m) 단위.
두 입력의 격자 원점이 달라도 1 화소 안쪽이라 정수 화소 판정에는 지장이 없다.

    conda run --no-capture-output -n s1_snappy python -m s1.tools.audit.geoloc_shift A.vrt B.vrt [--thr -20] [--radius 12]

⚠ env 를 활성화하지 않고 `F:\\envs\\s1_snappy\\python.exe` 만 부르면 GDAL 이 VRT 원본을 열 때 DLL 을 못 찾아
**아무 출력 없이 rc=127** 로 끝난다. `conda run` 으로 부르거나 env 의 `Library\\bin` 을 PATH 앞에 둔다.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
LAKES_JSON = ROOT / "reservoir_points.json"
HALF = 0.05     # 창 반경(도)


def window(path: str, x: float, y: float) -> np.ndarray:
    with rasterio.open(path) as ds:
        win = from_bounds(x - HALF, y - HALF, x + HALF, y + HALF, ds.transform)
        win = win.round_offsets().round_lengths()
        return ds.read(1, window=win, boundless=True, masked=True).astype("float32").filled(np.nan)


def best_shift(a: np.ndarray, b: np.ndarray, r: int) -> tuple[float, float, int, int]:
    """(이동 전 IoU, 최대 IoU, dx, dy) — B 를 (dx, dy) 옮겼을 때 A 와 가장 잘 겹친다."""
    def iou(s, t):
        return (s & t).sum() / max((s | t).sum(), 1)
    core = (slice(r, -r), slice(r, -r))
    base = iou(b[core], a[core])
    best = (base, 0, 0)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            v = iou(np.roll(np.roll(b, dy, 0), dx, 1)[core], a[core])
            if v > best[0]:
                best = (v, dx, dy)
    return base, best[0], best[1], best[2]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", help="기준 영상(tif/VRT)")
    ap.add_argument("b", help="옮겨 볼 영상(tif/VRT)")
    ap.add_argument("--thr", type=float, default=-20.0, help="수체 임계 VH dB (기본 -20)")
    ap.add_argument("--radius", type=int, default=12, help="찾을 이동 범위 ±화소 (기본 12)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    lakes = json.load(open(LAKES_JSON, encoding="utf-8"))["lakes"]
    dxs, dys = [], []
    for name, v in lakes.items():
        ia, ib = window(a.a, v["lon"], v["lat"]), window(a.b, v["lon"], v["lat"])
        h, w = min(ia.shape[0], ib.shape[0]), min(ia.shape[1], ib.shape[1])
        ia, ib = ia[:h, :w], ib[:h, :w]
        if np.isnan(ia).mean() > 0.2 or np.isnan(ib).mean() > 0.2:
            continue                                   # 둘 중 하나가 그 저수지를 덮지 않는다
        ma, mb = ia < a.thr, ib < a.thr
        if ma.mean() < 0.01:
            continue                                   # 창 안에 물이 거의 없다
        base, best, dx, dy = best_shift(ma, mb, a.radius)
        dxs.append(dx)
        dys.append(dy)
        print(f"{name:6s} dx={dx:+3d} dy={dy:+3d} 화소   IoU {base:.3f} -> {best:.3f}   (수체 {ma.mean() * 100:4.1f}%)")
    if dxs:
        print(f"\n저수지 {len(dxs)}곳  dx 중앙값 {statistics.median(dxs):+.1f} · 범위 {min(dxs):+d}~{max(dxs):+d}"
              f"   dy 중앙값 {statistics.median(dys):+.1f}")
    else:
        print("두 영상이 함께 덮는 담수호가 없다")


if __name__ == "__main__":
    main()
