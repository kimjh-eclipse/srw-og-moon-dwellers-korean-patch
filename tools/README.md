# 파이프라인 도구

원본 게임 데이터에서 한국어 패치를 만들기까지 사용한 스크립트 모음입니다.
포맷과 절차 설명은 [문서 사이트](https://kimjh-eclipse.github.io/srw-og-moon-dwellers-korean-patch/)를 참고하세요.

실행에는 본인이 합법적으로 소유한 원본 게임 데이터가 필요합니다.

```
pip install pycryptodome pillow
```

## 공용 라이브러리

| 파일 | 역할 |
|---|---|
| `sdat.py` | SDAT 복호. `decrypt_stream()`, 랜덤 액세스용 `SDATReader` |
| `sdat_encode.py` | 평문 → SDAT 재암호화. 원본 NPD 헤더 재사용, 블록 메타데이터 위조 |
| `psarc.py` | PSARC 1.4 파서. `entries`, `block_table`, `read_entry(i)` |
| `psarc_write.py` | 표준 재패킹. 특정 엔트리만 교체하고 나머지 블록은 원본 압축본을 복사 |
| `psarc_fixed_blocks.py` | 블록 단위 고정 슬롯 재빌드 |
| `psarc_fixed_entry_spans.py` | 엔트리 물리 구간을 고정하고 내부 블록 경계를 재배분 |
| `textextract.py` | 텍스트 컨테이너 추출 |
| `patch_text.py` | 텍스트 치환 |
| `bmd_rebuild.py` | 전투 대사 BMD 컨테이너 재작성 |
| `scr_rebuild.py` | Logic 안 `scr*.bin`(매직 `LOGO`) 스크립트 재삽입 |
| `common_rebuild.py` | Common 텍스트 컨테이너 `.csb`(`CSB `/`STRP`) 재작성 |
| `dat_rebuild.py` | Dat 계열 컨테이너 재작성 |
| `rpcs3mem.py` | RPCS3 메모리 조회 — 인게임 검증용 |

## 분석 · 추출

| 스크립트 | 역할 |
|---|---|
| `01_iso_list.py` | ISO9660 디렉터리 트리 나열 |
| `02_sdat_header.py` / `03_sdat_probe.py` | NPD 헤더 파싱, 블록 구조 확인 |
| `04_key_bruteforce.py` / `05_erk_test.py` | 키 유도 방식 규명 |
| `08_text_probe.py` / `09_utf16_extract.py`\* | 텍스트 영역 탐색 |
| `10_scan_all_manifests.py` / `11_extract_all.py` | PSARC 매니페스트 스캔, 전체 추출 |
| `17_scan_all_text.py` / `20_extract_all_text.py` | 텍스트 전수 추출 |
| `21_extract_bmd.py` | 전투 대사 BMD 추출 |
| `34_probe_variable_fixeddata.py` / `38_probe_variable_bmd.py` | 가변·고정 데이터 구간 조사 |

## 폰트

| 스크립트 | 역할 |
|---|---|
| `14_font_probe.py` / `15_font_dxt5.py` | 폰트 구조와 텍스처 포맷 조사 |
| `16_build_korean_font.py` | FTTF에 한글 글리프 주입, 대체 CJK 코드로 인코딩 |
| `20_build_korean_font_existing_metrics.py` | 기존 메트릭을 유지한 글리프 생성 |
| `25_pack_v4_font.py` / `26_rebuild_matched_v3_font.py` | 폰트 패킹·재빌드 |
| `26_append_wtd_glyphs_to_v3.py` / `39_extend_v3_battle_font.py` | 글리프 추가 |
| `58_patch_common_terrain_glyphs.py` / `59_patch_common_icon_font.py` | 지형·아이콘 글리프 |

## 번역 배치 · 검수

| 스크립트 | 역할 |
|---|---|
| `12_make_batches.py` / `13_validate_tl.py` | 번역 배치 생성·검증 |
| `36_review_battle_draft.py` / `37_review_logic_overflows.py` | 초안 검수, 칸 넘침 검출 |
| `48_make_review4000_oversize_worklists.py` | 칸 초과 항목 작업 목록 생성 |
| `50~52_merge_battle_review_*.py` | 검수 결과 병합 |
| `53_validate_battle_review_5000.py` | 병합본 검증 |
| `54_make_legacy_fit_worklists.py` | 축약 필요 항목 목록 |

## 빌드 — 고정 배치

배포 델타를 667.7MB에서 7.32MiB로 줄인 빌더입니다.
원리는 [고정 배치 재빌드](https://kimjh-eclipse.github.io/srw-og-moon-dwellers-korean-patch/#/fixed-layout) 참고.

| 스크립트 | 대상 |
|---|---|
| `60_build_common_font_fixed_layout.py` | Common — 폰트 엔트리만 원본 슬롯에 이식 |
| `61_build_general2d_fixed_layout.py` | General2d |
| `62_build_logic_fixed_spans.py` | Logic — 엔트리 구간 고정 + 블록 경계 재배분 |
| `47_build_battle_c117_review4000_test.py` | Battle |

## ISO 빠른 패처 (`iso_quickpatch/`)

복호화된 ISO의 바뀐 구간만 직접 덮어써 패치하는 도구입니다.
소스와 빌드 방법은 [`iso_quickpatch/README.md`](iso_quickpatch/README.md)를 참고하세요.

| 파일 | 역할 |
|---|---|
| `OGMDIsoQuickPatch.cs` | 패처 본체 (GUI, ISO 구간 쓰기, 백업·복구) |
| `build_range_pack.py` | 원본과 최종 PSARC를 비교해 변경 구간만 모으는 생성기 |
| `build.ps1` | 실행 파일 빌드 |

빌드된 실행 파일과 range pack 바이너리는 저장소에 넣지 않습니다.
실행 파일은 릴리스 자산으로 배포되고, range pack은 게임 데이터에서 뽑아낸 페이로드입니다.

## 이미지 한글화 (`102`~`110`)

게임 내 이미지 자산을 찾아 목록을 만들고, 추출·대조표 생성·한글화·재설치·감사까지 하는 묶음입니다.

| 스크립트 | 역할 |
|---|---|
| `102_inventory_image_assets.py` | 이미지 자산 목록화 |
| `103_extract_image_assets.py` | 추출 |
| `104_make_contact_sheet.py` | 한눈에 보는 대조표 생성 |
| `105_localize_image_assets.py` | 한글화 적용 |
| `106_build_image_localization.py` | 빌드 |
| `107_audit_image_localization.py` | 결과 감사 |

## 검증 (`work/`)

| 스크립트 | 역할 |
|---|---|
| `verify_installed_final.py` | 설치본 해시 대조 |
| `iso_extract_missing.py` | ISO에서 누락 PSARC 추출 (다중 익스텐트 처리) |
| `check_fit_*.py` / `check_legacy_fit_*.py` | 칸 맞춤 검사 |
| `audit_general2d_icon_records.py` | 아이콘 레코드 감사 |
| `decode_exfont_pages.py` / `label_exfont01_cells.py` | 확장 폰트 페이지 해석 |

---

## 번역 대역표는 코드와 분리되어 있습니다

빌드 스크립트 18개에는 원문→번역 대역표가 소스 안에 그대로 박혀 있었습니다.
그대로 공개하면 게임 텍스트를 배포하는 것과 같으므로, **코드는 그대로 두고 데이터만
외부 파일로 분리**했습니다.

```python
# 이전
BATTLE_REVIEW_OVERRIDES = {
    "<원문 대사>": "<번역 대사>",
    ...
}

# 지금
BATTLE_REVIEW_OVERRIDES = load_table('BATTLE_REVIEW_OVERRIDES')
```

대역표는 `tools/data/<스크립트이름>.json` 에서 읽습니다.
**이 폴더는 저장소에 포함되지 않습니다.**

| | |
|---|---|
| 분리된 스크립트 | 18개 |
| 분리된 테이블 | 33개 |
| 로더 | `tl_data.py` |

형식과 작성 방법은 [`tl_data.py`](tl_data.py)의 독스트링에 있습니다.
자기 번역 데이터를 같은 형식으로 만들어 `tools/data/` 에 두면 그대로 동작합니다.
데이터가 없으면 로더가 경로와 형식을 알려주며 중단합니다.

## 그 밖에 공개하지 않는 것

- **원본 게임 데이터** — `.sdat`, `.psarc`, ISO
- **추출된 텍스트·폰트·이미지**
- **번역 배치·검수 산출물** — `translated/`, `extract*/`, `review_*/` 등

`.gitignore` 가 위 경로와 확장자를 막아 두었습니다.

## 이어서 작업하려면

1. 원본 `.sdat`을 `sdat.py`로 복호
2. `psarc.py`로 엔트리를 열고 `textextract.py` / `21_extract_bmd.py`로 텍스트 추출
3. 번역
4. `16_build_korean_font.py`로 한글 글리프를 폰트에 주입
5. `bmd_rebuild.py` / `scr_rebuild.py` / `common_rebuild.py`로 컨테이너 재작성
6. **`psarc_fixed_blocks.py` 또는 `psarc_fixed_entry_spans.py`로 재빌드** —
   표준 재패킹을 쓰면 배포 델타가 수백 배 커집니다
7. `sdat_encode.py`로 재암호화
8. xdelta로 델타 생성 후 **왕복 검증** — 원본에 다시 적용해 해시가 일치해야 합니다
