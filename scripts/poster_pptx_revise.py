# -*- coding: utf-8 -*-
"""poster_pptx_revise — 원탐학회 포스터 원고(KSRS-131_유하은.pptx)를 현재 기준으로 고친 판을 만든다 (2026-10-15).

현재 기준 = 순위로 가뭄을 판정하지 않는다(WAMIS 는 댐별 10년 기록, 정부는 보도자료 자체) + v11 확정 수치
(gee docs/DROUGHT_2026_EVIDENCE_KR.md · S1 docs/drought/REVIEW_20261005_KR.md §2-2). 원본은 읽기만 한다.

    v12  Introduction 둘째 줄 · Study area 「연구 자료」 · Table 1(순위 열 → 댐별 10년 기록 대비, 표준 중앙값) ·
         Methods(11m → 10 m, Edge-Otsu → Otsu — γ⁰ 수식 대체콘텐츠라 XML 에서 직접) · 왼쪽 Results(메모 → Table 2 +
         Fig. 1 + 각주) · 오른쪽 그림 캡션 · Conclusion
    v13  v12 + 오른쪽 Results 칸: 유역별 S2 그림 4장 → 꺾은선(Fig. 2) · 남부 지도(Fig. 3) · S2 합본(Fig. 4) · 비교 설계(Fig. 5)

사용자가 직접 넣은 것(Introduction 의 Sentinel-2 취소선, 슬라이드 밖 작업용 표)은 건드리지 않는다.
그림은 scripts/poster_kit.py 산출(S1_SAR_그림_20261015) 을 쓴다. 렌더 검수는 PowerPoint COM(Slide.Export).

    F:\envs\gis_clean\python.exe scripts\poster_pptx_revise.py --variant v13 --pylib <python-pptx 경로>
"""
import argparse
import copy
import shutil
import sys
import zipfile
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--variant", choices=["v12", "v13"], default="v13")
ap.add_argument("--pylib", type=Path, help="python-pptx 가 있는 site-packages (뒤에 붙인다)")
ap.add_argument("--dir", type=Path, default=Path(r"E:\~K-water_지상국61021_원탐학회"))
ARGS = ap.parse_args()
if ARGS.pylib:
    sys.path.append(str(ARGS.pylib))
sys.stdout.reconfigure(encoding="utf-8")
from pptx import Presentation  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402
from pptx.util import Cm  # noqa: E402

DIR = ARGS.dir
SRC = DIR / "KSRS-131_유하은.pptx"
DST = DIR / {"v12": "KSRS-131_유하은_v12_현재기준.pptx", "v13": "KSRS-131_유하은_v13_그림합본.pptx"}[ARGS.variant]
FIG1 = DIR / "S1_SAR_그림_20261015" / "그림4_SAR면적_WAMIS저수량_민감도.png"
HI = "C4400A"
M = "−"

prs = Presentation(SRC)
slide = prs.slides[0]
tree = slide.shapes._spTree


def by_id(i):
    return next(s for s in slide.shapes if s.shape_id == i)


def next_id():
    ids = [int(e.get("id")) for e in tree.iter(qn("p:cNvPr"))]
    return max(ids) + 1


def first_rpr(p):
    r = p.find(qn("a:r"))
    if r is not None and r.find(qn("a:rPr")) is not None:
        return copy.deepcopy(r.find(qn("a:rPr")))
    e = p.find(qn("a:endParaRPr"))
    rp = copy.deepcopy(e) if e is not None else None
    if rp is not None:
        rp.tag = qn("a:rPr")
    return rp


def set_color(rpr, hexcol):
    for f in rpr.findall(qn("a:solidFill")):
        rpr.remove(f)
    sf = rpr.makeelement(qn("a:solidFill"), {})
    c = (sf.makeelement(qn("a:schemeClr"), {"val": "tx1"}) if hexcol == "tx1"
         else sf.makeelement(qn("a:srgbClr"), {"val": hexcol}))
    sf.append(c)
    # solidFill 은 ln 다음, latin/ea 앞이어야 한다
    anchor = None
    for tag in ("a:effectLst", "a:highlight", "a:latin", "a:ea", "a:cs", "a:sym"):
        anchor = rpr.find(qn(tag))
        if anchor is not None:
            break
    if anchor is not None:
        anchor.addprevious(sf)
    else:
        rpr.append(sf)


def fill_paras(txBody, lines, size=None, bold=None, color=None, tmpl_p=None):
    """txBody 의 문단을 lines 로 바꾼다 — 첫 문단의 pPr·rPr 을 본으로 쓴다."""
    ps = txBody.findall(qn("a:p"))
    tp = copy.deepcopy(tmpl_p if tmpl_p is not None else ps[0])
    rpr0 = first_rpr(tp)
    for p in ps:
        txBody.remove(p)
    for ln in lines:
        p = copy.deepcopy(tp)
        for ch in list(p):
            if ch.tag in (qn("a:r"), qn("a:br"), qn("a:fld"), qn("a:endParaRPr")) or ch.tag.endswith("}m") \
                    or "AlternateContent" in ch.tag:
                p.remove(ch)
        segs = ln if isinstance(ln, list) else [(ln, None)]
        for txt, col in segs:
            r = p.makeelement(qn("a:r"), {})
            rp = copy.deepcopy(rpr0) if rpr0 is not None else r.makeelement(qn("a:rPr"), {"lang": "ko-KR"})
            if size:
                rp.set("sz", str(int(size * 100)))
            if bold is not None:
                rp.set("b", "1" if bold else "0")
            for a in ("strike", "u", "i"):
                rp.attrib.pop(a, None)
            if col or color:
                set_color(rp, col or color)
            r.append(rp)
            t = r.makeelement(qn("a:t"), {})
            t.text = txt
            r.append(t)
            p.append(r)
        txBody.append(p)


def set_cell(cell, text, color=None):
    fill_paras(cell._tc.txBody, text.split("\n"), color=color)


def clone(shape, name):
    el = copy.deepcopy(shape._element)
    cnv = el.find(".//" + qn("p:cNvPr"))
    cnv.set("id", str(next_id()))
    cnv.set("name", name)
    tree.append(el)
    return next(s for s in slide.shapes if s._element is el)


def place(sh, x, y, w=None, h=None):
    sh.left, sh.top = Cm(x), Cm(y)
    if w is not None:
        sh.width = Cm(w)
    if h is not None:
        sh.height = Cm(h)


# ── 1. Introduction 둘째 글머리 ─────────────────────────────
intro = by_id(71).text_frame._txBody
ps = intro.findall(qn("a:p"))
new_p = copy.deepcopy(ps[1])
tmp = new_p.makeelement(qn("p:txBody"), {})
tmp.append(new_p)
fill_paras(tmp, ["WAMIS 댐별 10년(2017~2026) 저수위 기록과 정부 가뭄 예·경보로 남부 대권역(낙동강·금강·섬진강·영산강)의 "
                 "2026년 여름 가뭄을 확인"])
ps[1].addprevious(tmp.find(qn("a:p")))
intro.remove(ps[1])

# ── 2. Study area 「연구 자료」 ────────────────────────────
for r in by_id(102).text_frame.paragraphs[6].runs:
    if r.text == "수위":
        r.text = "저수위·저수량"

# ── 3. Table 1 — 순위 열 → 댐별 10년 기록 대비 ─────────────
t1 = by_id(11)
T1 = [["저수지", "경보단계", "10년 중앙값\n(EL.m)", "Aug-25\n(EL.m)", "Aug-26\n(EL.m)", "중앙값 대비 (m)\n2025 / 2026",
       "10년 기록에서\n2026"],
      ["안동호", "주의", "148.06", "145.66", "143.17", f"{M}2.40 / {M}4.89", "10년 최저"],
      ["임하호", "주의", "151.66", "153.81", "147.81", f"+2.15 / {M}3.85", "2022년 다음"],
      ["밀양호", "경계", "198.07", "200.49", "179.25", f"+2.42 / {M}18.82", "10년 최저"],
      ["영천호", "주의", "152.20", "153.71", "145.38", f"+1.51 / {M}6.82", "2022년 다음"],
      ["성덕저수지", "주의", "357.32", "357.57", "346.05", f"+0.25 / {M}11.27", "10년 최저"],
      ["운문호", "심각", "142.76", "144.56", "131.86", f"+1.80 / {M}10.90", "2022년 다음"],
      ["섬진강댐", "경계", "184.05", "189.31", "173.87", f"+5.26 / {M}10.18", "10년 최저"],
      ["평림호", "주의", "107.17", "109.69", "105.96", f"+2.52 / {M}1.22", "중앙값 아래"]]
tb = t1.table
for i, row in enumerate(T1):
    for j, v in enumerate(row):
        set_cell(tb.cell(i, j), v, color=HI if (i > 0 and v == "10년 최저") else None)
for j, w in enumerate([4.4, 3.4, 4.6, 3.8, 3.8, 6.6, 5.4]):
    tb.columns[j].width = Cm(w)
t1.width = Cm(32.0)
cap1 = by_id(8)
fill_paras(cap1.text_frame._txBody, ["Table 1. WAMIS 8월 평균 저수위 — 댐별 10년(2017~2026) 기록 대비와 가뭄 예·경보 단계(8.10 발표)"])
place(cap1, 3.7, 49.3, 36.8, 1.2)

# ── 4. Results(왼쪽) — 메모 제거 → Table 2 · Fig. 1 · 각주 ───
for sid in (2242, 58):                       # 붙여 둔 메모 글상자 · 「Fig.4.」 자리표시
    e = by_id(sid)._element
    e.getparent().remove(e)

cap2 = clone(cap1, "Table 2 캡션")
fill_paras(cap2.text_frame._txBody, ["Table 2. 본문 8개 댐유역 SAR 수체 면적 변화(2025→2026, 동일 상대궤도 1:1 쌍)와 "
                                     "저수지 SAR 면적 · WAMIS 저수량 Δ%(8월)"])
place(cap2, 3.2, 84.0, 36.8, 1.9)

t2 = clone(t1, "Table 2")
tbl2 = t2.table
tr_body = tbl2._tbl.findall(qn("a:tr"))[-1]
tbl2._tbl.append(copy.deepcopy(tr_body))          # 9 → 10 줄 (요약 줄)
T2 = [["댐유역", "SAR 유역\n7월 Δ%", "SAR 유역\n8월 Δ%", "8월 유역 수체 km²\n2025 → 2026 (Δkm²)", "저수지 SAR\n8월 Δ%",
       "WAMIS 저수량\n8월 Δ%", "k_eff"],
      ["안동 ⓒ", f"{M}12.7", f"{M}7.8", f"35.02 → 32.27 ({M}2.75)", f"{M}10.9", f"{M}17.1", "1.62"],
      ["임하", f"{M}13.2", f"{M}7.1", f"19.74 → 18.35 ({M}1.39)", f"{M}2.9", f"{M}30.5", "12.31"],
      ["밀양", f"{M}24.8", f"{M}26.3", f"1.73 → 1.28 ({M}0.45)", f"{M}25.0", f"{M}55.3", "2.80"],
      ["영천", f"{M}13.5", f"{M}22.7", f"5.14 → 3.98 ({M}1.16)", f"{M}9.5", f"{M}54.9", "8.01"],
      ["성덕 †", f"{M}25.7", f"{M}27.1", f"0.91 → 0.66 ({M}0.25)", f"{M}26.6", f"{M}55.9", "2.65"],
      ["운문", f"{M}26.7", f"{M}25.9", f"5.89 → 4.36 ({M}1.53)", f"{M}15.7", f"{M}57.8", "5.04"],
      ["섬진강", f"{M}20.0", f"{M}27.7", f"19.93 → 14.40 ({M}5.53)", f"{M}32.5", f"{M}65.8", "2.73"],
      ["평림 †", "제외 ⓕ", f"{M}4.7", f"0.61 → 0.59 ({M}0.03)", f"{M}3.2", f"{M}34.3", "13.00"],
      ["범위", "", "", "", "", "", "8/8 > 1"]]
for i, row in enumerate(T2):
    for j, v in enumerate(row):
        set_cell(tbl2.cell(i, j), v, color=None if i == 0 else (HI if j == 2 else "tx1"))
tbl2.cell(9, 1).merge(tbl2.cell(9, 5))           # 요약 줄은 칸을 합쳐 한 줄로
set_cell(tbl2.cell(9, 1), f"7월 {M}12.7 ~ {M}26.7% (7/8)   ·   8월 {M}4.7 ~ {M}27.7% (8/8)", color=HI)
for j, w in enumerate([4.6, 4.0, 4.0, 9.7, 4.7, 5.8, 3.6]):
    tbl2.columns[j].width = Cm(w)
place(t2, 3.2, 86.1, 36.4)

pic = slide.shapes.add_picture(str(FIG1), Cm(4.5), Cm(96.0), width=Cm(34.0))
pic.name = "Fig. 1 SAR면적-WAMIS저수량"

cap3 = clone(cap1, "Fig. 1 캡션")
fill_paras(cap3.text_frame._txBody, ["Fig. 1. (a) 저수지 SAR 면적 Δ% ↔ WAMIS 저수량 Δ%(같은 쌍·같은 시각, 음영 = 하한) — "
                                     "32칸 중 30칸 하한. (b) 8월 DESC134 S1C↔S1C 민감도 4쌍 — 20칸 모두 감소, 본쌍이 가장 보수적."])
place(cap3, 3.2, 111.4, 36.6, 1.9)

note = clone(cap1, "Results 각주")
fill_paras(note.text_frame._txBody,
           ["ⓒ 안동은 2025년 8월도 10년 중앙값보다 2.4 m 낮아 Δ%가 작게 보임(2026년은 10년 최저). † 수체 1 km² 미만 — Δkm² 병기. "
            "ⓕ 평림 7월은 두 해 임계가 달라 제외(같은 임계 적용 시 +0.2~+0.7%). 쌍: 7월 ASC54 0725↔0715 · DESC134 0718↔0720"
            "(섬진강), 8월 ASC54 0806↔0802 · ASC127 0811↔0807(섬진강·평림). k_eff = 저수량 Δ% ÷ 저수지 SAR 면적 Δ%. "
            "2025년 8월은 8곳 중 7곳이 10년 중앙값 위(전년도 다우) → 전년 대비 Δ%가 평년 대비보다 크게 보임. "
            "*장성호: 8개 댐 밖 대조 저수지."],
           size=15, bold=False)
place(note, 3.2, 113.6, 36.6, 3.9)

# ── 5. Results(오른쪽) 그림 캡션 ─────────────────────────────
cap4 = by_id(37)
fill_paras(cap4.text_frame._txBody, ["Fig. 2. 8월 공통 유효화소 85% 이상 4개 유역의 SAR(γ⁰ VH)·S2(RGB) 수체 변화 화소 대응 — "
                                     "SAR 소실 화소의 74~87%를 S2도 소실로 판정(영천·운문·밀양). SAR 2025-08-06↔2026-08-02, "
                                     "S2 2025-08-01↔2026-08-06(운문 08-01)."], size=18)
place(cap4, 43.6, 101.0, 37.6, 2.9)

# ── 6. Conclusion ────────────────────────────────────────────
conc = by_id(119)
fill_paras(conc.text_frame._txBody,
           [f"2026년 여름 남부 가뭄은 WAMIS 댐별 10년 기록(8개 댐 모두 10년 중앙값 아래, 4곳 10년 최저)과 정부 가뭄 "
            f"예·경보(8개 댐 모두 단계 발령)로 확인되는 이례적 사례였다.",
            f"Sentinel-1 SAR는 8개 댐유역의 수체 감소(8월 8/8, {M}4.7 ~ {M}27.7%)를 관측했으며, 면적 감소는 저수량 감소의 "
            f"하한(32칸 중 30칸)으로 동일 위성 민감도에서도 유지되었다.",
            "Sentinel-2는 맑은 조건에서 SAR 수체 변화의 방향과 위치를 확인했다(SAR 소실 화소의 74~87%)."],
           size=22, bold=False)
place(conc, 43.7, 108.2, 37.2, 6.6)

if ARGS.variant == "v13":
    from PIL import Image
    # ── v13: 오른쪽 Results 칸 — S2 그림 4장 → 합본 1장 + 꺾은선 · 남부 지도 · 비교 설계 ──
    FIGDIR = DIR / "S1_SAR_그림_20261015"
    for sid in (2283, 2275, 2281, 2279):                 # 유역별 S2 화소대응 4장
        e = by_id(sid)._element
        e.getparent().remove(e)

    X0, W = 43.8, 37.4                                   # 오른쪽 칸 안쪽
    TOP, BOTTOM = 20.5, 103.9
    RIGHT = [
        ("그림1_WAMIS_8월저수위_10년추이.png",
         "Fig. 2. 8개 저수지 8월 평균 저수위(WAMIS, 2017~2026). 주황 = 2025→2026, 점선 = 각 댐의 10년 중앙값 — "
         "2026년은 8곳 모두 중앙값 아래(4곳 10년 최저, 3곳 2022년 다음).", 2),
        ("그림2_남부지도_WAMIS10년기록_SAR댐유역.png",
         "Fig. 3. (a) 2026년 8월 WAMIS 저수위의 댐별 10년 기록 대비와 8월 가뭄 예·경보 단계, "
         "(b) 같은 댐유역의 SAR 수체 면적 Δ%(2025→2026, 8월).", 2),
        ("그림5_SAR_S2_화소대응.png",
         "Fig. 4. 8월 공통 유효화소 85% 이상 4개 유역의 SAR·S2 수체 변화 화소 대응 — SAR 소실 화소의 74~87%를 S2도 "
         "소실로 판정(영천·운문·밀양). SAR 2025-08-06↔2026-08-02, S2 2025-08-01↔2026-08-06(운문 08-01).", 3),
        ("그림6_관측쌍_타임라인_강우.png",
         "Fig. 5. 비교 설계 — 동일 상대궤도 1:1 관측쌍(본쌍·민감도 4쌍·건조 대조)과 쌍 대상 권역의 직전 5일 강우(mm).", 2),
    ]
    LINE = 0.82                                           # 18 pt 캡션 한 줄 높이(cm)
    blocks = []
    for fn, cap, nl in RIGHT:
        w, h = Image.open(FIGDIR / fn).size
        blocks.append((fn, cap, W * h / w, nl * LINE + 0.2))
    content = sum(b[2] + b[3] for b in blocks)
    gap = (BOTTOM - TOP - content) / len(blocks)
    y = TOP
    for k, (fn, cap, ih, ch) in enumerate(blocks):
        pic = slide.shapes.add_picture(str(FIGDIR / fn), Cm(X0), Cm(y), width=Cm(W))
        pic.name = cap.split(".")[0] + ". " + fn.split("_")[0]
        y += ih + 0.15
        c = cap4 if k == 2 else clone(cap4, f"Fig. {k + 2} 캡션")
        fill_paras(c.text_frame._txBody, [cap], size=18)
        place(c, X0, y, W, ch)
        y += ch + gap
    print(f"오른쪽 칸: 그림 {content:.1f} cm · 간격 {gap:.2f} cm")

prs.save(DST)

# ── 7. Methods(수식 대체 콘텐츠 안) — XML 에서 직접 ─────────
tmp = DST.with_suffix(".tmp.pptx")
shutil.move(DST, tmp)
with zipfile.ZipFile(tmp) as zin, zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED) as zout:
    for it in zin.infolist():
        data = zin.read(it.filename)
        if it.filename == "ppt/slides/slide1.xml":
            x = data.decode("utf-8")
            n1 = x.count("<a:t>11m </a:t>"); n2 = x.count("<a:t>Edge-Otsu</a:t>")
            assert n1 == 1 and n2 == 1, (n1, n2)
            x = x.replace("<a:t>11m </a:t>", "<a:t>10 m </a:t>").replace("<a:t>Edge-Otsu</a:t>", "<a:t>Otsu</a:t>")
            data = x.encode("utf-8")
        zout.writestr(it, data)
tmp.unlink()
print("→", DST)
