# -*- coding: utf-8 -*-
"""EGM 켬 재처리(ISSUES #26) 산출로 모자이크 VRT 를 다시 쓴다 (2026-10-12).

`scripts/run_egm_queue.sh` 가 `downloads/rtc_grd_frost_vh_egm_{2025,2026}` 에 쓰는 RTC 로
gee 가 읽는 `downloads/water_otsu_vh/vrt/mosaic_{날짜}_o{절대궤도}.vrt` 를 **같은 이름으로** 덮어쓴다.

- 대상 관측과 그 프레임은 **v10(EGM 끔) VRT 의 원본 목록**에서 가져온다 — 같은 프레임을 같은 조합으로.
- 관측의 프레임이 **전부** 완료(러너 로그의 `완료 (..분)` 행 + 파일 존재)돼야 쓴다. 일부만이면 건너뛴다.
- 처음 실행 때 지금 VRT 를 `vrt_poeorb_egmoff_20261012/` 로 백업한다(밀린 판 ↔ 제자리 판 대조용).
- 이미 EGM 판으로 다시 쓴 관측은 `temp/egm_vrt_done.txt` 에 남겨 **새로 쓴 것만** gee 통보 목록에 찍는다.
- VRT 생성은 `build_water_per_date_otsu.build_group_vrt`(전역 격자 `-tap`)를 그대로 쓴다.

    conda run --no-capture-output -n s1_snappy python -m s1.tools.mosaic.rebuild_vrt_egm [--dry-run]
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

from s1.tools.water import build_water_per_date_otsu as m

ROOT = Path(__file__).resolve().parents[3]
VRT_DIR = ROOT / "downloads" / "water_otsu_vh" / "vrt"
BAK = ROOT / "downloads" / "water_otsu_vh" / "vrt_poeorb_egmoff_20261012"
EGM = {y: ROOT / "downloads" / f"rtc_grd_frost_vh_egm_{y}" for y in ("2025", "2026")}
LOGS = ROOT / "temp" / "logs"
STATE = ROOT / "temp" / "egm_vrt_done.txt"
SRC = re.compile(r"<SourceFilename[^>]*>([^<]+)</SourceFilename>")
DONE = re.compile(r"완료 \(([\d.]+)분\): (\S+_rtc_db_vh\.tif)")

# 1단계: 포스터(10-22)용 13개 관측 — temp/egm_queue.txt 와 같다(REVIEW §2-6 재결정 박스, gee-61 합의).
# 2단계(나머지 16개 관측)는 백업 폴더의 VRT 전체에서 자동으로 잡는다 — 아래 all_obs().
POSTER = ["20260802_o003945", "20250806_o003550", "20260807_o004018", "20250811_o003623",
          "20260715_o008552", "20250725_o003375", "20260720_o008632", "20250718_o003280",
          "20250812_o060501", "20260813_o008982", "20250823_o003805", "20260825_o009157",
          "20250811_o003630"]


def all_obs(ref: Path) -> list[str]:
    """포스터 13개를 먼저, 나머지는 날짜순."""
    rest = sorted(v.stem[len("mosaic_"):] for v in ref.glob("mosaic_*.vrt") if v.stem[len("mosaic_"):] not in POSTER)
    return POSTER + rest


def done_names() -> set[str]:
    out = set()
    for log in [*LOGS.glob("rtc_egm_q_*.log"), *LOGS.glob("_egm_test_*.log")]:   # 시험 2장(0714)도 쓴다
        for mt in DONE.finditer(log.read_text(encoding="utf-8", errors="replace")):
            out.add(Path(mt.group(2).replace("\\", "/")).name)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if not BAK.exists() and not a.dry_run:
        BAK.mkdir(parents=True)
        for v in VRT_DIR.glob("mosaic_*.vrt"):
            shutil.copy2(v, BAK / v.name)
        print(f"지금 VRT(EGM 끔) 백업 -> {BAK.relative_to(ROOT)}")
    ref = BAK if BAK.exists() else VRT_DIR          # 원본 목록은 EGM 끔 판에서 읽는다

    finished = done_names()
    already = set(STATE.read_text(encoding="utf-8").split()) if STATE.exists() else set()
    new, waiting = [], []
    obs = all_obs(ref)
    for ob in obs:
        d, ab = ob.split("_o")
        names = [Path(s).name for s in SRC.findall((ref / f"mosaic_{ob}.vrt").read_text(encoding="utf-8"))]
        frames = [EGM[d[:4]] / n for n in sorted(set(names))]
        ok = [f for f in frames if f.name in finished and f.exists()]
        if len(ok) < len(frames):
            waiting.append(f"{ob} {len(ok)}/{len(frames)}")
            continue
        if ob in already:
            continue
        if a.dry_run:
            print(f"(dry-run) 쓸 것 mosaic_{ob}.vrt  {len(frames)}장")
        else:
            v = m.build_group_vrt(d, ab, frames, VRT_DIR)
            already.add(ob)
            print(f"재작성(EGM 켬) {v.name}  {len(frames)}장")
        new.append(ob)

    if not a.dry_run:
        STATE.write_text("\n".join(sorted(already)) + "\n", encoding="utf-8")
    print(f"\nEGM 판 VRT {len(already)}/{len(obs)} (포스터용 {len(already & set(POSTER))}/{len(POSTER)})")
    if waiting:
        print("아직: " + " · ".join(waiting))
    if new and not a.dry_run:
        print("\n📣 gee 에 알릴 것 — EGM 판으로 바뀐 (날짜, 궤도): " + " · ".join(new))


if __name__ == "__main__":
    main()
