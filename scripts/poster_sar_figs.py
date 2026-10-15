# -*- coding: utf-8 -*-
"""poster_sar_figs — 2026 원탐학회 가뭄 포스터 Results 그림 (SAR v11 · EGM 켬).

    그림A  poster_A_sar_basins.png     (a) 남부 8개 댐유역 8월 SAR 수체 Δ% 지도
                                       (b) 7·8월 Δ% 막대 — 유역 단위, 동일 상대궤도 1:1 쌍
    그림B  poster_B_sar_wamis.png      (a) 저수지 SAR 면적 Δ% ↔ WAMIS 저수량 Δ% (본쌍 16 + 민감도 16)
                                       (b) 8월 DESC134 S1C↔S1C 민감도 4쌍 ↔ 본쌍
    그림C  poster_C_s2_pixel.png       8월 85% 통과 4곳 SAR·S2 화소 대응(가로 나열, 큰 글자판)

입력 (전부 읽기만 한다)
    gee  Korea_WaterDetection_2025_2026/output/watershed_change_v11_{jul_a,jul_b,aug_a,aug_b}.csv
         Korea_WaterDetection_2025_2026/output/reservoir_km2_v11*.csv (날짜 열에서 직접 Δ% — `·궤도혼합` 열 안 씀)
         대권역/WKMBBSN.shp · 전댐유역/전댐유역.shp
    S1   experiments/swot_wamis/sar_vs_wamis_v11.csv · _v11_sens.csv
    S2   results/S2_DAM8_XVAL/aug_a_ws/figdata/fig4_<댐>.npz (그림C, poster_fig4_render 재사용)

수치 근거: gee docs/DROUGHT_2026_EVIDENCE_KR.md 「포스터 조립용 최종 목록」.
평림 7월은 그리지 않는다(두 해 임계 비일관 — 같은 임계로 +0.2~+0.7%, 근거 문서 ⓕ).

실행 (gis_clean: geopandas 필요)
    $env:GDAL_DATA = "F:\\envs\\gis_clean\\Library\\share\\gdal"
    F:\\envs\\gis_clean\\python.exe scripts\\poster_sar_figs.py --out <폴더>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poster_fig4_render as f4  # noqa: E402

ROOT = Path(r"F:\06_SAR_system")
GEE = ROOT / "gee" / "Korea_WaterDetection_2025_2026" / "output"
WAMIS = ROOT / "S1" / "experiments" / "swot_wamis"
FIG4 = ROOT / "S2" / "results" / "S2_DAM8_XVAL" / "aug_a_ws" / "figdata"
SHP_BBSN = ROOT / "gee" / "대권역" / "WKMBBSN.shp"
SHP_DAM = ROOT / "gee" / "전댐유역" / "전댐유역.shp"

# 표 1 과 같은 순서. 단계 = 정부 가뭄 예·경보 2026-08-01(보도 인용)
DAMS = ["안동", "임하", "밀양", "영천", "성덕", "운문", "섬진강", "평림"]
STAGE = {"안동": "주의", "임하": "주의", "밀양": "경계", "영천": "주의", "성덕": "주의",
         "운문": "심각", "섬진강": "경계", "평림": "주의"}
RESV = {"안동": "안동호", "임하": "임하호", "밀양": "밀양호", "영천": "영천호",
        "성덕": "성덕저수지", "운문": "운문호", "섬진강": "옥정호", "평림": "평림호"}
SMALL = {"성덕", "평림"}                       # 수체 1 km² 미만 → Δkm² 병기
# 유역 정본 쌍 (근거 문서 ③)
JUL = {"jul_a": ["안동", "임하", "밀양", "영천", "성덕", "운문"], "jul_b": ["섬진강"]}
AUG = {"aug_a": ["안동", "임하", "밀양", "영천", "성덕", "운문"], "aug_b": ["섬진강", "평림"]}

# 색 — 감소는 S2 그림4 의 「소실」 주황 계열, 대조 요소는 포스터 남색
C_JUL, C_AUG = "#fdae6b", "#d94801"
C_NAVY, C_INK, C_MUTED, C_GRID = "#00478B", "#222222", "#666666", "#dddddd"
FS = 16                                         # 포스터 1:1 인쇄 기준 본문 pt


def style() -> None:
    f4.set_korean_font()
    # 맑은 고딕에 U+2212(−)·U+2070(⁰) 글리프가 없다 → 글꼴 대체 목록으로 DejaVu 에서 가져온다
    plt.rcParams["font.family"] = [plt.rcParams["font.family"][0], "DejaVu Sans"]
    plt.rcParams.update({"font.size": FS, "axes.titlesize": FS + 2, "axes.labelsize": FS,
                         "xtick.labelsize": FS - 1, "ytick.labelsize": FS - 1,
                         "axes.edgecolor": "#999999", "axes.linewidth": 0.8,
                         "xtick.color": C_MUTED, "ytick.color": C_MUTED,
                         "legend.fontsize": FS - 1, "legend.frameon": False,
                         "savefig.dpi": 300})


def fmt(v: float) -> str:
    return f"{v:+.1f}".replace("-", "−").replace("+", "+" if v > 0 else "")


# ───────────────────────── 자료 ─────────────────────────
def basin_table() -> pd.DataFrame:
    """댐유역 7·8월 Δ%·수체 km² — 정본 쌍 CSV 에서 직접."""
    rows = {d: {"dam": d} for d in DAMS}
    for month, groups in (("jul", JUL), ("aug", AUG)):
        for tag, dams in groups.items():
            df = pd.read_csv(GEE / f"watershed_change_v11_{tag}.csv", encoding="utf-8-sig")
            df = df[df["구분"] == "댐유역"].set_index("대상")
            for d in dams:
                r = df.loc[d]
                rows[d].update({f"{month}_pct": float(r["Δ%"]), f"{month}_w25": float(r["2025수체km2"]),
                                f"{month}_w26": float(r["2026수체km2"]),
                                f"{month}_lost": float(r["소실km2"]), f"{month}_new": float(r["신규km2"])})
    t = pd.DataFrame(rows.values()).set_index("dam")
    t.loc["평림", "jul_pct"] = np.nan          # ⓕ 임계 비일관 — 감소로 세지 않는다
    return t


def wamis_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    main = pd.read_csv(WAMIS / "sar_vs_wamis_v11.csv", encoding="utf-8-sig")
    main = main[main["월"].isin(["7월", "8월"])]          # 건조 대조 행은 그림에서 뺀다
    sens = pd.read_csv(WAMIS / "sar_vs_wamis_v11_sens.csv", encoding="utf-8-sig")
    return main, sens


def sens_table() -> pd.DataFrame:
    """저수지 8월 본쌍 + DESC134 네 쌍 Δ% (날짜 열에서 직접)."""
    base = pd.read_csv(GEE / "reservoir_km2_v11.csv", encoding="utf-8-sig").set_index("저수지")
    main_cols = {"안동호": ("2025-08-06_ASC54", "2026-08-02_ASC54"),
                 "임하호": ("2025-08-06_ASC54", "2026-08-02_ASC54"),
                 "옥정호": ("2025-08-11_ASC127", "2026-08-07_ASC127"),
                 "평림호": ("2025-08-11_ASC127", "2026-08-07_ASC127"),
                 "장성호": ("2025-08-11_ASC127", "2026-08-07_ASC127")}
    files = {"0811→0813": "reservoir_km2_v11_d134_0811.csv", "0823→0813": "reservoir_km2_v11_sens_0823.csv",
             "0811→0825": "reservoir_km2_v11_sens_0811_0825.csv",
             "0823→0825": "reservoir_km2_v11_sens_0823_0825.csv"}
    out = []
    for res, (c0, c1) in main_cols.items():
        row = {"res": res, "main": 100 * (base.loc[res, c1] / base.loc[res, c0] - 1)}
        for k, fn in files.items():
            df = pd.read_csv(GEE / fn, encoding="utf-8-sig").set_index("저수지")
            a, b = [c for c in df.columns if c[:4] in ("2025", "2026") and "DESC134" in c][:2]
            row[k] = 100 * (df.loc[res, b] / df.loc[res, a] - 1)
        out.append(row)
    return pd.DataFrame(out).set_index("res")


# ───────────────────────── 그림 A ─────────────────────────
LABEL_POS = {   # 지도 라벨 위치(EPSG:5179 m) — 낙동강 댐은 동해 쪽, 서쪽 둘은 서해 쪽으로 뺀다
    "안동": (1_185_000, 1_850_000), "임하": (1_185_000, 1_806_000), "성덕": (1_185_000, 1_762_000),
    "영천": (1_185_000, 1_718_000), "운문": (1_185_000, 1_674_000), "밀양": (1_185_000, 1_630_000),
    "섬진강": (1_000_000, 1_578_000), "평림": (838_000, 1_578_000)}
# 1 km² 미만은 CSV 수체 열(소수 2자리)을 빼지 않는다 — Δ% 에서 되돌린 값(근거 문서 ② 규칙)
SMALL_DKM2 = {"성덕": -0.25, "평림": -0.03}


def fig_a(t: pd.DataFrame, out: Path) -> None:
    import geopandas as gpd
    bb = gpd.read_file(SHP_BBSN).to_crs(5179)
    dm = gpd.read_file(SHP_DAM).to_crs(5179)
    dm = dm[dm["damname"].isin(DAMS)].copy()
    dm["aug"] = dm["damname"].map(t["aug_pct"])
    south = bb[bb["BBSNCD"].astype(int).between(20, 53)]
    big4 = bb[bb["BBSNCD"].astype(int).isin([20, 30, 40, 50])]

    fig = plt.figure(figsize=(14.8, 7.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.0], wspace=0.30,
                          left=0.005, right=0.985, top=0.93, bottom=0.10)
    ax = fig.add_subplot(gs[0, 0])
    bb[~bb.index.isin(south.index)].plot(ax=ax, color="#f2f2f2", edgecolor="#d0d0d0", lw=0.5)
    south.plot(ax=ax, color="#e9eef5", edgecolor="#b8c4d6", lw=0.6)
    big4.boundary.plot(ax=ax, color=C_NAVY, lw=1.4)
    bounds = [-30, -25, -20, -15, -10, -5, 0]
    cmap = ListedColormap(["#a63603", "#d94801", "#f16913", "#fd8d3c", "#fdae6b", "#fdd0a2"])
    norm = BoundaryNorm(bounds, cmap.N)
    dm.plot(ax=ax, column="aug", cmap=cmap, norm=norm, edgecolor="#333333", lw=0.8)
    for name, (lx, ly) in {"낙동강": (1_105_000, 1_790_000), "금강": (985_000, 1_815_000),
                           "섬진강": (935_000, 1_640_000), "영산강": (895_000, 1_610_000)}.items():
        ax.text(lx, ly, name, color=C_NAVY, fontsize=FS - 2, ha="center", va="center", alpha=0.9,
                fontweight="bold")
    for _, r in dm.iterrows():
        d = r["damname"]
        cx, cy = r.geometry.representative_point().coords[0]
        lx, ly = LABEL_POS[d]
        ha = "left" if (lx > cx or ly < 1_600_000) else "right"
        ax.annotate(f"{d} {fmt(t.loc[d, 'aug_pct'])}%", xy=(cx, cy), xytext=(lx, ly), ha=ha, va="center",
                    fontsize=FS - 1, color=C_INK,
                    arrowprops=dict(arrowstyle="-", color="#555555", lw=0.8, shrinkA=2, shrinkB=1))
    ax.set_xlim(825_000, 1_300_000); ax.set_ylim(1_560_000, 1_900_000)
    ax.set_aspect("equal"); ax.set_axis_off()
    ax.set_title("(a) 8월 댐유역 수체 면적 변화", loc="left", fontweight="bold")
    cax = fig.add_axes([0.06, 0.075, 0.33, 0.028])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
    cb.set_ticks(bounds); cb.set_ticklabels([f"{b}".replace("-", "−") for b in bounds])
    cb.outline.set_visible(False); cb.ax.tick_params(labelsize=FS - 3, length=0)
    cb.set_label("Δ% (2025→2026, 8월)", fontsize=FS - 2, color=C_MUTED)

    # (b) 막대
    bx = fig.add_subplot(gs[0, 1])
    y = np.arange(len(DAMS))[::-1]
    h = 0.36
    for i, d in enumerate(DAMS):
        yi = y[i]
        jv, av = t.loc[d, "jul_pct"], t.loc[d, "aug_pct"]
        if np.isfinite(jv):
            bx.barh(yi + h / 2, jv, h, color=C_JUL, edgecolor="white", lw=1.5)
            bx.text(jv - 0.5, yi + h / 2, fmt(jv), ha="right", va="center", fontsize=FS - 3, color=C_MUTED)
        else:
            bx.text(-0.5, yi + h / 2, "7월 제외 (두 해 임계 다름)", ha="right", va="center",
                    fontsize=FS - 4, color=C_MUTED, style="italic")
        bx.barh(yi - h / 2, av, h, color=C_AUG, edgecolor="white", lw=1.5)
        lab = fmt(av)
        if d in SMALL:
            lab += f"  ({SMALL_DKM2[d]:+.2f} km²)".replace("-", "−")
        bx.text(av - 0.5, yi - h / 2, lab, ha="right", va="center", fontsize=FS - 3, color=C_INK,
                fontweight="bold")
    bx.set_yticks(y)
    bx.set_yticklabels([f"{d} ({STAGE[d]})" for d in DAMS], color=C_INK, fontsize=FS - 1)
    bx.set_xlim(-38, 0); bx.set_ylim(-0.7, len(DAMS) - 0.3)
    bx.xaxis.set_ticks([-30, -20, -10, 0])
    bx.set_xticklabels(["−30", "−20", "−10", "0"])
    bx.set_xlabel("SAR 수체 면적 Δ% (유역)", color=C_MUTED)
    bx.grid(axis="x", color=C_GRID, lw=0.8); bx.set_axisbelow(True)
    for s in ("top", "right", "left"):
        bx.spines[s].set_visible(False)
    bx.tick_params(axis="y", length=0)
    bx.axhline(1.5, color="#bbbbbb", lw=0.8, ls=(0, (3, 3)))
    bx.text(-37.5, 1.5 + 0.08, "섬진강·영산강", fontsize=FS - 4, color=C_MUTED, va="bottom")
    bx.text(-37.5, 1.5 - 0.08, "", fontsize=FS - 4)
    bx.text(-37.5, len(DAMS) - 0.45, "낙동강", fontsize=FS - 4, color=C_MUTED, va="top")
    bx.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=C_JUL), plt.Rectangle((0, 0), 1, 1, color=C_AUG)],
              labels=["7월 (S1C↔S1C)", "8월 (S1C↔S1D)"], loc="lower left", bbox_to_anchor=(0.0, 0.0),
              ncol=1, handlelength=1.2)
    bx.set_title("(b) 7·8월 댐유역 수체 면적 Δ%", loc="left", fontweight="bold")
    fig.savefig(out, facecolor="white"); plt.close(fig)


# ───────────────────────── 그림 B ─────────────────────────
SHORT = {"안동호": "안동", "임하호": "임하", "밀양호": "밀양", "영천호": "영천", "성덕저수지": "성덕",
         "운문호": "운문", "옥정호": "옥정", "평림호": "평림", "장성호": "장성"}
LBL_OFF = {  # 8월 점 라벨 오프셋(데이터 단위 %)
    "안동호": (1.5, 1.2), "임하호": (1.5, 1.7), "밀양호": (1.5, 0.2), "영천호": (1.5, -0.9),
    "성덕저수지": (-1.5, -1.3), "운문호": (-1.5, 0.0), "옥정호": (1.5, -1.0), "평림호": (-1.2, 2.2)}


def fig_b(main: pd.DataFrame, sens: pd.DataFrame, st: pd.DataFrame, out: Path) -> None:
    fig = plt.figure(figsize=(14.8, 6.6))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.12, 1.0], wspace=0.30,
                          left=0.075, right=0.985, top=0.92, bottom=0.14)
    ax = fig.add_subplot(gs[0, 0])
    lim_x, lim_y = (-80, 0), (-45, 0)
    xs = np.linspace(*lim_x, 50)
    ax.fill_between(xs, np.maximum(xs, lim_y[0]), 0, color="#eef3f9", zorder=0)
    ax.plot(xs, xs, color="#888888", lw=1.2, ls=(0, (4, 3)), zorder=1)
    ax.text(-43, -43.5, "1:1", color="#888888", fontsize=FS - 3, ha="left", va="bottom")
    ax.text(-78, -3, "SAR 감소 < 저수량 감소 (하한)", color=C_NAVY, fontsize=FS - 2, va="top")
    sv = sens
    ax.scatter(sv["WAMIS_dV_pct"], sv["SAR_dA_pct"], s=70, marker="D", facecolor="white",
               edgecolor=C_NAVY, lw=1.4, zorder=3)
    for m, c, mk in (("7월", C_JUL, "o"), ("8월", C_AUG, "s")):
        d = main[main["월"] == m]
        ax.scatter(d["WAMIS_dV_pct"], d["SAR_dA_pct"], s=110, marker=mk, color=c, edgecolor="white",
                   lw=1.5, zorder=4)
    for _, r in main[main["월"] == "8월"].iterrows():
        dx, dy = LBL_OFF[r["저수지"]]
        ax.text(r["WAMIS_dV_pct"] + dx, r["SAR_dA_pct"] + dy, SHORT[r["저수지"]], fontsize=FS - 3,
                color=C_INK, ha="left" if dx > 0 else "right", va="center", zorder=5)
    an = sv[(sv["저수지"] == "안동호") & sv["월"].str.contains("0823")]
    ax.annotate("안동 2025-08-23 기준 두 칸\nSAR −12.1·−12.2 ↔ 저수량 −12.0·−9.6",
                xy=(an["WAMIS_dV_pct"].min(), an["SAR_dA_pct"].min()), xytext=(-23, -29),
                fontsize=FS - 4, color=C_MUTED, ha="left",
                arrowprops=dict(arrowstyle="-", color="#999999", lw=0.8))
    ax.set_xlim(*lim_x); ax.set_ylim(*lim_y)
    ax.set_xticks(range(-80, 1, 20)); ax.set_yticks(range(-40, 1, 10))
    ax.set_xticklabels([str(v).replace("-", "−") for v in range(-80, 1, 20)])
    ax.set_yticklabels([str(v).replace("-", "−") for v in range(-40, 1, 10)])
    ax.set_xlabel("WAMIS 저수량 Δ%", color=C_MUTED); ax.set_ylabel("SAR 저수지 면적 Δ%", color=C_MUTED)
    ax.grid(color=C_GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    n_low = int((main["SAR_dA_pct"] > main["WAMIS_dV_pct"]).sum() + (sens["k_eff"] > 1.0).sum())
    ax.set_title(f"(a) 면적 ↔ 저수량 — 32칸 중 {n_low}칸 하한", loc="left", fontweight="bold")
    ax.legend(handles=[Line2D([], [], marker="o", ls="", ms=10, color=C_JUL),
                       Line2D([], [], marker="s", ls="", ms=10, color=C_AUG),
                       Line2D([], [], marker="D", ls="", ms=8, mfc="white", mec=C_NAVY, mew=1.4)],
              labels=["본쌍 7월", "본쌍 8월", "민감도 4쌍 (8월 D134)"], loc="lower right",
              handletextpad=0.3, borderaxespad=0.3)

    # (b) 민감도
    bx = fig.add_subplot(gs[0, 1])
    order = ["안동호", "임하호", "옥정호", "평림호", "장성호"]
    pairs = ["0811→0813", "0823→0813", "0811→0825", "0823→0825"]
    for i, res in enumerate(order):
        yi = len(order) - 1 - i
        v = st.loc[res, pairs].to_numpy(float)
        bx.plot([v.min(), v.max()], [yi, yi], color=C_NAVY, lw=2.5, alpha=0.35, solid_capstyle="round")
        bx.scatter(v, [yi] * 4, s=60, marker="D", facecolor="white", edgecolor=C_NAVY, lw=1.4, zorder=3)
        bx.scatter([st.loc[res, "main"]], [yi], s=120, marker="s", color=C_AUG, edgecolor="white",
                   lw=1.5, zorder=4)
        bx.text(st.loc[res, "main"] + 1.0, yi, fmt(st.loc[res, "main"]), va="center", ha="left",
                fontsize=FS - 3, color=C_INK, fontweight="bold")
    bx.set_yticks(range(len(order)))
    bx.set_yticklabels([SHORT[r] + ("호" if r != "장성호" else "호*") for r in order][::-1],
                       color=C_INK, fontsize=FS - 1)
    bx.set_xlim(-46, 3); bx.set_ylim(-0.6, len(order) - 0.1)
    bx.set_xticks([-40, -30, -20, -10, 0]); bx.set_xticklabels(["−40", "−30", "−20", "−10", "0"])
    bx.set_xlabel("SAR 저수지 면적 Δ% (8월)", color=C_MUTED)
    bx.grid(axis="x", color=C_GRID, lw=0.8); bx.set_axisbelow(True)
    for s in ("top", "right", "left"):
        bx.spines[s].set_visible(False)
    bx.tick_params(axis="y", length=0)
    neg = int((st[pairs] < 0).to_numpy().sum())
    least = int((st["main"] > st[pairs].max(axis=1)).sum())
    bx.set_title(f"(b) 민감도 4쌍 — {neg}칸 모두 감소", loc="left", fontweight="bold")
    bx.text(0.0, -0.13, f"본쌍이 {least}/{len(st)} 곳에서 네 쌍보다 감소가 작다(보수적)",
            transform=bx.transAxes, fontsize=FS - 3, color=C_MUTED, ha="left", va="top")
    bx.legend(handles=[Line2D([], [], marker="s", ls="", ms=10, color=C_AUG),
                       Line2D([], [], marker="D", ls="", ms=8, mfc="white", mec=C_NAVY, mew=1.4)],
              labels=["본쌍 (S1C↔S1D)", "DESC134 S1C↔S1C 4쌍"], loc="upper center",
              bbox_to_anchor=(0.5, 1.0), ncol=2, handletextpad=0.3, columnspacing=1.0)
    fig.savefig(out, facecolor="white"); plt.close(fig)


# ───────────────────────── 그림 C ─────────────────────────
def fig_c(out: Path) -> None:
    """4곳 × (3행 × 2열) — 제목·날짜는 캡션으로 빼고 글자를 키운 포스터판."""
    rows = [f4.load(FIG4 / f"fig4_{d}.npz") for d in f4.MAIN_ORDER]
    n = len(rows)
    asp = [r["sar"].shape[1] / r["sar"].shape[0] for r in rows]
    ratios = [a for a in asp for _ in (0, 1)]
    W = 14.8
    left, right, top_in, bot_in = 0.80, 0.05, 0.95, 0.55
    wsp = 0.05
    pw = (W - left - right) / (sum(ratios) * (1 + wsp))
    H = 3 * pw * 1.12 + top_in + bot_in
    fig = plt.figure(figsize=(W, H))
    gs = fig.add_gridspec(3, 2 * n, width_ratios=ratios, wspace=wsp, hspace=0.10,
                          left=left / W, right=1 - right / W, top=1 - top_in / H, bottom=bot_in / H)
    axs = np.array([[fig.add_subplot(gs[i, j]) for j in range(2 * n)] for i in range(3)])
    cmap = ListedColormap(f4.CHANGE_COLORS)
    for i, r in enumerate(rows):
        a = axs[:, 2 * i:2 * i + 2]
        for k, g in enumerate(("gam25", "gam26")):
            a[k][0].imshow(np.ma.masked_invalid(r[g]), cmap="gray", vmin=f4.GAMMA_VMIN, vmax=f4.GAMMA_VMAX,
                           interpolation="nearest")
        for k, g in enumerate(("rgb25", "rgb26")):
            a[k][1].imshow(r[g], interpolation="nearest")
        a[2][0].imshow(r["sar"], cmap=cmap, vmin=0, vmax=3, interpolation="nearest")
        a[2][1].set_facecolor("#cccccc")
        a[2][1].imshow(np.ma.masked_where(r["s2"] == 255, r["s2"]), cmap=cmap, vmin=0, vmax=3,
                       interpolation="nearest")
        for col, key in ((0, "sar_dpct"), (1, "s2_dpct")):
            a[2][col].text(0.03, 0.04, f"{r[key]}%".replace("-", "−"), transform=a[2][col].transAxes,
                           fontsize=FS - 2, fontweight="bold", color=C_INK, ha="left", va="bottom",
                           bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
        a[0][0].set_title("SAR γ⁰ VH", fontsize=FS - 3, color=C_MUTED, pad=3)
        a[0][1].set_title("S2 RGB", fontsize=FS - 3, color=C_MUTED, pad=3)
        p0, p1 = a[0][0].get_position(), a[0][1].get_position()
        fig.text((p0.x0 + p1.x1) / 2, p0.y1 + 0.40 / H, f4.title_of(r).replace("가뭄 ", ""),
                 ha="center", va="bottom", fontsize=FS, fontweight="bold", color=C_INK)
    for ax in axs.ravel():
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_edgecolor("#999999"); s.set_linewidth(0.6)
    for k, lab in enumerate(("2025", "2026", "변화")):
        axs[k][0].set_ylabel(lab, fontsize=FS - 1, rotation=0, ha="right", va="center", labelpad=8)
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=c) for c in f4.CHANGE_COLORS[1:] + ["#cccccc"]],
               labels=["유지", "소실", "신규", "S2 평가 밖"], loc="lower center", ncol=4,
               bbox_to_anchor=(0.5, 0.0), handlelength=1.2, columnspacing=1.6, fontsize=FS - 2)
    fig.savefig(out, facecolor="white"); plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", nargs="*", choices=["A", "B", "C"])
    args = ap.parse_args()
    style()
    args.out.mkdir(parents=True, exist_ok=True)
    todo = set(args.only or ["A", "B", "C"])
    t = basin_table()
    t.round(3).to_csv(args.out / "poster_A_basins.csv", encoding="utf-8-sig")
    main_w, sens_w = wamis_tables()
    st = sens_table()
    st.round(2).to_csv(args.out / "poster_B_sens.csv", encoding="utf-8-sig")
    if "A" in todo:
        fig_a(t, args.out / "poster_A_sar_basins.png")
    if "B" in todo:
        fig_b(main_w, sens_w, st, args.out / "poster_B_sar_wamis.png")
    if "C" in todo:
        fig_c(args.out / "poster_C_s2_pixel.png")
    print(t[["jul_pct", "aug_pct", "aug_w25", "aug_w26"]].to_string())
    print(st.round(1).to_string())
    print(f"→ {args.out}")


if __name__ == "__main__":
    main()
