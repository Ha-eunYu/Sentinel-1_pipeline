# -*- coding: utf-8 -*-
"""poster_fig4_render — 그림 4 「SAR 소실 구역 ↔ 광학 변화 화소 대응」 렌더러.

입력은 S2 `s2_dam8_sar_xval.py --export-npz <DIR>` 가 낸 댐별 `fig4_<댐>.npz` 뿐이다.
래스터·JP2·S2 모듈을 읽지 않으므로 numpy + matplotlib 만 있으면 된다(gis_clean 불필요).
문서: S1 `docs/drought/FIG4_SAR_S2_PIXEL_KR.md`

산출 (--out)
    그림4_<댐>_SAR소실구역_광학변화_화소대응.png            2행(SAR γ0·S2) × 3열(2025·2026·변화)
    그림4_<댐>_SAR소실구역_광학변화_화소대응_행열반전.png    3행(2025·2026·변화) × 2열(SAR·S2)
    그림4_SAR소실구역_광학변화_화소대응.png                 85% 통과 4곳 합본(2행×3열 블록을 세로로)
    그림4_SAR소실구역_광학변화_화소대응_행열반전.png        85% 통과 4곳 합본(3행×2열 블록을 가로로)

실행
    python poster_fig4_render.py --data <S2>/results/S2_DAM8_XVAL/aug_a_ws/figdata \
        --out <폴더> --label "SAR v11 0806-0802 · S2 0801-0806"

⚠ 이 파일은 S2 `s2_dam8_sar_xval.py` 의 그림 함수(`_panels_2x3`·`dam_figure_2x3`·
  `dam_figure_3x2`·`poster_figure`·`poster_figure_t`)를 npz 입력으로 옮긴 **스냅샷**이다.
  그림 규약(색·회색조 범위·라벨)을 바꿀 때는 S2 쪽이 정본이고 이 파일을 맞춘다.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

# 0 흰색 · 1 유지(파랑) · 2 소실(주황) · 3 신규(초록) — SAR·S2 같은 색
CHANGE_COLORS = ["#ffffff", "#2c7fb8", "#e6550d", "#31a354"]
GAMMA_VMIN, GAMMA_VMAX = -25.0, -8.0     # γ0 VH dB 회색조 범위(어두울수록 수면)
ROW_LABELS_T = ("2025", "2026", "변화")
NAME = "그림4_{}SAR소실구역_광학변화_화소대응"


def set_korean_font() -> None:
    have = {f.name for f in fm.fontManager.ttflist}
    for name in ("Malgun Gothic", "Gulim", "Batang", "NanumGothic", "AppleGothic"):
        if name in have:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False     # U+2212 글리프 없음
            return
    print("⚠ 한글 폰트를 못 찾았다 — 라벨이 깨질 수 있다")


def load(path: Path) -> dict:
    z = np.load(path, allow_pickle=False)
    m = [str(x) for x in z["meta"]]
    return {"dam": m[0], "main": m[1] == "True", "d25": m[2], "d26": m[3],
            "g25": m[4], "g26": m[5], "stage": m[6], "sar_dpct": m[7], "s2_dpct": m[8],
            "ring_m": m[9], "mask": m[10],
            "sar": z["sar_change"], "s2": z["s2_change"], "gam25": z["gamma25"],
            "gam26": z["gamma26"], "rgb25": z["rgb25"], "rgb26": z["rgb26"]}


def panels(axs: np.ndarray, r: dict, ts: float = 10) -> None:
    """axs 는 2×3: 행 SAR·S2, 열 2025·2026·변화. 행열 반전은 `axs.T` 를 넘긴다."""
    cmap = ListedColormap(CHANGE_COLORS)
    for ax, a, d in ((axs[0][0], r["gam25"], r["g25"]), (axs[0][1], r["gam26"], r["g26"])):
        ax.imshow(np.ma.masked_invalid(a), cmap="gray", vmin=GAMMA_VMIN, vmax=GAMMA_VMAX,
                  interpolation="nearest")
        ax.set_title(f"SAR γ0 VH {d[:4]}-{d[4:6]}-{d[6:]}", fontsize=ts)
    axs[0][2].imshow(r["sar"], cmap=cmap, vmin=0, vmax=3, interpolation="nearest")
    axs[0][2].set_title(f"SAR 변화  {r['sar_dpct']}%", fontsize=ts)
    for ax, img, d in ((axs[1][0], r["rgb25"], r["d25"]), (axs[1][1], r["rgb26"], r["d26"])):
        ax.imshow(img, interpolation="nearest")
        ax.set_title(f"S2 RGB {d[:4]}-{d[4:6]}-{d[6:]}", fontsize=ts)
    s2 = np.ma.masked_where(r["s2"] == 255, r["s2"])     # 255 = 평가 밖 → 회색 바탕
    axs[1][2].set_facecolor("#cccccc")
    axs[1][2].imshow(s2, cmap=cmap, vmin=0, vmax=3, interpolation="nearest")
    axs[1][2].set_title(f"S2 변화 (MNDWI>0 고정)  {r['s2_dpct']}%", fontsize=ts)
    for a in axs.ravel():
        a.set_xticks([]); a.set_yticks([])


def legend_and_foot(fig, y_leg: float, r: dict | None = None) -> None:
    fig.legend(handles=[Patch(color=c, label=l) for c, l in
                        zip(CHANGE_COLORS[1:] + ["#cccccc"],
                            ["유지", "소실", "신규", "S2 평가 밖 (SCL 제외)"])],
               loc="lower center", bbox_to_anchor=(0.5, y_leg), ncol=4, fontsize=10,
               frameon=False)
    ring = r["ring_m"] if r else "100"
    mask = f" · 마스크 {r['mask']}" if r and r["mask"] else ""
    fig.text(0.5, 0.004, ha="center", va="bottom", s=
             f"S2 변화: MNDWI>0 두 해 고정 임계{mask} · 평가 영역 = 본 저수지 {ring} m 띠.  "
             "가뭄 단계 = 정부 가뭄 예·경보 2026-08-01.\n"
             "Δ% 는 평가 영역 안 같은 화소에서 낸 값이라 유역 CSV 와 다르다.  "
             f"γ0 VH: SNAP RTC dB, 회색조 {GAMMA_VMIN:.0f}~{GAMMA_VMAX:.0f} dB(어두울수록 수면).",
             fontsize=8.5, color="#444")


def ylabel(ax, text: str, fs: float = 12) -> None:
    ax.set_ylabel(text, fontsize=fs, rotation=0, ha="right", va="center", labelpad=10)


def title_of(r: dict) -> str:
    return r["dam"] + (f" (가뭄 {r['stage']})" if r["stage"] else "")


def dam_2x3(r: dict, out: Path, label: str) -> None:
    fig, axs = plt.subplots(2, 3, figsize=(12, 8.2), dpi=200, squeeze=False)
    panels(axs, r)
    ylabel(axs[0][0], title_of(r).replace(" (", "\n(") + "\n\nSAR")
    ylabel(axs[1][0], "S2 (EO)")
    fig.suptitle(f"{r['dam']}  SAR 수체 소실 구역 ↔ 광학 변화  (8월 · {label})", fontsize=13)
    legend_and_foot(fig, 0.06, r)
    fig.tight_layout(rect=(0, 0.09, 1, 0.95))
    fig.savefig(out, facecolor="white"); plt.close(fig)


def dam_3x2(r: dict, out: Path, label: str) -> None:
    fig, axs = plt.subplots(3, 2, figsize=(8.6, 12.4), dpi=200, squeeze=False)
    panels(axs.T, r)
    for i, lab in enumerate(ROW_LABELS_T):
        ylabel(axs[i][0], lab, 13)
    fig.suptitle(f"{title_of(r)}  SAR 수체 소실 구역 ↔ 광학 변화  (8월 · {label})", fontsize=12)
    legend_and_foot(fig, 0.055, r)
    fig.tight_layout(rect=(0, 0.1, 1, 0.96))
    fig.savefig(out, facecolor="white"); plt.close(fig)


def poster_stacked(rows: list[dict], out: Path, label: str) -> None:
    """4곳 × (2행×3열) 세로 적층."""
    fig, axs = plt.subplots(2 * len(rows), 3, figsize=(12, 7.4 * len(rows)), dpi=200,
                            squeeze=False)
    for i, r in enumerate(rows):
        panels(axs[2 * i:2 * i + 2], r)
        ylabel(axs[2 * i][0], title_of(r).replace(" (", "\n(") + "\n\nSAR")
        ylabel(axs[2 * i + 1][0], "S2 (EO)")
    fig.suptitle(f"SAR 수체 소실 구역 ↔ 광학 변화  (8월, 공통 유효화소 85% 이상 {len(rows)}개 "
                 f"유역 · {label})", fontsize=13)
    legend_and_foot(fig, 0.022, rows[0])
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    fig.savefig(out, facecolor="white"); plt.close(fig)


def poster_wide(rows: list[dict], out: Path, label: str) -> None:
    """4곳 × (3행×2열) 가로 나열. 열 폭을 저수지 창 가로세로비에 맞춰 행이 어긋나지 않게."""
    n = len(rows)
    asp = [r["sar"].shape[1] / r["sar"].shape[0] for r in rows]
    ratios = [a for a in asp for _ in (0, 1)]
    h_in = 3.4
    fig = plt.figure(figsize=(h_in * sum(ratios) + 1.6, 3 * h_in + 2.6), dpi=200)
    gs = fig.add_gridspec(3, 2 * n, width_ratios=ratios, wspace=0.04, hspace=0.16,
                          left=1.0 / fig.get_figwidth(), right=0.995,
                          top=1 - 1.25 / fig.get_figheight(), bottom=1.3 / fig.get_figheight())
    axs = np.array([[fig.add_subplot(gs[i, j]) for j in range(2 * n)] for i in range(3)])
    for i, r in enumerate(rows):
        panels(axs[:, 2 * i:2 * i + 2].T, r, 9)
        p0, p1 = axs[0][2 * i].get_position(), axs[0][2 * i + 1].get_position()
        fig.text((p0.x0 + p1.x1) / 2, p0.y1 + 0.5 / fig.get_figheight(), title_of(r),
                 ha="center", va="bottom", fontsize=13)
    for k, lab in enumerate(ROW_LABELS_T):
        ylabel(axs[k][0], lab, 13)
    fig.suptitle(f"SAR 수체 소실 구역 ↔ 광학 변화  (8월, 공통 유효화소 85% 이상 {n}개 유역 · "
                 f"{label})", fontsize=13, y=0.985)
    legend_and_foot(fig, 0.055, rows[0])
    fig.savefig(out, facecolor="white"); plt.close(fig)


MAIN_ORDER = ["영천", "성덕", "운문", "밀양"]       # 8월 공통 유효화소 85% 통과 4곳


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, required=True, help="fig4_<댐>.npz 가 있는 폴더")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--label", default="SAR v11 0806-0802 · S2 0801-0806")
    args = ap.parse_args()
    set_korean_font()
    args.out.mkdir(parents=True, exist_ok=True)
    rows = {p.stem.removeprefix("fig4_"): load(p) for p in sorted(args.data.glob("fig4_*.npz"))}
    if not rows:
        raise SystemExit(f"npz 없음: {args.data}")
    for dam, r in rows.items():
        dam_2x3(r, args.out / (NAME.format(dam + "_") + ".png"), args.label)
        dam_3x2(r, args.out / (NAME.format(dam + "_") + "_행열반전.png"), args.label)
        print("  ", dam)
    main4 = [rows[d] for d in MAIN_ORDER if d in rows]
    if main4:
        poster_stacked(main4, args.out / (NAME.format("") + ".png"), args.label)
        poster_wide(main4, args.out / (NAME.format("") + "_행열반전.png"), args.label)
    print(f"→ {args.out}")


if __name__ == "__main__":
    main()
