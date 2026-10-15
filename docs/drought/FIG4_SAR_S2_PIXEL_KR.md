# 그림 4 — SAR 소실 구역 ↔ 광학 변화 화소 대응 (제작 파이프라인)

2026-10-15 · S2 세션 작성 · 포스터(2026 원탐학회, 10-22) 그림 4.
S2 근거 문서: `S2/docs/POSTER_S2_EVIDENCE_KR.md` §4. 이 문서는 **그림을 다시 뽑는 법**만 적는다.

## 1. 한눈에

| | |
|---|---|
| 무엇을 보여주나 | SAR(v11)이 「소실」이라 한 화소에서 S2 광학도 물→뭍으로 바뀌었는가. 2025·2026 γ0 VH, RGB, 변화 구역을 같은 창에 놓는다. |
| 대상 | 8월 공통 유효화소 85% 통과 4곳 **영천·성덕·운문·밀양**(본론) + 안동·임하(참고, 포스터 미사용) |
| SAR 쌍 | 2025-08-06 ↔ 2026-08-02 (ASC54, v11 EGM 켬) |
| S2 쌍 | 2025-08-01 ↔ 2026-08-06 (밀양만 2026-08-06; 나머지 2026은 PAIRS — 운문 08-01) |
| 정본 코드 | `S2/s2_dam8_sar_xval.py` (계산 + 그림) |
| 렌더러 | `S1/scripts/poster_fig4_render.py` (npz 만 읽는 그림 전용 스냅샷) |
| 산출 | `S2/results/S2_DAM8_XVAL/aug_a_ws/` — `그림4_*.png`, `xval_aug_a_ws.csv`, `figdata/fig4_<댐>.npz` |

## 2. 파이프라인

```
[gee] watershed_change --save-tif ──► v11_s2xval/aug_a/tif_watershed/D_<댐>_change_10m.tif  (1 유지·2 소실·3 신규·0 nodata)
                                  └─► v11_s2xval/aug_a/tif_db_watershed/D_<댐>_{20250806,20260802}_db_10m.tif  (γ0 VH dB)
[S2]  results/S2_DAM8_AUG/<댐>_<YYYYMMDD>_{MNDWI,RGB,NDVI}.tif  (같은 EPSG:5179 10 m 유역 클립 격자)
          │
          ▼  s2_dam8_sar_xval.py --water-safe --export-npz …/figdata
      ① SAR 수체 근방(RING 100 m 띠)으로 창을 자른다 → ② 2025 수면끼리 ±6 화소 IoU 로 위치 정합을 잰다
      ③ S2 변화 = MNDWI>0 두 해 고정 임계(Otsu 안 씀) ④ 본 저수지(SAR 2025 수면 최대 연결성분)+100 m 띠에서 교차표
          │
          ├─► xval_aug_a_ws.csv            (일치율·Δ%·정합 이동 — 캡션 수치의 출처)
          ├─► 그림4_*.png                   (S2 쪽 그림 함수)
          └─► figdata/fig4_<댐>.npz         (그림 입력: 저수지 창으로 자른 배열)
                    │
                    ▼  S1/scripts/poster_fig4_render.py
              그림4_*.png  (래스터·JP2 없이 재현 — 서식만 고칠 때)
```

### 실행

```powershell
# (1) 계산 + S2 쪽 그림 + npz  — gis_clean, JP2 를 읽으므로 메모리 주의(GB 단위 → S1 창 절차)
$env:GDAL_DATA = "F:\envs\gis_clean\Library\share\gdal"
cd F:\06_SAR_system\S2
& F:\envs\gis_clean\python.exe s2_dam8_sar_xval.py --tag aug_a_ws --water-safe `
    --label "SAR v11 0806-0802 · S2 0801-0806" `
    --export-npz results\S2_DAM8_XVAL\aug_a_ws\figdata

# (2) 그림만 다시 — numpy+matplotlib 만 필요(수 초)
& F:\envs\gis_clean\python.exe F:\06_SAR_system\S1\scripts\poster_fig4_render.py `
    --data F:\06_SAR_system\S2\results\S2_DAM8_XVAL\aug_a_ws\figdata `
    --out  F:\06_SAR_system\S2\results\S2_DAM8_XVAL\aug_a_ws
```

`--only 영천 …` 로 일부만 돌리면 CSV 는 `_partial.csv` 로 따로 쓴다. 전체(6곳)를 돌려도 CSV 값은 같다(2026-10-15 바이트 비교).

## 3. 그림 규약

- **구성** 댐당 2행(SAR γ0 VH · S2 EO) × 3열(2025 · 2026 · 변화). 행열 반전판은 3행(2025·2026·변화) × 2열(SAR · S2).
- **합본** 4곳: 세로 적층(2행×3열 블록) / 가로 나열(3행×2열 블록, 열 폭을 저수지 창 가로세로비에 맞춤).
- **색** 유지 파랑 `#2c7fb8` · 소실 주황 `#e6550d` · 신규 초록 `#31a354` · S2 평가 밖 회색 `#cccccc`.
- **γ0** 회색조 −25 ~ −8 dB, 어두울수록 수면. 흰색 = 자료 없음.
- **왼쪽 라벨** 가로(rotation=0). 댐 이름 + 가뭄 단계(정부 예·경보 2026-08-01: 운문 심각·밀양 경계·영천·성덕·안동·임하 주의).
- **그림에 일치율을 싣지 않는다** — 제목 옆에는 SAR Δ%·S2 Δ% 만. 일치율은 캡션·본문에 영천·운문·밀양 셋만 인용(성덕 30.2% 는 수체 0.66 km² 라 1화소 정합이 비율을 흔들어 인용하지 않기로 함, gee-f0 6966d4f).

## 4. 캡션에 쓸 수치 (`xval_aug_a_ws.csv`, 본 저수지 띠)

| 댐 (가뭄 단계) | 정합 이동(행,열) | IoU 2025 | SAR Δ% | S2 Δ% | SAR 소실 → S2 소실 | S2 소실 → SAR 유지 |
|---|---|---:|---:|---:|---:|---:|
| 영천 (주의) | (−1, +1) | 0.89 | −21.7 | −30.8 | **79.2%** | 34.7% |
| 성덕 (주의) | (0, +1) | 0.76 | −17.8 | −22.3 | 30.2% (인용 안 함) | 62.2% |
| 운문 (심각) | (−1, 0) | 0.90 | −26.0 | −33.4 | **87.1%** | 22.4% |
| 밀양 (경계) | (−1, 0) | 0.83 | −23.3 | −36.4 | **73.8%** | 42.9% |
| 안동 (주의) · 참고 | (−1, 0) | 0.83 | −9.4 | −20.3 | 69.3% | 47.1% |
| 임하 (주의) · 참고 | (−1, +1) | 0.77 | −3.4 | −19.8 | 38.6% | 71.0% |

Δ% 는 평가 영역 안 **같은 화소 집합**에서 낸 값이라 유역 CSV(`s2_dam8_clip_stats`)와 다르다.

## 5. 함정 (이 그림에서 실제로 났던 것)

1. **밀양 날짜** — 2026-08-01 은 유역 88% 청명이나 SAR 수면 위 71% 가 SCL THIN_CIRRUS. 화소 대응만 08-06 을 쓴다(`XVAL_DATES`). 유역평균 ΔMNDWI 의 날짜는 그대로.
2. **수면 보존 마스크(`--water-safe`)** — 정본 SCL 제외{2,7 포함}는 맑은 저수지의 어두운 수면(DARK·UNCLASSIFIED)을 4~32% 지운다. 화소 대응만 구름·그림자·권운·눈·무효{0,1,3,8,9,10,11}만 지운다.
3. **음수 반사도** — `s2_common.to_reflectance` 가 음수를 NaN 으로 지워 저수지 한가운데가 빠졌다. 화소 대응 경로(`refl_keep_dark`)만 0 으로 자른다. 호출부 전환·재산출은 논문 전(`to_reflectance(negative=)` 인자만 추가됨).
4. **고정 임계** — S2 도 SAR 도 두 해 같은 임계. 장면별 Otsu 는 2026 임계를 6곳 모두 내려 Δ 를 왜곡했다.
5. **격자** — 두 래스터가 같은 격자가 아니면 재표본화하지 않고 멈춘다(반 화소 리샘플 = 호안선 한 줄 이동).
6. **섬진강·평림은 이 그림에 없다** — 8월 SAR 이 ASC127 별도 쌍(0811↔0807)이라 `v11_s2xval/aug_a` 에 변화·γ0 래스터가 없다. gee 산출 세션이 ASC127 판 `--save-tif` 를 내면 같은 코드로 된다(S2 쌍은 `PAIRS`·평림 07-12 예외 참조).

## 6. SAR 자료가 RTC 인가 (2026-10-15 확인)

- **처리 이력**: 입력 `E:\06_SAR_system_archive\rtc_grd_frost_vh_egm_{2025,2026}` — 체인 `Calibration(Beta0) → Frost → Terrain-Flattening → Terrain-Correction(EGM) → dB` (`s1/preprocess/prepro_grd_gpt.py`). 산출 GeoTIFF 자체에는 처리 메타데이터가 없어 코드·경로로 확인했다.
- **실측**: 영천·운문·밀양 2025·2026 육지 화소에서 γ0(dB) 대 레이더 시선 방향 경사각 상관 r = −0.03 ~ −0.09, 기울기 −0.004 ~ −0.009 dB/° → 지형 의존 거의 없음(비보정이면 뚜렷). Terrain-Flattening 적용으로 판단.
- **그림의 줄무늬**: 회색조 범위가 좁아 잔여 텍스처(σ≈1.9 dB)가 크게 보이는 것. 시선 방향 경사만 본 검증이라 레이오버·그림자 주변 잔차까지 배제한 것은 아니다.

## 7. 파일

| 구분 | 경로 |
|---|---|
| 계산·그림 정본 | `S2/s2_dam8_sar_xval.py` |
| 렌더러 | `S1/scripts/poster_fig4_render.py` |
| 입력 npz (6곳, ~43 MB) | `S2/results/S2_DAM8_XVAL/aug_a_ws/figdata/fig4_<댐>.npz` |
| 통계 | `S2/results/S2_DAM8_XVAL/aug_a_ws/xval_aug_a_ws.csv` |
| 그림 | `S2/results/S2_DAM8_XVAL/aug_a_ws/그림4_*.png` (합본 2 + 댐별 6×2) |
