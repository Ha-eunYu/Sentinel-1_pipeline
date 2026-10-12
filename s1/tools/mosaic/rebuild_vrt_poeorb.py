# -*- coding: utf-8 -*-
"""POEORB 산출로 (날짜, 절대궤도) 모자이크 VRT 를 다시 만든다 (2026-10-06, 10-12 개정).

gee `kwater/orbit_vrt.py` 가 읽는 `downloads/water_otsu_vh/vrt/mosaic_{날짜}_o{절대궤도}.vrt`
를 `rtc_grd_frost_vh_poeorb_{2025,2026}` 기준으로 다시 쓴다.

- **대상 프레임이 전부 완료된 그룹만** 쓴다 — 일부만 끝난 날짜로 만들면 프레임이 빠진
  모자이크가 된다. 재처리가 진행되는 대로 다시 돌리면 늘어난다(이미 쓴 것은 덮어쓴다).
- 모자이크에는 그 패스의 **완료된 프레임을 모두** 넣는다 — 대상(남한 대권역 1%↑) 밖
  프레임도 처리돼 있으면 들어간다.
- VRT 생성은 `build_water_per_date_otsu.build_group_vrt`(전역 격자 `-tap`)를 그대로 쓴다.
- 처음 실행 때 옛 VRT 폴더를 `vrt_stale_rtc_grd_frost_vh_20261006` 으로 백업한다.
- **rel 32 는 건너뛴다**(2025 짝이 없다). **rel 61 은 RTC 가 한 장이라도 있으면 포함한다**
  — 10-12 전에는 하드코딩으로 건너뛰어, rel 61 을 처리해도 VRT 가 안 생길 뻔했다
  (gee HANDOFF_FROM_GEE_20261012 §2-2).
- 끝에 **gee `orbit_vrt.py` 의 `ORBIT`·`SAT` 두 표에 (날짜, 궤도)가 다 있는지** 대조한다.
  2026-10-11 에 `ORBIT` 에만 넣고 `SAT` 를 빠뜨려 `sat_of()` 가 `KeyError` 로 멈췄다
  (ISSUES #25). 표가 둘이면 둘 다 본다.
- 모자이크를 다시 쓰면 **gee 에 (날짜, 궤도)를 알려야 한다** — gee 의 쌍 파일 `cover_all`
  이 낡는다(커버 0% 로 조용히 건너뛰는 사고, 2026-08-25). 끝에 그 목록을 찍는다.

    conda run -n s1_snappy python -m s1.tools.mosaic.rebuild_vrt_poeorb [--dry-run]
"""
import argparse
import csv
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from s1.tools.audit.poeorb_inventory import inventory, orbit_offsets
from s1.tools.water import build_water_per_date_otsu as m

ROOT = Path(__file__).resolve().parents[3]
VRT_DIR = ROOT / "downloads" / "water_otsu_vh" / "vrt"
DIRS = {y: ROOT / "downloads" / f"rtc_grd_frost_vh_poeorb_{y}" for y in ("2025", "2026")}
GEE_ORBIT_VRT = ROOT.parent / "gee" / "Korea_WaterDetection_2025_2026" / "kwater" / "orbit_vrt.py"
KEY = re.compile(r"_(\d{8})T\d{6}_\d{8}T\d{6}_(\d{6})_\w{6}_([0-9A-F]{4})")
SKIP_REL = {32}          # 2025 짝 없음
DEFER_REL = {61}         # 추후 진행 — RTC 가 생기면 자동 포함


def gee_tables() -> dict[str, set[tuple[str, str]]]:
    """gee orbit_vrt.py 의 ORBIT·SAT 표에 있는 (날짜, 궤도) 키. 파일이 없으면 빈 dict."""
    if not GEE_ORBIT_VRT.exists():
        return {}
    txt = GEE_ORBIT_VRT.read_text(encoding="utf-8", errors="ignore")
    out = {}
    for name in ("ORBIT", "SAT"):
        mt = re.search(rf"^{name}\s*:\s*dict.*?=\s*\{{(.*?)^\}}", txt, flags=re.S | re.M)
        out[name] = set(re.findall(r'\("(\d{8})",\s*"(\d{6})"\)', mt.group(1))) if mt else set()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="쓰지 않고 무엇을 할지만 찍는다")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    off = orbit_offsets()
    need, sat = defaultdict(set), {}
    for f in ("temp/poeorb2025_targets.csv", "temp/poeorb2026_targets.csv"):
        for r in csv.DictReader(open(ROOT / f, encoding="utf-8-sig")):
            if float(r["basins_pct_of_frame"]) < 1:
                continue
            d, ab, sid = KEY.search(r["zip"]).groups()
            sat[(d, ab)] = re.search(r"S1([A-D])_", r["zip"]).group(1)
            need[(d, ab)].add(sid)
    need[("20260703", "008384")].add("BB45")      # 10-05 에 받은 원본(목록 CSV 이후)
    sat[("20260703", "008384")] = "C"

    state = {(r["date"], r["id"]): r["state"] for r in inventory(measure_unlogged=True)}
    done = defaultdict(list)
    for p in DIRS.values():
        for t in sorted(p.glob("*_rtc_db_vh.tif")):
            d, ab, sid = KEY.search(t.name).groups()
            if state.get((d, sid), "").startswith("완료"):
                done[(d, ab)].append(t)

    ok, partial, deferred = [], [], []
    for g, ids in sorted(need.items()):
        rel = (int(g[1]) - off[(sat[g], g[0][:4])]) % 175
        have = {KEY.search(t.name).group(3) for t in done.get(g, [])}
        if rel in SKIP_REL:
            continue
        if rel in DEFER_REL and not have:
            deferred.append((g, rel, len(ids)))
            continue
        (ok if ids <= have else partial).append((g, rel, len(ids)))

    bak = VRT_DIR.parent / "vrt_stale_rtc_grd_frost_vh_20261006"
    if not bak.exists() and not a.dry_run:
        shutil.copytree(VRT_DIR, bak)
        print(f"옛 VRT 백업 -> {bak}")

    for (d, ab), rel, tot in ok:
        extra = len(done[(d, ab)]) - tot
        tag = f"대상 {tot}장" + (f" + 대상 밖 {extra}장" if extra else "")
        if a.dry_run:
            print(f"(dry-run) 쓸 것  mosaic_{d}_o{ab}.vrt  rel{rel}  {tag}")
        else:
            v = m.build_group_vrt(d, ab, sorted(done[(d, ab)]), VRT_DIR)
            print(f"재작성 {v.name}  rel{rel}  {tag}")
    if partial:
        print("\n아직(일부 프레임 미완료) — 나중에 다시:")
        for (d, ab), rel, tot in partial:
            print(f"  {d} o{ab} rel{rel}  {len(done.get((d, ab), []))}/{tot}")
    if deferred:
        print("\n보류(rel 61 추후 진행 — RTC 가 생기면 자동 포함): "
              + " · ".join(f"{d} o{ab}" for (d, ab), _, _ in deferred))

    # ── gee 표 대조: ORBIT·SAT 둘 다 ──────────────────────────────────────
    tables = gee_tables()
    if not tables:
        print(f"\n⚠ gee orbit_vrt.py 를 못 찾았다 — 표 대조 생략 ({GEE_ORBIT_VRT})")
    else:
        miss = [(g, name) for g, _, _ in ok for name in ("ORBIT", "SAT") if g not in tables[name]]
        if miss:
            print("\n🔴 gee orbit_vrt.py 에 없는 (날짜, 궤도) — **ORBIT·SAT 둘 다** 넣어야 gee 가 쓴다:")
            for (d, ab), name in miss:
                print(f"  {name:5s} ← (\"{d}\", \"{ab}\")")
        else:
            print(f"\n✅ 쓴 {len(ok)}개 모두 gee ORBIT·SAT 두 표에 있다")
    if ok and not a.dry_run:
        print("\n📣 gee 에 알릴 것 — 쌍 파일 cover_all 이 낡는다(재작성한 (날짜, 궤도)): "
              + " · ".join(f"{d} o{ab}" for (d, ab), _, _ in ok))


if __name__ == "__main__":
    main()
