# -*- coding: utf-8 -*-
"""POEORB 산출로 (날짜, 절대궤도) 모자이크 VRT 를 다시 만든다 (2026-10-06).

gee `kwater/orbit_vrt.py` 가 읽는 `downloads/water_otsu_vh/vrt/mosaic_{날짜}_o{절대궤도}.vrt`
가 옛 `rtc_grd_frost_vh/`(RESORB·옛 DEM, NAS 이관 후 비어 있음)를 가리키고 있어
`rtc_grd_frost_vh_poeorb_{2025,2026}` 기준으로 다시 쓴다.

- **대상 프레임이 전부 완료된 그룹만** 쓴다 — 일부만 끝난 날짜로 만들면 프레임이 빠진
  모자이크가 된다. 재처리가 진행되는 대로 다시 돌리면 늘어난다(이미 쓴 것은 덮어쓴다).
- VRT 생성은 `build_water_per_date_otsu.build_group_vrt`(전역 격자 `-tap`)를 그대로 쓴다.
- 처음 실행 때 옛 VRT 폴더를 `vrt_stale_rtc_grd_frost_vh_20261006` 으로 백업한다.
- rel 61(추후)·rel 32(짝 없음)는 건너뛴다.
- 모자이크에는 그 패스의 **완료된 프레임을 모두** 넣는다 — 대상(남한 대권역 1%↑) 밖 프레임도
  처리돼 있으면 들어간다(2026-10-12: 한강 유역 밖 북한 9장을 따로 재처리했다).

    conda run -n s1_snappy python -m s1.tools.mosaic.rebuild_vrt_poeorb
"""
import csv, re, shutil, sys
from collections import defaultdict
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from s1.tools.water import build_water_per_date_otsu as m
from s1.tools.audit.poeorb_inventory import inventory, orbit_offsets
ROOT = Path(r"F:\06_SAR_system\S1")
VRT_DIR = ROOT / "downloads" / "water_otsu_vh" / "vrt"
DIRS = {y: ROOT / "downloads" / f"rtc_grd_frost_vh_poeorb_{y}" for y in ("2025", "2026")}
KEY = re.compile(r"_(\d{8})T\d{6}_\d{8}T\d{6}_(\d{6})_\w{6}_([0-9A-F]{4})")
# 대상(남한 대권역 1%↑) 중 rel 61·32 제외 — 대기열/완료 기준과 같게
skip_rel = {32, 61}
need = defaultdict(set)
OFF = orbit_offsets()
SAT = {}
for f in ("temp/poeorb2025_targets.csv", "temp/poeorb2026_targets.csv"):
    for r in csv.DictReader(open(ROOT / f, encoding="utf-8-sig")):
        if float(r["basins_pct_of_frame"]) < 1: continue
        k = KEY.search(r["zip"]); d, ab, sid = k.groups()
        SAT[(d, ab)] = re.search(r"S1([A-D])_", r["zip"]).group(1)
        need[(d, ab)].add(sid)
need[("20260703", "008384")].add("BB45"); SAT[("20260703", "008384")] = "C"
done = defaultdict(list)
state = {(r["date"], r["id"]): r["state"] for r in inventory(measure_unlogged=True)}
for y, p in DIRS.items():
    for t in sorted(p.glob("*_rtc_db_vh.tif")):
        d, ab, sid = KEY.search(t.name).groups()
        if state.get((d, sid), "").startswith("완료"):
            done[(d, ab)].append(t)
ok, partial = [], []
for g, ids in sorted(need.items()):
    rel = (int(g[1]) - OFF[(SAT[g], g[0][:4])]) % 175
    have = {KEY.search(t.name).group(3) for t in done.get(g, [])}
    if rel in skip_rel: continue
    (ok if ids <= have else partial).append((g, rel, len(have), len(ids)))
bak = VRT_DIR.parent / "vrt_stale_rtc_grd_frost_vh_20261006"
if not bak.exists():
    shutil.copytree(VRT_DIR, bak)
    print(f"옛 VRT 백업 -> {bak}")
for (d, ab), rel, n, tot in ok:
    v = m.build_group_vrt(d, ab, sorted(done[(d, ab)]), VRT_DIR)
    extra = len(done[(d, ab)]) - tot
    print(f"재작성 {v.name}  rel{rel}  대상 {tot}장" + (f" + 대상 밖 {extra}장" if extra else ""))
print("\n아직(일부 프레임 미완료) — 나중에 다시:")
for (d, ab), rel, n, tot in partial:
    print(f"  {d} o{ab} rel{rel}  {n}/{tot}")
