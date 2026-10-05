# -*- coding: utf-8 -*-
"""SWOT LakeSP_Prior(Version D) 한 주기(21일)를 내려받는다.

CMR 의 LakeSP 그래뉼 footprint 는 **대륙 단위**라 점 질의가 거의 모든 패스를
돌려준다 — 그래서 커버리지는 그래뉼을 받아 호수 레코드로 센다(swot_vs_wamis.py).

    conda run -n s1_snappy python -m s1.tools.swot.swot_fetch 2026-08-01 2026-08-21

인증: ~/.netrc 의 urs.earthdata.nasa.gov 항목(curl -n). 산출: downloads/swot/lakesp_prior_<시작>/
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COLLECTION = "C3233942291-POCLOUD"   # SWOT_L2_HR_LakeSP_prior_D
POINT = "127.11,35.60"               # 옥정호 — 남한 내륙 아무 점이면 된다(대륙 단위 footprint)


def granules(t0: str, t1: str) -> list[str]:
    q = urllib.parse.urlencode({"collection_concept_id": COLLECTION, "point": POINT,
                                "temporal": f"{t0}T00:00:00Z,{t1}T23:59:59Z", "page_size": 200})
    with urllib.request.urlopen("https://cmr.earthdata.nasa.gov/search/granules.json?" + q, timeout=60) as r:
        entries = json.load(r)["feed"]["entry"]
    urls = []
    for e in entries:
        urls += [l["href"] for l in e.get("links", [])
                 if l["href"].startswith("https") and l["href"].endswith(".zip")][:1]
    return urls


def main() -> None:
    t0, t1 = sys.argv[1], sys.argv[2]
    out = ROOT / "downloads" / "swot" / f"lakesp_prior_{t0.replace('-', '')}"
    out.mkdir(parents=True, exist_ok=True)
    urls = granules(t0, t1)
    print(f"{len(urls)} granules -> {out}")
    for u in urls:
        f = out / u.rsplit("/", 1)[1]
        if f.exists() and f.stat().st_size > 0:
            continue
        # Earthdata 는 리다이렉트+쿠키 인증이라 curl -n -L 이 가장 덜 번거롭다
        subprocess.run(["curl", "-s", "-n", "-L", "--fail", "-c", str(out / ".cj"), "-b", str(out / ".cj"),
                        "-o", str(f), u], check=True)
    print("done")


if __name__ == "__main__":
    main()
