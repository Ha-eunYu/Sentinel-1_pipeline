# -*- coding: utf-8 -*-
"""poster_kit — 2026 원탐학회 가뭄 포스터 그림·표 한 벌 (S1 · 2026-10-15).

수치 기준: gee docs/DROUGHT_2026_EVIDENCE_KR.md 「포스터 조립용 최종 목록」(v11 · EGM 켬).
서사 순서: ① 이례성(WAMIS 10년 순위·공식 예·경보) → ② SAR 면적 감소 → ③ 공식 자료와 일치(하한) → ④ 부록.

    그림1  이례성 — 8개 저수지 8월 평균 저수위 10년 중 위치 + 남부 권역 순위 중앙값
    그림2  남부 지도 — (a) WAMIS 권역 판정 (b) SAR 댐유역 8월 Δ% (정본 배정)
    그림3  8개 댐유역 지도·막대          (poster_sar_figs 그림A 재사용)
    그림4  SAR 면적 ↔ WAMIS 저수량·민감도 (poster_sar_figs 그림B 재사용)
    그림5  SAR·S2 화소 대응              (poster_sar_figs 그림C 재사용)
    그림6  관측쌍 타임라인 + 직전 5일 강우 (방법)
    그림7  부록 — 강우 위상: 저수지 ↔ 유역
    표1~11  PNG + 표모음.xlsx + 표모음_A0.pptx(포스터와 같은 A0 세로·22/20 pt, 편집 가능)

입력은 전부 읽기만 한다. 유역 정본 배정은 gee scripts/canon_table.py 의 규칙을 그대로 옮겨
(그 스크립트는 import 시 파일을 쓰므로 부르지 않는다) output/canon_table.txt 와 대조한다.

실행 (gis_clean; xlsx·pptx 는 openpyxl·python-pptx 가 있는 경로를 --pylib 로)
    $env:GDAL_DATA = "F:\\envs\\gis_clean\\Library\\share\\gdal"
    F:\\envs\\gis_clean\\python.exe scripts\\poster_kit.py --out <폴더> [--pylib <site-packages>]
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poster_sar_figs as psf  # noqa: E402

ROOT, GEE, WAMIS_DIR = psf.ROOT, psf.GEE, psf.WAMIS
S1 = ROOT / "S1"
RANK_CSV = S1 / "data" / "wamis_rank_jul_aug.csv"
RAIN_CSV = S1 / "data" / "rain_phase_5d.csv"
S2_DIR = Path(r"E:\~K-water_지상국\20261021_원탐학회\S2_자료_20261015")
FS = psf.FS
C_JUL, C_AUG, C_NAVY, C_INK, C_MUTED, C_GRID = psf.C_JUL, psf.C_AUG, psf.C_NAVY, psf.C_INK, psf.C_MUTED, psf.C_GRID
C_25 = "#3a7dbf"                     # 2025 (전년도, 다우) — 파랑
C_26 = C_AUG                         # 2026 (가뭄) — 진주황
C_HI = "#c4400a"                     # 표 강조 숫자
M = "−"


def f1(v: float, sign: bool = True) -> str:
    """소수 1자리, U+2212."""
    s = f"{v:+.1f}" if sign else f"{v:.1f}"
    return s.replace("-", M) if v < 0 else (s if v > 0 or not sign else s.replace("+", ""))


def f2(v: float, sign: bool = False) -> str:
    s = f"{v:+.2f}" if sign else f"{v:.2f}"
    return s.replace("-", M)


# ════════════════════════ 자료 ════════════════════════
# 정본 배정 — gee scripts/canon_table.py 2026-10-15 판 규칙 (RUNS·ASSIGN·_fix 우선·동급 겹침 정지)
RUNS = {
    "7월A": ("0725↔0715", "ASC54", ["watershed_change_v11_jul_a.csv", "watershed_change_v11_jul_a_han.csv",
                                    "watershed_change_v11_jul_a_fix.csv", "watershed_change_v11_jul_a_namgang.csv"]),
    "7월B": ("0718↔0720", "DESC134", ["watershed_change_v11_jul_b.csv"]),
    "8월A": ("0806↔0802", "ASC54", ["watershed_change_v11_aug_a.csv", "watershed_change_v11_aug_a_fix.csv"]),
    "8월B": ("0811↔0807", "ASC127", ["watershed_change_v11_aug_b.csv", "watershed_change_v11_aug_b_fix.csv"]),
}
ASSIGN = {("7월", "대청"): "7월B", ("7월", "남강"): "7월B", ("7월", "영주"): "7월A", ("7월", "광동"): "7월A",
          ("7월", "군위"): "7월A", ("7월", "부항"): "7월A", ("7월", "합천"): "7월A",
          ("8월", "대청"): "8월B", ("8월", "합천"): "8월A", ("8월", "부항"): "8월A", ("8월", "남강"): "8월B"}
HAN = {"한 강", "한강동해", "한강서해", "충주", "횡성", "광동", "달방", "소양강", "임남댐", "평화화천", "한탄강", "군남"}
OUT_OF_SCOPE = HAN | {"제주도", "삽교천", "안성천"}     # 포스터 = 남부 15 대권역 (사용자 10-14)


def _load_run(run: str) -> dict:
    out, grade = {}, {}
    for fn in sorted(RUNS[run][2], key=lambda f: 2 if "_fix" in f else 1):
        p = GEE / fn
        if not p.exists():
            continue
        g = 2 if "_fix" in fn else 1
        for r in pd.read_csv(p, encoding="utf-8-sig", dtype=str).to_dict("records"):
            k = (r["구분"].strip(), r["대상"].strip())
            if k in out and grade[k] == g:
                raise SystemExit(f"동급 겹침 {k} — {fn}")
            out[k], grade[k] = r, g
    return out


def canon() -> pd.DataFrame:
    data = {r: _load_run(r) for r in RUNS}
    recs = []
    for kind, nm in sorted({k for r in data for k in data[r]}):
        if nm in OUT_OF_SCOPE:
            continue
        for month in ("7월", "8월"):
            c = [r for r in RUNS if r.startswith(month) and (kind, nm) in data[r]]
            if not c:
                continue
            run = c[0] if len(c) == 1 else ASSIGN[(month, nm)]
            r = data[run][(kind, nm)]
            recs.append(dict(구분=kind, 대상=nm, 월=month, 회차=run, 쌍=RUNS[run][0], 궤도=RUNS[run][1],
                             pct=float(r["Δ%"]), w25=float(r["2025수체km2"]), w26=float(r["2026수체km2"]),
                             lost=float(r["소실km2"]), new=float(r["신규km2"]), cov=float(r["커버"]),
                             how=str(r.get("임계산정", ""))))
    df = pd.DataFrame(recs)
    _check_canon(df)
    return df


def _check_canon(df: pd.DataFrame) -> None:
    """gee output/canon_table.txt(사람이 읽은 정본) 와 Δ% 를 칸마다 대조한다."""
    p = GEE / "canon_table.txt"
    if not p.exists():
        print("⚠ canon_table.txt 없음 — 대조 생략"); return
    n = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.startswith(("대권역", "댐유역")) or "|" not in line:
            continue
        left, *cells = line.split("|")
        kind, nm = left.split(None, 1)[0], left.split(None, 1)[1].strip()
        if nm in OUT_OF_SCOPE:
            continue
        for month, cell in zip(("7월", "8월"), cells):
            m = re.match(r"\s*(\d월[AB])\s+([+-]?\d+\.\d)", cell)
            if not m:
                continue
            row = df[(df.구분 == kind) & (df.대상 == nm) & (df.월 == month)].iloc[0]
            assert row.회차 == m.group(1) and abs(row.pct - float(m.group(2))) < 0.05, (kind, nm, month)
            n += 1
    print(f"정본 대조: canon_table.txt 와 {n}칸 일치")


def cget(cn: pd.DataFrame, nm: str, month: str, kind: str = "댐유역") -> pd.Series | None:
    s = cn[(cn.구분 == kind) & (cn.대상 == nm) & (cn.월 == month)]
    return None if s.empty else s.iloc[0]


# WAMIS 순위
REG = [("낙동강", "낙동강", "낙동강"), ("금강", "금 강", "금강"), ("섬진강", "섬진강", "섬진강"),
       ("영산강", "영산강", "영산강"), ("태화강", "태화강", "태화강"), ("낙동강남해", "낙동강남해", "낙동강남해"),
       ("섬진강남해", "섬진강남해", "섬진강남해"), ("만경·동진", "만경동진", "만경 · 동진"),
       ("낙동강동해", "낙동강동해", "낙동강동해"), ("탐진강", "탐진강", "탐진강"),
       ("회야·수영", "회야수영", "회야 · 수영"), ("형산강", "형산강", "형산강")]
NO_DAM = ["영산강남해", "금강서해", "영산강서해"]
# 근거 문서 §0-1 「권역 사건 판정」 — 재계산이 이와 같아야 한다
DOC_JUD = {"금강": (3.5, 1.5), "낙동강": (2.5, 2.0), "섬진강": (3.0, 2.0), "영산강": (3.0, 2.0),
           "태화강": (3.0, 3.0), "낙동강남해": (2.5, 3.0), "섬진강남해": (4.0, 2.5), "만경·동진": (4.0, 3.0),
           "낙동강동해": (5.0, 4.0), "탐진강": (4.0, 4.0), "회야·수영": (5.0, 8.0), "형산강": (7.0, 7.0)}


def ranks() -> pd.DataFrame:
    rk = pd.read_csv(RANK_CSV, encoding="utf-8-sig")
    rk["권역"] = rk["권역"].fillna("")
    return rk


def region_table(rk: pd.DataFrame) -> pd.DataFrame:
    ok = rk[~rk["댐"].str.contains("조정지")]          # 조정지 제외 (주암(조) 는 저류 댐이라 남긴다 — 문서 값과 같다)
    rows = []
    for lab, bb, wk in REG:
        g = ok[ok["권역"] == wk]
        rec = dict(권역=lab, bb=bb, n=len(g), dams="·".join(g["댐"]))
        for m in ("7월", "8월"):
            for y in ("2025", "2026"):
                rec[f"{m}{y}"] = float(g[f"{m}_{y}순위"].median())
        rows.append(rec)
    df = pd.DataFrame(rows).set_index("권역")
    for lab, (j, a) in DOC_JUD.items():
        assert (df.loc[lab, "7월2026"], df.loc[lab, "8월2026"]) == (j, a), lab
    print("권역 판정: 근거 문서 §0-1 표와 12권역 일치")
    return df


def judge(j: float, a: float) -> str:
    if j <= 3 and a <= 3:
        return "7·8월 가뭄"
    if a <= 3:
        return "8월 가뭄"
    if j <= 3:
        return "7월 가뭄"
    return "해당 없음 (평년 위)" if min(j, a) >= 6 else "해당 없음 (문턱 위)"


WAMIS_NAME = {"주암": "주암(본)", "부항": "김천부항"}


def dam_rank(rk: pd.DataFrame, nm: str) -> pd.Series | None:
    s = rk[rk["댐"] == WAMIS_NAME.get(nm, nm)]
    return None if s.empty else s.iloc[0]


def wamis_monthly(cache: Path) -> pd.DataFrame:
    """8개 저수지 7·8월 월평균 저수위 2017~2026. 없으면 WAMIS 에서 받는다(인증키 없음, 8080 HTTP)."""
    if not cache.exists():
        sys.path.insert(0, str(S1))
        from s1.tools.wamis.wamis_august_climatology import DAMS, monthly
        rows = []
        for name, cd in DAMS.items():
            for (y, mm), v in sorted(monthly(cd, ("07", "08"), spans=((2009, 2016), (2017, 2026))).items()):
                rows.append({"저수지": name, "코드": cd, "연": y, "월": int(mm), "월평균수위_m": v})
        cache.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(cache, index=False, encoding="utf-8-sig")
    return pd.read_csv(cache, encoding="utf-8-sig")


# 본문 8개 — 순서·이름·단계
DAMS8 = psf.DAMS
RES8 = psf.RESV
REGION8 = {"안동": "낙동강", "임하": "낙동강", "밀양": "낙동강", "영천": "낙동강", "성덕": "낙동강",
           "운문": "낙동강", "섬진강": "섬진강", "평림": "영산강"}
STAGE = psf.STAGE                       # 8월 가뭄 예·경보(행안부 8.10 발표) — 원문 대조 완료(10-15)
STAGE_ENTRY = {"운문": "07-15", "안동": "07-08", "임하": "07-08", "성덕": "07-18", "밀양": "08-02",
               "평림": "08-02"}         # 기후부 보도참고자료 원문(E:/…/기후에너지환경부 보도자료) 날짜
SMALL_DKM2 = psf.SMALL_DKM2             # 성덕 −0.25 · 평림 −0.03 (Δ% 에서 되돌린 값, 근거 문서 ② 규칙)


# ════════════════════════ 그림 ════════════════════════
RES_LABEL = {"안동호": "안동호", "임하호": "임하호", "밀양호": "밀양호", "영천호": "영천호",
             "성덕저수지": "성덕저수지", "운문호": "운문호", "옥정호": "옥정호(섬진강댐)", "평림호": "평림호"}


def fig1(mon: pd.DataFrame, reg: pd.DataFrame, out: Path) -> None:
    fig = plt.figure(figsize=(14.8, 7.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.25, 1.0], wspace=0.42, left=0.15, right=0.985,
                          top=0.86, bottom=0.12)
    ax = fig.add_subplot(gs[0, 0])
    aug = mon[(mon.월 == 8) & (mon.연 >= 2017)]
    order = list(RES_LABEL)
    for i, res in enumerate(order):
        yi = len(order) - 1 - i
        s = aug[aug.저수지 == res].set_index("연")["월평균수위_m"]
        med = s.median()
        a = s - med
        rk = s.rank(method="min").astype(int)
        others = a.drop([2025, 2026])
        ax.plot([a.min(), a.max()], [yi, yi], color="#cfcfcf", lw=1.2, zorder=1)
        ax.scatter(others, [yi] * len(others), s=46, color="#9a9a9a", edgecolor="white", lw=0.8, zorder=2)
        ax.scatter([a[2025]], [yi], s=120, color=C_25, edgecolor="white", lw=1.4, zorder=3)
        ax.scatter([a[2026]], [yi], s=150, marker="s", color=C_26, edgecolor="white", lw=1.4, zorder=4)
        ax.text(a[2026] - 0.55, yi, f"{rk[2026]}위", ha="right", va="center", fontsize=FS - 2, color=C_26,
                fontweight="bold")
        ax.text(a[2025], yi + 0.22, f"{rk[2025]}위", ha="center", va="bottom", fontsize=FS - 5, color=C_25)
    ax.axvline(0, color="#777777", lw=1.0, ls=(0, (3, 3)), zorder=0)
    ax.text(0.3, len(order) - 0.35, "10년 중앙값", fontsize=FS - 4, color=C_MUTED, va="bottom")
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f"{RES_LABEL[r]}" for r in order][::-1], color=C_INK, fontsize=FS - 1)
    ax.set_ylim(-0.6, len(order) - 0.2)
    ax.set_xlim(-21.5, 6.5)
    ax.set_xticks([-20, -15, -10, -5, 0, 5])
    ax.set_xticklabels([str(v).replace("-", M) for v in (-20, -15, -10, -5, 0, 5)])
    ax.set_xlabel("8월 평균 저수위 − 10년(2017~2026) 중앙값 (m)", color=C_MUTED)
    ax.grid(axis="x", color=C_GRID, lw=0.8); ax.set_axisbelow(True)
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title("(a) 8월 평균 저수위 — 10년 중 위치 (1위 = 최저)", loc="left", fontweight="bold", pad=34)
    ax.legend(handles=[Line2D([], [], marker="s", ls="", ms=11, color=C_26),
                       Line2D([], [], marker="o", ls="", ms=10, color=C_25),
                       Line2D([], [], marker="o", ls="", ms=8, color="#9a9a9a")],
              labels=["2026", "2025 (전년도)", "2017~2024"], loc="lower left", ncol=3,
              bbox_to_anchor=(-0.02, 1.0), handletextpad=0.2, columnspacing=1.0, fontsize=FS - 2)

    # (b) 권역 순위 중앙값 히트맵
    bx = fig.add_subplot(gs[0, 1])
    cols = [("7월2025", "2025\n7월"), ("7월2026", "2026\n7월"), ("8월2025", "2025\n8월"), ("8월2026", "2026\n8월")]
    labs = list(reg.index)
    cmap = ListedColormap(["#a63603", "#f16913", "#fdd0a2", "#eef3f9", "#9ecae1", "#3a7dbf"])
    norm = BoundaryNorm([0.5, 2.25, 3.25, 5.25, 6.25, 8.25, 10.5], cmap.N)
    for i, lab in enumerate(labs):
        for j, (c, _) in enumerate(cols):
            v = reg.loc[lab, c]
            x0 = j + (0.25 if j >= 2 else 0)
            bx.add_patch(Rectangle((x0, i), 1, 1, color=cmap(norm(v)), ec="white", lw=1.5))
            dark = v <= 2.25 or v >= 8.25
            bx.text(x0 + 0.5, i + 0.5, f"{v:g}", ha="center", va="center", fontsize=FS - 3,
                    color="white" if dark else C_INK, fontweight="bold" if (v <= 3 and "2026" in c) else "normal")
            if v <= 3 and "2026" in c:
                bx.add_patch(Rectangle((x0 + 0.04, i + 0.04), 0.92, 0.92, fill=False, ec=C_INK, lw=1.6))
    bx.set_xlim(0, 4.25); bx.set_ylim(len(labs), 0)
    bx.set_xticks([0.5, 1.5, 2.75, 3.75]); bx.set_xticklabels([c[1] for c in cols], fontsize=FS - 3)
    bx.xaxis.tick_top()
    bx.set_yticks(np.arange(len(labs)) + 0.5)
    bx.set_yticklabels([f"{lab} ({int(reg.loc[lab, 'n'])})" for lab in labs], fontsize=FS - 2, color=C_INK)
    bx.tick_params(length=0)
    for s_ in bx.spines.values():
        s_.set_visible(False)
    bx.axhline(4, color=C_MUTED, lw=1.0, ls=(0, (2, 2)))
    bx.set_title("(b) 남부 권역 — 대표 댐 순위 중앙값", loc="left", fontweight="bold", pad=10)
    bx.text(0, len(labs) + 0.35, "굵은 테 = 중앙 ≤3위(10년 하위 30%) → 그 달 권역 가뭄\n괄호 = 대표 댐 수(조정지 제외)",
            fontsize=FS - 5, color=C_MUTED, va="top", ha="left")
    fig.savefig(out, facecolor="white"); plt.close(fig)


DCOL = ListedColormap(["#7f2704", "#a63603", "#d94801", "#f16913", "#fd8d3c", "#fdd0a2",
                       "#c6dbef", "#6baed6", "#2171b5"])
DBND = [-50, -25, -20, -15, -10, -5, 0, 5, 10, 20]
RCOL = ListedColormap(["#a63603", "#fd8d3c", "#fdd0a2", "#c6dbef"])
RBND = [0.5, 2.25, 3.25, 5.75, 10.5]


def _spread(items: list, ymin: float, ymax: float, dy: float) -> list:
    """(이름, cx, cy) 를 cy 내림차순으로 놓고 겹치지 않게 라벨 y 를 아래로 민다."""
    items = sorted(items, key=lambda t: -t[2])
    ys, last = [], ymax + dy
    for _, _, cy in items:
        y = min(cy, last - dy)
        ys.append(y); last = y
    shift = max(0.0, ymin - ys[-1]) if ys else 0.0
    return [(it[0], it[1], it[2], y + shift) for it, y in zip(items, ys)]


def fig2(cn: pd.DataFrame, reg: pd.DataFrame, rk: pd.DataFrame, out: Path) -> None:
    import geopandas as gpd
    bb = gpd.read_file(psf.SHP_BBSN).to_crs(5179)
    dm = gpd.read_file(psf.SHP_DAM).to_crs(5179)
    south_nm = [r[1] for r in REG] + NO_DAM
    south = bb[bb["BBSNNM"].isin(south_nm)].copy()
    other = bb[~bb["BBSNNM"].isin(south_nm) & (bb["BBSNNM"] != "제주도")]
    bb2lab = {r[1]: r[0] for r in REG}
    south["rank"] = south["BBSNNM"].map(lambda n: reg.loc[bb2lab[n], "8월2026"] if n in bb2lab else np.nan)
    aug = cn[(cn.구분 == "댐유역") & (cn.월 == "8월")].set_index("대상")
    dm = dm[dm["damname"].isin(aug.index)].copy()
    dm["pct"] = dm["damname"].map(aug["pct"])
    dm["area"] = dm.area
    dm = dm.sort_values("area", ascending=False)
    parts = south.explode(index_parts=False)
    x0, y0, x1, y1 = parts[parts.geometry.centroid.x < 1_250_000].total_bounds   # 울릉·독도 제외한 범위
    padw, pade = 150_000, 150_000

    fig = plt.figure(figsize=(14.8, 7.0))
    gs = fig.add_gridspec(1, 2, wspace=0.02, left=0.0, right=1.0, top=0.93, bottom=0.15)
    axs = [fig.add_subplot(gs[0, i]) for i in range(2)]
    for ax in axs:
        other.plot(ax=ax, color="#f3f3f3", edgecolor="#d6d6d6", lw=0.5)
        ax.set_xlim(x0 - padw, x1 + pade); ax.set_ylim(y0 - 10_000, y1 + 15_000)
        ax.set_aspect("equal"); ax.set_axis_off()

    # (a) 권역 판정
    ax = axs[0]
    rnorm = BoundaryNorm(RBND, RCOL.N)
    has = south[south["rank"].notna()]
    has.plot(ax=ax, color=[RCOL(rnorm(v)) for v in has["rank"]], edgecolor="white", lw=0.8)
    south[south["rank"].isna()].plot(ax=ax, facecolor="#ececec", edgecolor="#b5b5b5", lw=0.5, hatch="///")
    south.boundary.plot(ax=ax, color="#8a8a8a", lw=0.5)
    items = []
    for _, r in south.iterrows():
        cx, cy = r.geometry.representative_point().coords[0]
        items.append((r["BBSNNM"], cx, cy))
    east = [t for t in items if t[1] > 1_080_000]
    west = [t for t in items if t[1] <= 1_080_000]
    dy = (y1 - y0) / 15
    for grp, xl, ha in ((east, x1 + 18_000, "left"), (west, x0 - 18_000, "right")):
        for nm, cx, cy, ly in _spread(grp, y0 + 20_000, y1 - 10_000, dy):
            lab = bb2lab.get(nm, nm)
            txt = f"{lab} {reg.loc[lab, '8월2026']:g}" if nm in bb2lab else f"{nm} ⓓ"
            bold = nm in bb2lab and reg.loc[lab, "8월2026"] <= 3
            ax.annotate(txt, xy=(cx, cy), xytext=(xl, ly), ha=ha, va="center", fontsize=FS - 4,
                        color=C_INK if nm in bb2lab else C_MUTED, fontweight="bold" if bold else "normal",
                        arrowprops=dict(arrowstyle="-", color="#9a9a9a", lw=0.6, shrinkA=1, shrinkB=0))
    ax.set_title("(a) WAMIS 권역 판정 — 2026년 8월 대표 댐 저수위 순위 중앙값", loc="left",
                 fontweight="bold", fontsize=FS)
    ax.legend(handles=[Patch(color=RCOL(i)) for i in range(4)] + [Patch(fc="#ececec", hatch="///", ec="#9a9a9a")],
              labels=["≤2위", "2.5~3위 (가뭄 문턱)", "3.5~5.5위", "≥6위 (평년 위)", "대표 댐 없음 ⓓ"],
              loc="upper left", bbox_to_anchor=(0.0, -0.005), ncol=3, fontsize=FS - 4, handlelength=1.2,
              columnspacing=1.0)

    # (b) SAR 댐유역 8월 Δ%
    ax = axs[1]
    south.plot(ax=ax, color="#eef1f5", edgecolor="#b9c3d1", lw=0.6)
    big4 = bb[bb["BBSNCD"].astype(int).isin([20, 30, 40, 50])]
    big4.boundary.plot(ax=ax, color=C_NAVY, lw=1.1)
    dnorm = BoundaryNorm(DBND, DCOL.N)
    dm.plot(ax=ax, color=[DCOL(dnorm(v)) for v in dm["pct"]], edgecolor="#555555", lw=0.5)
    main = dm[dm["damname"].isin(DAMS8)]
    main.boundary.plot(ax=ax, color="#111111", lw=1.6)
    show = DAMS8 + ["용담", "대청", "영주", "안계"]
    note = {"대청": " (변화 없음)", "영주": " ⓐ", "안계": " ⓐⓒ", "평림": "†", "성덕": "†"}
    items = []
    for _, r in dm[dm["damname"].isin(show)].iterrows():
        cx, cy = r.geometry.representative_point().coords[0]
        items.append((r["damname"], cx, cy))
    east = [t for t in items if t[1] > 1_060_000]
    west = [t for t in items if t[1] <= 1_060_000]
    for grp, xl, ha in ((east, x1 + 18_000, "left"), (west, x0 - 18_000, "right")):
        for nm, cx, cy, ly in _spread(grp, y0 + 20_000, y1 - 10_000, (y1 - y0) / 12):
            v = aug.loc[nm, "pct"]
            ax.annotate(f"{nm} {f1(v)}{note.get(nm, '')}", xy=(cx, cy), xytext=(xl, ly), ha=ha, va="center",
                        fontsize=FS - 3 if nm in DAMS8 else FS - 4,
                        color=C_INK if nm in DAMS8 else C_MUTED, fontweight="bold" if nm in DAMS8 else "normal",
                        arrowprops=dict(arrowstyle="-", color="#777777", lw=0.7, shrinkA=1, shrinkB=0))
    ax.set_title("(b) SAR 댐유역 수체 면적 Δ% — 2025→2026 8월", loc="left", fontweight="bold", fontsize=FS)
    cax = fig.add_axes([0.56, 0.085, 0.40, 0.025])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=dnorm, cmap=DCOL), cax=cax, orientation="horizontal")
    cb.set_ticks(DBND); cb.set_ticklabels([str(b).replace("-", M) for b in DBND])
    cb.outline.set_visible(False); cb.ax.tick_params(labelsize=FS - 5, length=0)
    cb.set_label("Δ% (굵은 테 = 본문 8개 댐유역)", fontsize=FS - 4, color=C_MUTED)
    fig.savefig(out, facecolor="white"); plt.close(fig)


PAIRS = [("7월A", 54, "20250725", "20260715", "main"), ("7월B", 134, "20250718", "20260720", "main"),
         ("8월A", 54, "20250806", "20260802", "main"), ("8월B", 127, "20250811", "20260807", "main"),
         ("민감도", 134, "20250811", "20260813", "sens"), ("민감도", 134, "20250811", "20260825", "sens"),
         ("민감도", 134, "20250823", "20260813", "sens"), ("민감도", 134, "20250823", "20260825", "sens"),
         ("건조 대조", 54, "20250812", "20260802", "dry")]
LANES = [(54, "ASC54"), (134, "DESC134"), (127, "ASC127")]
SAT_MK = {"S1A": "^", "S1C": "o", "S1D": "s"}
BASINS5 = ["한강", "금강", "낙동강", "섬진강", "영산강"]
PAIR_BASINS = {"7월A": ["낙동강"], "8월A": ["낙동강"], "건조 대조": ["낙동강"], "7월B": ["섬진강", "영산강"],
               "8월B": ["섬진강", "영산강"], "민감도": ["낙동강", "섬진강", "영산강"]}


def fig6(rain: pd.DataFrame, out: Path) -> None:
    def X(d: str) -> int:
        return (date(2000, int(d[4:6]), int(d[6:8])) - date(2000, 7, 1)).days

    lane_y = {}
    for i, (rel, _) in enumerate(LANES):
        lane_y[(rel, "2025")] = -i * 2.7
        lane_y[(rel, "2026")] = -i * 2.7 - 1.0
    fig, ax = plt.subplots(figsize=(14.8, 6.4))
    fig.subplots_adjust(left=0.13, right=0.985, top=0.83, bottom=0.11)
    for (rel, yr), y in lane_y.items():
        ax.plot([0, 61], [y, y], color="#e3e3e3", lw=1.0, zorder=0)
    used = {(p[1], p[2]) for p in PAIRS} | {(p[1], p[3]) for p in PAIRS}
    style = {"main": dict(color=C_AUG, lw=3.0, ls="-", alpha=0.9), "sens": dict(color=C_NAVY, lw=1.3, ls=(0, (4, 2)), alpha=0.8),
             "dry": dict(color="#555555", lw=1.6, ls=(0, (1, 1.5)), alpha=0.9)}
    labeled = set()
    for lab, rel, d25, d26, kind in PAIRS:
        xa, ya, xb, yb = X(d25), lane_y[(rel, "2025")], X(d26), lane_y[(rel, "2026")]
        ax.plot([xa, xb], [ya, yb], zorder=1, **style[kind])
        if lab not in labeled:
            labeled.add(lab)
            tx, ty = (xa + xb) / 2, (ya + yb) / 2
            off = {"7월A": (-1.2, 0), "7월B": (-1.6, 0), "8월A": (0.9, 0), "8월B": (0.9, 0),
                   "민감도": (6.2, 0.05), "건조 대조": (3.4, -0.05)}[lab]
            ax.text(tx + off[0], ty + off[1], lab, ha="center", va="center", fontsize=FS - 3,
                    color=style[kind]["color"], fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.9), zorder=5)
    # 쓰인 관측은 「그 쌍의 대상 권역」 강우만 본다 (다른 권역의 비를 붙이지 않는다)
    obs_basins: dict = {}
    for lab, rel, d25, d26, _ in PAIRS:
        for d in (d25, d26):
            obs_basins.setdefault((rel, d), set()).update(PAIR_BASINS[lab])
    for _, r in rain.iterrows():
        d, rel = str(r["date"]), int(r["rel"])
        yr = d[:4]
        if (rel, yr) not in lane_y:
            continue
        u = (rel, d) in used
        bs = obs_basins.get((rel, d), BASINS5)
        vals = [r[b] for b in bs if pd.notna(r[b])]
        mx = max(vals) if vals else np.nan
        wet = (mx >= 50) if u else (isinstance(r["wet"], str) and r["wet"].strip() != "")
        ax.scatter([X(d)], [lane_y[(rel, yr)]], s=150 if u else 60, marker=SAT_MK[r["sat"]],
                   facecolor="#6baed6" if wet else "white", edgecolor=C_INK if u else "#9a9a9a",
                   lw=1.6 if u else 0.9, zorder=3)
        if u and np.isfinite(mx):
            ax.text(X(d), lane_y[(rel, yr)] + 0.30, f"{mx:.0f}", ha="center", va="bottom", fontsize=FS - 6,
                    color="#2171b5" if wet else C_MUTED, zorder=4)
    ax.set_yticks([lane_y[k] for k in lane_y])
    ax.set_yticklabels([f"{lab}  {yr}" for rel, lab in LANES for yr in ("2025", "2026")], fontsize=FS - 2)
    ax.tick_params(axis="y", length=0)
    ticks = [0, 14, 31, 45, 61]
    ax.set_xticks(ticks); ax.set_xticklabels(["7/1", "7/15", "8/1", "8/15", "8/31"])
    ax.set_xlim(-1, 62); ax.set_ylim(lane_y[(127, "2026")] - 0.7, 0.9)
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.grid(axis="x", color=C_GRID, lw=0.8); ax.set_axisbelow(True)
    ax.set_xlabel("촬영일 (UTC, 두 해를 같은 달력에 겹침) · 숫자 = 대상 권역 직전 5일 강우(권역 중앙값, mm)", color=C_MUTED)
    ax.legend(handles=[Line2D([], [], color=C_AUG, lw=3), Line2D([], [], color=C_NAVY, lw=1.3, ls=(0, (4, 2))),
                       Line2D([], [], color="#555555", lw=1.6, ls=(0, (1, 1.5))),
                       Line2D([], [], marker="o", ls="", ms=10, mfc="white", mec=C_INK),
                       Line2D([], [], marker="s", ls="", ms=9, mfc="white", mec=C_INK),
                       Line2D([], [], marker="^", ls="", ms=10, mfc="white", mec=C_INK),
                       Line2D([], [], marker="o", ls="", ms=10, mfc="#6baed6", mec=C_INK)],
              labels=["본쌍 (7월 S1C↔S1C · 8월 S1C↔S1D)", "민감도 4쌍 (S1C↔S1C)", "건조 대조 (저수지)",
                      "S1C", "S1D", "S1A", "직전 5일 ≥50 mm"],
              loc="lower left", bbox_to_anchor=(-0.12, 1.02), ncol=4, fontsize=FS - 4, handlelength=1.8,
              columnspacing=1.0, handletextpad=0.4)
    fig.savefig(out, facecolor="white"); plt.close(fig)


def fig7(cn: pd.DataFrame, out: Path) -> None:
    sw = pd.read_csv(WAMIS_DIR / "sar_vs_wamis_v11.csv", encoding="utf-8-sig")
    dry = pd.read_csv(GEE / "watershed_change_v11_aug_a_dry0812.csv", encoding="utf-8-sig").set_index("대상")
    dams = ["안동", "임하", "영천", "성덕", "밀양", "운문"]
    wet12 = {"밀양", "운문"}                                       # 0812 도 54~82 mm — 건조 대조가 아니다
    fig = plt.figure(figsize=(14.8, 5.9))
    gs = fig.add_gridspec(1, 2, wspace=0.28, left=0.09, right=0.985, top=0.84, bottom=0.15)
    panels = []
    for res_or_dam, src in (("res", None), ("bas", None)):
        rows = []
        for d in dams:
            if res_or_dam == "res":
                s = sw[sw.저수지 == RES8[d]].set_index("월")["SAR_dA_pct"]
                rows.append((d, s["8월"], s["8월 0812→0802 건조대조"]))
            else:
                rows.append((d, cget(cn, d, "8월").pct, float(dry.loc[d, "Δ%"])))
        panels.append(rows)
    titles = ["(a) 저수지 폴리곤 — 차 ≤1.0%p", "(b) 댐유역 — 최대 6.2%p (안동·임하)"]
    for k, rows in enumerate(panels):
        ax = fig.add_subplot(gs[0, k])
        for i, (d, a, b) in enumerate(rows):
            yi = len(rows) - 1 - i
            grey = k == 1 and d in wet12
            ax.plot([a, b], [yi, yi], color="#c9c9c9", lw=2.4, zorder=1)
            ax.scatter([a], [yi], s=120, marker="s", color="#cccccc" if grey else C_AUG, edgecolor="white", lw=1.3, zorder=3)
            ax.scatter([b], [yi], s=95, marker="o", facecolor="white", edgecolor="#bbbbbb" if grey else C_NAVY,
                       lw=1.6, zorder=4)
            ax.text(max(a, b) + 1.0, yi, f"{f1(b - a)}%p" + ("  (0812도 젖음)" if grey else ""), va="center",
                    fontsize=FS - 4, color=C_MUTED if grey else C_INK)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([RES8[d] if k == 0 else d for d, _, _ in rows][::-1], fontsize=FS - 2)
        ax.set_xlim(-30, 8)
        ax.set_xticks([-30, -20, -10, 0])
        ax.set_xticklabels([str(v).replace("-", M) for v in (-30, -20, -10, 0)])
        ax.set_xlabel("SAR 수체 면적 Δ% (8월A, 2026 = 08-02 고정)", color=C_MUTED)
        ax.grid(axis="x", color=C_GRID, lw=0.8); ax.set_axisbelow(True)
        for s_ in ("top", "right", "left"):
            ax.spines[s_].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.set_title(titles[k], loc="left", fontweight="bold")
    fig.legend(handles=[Line2D([], [], marker="s", ls="", ms=11, color=C_AUG),
                        Line2D([], [], marker="o", ls="", ms=10, mfc="white", mec=C_NAVY, mew=1.6)],
               labels=["본쌍 2025-08-06 (직전 5일 낙동강 102 mm)", "건조 대조 2025-08-12 (33 mm)"],
               loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=FS - 2)
    fig.savefig(out, facecolor="white"); plt.close(fig)


# ════════════════════════ 표 ════════════════════════
@dataclass
class Tbl:
    key: str
    caption: str
    header: list
    rows: list                        # list[list[str]] | str(구역 제목 줄)
    notes: list = field(default_factory=list)
    align: list | None = None         # 'l' | 'c'
    cell: dict = field(default_factory=dict)   # (r, c) → {'bold','color','bg'};  (r, None) = 그 줄 전체
    sep: list = field(default_factory=list)     # 이 줄 뒤에 굵은 선


def _style(t: Tbl, r: int, c: int) -> dict:
    st = dict(t.cell.get((r, None), {}))
    st.update(t.cell.get((r, c), {}))
    return st


# ── PNG
_MFIG = None


def _tw(s: str, fs: float, bold: bool = False) -> float:
    global _MFIG
    if _MFIG is None:
        _MFIG = plt.figure(dpi=72)
    t = _MFIG.text(0, 0, s, fontsize=fs, fontweight="bold" if bold else "normal")
    w = t.get_window_extent(_MFIG.canvas.get_renderer()).width
    t.remove()
    return w


def _wrap(s: str, width: float, fs: float) -> list:
    out, cur = [], ""
    for tok in s.split(" "):
        cand = (cur + " " + tok) if cur else tok
        if _tw(cand, fs) <= width or not cur:
            cur = cand
        else:
            out.append(cur); cur = tok
    if cur:
        out.append(cur)
    return out


def render_png(t: Tbl, out: Path, fs: float = 11.0) -> list:
    hfs, pad, lh = fs + 0.5, 7.0, fs * 1.32
    ncol = len(t.header)
    al = t.align or (["l"] + ["c"] * (ncol - 1))
    widths = [_tw(h, hfs, True) for h in t.header]
    for r in t.rows:
        if isinstance(r, str):
            continue
        for c, v in enumerate(r):
            widths[c] = max(widths[c], _tw(str(v), fs, True))
    widths = [w + 2 * pad for w in widths]
    W = sum(widths)
    hh = max(h.count("\n") + 1 for h in t.header) * lh + 2 * pad
    rh = [((1 if isinstance(r, str) else max(str(v).count("\n") + 1 for v in r)) * lh + 1.3 * pad) for r in t.rows]
    cap = _wrap(t.caption, W, fs + 1.5)
    notes = [ln for n in t.notes for ln in _wrap(n, W, fs - 1.5)]
    capH = len(cap) * (fs + 1.5) * 1.35 + 6
    notesH = len(notes) * (fs - 1.5) * 1.38 + (8 if notes else 0)
    H = capH + hh + sum(rh) + notesH + 6
    m = 6.0
    fig = plt.figure(figsize=((W + 2 * m) / 72, (H + 2 * m) / 72))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(-m, W + m); ax.set_ylim(H + m, -m); ax.axis("off")
    y = 0.0
    for ln in cap:
        ax.text(0, y, ln, fontsize=fs + 1.5, fontweight="bold", va="top", color=C_INK)
        y += (fs + 1.5) * 1.35
    y += 6
    ax.add_patch(Rectangle((0, y), W, hh, color=C_NAVY, lw=0))
    x = 0.0
    for c, h in enumerate(t.header):
        ax.text(x + widths[c] / 2, y + hh / 2, h, fontsize=hfs, fontweight="bold", color="white",
                ha="center", va="center", linespacing=1.15)
        x += widths[c]
    y += hh
    body = 0
    for i, r in enumerate(t.rows):
        h = rh[i]
        if isinstance(r, str):
            st = _style(t, i, 0)
            ax.add_patch(Rectangle((0, y), W, h, color=st.get("bg", "#e4e9f1"), lw=0))
            ax.text(pad, y + h / 2, r, fontsize=fs, fontweight="bold", color=st.get("color", C_NAVY), va="center")
            body = 0
        else:
            bg = "#f4f7fb" if body % 2 else "white"
            st_row = t.cell.get((i, None), {})
            ax.add_patch(Rectangle((0, y), W, h, color=st_row.get("bg", bg), lw=0))
            x = 0.0
            for c, v in enumerate(r):
                st = _style(t, i, c)
                if "bg" in st and (i, c) in t.cell:
                    ax.add_patch(Rectangle((x, y), widths[c], h, color=st["bg"], lw=0))
                xa = x + (pad if al[c] == "l" else widths[c] / 2)
                ax.text(xa, y + h / 2, str(v), fontsize=fs, ha="left" if al[c] == "l" else "center", va="center",
                        fontweight="bold" if st.get("bold") else "normal", color=st.get("color", C_INK),
                        linespacing=1.15)
                x += widths[c]
            body += 1
        y += h
        ax.plot([0, W], [y, y], color="#7a8796" if i in t.sep else "#d5dbe3", lw=1.3 if i in t.sep else 0.6)
    ax.plot([0, W], [y, y], color=C_NAVY, lw=1.4)
    y += 8
    for ln in notes:
        ax.text(0, y, ln, fontsize=fs - 1.5, va="top", color=C_MUTED)
        y += (fs - 1.5) * 1.38
    fig.savefig(out, dpi=300, facecolor="white"); plt.close(fig)
    return widths


# ── XLSX
def write_xlsx(tbls: list, path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    wb = Workbook(); wb.remove(wb.active)
    thin = Side(style="thin", color="D5DBE3")
    for t in tbls:
        ws = wb.create_sheet(t.key.split("_")[0])
        ncol = len(t.header)
        ws.cell(1, 1, t.caption).font = Font(bold=True, size=12)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
        for c, h in enumerate(t.header, 1):
            cl = ws.cell(2, c, h.replace("\n", " "))
            cl.font = Font(bold=True, color="FFFFFF"); cl.fill = PatternFill("solid", fgColor="00478B")
            cl.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for i, r in enumerate(t.rows):
            rr = 3 + i
            if isinstance(r, str):
                cl = ws.cell(rr, 1, r); cl.font = Font(bold=True, color="00478B")
                cl.fill = PatternFill("solid", fgColor="E4E9F1")
                ws.merge_cells(start_row=rr, start_column=1, end_row=rr, end_column=ncol)
                continue
            for c, v in enumerate(r, 1):
                st = _style(t, i, c - 1)
                cl = ws.cell(rr, c, str(v).replace("\n", " "))
                cl.font = Font(bold=bool(st.get("bold")), color=st.get("color", "#222222").lstrip("#").upper())
                if "bg" in st:
                    cl.fill = PatternFill("solid", fgColor=st["bg"].lstrip("#").upper())
                al = t.align or (["l"] + ["c"] * (ncol - 1))
                cl.alignment = Alignment(horizontal="left" if al[c - 1] == "l" else "center",
                                         vertical="center", wrap_text=True)
                cl.border = Border(bottom=thin)
        rr = 3 + len(t.rows) + 1
        for n in t.notes:
            ws.cell(rr, 1, n).font = Font(size=9, color="666666"); rr += 1
        for c in range(1, ncol + 1):
            col = [len(t.header[c - 1])] + [len(str(r[c - 1])) for r in t.rows if not isinstance(r, str)]
            ws.column_dimensions[ws.cell(2, c).column_letter].width = min(46, max(8, 1.6 * max(col) + 2))
        ws.freeze_panes = "A3"
    wb.save(path)


# ── PPTX (포스터와 같은 A0 세로 · 머리 22 pt · 본문 20 pt 굵게 · 맑은 고딕)
def write_pptx(tbls: list, widths_png: dict, path: Path) -> None:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.oxml.ns import qn
    from pptx.util import Cm, Emu, Pt

    def setfont(run, size, bold, color):
        f = run.font
        f.size, f.bold, f.name = Pt(size), bold, "맑은 고딕"
        f.color.rgb = RGBColor.from_string(color.lstrip("#").upper())
        rpr = run._r.get_or_add_rPr()
        ea = rpr.find(qn("a:ea"))
        if ea is None:
            ea = rpr.makeelement(qn("a:ea"), {}); rpr.append(ea)
        ea.set("typeface", "맑은 고딕")

    prs = Presentation()
    prs.slide_width, prs.slide_height = Cm(84.1), Cm(118.9)
    blank = prs.slide_layouts[6]
    scale = 20.0 / 11.0                                 # PNG 본문 11 pt → pptx 20 pt
    for t in tbls:
        s = prs.slides.add_slide(blank)
        left, top = Cm(4.0), Cm(4.0)
        wpt = [w * scale for w in widths_png[t.key]]
        Wtot = int(sum(wpt) * 12700)
        tb = s.shapes.add_textbox(left, top, Wtot, Cm(1.6))
        tf = tb.text_frame; tf.word_wrap = True
        setfont(tf.paragraphs[0].add_run(), 22, True, C_INK)
        tf.paragraphs[0].runs[0].text = t.caption
        nrow = 1 + len(t.rows)
        gt = s.shapes.add_table(nrow, len(t.header), left, top + Cm(2.2), Wtot, Cm(1.3 * nrow))
        tab = gt.table
        tab.first_row = True
        for c, w in enumerate(wpt):
            tab.columns[c].width = Emu(int(w * 12700))
        al = t.align or (["l"] + ["c"] * (len(t.header) - 1))

        def fill(cell, text, size, bold, color, bg, align):
            cell.margin_left = cell.margin_right = Cm(0.15)
            cell.margin_top = cell.margin_bottom = Cm(0.05)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid(); cell.fill.fore_color.rgb = RGBColor.from_string(bg.lstrip("#").upper())
            tf = cell.text_frame; tf.word_wrap = True
            lines = str(text).split("\n")
            for k, ln in enumerate(lines):
                p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                p.alignment = PP_ALIGN.LEFT if align == "l" else PP_ALIGN.CENTER
                r = p.add_run(); r.text = ln
                setfont(r, size, bold, color)

        for c, h in enumerate(t.header):
            fill(tab.cell(0, c), h, 22, True, "#FFFFFF", C_NAVY, "c")
        body = 0
        for i, r in enumerate(t.rows):
            rr = i + 1
            if isinstance(r, str):
                st = _style(t, i, 0)
                a = tab.cell(rr, 0)
                a.merge(tab.cell(rr, len(t.header) - 1))
                fill(a, r, 20, True, st.get("color", C_NAVY), st.get("bg", "#E4E9F1"), "l")
                body = 0
                continue
            row_bg = t.cell.get((i, None), {}).get("bg", "#F4F7FB" if body % 2 else "#FFFFFF")
            for c, v in enumerate(r):
                st = _style(t, i, c)
                fill(tab.cell(rr, c), v, 20, True, st.get("color", C_INK),
                     st["bg"] if ((i, c) in t.cell and "bg" in st) else row_bg, al[c])
            body += 1
        if t.notes:
            nt = s.shapes.add_textbox(left, top + Cm(2.4 + 1.25 * nrow), Wtot, Cm(1.0 * len(t.notes)))
            ntf = nt.text_frame; ntf.word_wrap = True
            for k, n in enumerate(t.notes):
                p = ntf.paragraphs[0] if k == 0 else ntf.add_paragraph()
                r = p.add_run(); r.text = n
                setfont(r, 16, False, "#555555")
    prs.save(path)


# ════════════════════════ 표 내용 ════════════════════════
HI = {"bold": True, "color": C_HI}
B = {"bold": True}
GREY = {"color": "#8a8a8a"}
SUM = {"bg": "#fff1e6", "bold": True}


def kst(t: str) -> str:
    """'2025072518' → '07-25 18시' (WAMIS 시자료는 KST)."""
    t = str(t)
    return f"{t[4:6]}-{t[6:8]} {int(t[8:10])}시"


def build_tables(cn, rk, reg, mon, sw, swsens, sens) -> list:
    T = []
    # 표1 ─ 본문 8개
    rows, cell = [], {}
    for i, d in enumerate(DAMS8):
        j, a = cget(cn, d, "7월"), cget(cn, d, "8월")
        rr = dam_rank(rk, d)
        sv = sw[(sw.저수지 == RES8[d]) & (sw.월 == "8월")].iloc[0]
        dk = SMALL_DKM2.get(d, a.w26 - a.w25)
        foot = []
        if d == "안동": foot.append("ⓒ")
        if rr["8월_2025순위"] >= 8: foot.append("ⓑ")
        if d in SMALL_DKM2: foot.append("†")
        if d == "평림": foot.append("ⓕ")
        rows.append([REGION8[d], f"{d} ({RES8[d]})",
                     STAGE[d], f"{int(rr['8월_2025순위'])} → {int(rr['8월_2026순위'])}",
                     "제외 ⓕ" if d == "평림" else f1(j.pct), f1(a.pct),
                     f"{a.w25:.2f} → {a.w26:.2f} ({f2(dk, True)})", f1(sv.SAR_dA_pct), f1(sv.WAMIS_dV_pct),
                     f"{sv.k_eff:.2f}", " ".join(foot) or "—"])
        cell[(i, 5)] = HI
        if STAGE[d] in ("심각", "경계"):
            cell[(i, 2)] = B
        if rr["8월_2026순위"] <= 2:
            cell[(i, 3)] = B
        if d == "평림":
            cell[(i, 4)] = GREY
    rows.append(["범위", "8곳", "8/8 발령", "7/8곳 1·2위", f"{M}12.7~{M}26.7 (7/8)", f"{M}4.7~{M}27.7 (8/8)", "", "",
                 "", "8/8 > 1", ""])
    cell[(8, None)] = SUM
    T.append(Tbl("표1_본문8개댐유역_핵심결과",
                 "Table 1. 본문 8개 댐유역 — 공식 단계·WAMIS 순위와 SAR 수체 면적 변화(2025→2026, v11)",
                 ["권역", "댐유역\n(저수지)", "8월 가뭄\n예·경보", "WAMIS 8월 순위\n2025 → 2026", "SAR 유역\n7월 Δ%",
                  "SAR 유역\n8월 Δ%", "8월 유역 수체 km²\n2025 → 2026 (Δkm²)", "저수지 SAR\n8월 Δ%",
                  "WAMIS 저수량\n8월 Δ%", "k_eff\n(저수량÷면적)", "각주"],
                 rows,
                 notes=["순위 1 = 10년(2017~2026) 최저. 예·경보 = 행정안전부 「8월 가뭄 예·경보」(2026-08-10 발표). "
                        "쌍: 7월 낙동강 6곳 ASC54 0725↔0715, 섬진강 DESC134 0718↔0720(모두 S1C↔S1C) · "
                        "8월 낙동강 6곳 ASC54 0806↔0802, 섬진강·평림 ASC127 0811↔0807(S1C↔S1D).",
                        "k_eff > 1 이면 SAR 면적 감소 < 저수량 감소(하한). 저수지 SAR·저수량은 같은 1:1 쌍·같은 촬영 시각(KST)의 WAMIS 시자료.",
                        "ⓑ 2025-08 순위 ≥8(전년도 다우 → 전년 대비 감소가 평년 대비보다 크게 보임) · ⓒ 2025-08 순위 ≤3"
                        "(전년도도 낮음 → 작게 보임; 안동 2026 은 7·8월 모두 10년 최저) · "
                        "† 수체 1 km² 미만 — Δ% 와 Δkm² 를 함께 읽는다 · "
                        "ⓕ 평림 7월(−1.5%)은 두 해 임계가 3구간 달라 같은 임계로 맞추면 +0.2~+0.7% → 감소로 세지 않는다."],
                 align=["c", "l"] + ["c"] * 9, cell=cell, sep=[7]))

    # 표2 ─ WAMIS 10년 순위
    rows, cell = [], {}
    aug = mon[mon.연 >= 2017]
    for i, d in enumerate(DAMS8):
        res = RES8[d]
        s7 = aug[(aug.저수지 == res) & (aug.월 == 7)].set_index("연")["월평균수위_m"]
        s8 = aug[(aug.저수지 == res) & (aug.월 == 8)].set_index("연")["월평균수위_m"]
        r7, r8 = s7.rank(method="min").astype(int), s8.rank(method="min").astype(int)
        rows.append([RES_LABEL[res], f"{s8.min():.2f} ~ {s8.max():.2f}", f"{s8.median():.2f}",
                     f"{s8[2025]:.2f}", str(r8[2025]), f"{s8[2026]:.2f}", str(r8[2026]),
                     f2(s8[2026] - s8.median(), True), f"{r7[2025]} → {r7[2026]}"])
        if r8[2026] <= 2:
            cell[(i, 6)] = HI
        if r8[2025] >= 6:
            cell[(i, 4)] = {"color": C_25, "bold": True}
    n25 = sum(1 for r in rows if int(r[4]) >= 6)
    n26 = sum(1 for r in rows if int(r[6]) <= 2)
    rows.append(["요약", "", "", "", f"{n25}/8곳 ≥6위", "", f"{n26}/8곳 1·2위", "", ""])
    cell[(8, None)] = SUM
    T.append(Tbl("표2_WAMIS_10년순위_8저수지",
                 "Table 2. WAMIS 8월 평균 저수위의 10년(2017~2026) 순위 — 2026 은 이례적으로 낮고 2025 는 평년보다 높았다",
                 ["저수지", "10년 범위\n(EL.m)", "10년\n중앙값", "2025-08\n(EL.m)", "순위", "2026-08\n(EL.m)", "순위",
                  "2026 −\n중앙값 (m)", "7월 순위\n2025 → 2026"],
                 rows,
                 notes=["WAMIS 월자료(mn_mndata) 월평균 저수위, 낮은 순(1 = 10년 최저). API 가 2017 이전 월자료를 주지 않아 "
                        "평년 = 10년 중앙(30년 기후값 아님). 중앙값은 10개 값의 표준 중앙값(5·6번째 평균).",
                        "2025-08 은 안동만 2위로 낮고 나머지 7곳이 중앙값 위(6위 이상)였다 → 전년 대비 Δ% 는 평년 대비보다 크게 나온다(안동은 반대)."],
                 align=["l"] + ["c"] * 8, cell=cell, sep=[7]))

    # 표3 ─ 남부 15 대권역
    rows, cell = [], {}
    for i, (lab, bbn, _) in enumerate(REG):
        j7, a8 = cget(cn, bbn, "7월", "대권역"), cget(cn, bbn, "8월", "대권역")
        jj = judge(reg.loc[lab, "7월2026"], reg.loc[lab, "8월2026"])
        foot = {"형산강": "ⓐ", "만경·동진": "ⓔ", "회야·수영": "ⓐ"}.get(lab, "")
        rows.append([lab, str(int(reg.loc[lab, "n"])), f"{reg.loc[lab, '7월2025']:g} → {reg.loc[lab, '7월2026']:g}",
                     f"{reg.loc[lab, '8월2025']:g} → {reg.loc[lab, '8월2026']:g}", jj,
                     f1(j7.pct), f1(a8.pct), foot or "—"])
        if "가뭄" in jj:
            cell[(i, 4)] = B
        if a8.pct > 0:
            cell[(i, 6)] = {"color": "#2171b5", "bold": True}
    rows.append("대표 댐 없음 ⓓ — 상위 수계 판정을 따른다")
    for lab in NO_DAM:
        j7, a8 = cget(cn, lab, "7월", "대권역"), cget(cn, lab, "8월", "대권역")
        rows.append([lab, "0", "—", "—", "—", f1(j7.pct), f1(a8.pct), "ⓓ"])
    T.append(Tbl("표3_남부15대권역_가뭄판정_SAR",
                 "Table 3. 남부 15개 대권역 — WAMIS 권역 가뭄 판정(대표 댐 저수위 순위 중앙값)과 SAR 대권역 수체 면적 Δ%",
                 ["권역", "대표 댐\n수", "7월 중앙 순위\n2025 → 2026", "8월 중앙 순위\n2025 → 2026", "2026 가뭄 판정\n(중앙 ≤3위)",
                  "SAR 7월\nΔ%", "SAR 8월\nΔ%", "각주"],
                 rows,
                 notes=["가뭄 정의: 수문학적 가뭄. WAMIS 댐 월평균 저수위 10년 순위에서 권역 대표 댐(조정지 제외) 중앙 ≤3위(하위 30%)인 달을 "
                        "그 권역의 가뭄 달로 본다. 남부 8권역이 8월 가뭄, 그중 5권역은 7월에도 가뭄. 한강 권역(2026-08 중앙 7.5위)은 아니다.",
                        "SAR 대권역 Δ% 는 정본 배정(7월 낙동강·동남권 ASC54 0725↔0715 / 금강·섬진·영산 계열 DESC134 0718↔0720, "
                        "8월 ASC54 0806↔0802 / ASC127 0811↔0807). SAR Δ% 는 판정이 아니라 관측(하한).",
                        "ⓐ 2026 이 평년 위인 대표 댐(형산강 안계 7위, 회야·수영 선암 8월 8위) · "
                        "ⓔ 만경·동진: 하구·간척지라 수체가 농업용수·조위에 지배되고 대표 댐(부안)이 하나뿐 — 저수위 순위로 설명되지 않음, "
                        "부안호는 저수지 대조 목록에 없음."],
                 align=["l"] + ["c"] * 7, cell=cell, sep=[3]))

    # 표4 ─ 공식 예·경보
    order = ["운문", "밀양", "섬진강", "안동", "임하", "성덕", "영천", "평림"]
    rows, cell = [], {}
    for i, d in enumerate(order):
        rr = dam_rank(rk, d)
        rows.append([f"{d}댐", REGION8[d], STAGE[d], STAGE_ENTRY.get(d, "—"), f"{int(rr['8월_2026순위'])}위",
                     f1(cget(cn, d, "8월").pct)])
        if STAGE[d] in ("심각", "경계"):
            cell[(i, 2)] = HI
    rows.append("대조 — 금강 권역: 순위는 하위, 공식 단계는 없음 (문턱이 다르다)")
    for d in ("용담", "대청"):
        rr = dam_rank(rk, d)
        rows.append([f"{d}댐", "금강", "단계 없음", "—", f"{int(rr['8월_2026순위'])}위",
                     f1(cget(cn, d, "8월").pct) + (" (변화 없음)" if d == "대청" else "")])
        cell[(len(rows) - 1, None)] = {"color": "#555555"}
    T.append(Tbl("표4_공식가뭄예경보_대조",
                 "Table 4. 정부 가뭄 예·경보와의 대조 — 본문 8개 댐이 전부 8월 공식 가뭄 단계였다",
                 ["댐", "권역", "8월 예·경보 단계\n(8.10 발표)", "현 단계 진입일\n(2026, 기후부)", "WAMIS 8월\n순위 2026",
                  "SAR 유역\n8월 Δ%"],
                 rows,
                 notes=["행정안전부 「8월 가뭄 예·경보」(2026-08-10): 다목적댐 19곳 저수량 예년의 104.3%, 용수댐 12곳 66.1% — 전국으로는 "
                        "안정적이나 낙동강·섬진강 유역의 다목적댐 11곳·용수댐 10곳이 예년 이하. 기상가뭄 48개 시·군(주의 경북 남부·경남, "
                        "경계 부산·김해·울주). 농업용 저수지 평균 53.2%(평년 대비 76.1%).",
                        "진입일 = 기후에너지환경부 보도참고자료(운문 심각 7.15 · 안동·임하 주의 7.8 · 성덕 주의 7.18 · 밀양 경계 8.2 · "
                        "평림 주의 8.2). 영천·섬진강은 진입 보도자료 미확보. 공식 단계(용수공급 조정 기준)와 WAMIS 순위(10년 상대 위치)는 "
                        "문턱이 달라 금강처럼 어긋날 수 있다. 일치는 WAMIS 순위·SAR 기준이다(광학 S2 운문 유역평균 ΔMNDWI ≈0)."],
                 align=["l", "c", "c", "c", "c", "c"], cell=cell, sep=[7]))

    # 표5 ─ SAR 면적 ↔ WAMIS 저수량
    rows, cell = [], {}
    sw2 = sw[sw.월.isin(["7월", "8월"])]
    for d in DAMS8:
        res = RES8[d]
        for m in ("7월", "8월"):
            r = sw2[(sw2.저수지 == res) & (sw2.월 == m)].iloc[0]
            rows.append([res if m == "7월" else "", m, f"{kst(r.t0)} → {kst(r.t1)}", f"{r.rsrt0:.1f} → {r.rsrt1:.1f}",
                         f2(r.dh_m, True), f1(r.WAMIS_dV_pct), f1(r.SAR_dA_pct), f"{r.k_eff:.2f}",
                         "하한" if r.k_eff > 1 else "—"])
            cell[(len(rows) - 1, 6)] = B
    nmain = sum(1 for r in rows if r[-1] == "하한")
    k = swsens["k_eff"]
    rows.append(["집계", "", "본쌍 16", "", "", "", "", f"{sw2.k_eff.min():.2f}~{sw2.k_eff.max():.2f}", f"{nmain}/16"])
    rows.append(["", "", "민감도 2×2 (16칸)", "", "", "", "", f"{k.min():.2f}~{k.max():.2f}",
                 f"{int((k > 1.0).sum())}/16 (동률 1·역전 1)"])
    rows.append(["", "", "합계 32칸", "", "", "", "", "", f"{nmain + int((k > 1.0).sum())}/32"])
    for r_ in range(len(rows) - 3, len(rows)):
        cell[(r_, None)] = SUM
    T.append(Tbl("표5_SAR면적_WAMIS저수량_하한",
                 "Table 5. 저수지 SAR 면적 Δ% ↔ WAMIS 저수량 Δ% — 같은 1:1 쌍·같은 촬영 시각, 32칸 중 30칸에서 SAR 감소가 더 작다(하한)",
                 ["저수지", "월", "촬영 시각 (KST)\n2025 → 2026", "저수율 (%)\n2025 → 2026", "수위 Δ\n(m)", "저수량\nΔ%",
                  "SAR 면적\nΔ%", "k_eff", "판정"],
                 rows,
                 notes=["k_eff = 저수량 Δ% ÷ SAR 면적 Δ%. 저수지는 위로 갈수록 넓어 수위가 내려가면 부피가 면적보다 빨리 준다 → "
                        "형상만으로 k 1.3~2.0 이 기대되나 16쌍 중 14쌍은 그 범위로도 설명되지 않는다(안동 8월 1.62·옥정 7월 1.89 만 범위 안).",
                        "하한이 깨진 2칸은 모두 안동·2025-08-23 기준 민감도 쌍(k 0.99 동률, 0.77 역전): SAR 은 네 쌍에서 −11.5~−12.2 로 "
                        "거의 고정인데 저수량이 −9.6~−16.7 로 날짜를 따라 움직인다(분모 쪽). 사후 민감도(저수량 월평균)로는 16/16 하한 — 본판 아님.",
                        "7월 옥정·평림은 DESC134 0718↔0720(KST 익일 06시). 저수지 SAR 은 gee reservoir_km2_v11 의 날짜 열(궤도혼합 열 아님)."],
                 align=["l", "c", "c", "c", "c", "c", "c", "c", "c"], cell=cell, sep=[15]))

    # 표6 ─ 민감도 2×2
    pairs = ["0811→0813", "0823→0813", "0811→0825", "0823→0825"]
    rain = {"안동호": "4.6 · 0.7 | 40.1 · 36.6", "임하호": "7.7 · 0.0 | 18.8 · 35.2", "옥정호": "43.0 · 0.0 | 0.0 · 4.5",
            "평림호": "57.5 · 0.0 | 0.0 · 0.0", "장성호": "—"}
    main_orb = {"안동호": "ASC54", "임하호": "ASC54", "옥정호": "ASC127", "평림호": "ASC127", "장성호": "ASC127"}
    rows, cell = [], {}
    for i, res in enumerate(["안동호", "임하호", "옥정호", "평림호", "장성호"]):
        cells = []
        for j, p in enumerate(pairs):
            v = sens.loc[res, p]
            kk = swsens[(swsens.저수지 == res) & swsens.월.str.endswith(p)]
            kt = f"\n(k {kk.k_eff.iloc[0]:.2f})" if len(kk) else ""
            cells.append(f1(v) + kt)
            if len(kk) and kk.k_eff.iloc[0] <= 1.0:
                cell[(i, 2 + j)] = HI
        v4 = sens.loc[res, pairs].astype(float).round(1)      # 표에 보이는 값끼리의 폭 (근거 문서와 같은 방식)
        rows.append([res + ("*" if res == "장성호" else ""), f"{f1(sens.loc[res, 'main'])}\n({main_orb[res]})", *cells,
                     f"{v4.max() - v4.min():.1f}", rain[res]])
        cell[(i, 1)] = B
    neg = int((sens[pairs] < 0).to_numpy().sum())
    least = int((sens["main"] > sens[pairs].max(axis=1)).sum())
    rows.append(["요약", f"{least}/5 감소 최소", f"{neg}/20 감소", "", "", "", "", ""])
    cell[(5, None)] = SUM
    T.append(Tbl("표6_민감도2x2_DESC134",
                 "Table 6. 8월 민감도 4쌍(DESC134, S1C↔S1C) — 위성·날짜·강우를 바꿔도 20칸 모두 감소, 본쌍이 가장 보수적",
                 ["저수지", "본쌍 8월\n(S1C↔S1D)", "2025-08-11\n→ 2026-08-13", "2025-08-23\n→ 2026-08-13",
                  "2025-08-11\n→ 2026-08-25", "2025-08-23\n→ 2026-08-25", "네 쌍 폭\n(%p)",
                  "직전 5일 강우 (mm)\n2025 0811·0823 | 2026 0813·0825"],
                 rows,
                 notes=["SAR 저수지 면적 Δ%(괄호 k_eff = 같은 시각 WAMIS 저수량 Δ% ÷ SAR Δ%). 범위는 DESC134 가 네 날짜 모두 덮는 저수지 — "
                        "밀양·영천·성덕·운문은 미커버. *장성호(영산강, 농어촌공사)는 8개 댐 밖 대조 저수지(WAMIS 저수량 대조 없음).",
                        "본쌍이 5/5 곳에서 네 쌍 범위 밖 작은 쪽 → 보고 수치는 과대가 아니라 과소평가. 크기는 옥정에서 흔들린다(폭 5.5%p, "
                        "거의 전부 2026 쪽 날짜 0813→0825 — 두 날 다 건조). 붉은 칸 = 하한이 깨진 안동 2칸."],
                 align=["l"] + ["c"] * 7, cell=cell, sep=[4]))

    # 표7 ─ S2 교차검증
    s1t = pd.read_csv(S2_DIR / "표1_16사례_S2_SARv11.csv", encoding="utf-8-sig")
    s2t = pd.read_csv(S2_DIR / "표2_화소대응_v11.csv", encoding="utf-8-sig").dropna(subset=["댐"])
    s2t = s2t[s2t["댐"].isin(["영천", "성덕", "운문", "밀양", "안동", "임하"])].set_index("댐")
    rows, cell = [], {}
    for i, d in enumerate(["운문", "영천", "밀양", "성덕", "안동", "임하"]):
        a = s1t[s1t["사례"] == f"{d} 8월"].iloc[0]
        b = s2t.loc[d]
        dm = float(a["ΔMNDWI"])
        rows.append([d, STAGE[d], f"{float(a['공통유효화소%']):.1f}", ("+" if dm > 0 else "") + f"{dm:.3f}".replace("-", M)
                     + (" (≈0)" if d == "운문" else ""),
                     f1(float(b["SAR Δ%(저수지띠)"])), f1(float(b["S2 Δ%(저수지띠)"])),
                     (f"({float(b['SAR소실→S2소실 %']):.1f})†" if d == "성덕" else f"{float(b['SAR소실→S2소실 %']):.1f}"),
                     f"{float(b['2025수면 IoU']):.2f}", "본문" if float(a["공통유효화소%"]) >= 85 else "참고 (85% 미만)"])
        if d in ("운문", "영천", "밀양"):
            cell[(i, 6)] = HI
        if float(a["공통유효화소%"]) < 85:
            cell[(i, None)] = {"color": "#7a7a7a"}
    T.append(Tbl("표7_S2교차검증_화소대응",
                 "Table 7. Sentinel-2 교차검증(8월 ASC54 쌍) — 맑은 사례에서 두 센서가 같은 방향, SAR 소실 화소의 74~87% 를 광학도 소실로 판정",
                 ["댐", "단계", "공통 유효\n화소 %", "유역평균\nΔMNDWI", "저수지띠\nSAR Δ%", "저수지띠\nS2 Δ%",
                  "SAR 소실 →\nS2 소실 %", "2025 수면\nIoU", "구분"],
                 rows,
                 notes=["S2 L2A 단일일(합성 안 함), SAR v11 2025-08-06↔2026-08-02. 유역평균 ΔMNDWI 는 정본 SCL 마스크, 화소 대응은 수면 보존 마스크"
                        "(SCL 2·7 유지 + 음수 반사도 0) — 두 지표를 한 문장에 섞지 않는다. 유역평균 ΔMNDWI 는 수면(유역의 2~4%)을 희석한다.",
                        "공통 유효화소 85% 이상 4사례 중 유역평균은 3사례가 같은 방향, 운문 ≈0(마스크 300 m 확장 시 −0.001). 수면 면적으로는 4/4 같은 방향. "
                        "85% 미만 12사례는 전부 ΔMNDWI 양수(잔여 대기효과). † 성덕 화소 대응은 수체 0.66 km²·IoU 최저라 인용하지 않는다. "
                        "밀양 S2 2026 은 08-06(08-01 수면 위 권운 71%)."],
                 align=["l"] + ["c"] * 8, cell=cell, sep=[3]))

    # 표8 ─ 관측쌍·전처리
    rainr = pd.read_csv(RAIN_CSV, dtype={"date": str})

    def rv(d, rel, basins):
        r = rainr[(rainr.date == d) & (rainr.rel == rel)].iloc[0]
        return " · ".join(f"{r[b]:.0f}" for b in basins)

    rows = [["7월A", "ASC54", "07-25 (S1C)", "07-15 (S1C)", "S1C↔S1C", "낙동강 6개 댐유역 · 낙동강·동남권 대권역",
             f"낙동강 {rv('20250725', 54, ['낙동강'])} → {rv('20260715', 54, ['낙동강'])}"],
            ["7월B", "DESC134", "07-18 (S1C)", "07-20 (S1C)", "S1C↔S1C", "섬진강·평림 · 금강·섬진강·영산강 계열",
             f"섬진·영산 {rv('20250718', 134, ['섬진강', '영산강'])} → {rv('20260720', 134, ['섬진강', '영산강'])}"],
            ["8월A", "ASC54", "08-06 (S1C)", "08-02 (S1D)", "S1C↔S1D", "낙동강 6개 댐유역 · 낙동강·동남권 대권역",
             f"낙동강 {rv('20250806', 54, ['낙동강'])} → {rv('20260802', 54, ['낙동강'])}"],
            ["8월B", "ASC127", "08-11 (S1C)", "08-07 (S1D)", "S1C↔S1D", "섬진강·평림 · 금강·섬진강·영산강 계열",
             f"섬진·영산 {rv('20250811', 127, ['섬진강', '영산강'])} → {rv('20260807', 127, ['섬진강', '영산강'])}"],
            "점검용 쌍 (본문 수치를 대체하지 않는다)",
            ["민감도 2×2", "DESC134", "08-11 · 08-23 (S1C)", "08-13 · 08-25 (S1C)", "S1C↔S1C", "안동·임하·옥정·평림 (+장성)",
             "Table 6"],
            ["건조 대조", "ASC54", "08-12 (S1A)", "08-02 (S1D)", "S1A↔S1D", "낙동강 6개 저수지 (8월A 대체)",
             f"낙동강 {rv('20250812', 54, ['낙동강'])} → {rv('20260802', 54, ['낙동강'])}"]]
    T.append(Tbl("표8_관측쌍_전처리",
                 "Table 8. 비교 설계 — 동일 상대궤도 1:1 관측쌍(전년도 2025 ↔ 2026, 월별)과 점검용 쌍",
                 ["쌍", "상대궤도", "2025 (위성)", "2026 (위성)", "위성", "대상", "직전 5일 강우 (mm)\n2025 → 2026"],
                 rows,
                 notes=["전처리(포스터 관측 13장 모두): Sentinel-1 GRD VH · 정밀궤도(POEORB) · 열잡음 제거·보정(β⁰) · Frost 3×3 · "
                        "Terrain-Flattening(γ⁰) · Range-Doppler 지형보정(COP30 DEM, EGM 지오이드 보정) · 10 m · EPSG:5179 · dB.",
                        "수체: 유역별 Otsu 임계(두 해 같은 구간 폭 0.1765 dB 히스토그램), 분리도 η 가 낮은 소유역은 상위 대권역 임계를 두 해 함께 상속. "
                        "8월은 2025 년에 S1D 가 없어 위성 교차가 불가피하다 — 같은 해·같은 궤도 두 위성 면적 차는 중앙 0.5%.",
                        "강우: WAMIS 댐유역 일강우, 촬영일 포함 직전 5일 합의 권역 중앙값(그 관측이 덮은 댐만). 강우는 거르는 기준이 아니라 해석용 주석이다."],
                 align=["l", "c", "c", "c", "c", "l", "c"], sep=[3]))

    # 표9 ─ 견고성 점검
    rows = [["위성 차이\n(8월 S1C↔S1D)", "같은 해·같은 궤도에서\n두 위성 면적 비교", "중앙 0.5%\n(유역 0.35%)",
             "8월 Δ% −4.7~−27.7% 를\n위성 차로 설명할 수 없다"],
            ["위성·날짜·강우\n(민감도 2×2)", "DESC134 S1C↔S1C 4쌍\n× 5개 저수지", "20/20 감소\n본쌍이 5/5 곳 가장 작은 감소",
             "보고 수치는 보수적\n(Table 6)"],
            ["직전 강우\n— 저수지", "2025 0806(102 mm) → 0812(33 mm)\n2026 0802 고정", "Δ% 차 ≤1.0%p\n6/6 하한 유지",
             "8월A 본쌍 감소율은\n0806 직전 비 때문이 아니다"],
            ["직전 강우\n— 댐유역", "같은 교체를\n유역 단위로", "최대 6.2%p(임하)·4.9%p(안동)\n담수호 안은 ≤1.05%",
             "차이는 담수호 밖 하천 — 젖은 날 하천이\n덜 잡힘 (안동·임하는 과소평가 쪽)"],
            ["임계 양자화\n(8월, ±1구간)", "0.1765 dB 를\n양쪽으로 직접 주입", "맑은 4유역 ≤1.10%p (상대 ≤4%)\n비대칭 0.00~0.20%p",
             "안동 1.00%p(13%)·임하 1.30%p(18%)\n— 8개 전체에 한 수로 쓰지 않는다"],
            ["임계 비대칭\n(7월)", "낙동강 두 해를\n같은 임계로 재산출", "6유역 모두 과소평가 쪽\n+0.3~+1.7%p",
             "7월 하한 −12.7(안동, 참값 −13.5~−13.7)은\n보수적 · 평림 7월 제외(ⓕ)"],
            ["SAR ↔ 저수량\n(하한)", "본쌍 16 + 민감도 16\n같은 촬영 시각", "30/32 하한\n안동 2칸 동률·역전",
             "「모두 하한」 이 아니라\n「32칸 중 30칸」"],
            ["커버리지", "유역 면적 중 관측 비율", "본문 8개 99.9~100%", "—"]]
    T.append(Tbl("표9_견고성점검_부록",
                 "Table 9. (부록) 견고성 점검 요약 — 무엇을 바꿔 봤고 결론이 어떻게 남았나",
                 ["점검", "방법", "결과", "해석 · 쓰는 범위"],
                 rows,
                 notes=["전부 실측(추정·외삽 없음). 임계 ±1구간은 「차(差) 항」만 덮고, 두 해 공통 오차는 민감도 4쌍이 따로 덮는다 — 섞지 않는다. "
                        "출처: gee DROUGHT_2026_EVIDENCE_KR §3-3·§3-4·§3-8·§4, S1 REVIEW_20261005 §2-1."],
                 align=["l", "l", "l", "l"]))

    # 표10 ─ 남부 댐유역 전수
    rows, cell = [], {}
    dams = sorted(set(cn[cn.구분 == "댐유역"].대상))
    reg_of = {}
    for d in dams:
        rr = dam_rank(rk, d)
        reg_of[d] = (rr["권역"] if rr is not None else {"군위": "낙동강", "보현산": "낙동강", "보령": "금강서해"}[d])
    order_reg = ["낙동강", "형산강", "태화강", "회야 · 수영", "낙동강동해", "낙동강남해", "금강", "금강서해", "만경 · 동진",
                 "섬진강", "섬진강남해", "영산강", "탐진강"]
    dams = sorted(dams, key=lambda d: (order_reg.index(reg_of[d]), cget(cn, d, "8월").pct))
    cur = None
    for d in dams:
        if reg_of[d] != cur:
            cur = reg_of[d]; rows.append(cur.replace(" · ", "·"))
        j, a = cget(cn, d, "7월"), cget(cn, d, "8월")
        rr = dam_rank(rk, d)
        foot = []
        if rr is not None:
            if max(rr["7월_2026순위"], rr["8월_2026순위"]) >= 6: foot.append("ⓐ")
            if rr["8월_2025순위"] >= 8: foot.append("ⓑ")
            if min(rr["7월_2025순위"], rr["8월_2025순위"]) <= 3: foot.append("ⓒ")
        small = min(a.w25, a.w26, j.w25, j.w26) < 1.0
        if small: foot.append("†")
        if d == "평림": foot.append("ⓕ")
        if d == "남강": foot.append("ⓖ")
        if d == "대청": foot.append("ⓗ")
        dk = SMALL_DKM2.get(d, a.new - a.lost)
        dks = ("반올림 수준" if abs(dk) <= 0.02 else f2(dk, True)) if small else f2(a.w26 - a.w25, True)
        rows.append([d + (" ★" if d in DAMS8 else ""), f"{j.회차} {f1(j.pct)}" if d != "평림" else f"{j.회차} ({f1(j.pct)})",
                     f"{a.회차} {f1(a.pct)}", f"{a.w25:.2f} → {a.w26:.2f}", dks,
                     f"{int(rr['8월_2025순위'])} → {int(rr['8월_2026순위'])}" if rr is not None else "—",
                     " ".join(foot) or "—"])
        i = len(rows) - 1
        if d in DAMS8:
            cell[(i, 0)] = B; cell[(i, 2)] = B
        if a.pct > 0:
            cell[(i, 2)] = {"color": "#2171b5", "bold": True}
        if d in ("대청", "평림"):
            cell[(i, 1 if d == "평림" else 2)] = GREY
    T.append(Tbl("표10_남부댐유역_전수_보조",
                 "Table 10. (보조) 남부 댐유역 전수 — SAR 수체 면적 Δ%(정본 쌍 배정)와 대표 댐 WAMIS 8월 순위",
                 ["댐유역", "7월 쌍 · Δ%", "8월 쌍 · Δ%", "8월 수체 km²\n2025 → 2026", "Δkm²", "WAMIS 8월 순위\n2025 → 2026", "각주"],
                 rows,
                 notes=["★ 본문 8개. 쌍: 7월A ASC54 0725↔0715 · 7월B DESC134 0718↔0720 · 8월A ASC54 0806↔0802 · 8월B ASC127 0811↔0807. "
                        "두 회차에 모두 있는 유역은 ① 커버 최대 ② 부모 대권역과 같은 쌍 순으로 배정(gee canon_table 규칙).",
                        "ⓐ 2026 순위 ≥6(평년 위) · ⓑ 2025-08 순위 ≥8(전년도 다우) · ⓒ 2025 순위 ≤3(전년도도 낮음) · "
                        "† 수체 1 km² 미만(Δkm² 는 소실−신규, 0.02 미만은 반올림 수준이라 인용하지 않음; 보현산 −48.6% 는 −0.37 km²) · "
                        "ⓕ 평림 7월 임계 비일관(감소로 세지 않음) · ⓖ 남강: 커버 때문에 B군 배정, 임계는 낙동강(다른 궤도)에서 상속 · "
                        "ⓗ 대청: 궤도에 따라 −4.4 ↔ +0.5%, 저수지 −0.3% — 「변화 없음」으로 읽고 Δ% 를 인용하지 않는다. "
                        "군위·보현산·보령은 WAMIS 월자료 순위 없음."],
                 align=["l", "c", "c", "c", "c", "c", "c"], cell=cell))

    # 표11 ─ 금강
    res = pd.read_csv(GEE / "reservoir_km2_v11.csv", encoding="utf-8-sig").set_index("저수지")

    def rpct(name):
        a, b = res.loc[name, "2025-08-11_ASC127"], res.loc[name, "2026-08-07_ASC127"]
        return f"{f1(100 * (b / a - 1))} ({a:.2f}→{b:.2f})"

    rows, cell = [], {}
    for lab, kind, nm, rname, wd in (("용담", "댐유역", "용담", "용담호", "용담"), ("대청", "댐유역", "대청", "대청호", "대청"),
                                     ("보령", "댐유역", "보령", None, None), ("금 강 (대권역)", "대권역", "금 강", None, None),
                                     ("금강서해 (대권역) ⓓ", "대권역", "금강서해", None, None),
                                     ("부안 (만경·동진)", "댐유역", "부안", None, "부안"),
                                     ("만경·동진 (대권역) ⓔ", "대권역", "만경동진", None, None)):
        j, a = cget(cn, nm, "7월", kind), cget(cn, nm, "8월", kind)
        rr = dam_rank(rk, wd) if wd else None
        rows.append([lab, f1(j.pct), f1(a.pct), rpct(rname) if rname else "—",
                     f"{int(rr['8월_2025순위'])} → {int(rr['8월_2026순위'])}" if rr is not None else "—",
                     {"용담": "공식 순위(10년 최저)와 일치 — 유역·저수지 1.7%p 안", "대청": "신호 없음 — Δ% 인용 안 함 ⓗ",
                      "부안": "약하지만 같은 방향", "만경동진": "하구·간척지 — 순위로 설명되지 않음"}.get(nm, "약한 감소")])
        if nm == "용담":
            cell[(len(rows) - 1, 2)] = HI; cell[(len(rows) - 1, 3)] = HI
        if nm in ("대청",):
            cell[(len(rows) - 1, None)] = {"color": "#7a7a7a"}
    T.append(Tbl("표11_금강권역_분해",
                 "Table 11. (보조) 금강 권역 — 공식 단계는 없지만 용담은 크게 감소, 대청은 변화 없음",
                 ["대상", "SAR 유역\n7월 Δ%", "SAR 유역\n8월 Δ%", "저수지 SAR 8월 Δ%\n(ASC127, km²)", "WAMIS 8월 순위\n2025 → 2026",
                  "해석"],
                 rows,
                 notes=["포스터 문구: 「금강은 저수위 순위 하위 · 공식 단계 없음 · 용담은 크게 감소, 대청은 변화 없음」. "
                        "대청은 궤도에 따라 −4.4 ↔ +0.5% 로 갈리고 8월B 두 해 임계가 한 구간 다르며(−20.5 ↔ −20.676) 만수 대비 면적이 "
                        "2025 94.1% · 2026 93.9% 로 둘 다 거의 만수다. 만경·동진은 금강과 별도 권역(대표 댐 부안)이다."],
                 align=["l", "c", "c", "c", "c", "l"], cell=cell))
    return T


# ════════════════════════ 실행 ════════════════════════
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pylib", type=Path, help="openpyxl·python-pptx 가 있는 site-packages (뒤에 붙인다)")
    ap.add_argument("--only", nargs="*", help="그림1 … 그림7 · 표 (생략하면 전부)")
    args = ap.parse_args()
    if args.pylib:
        sys.path.append(str(args.pylib))
    psf.style()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    todo = set(args.only or ["그림1", "그림2", "그림3", "그림4", "그림5", "그림6", "그림7", "표"])

    cn = canon()
    rk = ranks()
    reg = region_table(rk)
    mon = wamis_monthly(out / "_자료" / "wamis_monthly_8res_2017_2026.csv")
    sw = pd.read_csv(WAMIS_DIR / "sar_vs_wamis_v11.csv", encoding="utf-8-sig")
    swsens = pd.read_csv(WAMIS_DIR / "sar_vs_wamis_v11_sens.csv", encoding="utf-8-sig")
    sens = psf.sens_table()
    rain = pd.read_csv(RAIN_CSV, dtype={"date": str, "orbit": str})

    if "그림1" in todo:
        fig1(mon, reg, out / "그림1_이례성_WAMIS_10년순위.png")
    if "그림2" in todo:
        fig2(cn, reg, rk, out / "그림2_남부지도_권역판정_SAR댐유역.png")
    if "그림3" in todo:
        psf.fig_a(psf.basin_table(), out / "그림3_8개댐유역_SAR_지도막대.png")
    if "그림4" in todo:
        main_w, sens_w = psf.wamis_tables()
        psf.fig_b(main_w, sens_w, sens, out / "그림4_SAR면적_WAMIS저수량_민감도.png")
    if "그림5" in todo:
        psf.fig_c(out / "그림5_SAR_S2_화소대응.png")
    if "그림6" in todo:
        fig6(rain, out / "그림6_관측쌍_타임라인_강우.png")
    if "그림7" in todo:
        fig7(cn, out / "그림7_부록_강우위상_저수지vs유역.png")
    if "표" in todo:
        tbls = build_tables(cn, rk, reg, mon, sw, swsens, sens)
        widths = {}
        for t in tbls:
            widths[t.key] = render_png(t, out / f"{t.key}.png")
        try:
            write_xlsx(tbls, out / "표모음_편집용.xlsx")
            write_pptx(tbls, widths, out / "표모음_A0_편집용.pptx")
        except ImportError as e:
            print(f"⚠ xlsx·pptx 생략 — {e} (--pylib 로 openpyxl·python-pptx 경로를 주면 만든다)")
        print(f"표 {len(tbls)}개")
    print(f"→ {out}")


if __name__ == "__main__":
    main()
