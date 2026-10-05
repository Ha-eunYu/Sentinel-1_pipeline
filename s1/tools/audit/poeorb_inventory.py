# -*- coding: utf-8 -*-
"""POEORB 재처리 산출물 목록 — 무엇이 끝났고, 상대궤도 짝이 어디까지 찼나 (2026-10-06)

`downloads/rtc_grd_frost_vh_poeorb_{2025,2026}`(E: junction)을 훑어 씬마다
날짜·위성·상대궤도·유효화소·용량을 표로 내고, 상대궤도별로 2025/2026 이 둘 다
있는지(= 육안 겹침 확인이 가능한지) 요약한다.

    conda run -n s1_snappy python -m s1.tools.audit.poeorb_inventory
    conda run -n s1_snappy python -m s1.tools.audit.poeorb_inventory --md docs/pipeline/POEORB_INVENTORY_KR.md

- **완료 판정은 배치 로그의 `완료 (` 줄**이다. 폴더에 파일이 있어도 로그에 완료가
  없으면 `처리중`(gpt 가 쓰는 중)으로 둔다 — 쓰다 만 파일을 완료로 세지 않기 위해서다
  (HANDOFF_20260826 §4.4).
- 유효화소·압축률은 그 로그 줄에서 읽는다(다시 재지 않는다 — 장당 수십 초).
- 로그에 완료가 없는데 **3시간 넘게 안 바뀐 파일**은 `로그없음`이다. 러너를 강제
  종료해도 gpt 자식은 끝까지 써서 **멀쩡한 산출물이 기록 없이** 남는다(실례: 2025-07-31
  `625F`, 8/27 강제 종료 — 실측 유효 70.5%). `--measure` 를 주면 그런 파일만
  `s1.core.rtc_qc.measure` 로 재서 `완료(실측)` 또는 `의심` 으로 가른다.
- 상대궤도는 절대궤도와 위성·연도별 오프셋으로 계산한다. 오프셋은
  `data/relative_orbits_sentinel-1-grd.csv` 에서 실측한다(S1C 는 2025→2026 에
  171→98 로 바뀌었다 — DROUGHT_KR 2-3 정정).
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from s1.core.paths import DATA_DIR

ROOT = Path(__file__).resolve().parents[3]
DIRS = {y: ROOT / "downloads" / f"rtc_grd_frost_vh_poeorb_{y}" for y in ("2025", "2026")}
LOGS = ROOT / "temp" / "logs"
NAME = re.compile(r"S1([A-D])_IW_GRDH_1SDV_(\d{8})T(\d{6})_\d{8}T\d{6}_(\d{6})_\w{6}_([0-9A-F]{4})")
DONE = re.compile(r"완료 \(([\d.]+)분\): (\S+_rtc_db_vh\.tif)\s+유효 ([\d.]+)% · 압축 ([\d.]+)%")


def orbit_offsets() -> dict[tuple[str, str], int]:
    off: dict[tuple[str, str], Counter] = defaultdict(Counter)
    with open(DATA_DIR / "relative_orbits_sentinel-1-grd.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            off[(r["platform"][-1], r["date"][:4])][(int(r["abs_orbit"]) - int(r["rel_orbit"])) % 175] += 1
    return {k: v.most_common(1)[0][0] for k, v in off.items()}


def done_lines() -> dict[str, tuple[float, float, float]]:
    """파일명 -> (분, 유효%, 압축%). 같은 파일이 여러 번 있으면 마지막 것."""
    out = {}
    for log in sorted(LOGS.glob("rtc_poeorb_*.log")):
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = DONE.search(line)
            if m:
                out[Path(m.group(2).replace("\\", "/")).name] = (float(m.group(1)), float(m.group(3)), float(m.group(4)))
    return out


def inventory(measure_unlogged: bool = False) -> list[dict]:
    offs, done = orbit_offsets(), done_lines()
    now = datetime.now().timestamp()
    rows = []
    for year, d in DIRS.items():
        for f in sorted(d.glob("*_rtc_db_vh.tif")):
            m = NAME.search(f.name)
            if not m:
                continue
            sat, day, hms, ab, sid = m.groups()
            o = offs.get((sat, day[:4]))
            st = f.stat()
            rec = done.get(f.name)
            state = "완료" if rec else "처리중"
            if not rec and now - st.st_mtime > 3 * 3600:
                state = "로그없음"
                if measure_unlogged:
                    from s1.core.rtc_qc import measure, LOW_VALID
                    q = measure(f)
                    rec = (None, round(q.valid_frac * 100, 1), round(q.compress_ratio * 100, 1))
                    state = "완료(실측)" if q.valid_frac >= LOW_VALID else "의심"
            rows.append({
                "year": year, "date": day, "utc": f"{hms[:2]}:{hms[2:4]}", "sat": f"S1{sat}",
                "rel": (int(ab) - o) % 175 if o is not None else None, "id": sid,
                "state": state,
                "minutes": rec[0] if rec else None, "valid": rec[1] if rec else None,
                "compress": rec[2] if rec else None,
                "gb": round(st.st_size / 1e9, 2),
                "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%m-%d %H:%M"),
            })
    return rows


def to_markdown(rows: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    done = [r for r in rows if r["state"].startswith("완료")]
    by_rel: dict[int, dict[str, list]] = defaultdict(lambda: {"2025": [], "2026": []})
    for r in done:
        by_rel[r["rel"]][r["year"]].append(r)
    L = [f"# POEORB 재처리 산출물 목록 ({now} 기준)", "",
         "`python -m s1.tools.audit.poeorb_inventory --md <이 파일>` 로 다시 만든다. "
         "손으로 고치지 말 것.", "",
         "규격: VH · Frost · `korea_peninsula_cop30` · EGM 끔 · POEORB. "
         "폴더는 `downloads/rtc_grd_frost_vh_poeorb_{2025,2026}` → "
         "`E:\\06_SAR_system_archive\\` 아래 junction.", "",
         f"**완료 {len(done)}장** (2025 {sum(r['year'] == '2025' for r in done)} · "
         f"2026 {sum(r['year'] == '2026' for r in done)}) · "
         + " · ".join(f"{k} {v}장" for k, v in Counter(r["state"] for r in rows if r not in done).items()), "",
         "## 상대궤도별 — 짝이 찼나", "",
         "| 상대궤도 | 2025 완료 (날짜: 장수) | 2026 완료 (날짜: 장수) | 육안 확인 |",
         "|---:|---|---|---|"]
    for rel in sorted(by_rel):
        g = by_rel[rel]
        fmt = lambda xs: " · ".join(f"{d[4:6]}-{d[6:]}: {n}" for d, n in sorted(Counter(x["date"] for x in xs).items())) or "—"
        ok = "✅ 가능" if g["2025"] and g["2026"] else "⏳ 한쪽만"
        L.append(f"| {rel} | {fmt(g['2025'])} | {fmt(g['2026'])} | {ok} |")
    L += ["", "## 씬별", "",
          "| 연도 | 날짜 | UTC | 위성 | rel | ID | 상태 | 유효% | 압축% | GB | 분 |",
          "|---|---|---|---|---:|---|---|---:|---:|---:|---:|"]
    for r in sorted(rows, key=lambda r: (r["rel"] or 0, r["date"], r["id"])):
        v = lambda x: "" if x is None else f"{x:g}"
        L.append(f"| {r['year']} | {r['date'][4:6]}-{r['date'][6:]} | {r['utc']} | {r['sat']} | {r['rel']} | "
                 f"{r['id']} | {r['state']} | {v(r['valid'])} | {v(r['compress'])} | {r['gb']} | {v(r['minutes'])} |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--md", help="이 경로에 마크다운으로 쓴다")
    ap.add_argument("--csv", help="이 경로에 CSV 로 쓴다")
    ap.add_argument("--measure", action="store_true",
                    help="로그에 완료가 없는 오래된 파일만 유효화소를 실측한다(장당 수십 초)")
    a = ap.parse_args()
    rows = inventory(measure_unlogged=a.measure)
    md = to_markdown(rows)
    if a.md:
        Path(a.md).write_text(md, encoding="utf-8", newline="\n")
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader(); w.writerows(rows)
    print(md)


if __name__ == "__main__":
    main()
