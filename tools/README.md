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

## 검증 (`work/`)

| 스크립트 | 역할 |
|---|---|
| `verify_installed_final.py` | 설치본 해시 대조 |
| `iso_extract_missing.py` | ISO에서 누락 PSARC 추출 (다중 익스텐트 처리) |
| `check_fit_*.py` / `check_legacy_fit_*.py` | 칸 맞춤 검사 |
| `audit_general2d_icon_records.py` | 아이콘 레코드 감사 |
| `decode_exfont_pages.py` / `label_exfont01_cells.py` | 확장 폰트 페이지 해석 |

---

## 이 폴더에 없는 것

다음은 **의도적으로 공개하지 않습니다.**

- **원본 게임 데이터** — `.sdat`, `.psarc`, ISO, 추출된 텍스트·폰트·이미지
- **번역 대역표** — 일본어 원문과 한국어 번역을 짝지은 데이터
- **원문이 인라인으로 박힌 빌드 스크립트 18개** — 아래 목록

```
09_utf16_extract.py                 30_build_battle_poc_stream.py
18_build_korean_font_poc.py         32_build_battle_safe_full.py
19_build_minimal_glyph_poc.py       35_review_translation_draft.py
21_build_v3_font_poc.py             40_build_battle_c117_override.py
22_build_scenario_menu_poc.py       42_build_battle_c117_manual_v2.py
24_build_general2d_full.py          44_build_battle_c117_eselda_v4.py
27_build_logic_translation.py       45_build_battle_c117_android0137_v5.py
                                    46_build_battle_c117_cleanup_v6.py
                                    55_patch_general2d_pilot_training.py
                                    57_patch_logic_ace_bonus.py
work/check_legacy_fit_tsv.py
```

이 스크립트들은 원문→번역 대역표를 소스 안에 그대로 담고 있어, 공개하면 게임 텍스트를
배포하는 것과 같아집니다. 포맷 처리 로직은 위 공용 라이브러리와 나머지 스크립트에
모두 들어 있으므로, 같은 절차를 자기 번역 데이터로 재현할 수 있습니다.

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
