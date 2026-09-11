#!/usr/bin/env python3
"""v20260910: 범위 팩을 6개 항목으로 확장하고, 패처의 「4개 고정」 제한을 푼다.

- build_range_pack.py FILES: Common·General2d·Logic 대상을 아카이브 판으로, PARAM.SFO·ICON0.PNG 추가
- OGMDIsoQuickPatch.cs: fileCount 검사 완화(1~16), 버전 문자열 갱신
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
PACK = ROOT / "iso_quickpatch/build_range_pack.py"
CS = ROOT / "iso_quickpatch/OGMDIsoQuickPatch.cs"
NEW_VERSION = "v20260910-archive-title-icon"

NEW_FILES = '''FILES = (
    {
        "name": "Common",
        "iso_path": "PS3_GAME/USRDIR/PSARC/COMMON_PSARC.SDAT",
        "source": ROOT / "original_backups/Common.psarc.sdat.orig",
        # Startup warning, title logo, scenario title cards, and the five
        # Archive story texts (246 paragraphs). Shared/animated UI images stay out.
        "target": ROOT / "korean_build_v3/Common_archive_ko_20260910.psarc.sdat",
        "source_hash": "99B298B3BBE126647582A8B6201513B5E80E2B2F06BF0D5BB1F0D87D0D2093BB",
        "target_hash": "52FFAF183FD89A2A0967A492CA369E6131CA121E403EC1E0E4FB941633B90373",
    },
    {
        "name": "General2d",
        "iso_path": "PS3_GAME/USRDIR/PSARC/GENERAL2D_PSARC.SDAT",
        "source": ROOT / "original_backups/General2d.psarc.sdat.orig",
        # General2d/tex_06.dds image localization is intentionally excluded.
        # It is a shared UI glyph atlas and corrupted the level-up display.
        "target": ROOT / "korean_build_v3/General2d_archive_ko_20260910.psarc.sdat",
        "source_hash": "04C3D1DA43BBE58622FE89499C08A2525CD5AB78C30B830A0D1781ED59F16667",
        "target_hash": "6BCB01A3D66FE668ECA2BF5167D9552DBD1D6F6DB1B0A24083FD40DA2D14AD47",
    },
    {
        "name": "Logic",
        "iso_path": "PS3_GAME/USRDIR/PSARC/LOGIC_PSARC.SDAT",
        "source": ROOT / "original_backups/Logic.psarc.sdat.orig",
        # Text-only archive: scenario titles, issue #6 name/dialogue fixes,
        # 2026-09-10 line-wrap pass, and the Archive REPORT dialog strings.
        "target": ROOT / "korean_build_v3/Logic_archive_ko_20260910.psarc.sdat",
        "source_hash": "AF453B395D358FAB79740310BBA03F400A54F3D86CC6A82FD0A504FF25F5F181",
        "target_hash": "8FA8EC93EFF285BB2AD74DC5D0A23BE8A67EBF1E5A47B9EB269A6E52FE86777C",
    },
    {
        "name": "Battle",
        "iso_path": "PS3_GAME/USRDIR/PSARC/BATTLE_PSARC.SDAT",
        "source": ROOT / "original_backups/Battle.psarc.sdat.orig",
        # Battle/cosl.dds: the shared HUD atlas. A whole-file replacement once hid
        # unit names and HP/EN; 173 repaints only the 9 attack-type label boxes.
        "target": ROOT / "korean_build_v3/Battle_issue6_ko_20260909.psarc.sdat",
        "source_hash": "2C5CA16F75FCE3725E97977F79CD281FD52BF78BC67C9232228E37AFF894A844",
        "target_hash": "F1AC61F80B70BC0E85B5ABB15DC82E2AF55E6A16084DD8C438FC7AA5B2A02E6E",
    },
    {
        "name": "ParamSfo",
        "iso_path": "PS3_GAME/PARAM.SFO",
        "source": ROOT / "original_backups/PARAM.SFO.orig",
        # Game list title only. TITLE_ID, APP_VER and every other field stay put.
        "target": ROOT / "korean_build_v3/PARAM_SFO_ko_20260910.bin",
        "source_hash": "0A876ACFABB16CEAA017EDD51A700079678AA8E61C0B7AEFE0B59CB19B59FF22",
        "target_hash": "B7ABDFE7FED52FB9EEEDDE02FBD33475A449C20B4EE6099E59BC025E1F32DE54",
    },
    {
        "name": "Icon0",
        "iso_path": "PS3_GAME/ICON0.PNG",
        "source": ROOT / "original_backups/ICON0.PNG.orig",
        # Korean game list icon, zero-padded to the retail slot size.
        # PNG readers stop at IEND, so the trailing padding is inert.
        "target": ROOT / "korean_build_v3/ICON0_PNG_ko_20260910.bin",
        "source_hash": "9B2E67DC606CEF3CD269E13DDA425445820A65F034DE4B3BC000435EA0B9B136",
        "target_hash": "0B038E45343B203DE00D1323247FD5AFFFF3AB61AF35A8206010EA5601948A00",
    },
)
'''


def main() -> None:
    raw = PACK.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    start = text.index("FILES = (")
    end = text.index(")\n\n\ndef file_hash", start) + 2
    text = text[:start] + NEW_FILES + text[end:]
    if text.count(chr(34) + "iso_path" + chr(34) + ":") != 6:
        raise AssertionError(f"항목 수 이상: {text.count(chr(34) + chr(105) + chr(115) + chr(111) + chr(95) + chr(112) + chr(97) + chr(116) + chr(104) + chr(34))}")
    PACK.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    print("build_range_pack.py: 6개 항목으로 갱신")

    raw = CS.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    cs = raw.decode("utf-8-sig")
    old_check = "            if (version != FormatVersion || fileCount != 4)\n"
    new_check = "            if (version != FormatVersion || fileCount < 1 || fileCount > 16)\n"
    if old_check in cs:
        cs = cs.replace(old_check, new_check, 1)
        print("OGMDIsoQuickPatch.cs: 파일 수 검사 완화(1~16)")
    elif new_check in cs:
        print("OGMDIsoQuickPatch.cs: 이미 완화됨")
    else:
        raise AssertionError("파일 수 검사 지점을 찾지 못함")
    marker = 'VersionText = "'
    at = cs.index(marker) + len(marker)
    close = cs.index('"', at)
    print("버전:", cs[at:close], "->", NEW_VERSION)
    cs = cs[:at] + NEW_VERSION + cs[close:]
    CS.write_bytes((b"\xef\xbb\xbf" if bom else b"") + cs.encode("utf-8"))


if __name__ == "__main__":
    main()
