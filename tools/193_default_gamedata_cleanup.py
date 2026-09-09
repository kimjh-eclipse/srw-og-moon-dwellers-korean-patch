#!/usr/bin/env python3
"""빠른 패처: ISO 패치 시 설치 데이터 정리를 기본 켜기로 바꾸고, 정리를 건너뛸 때 위험을 알린다.

배경: v20260909b 의 수정시각 보존 핫픽스로 롬 패치 후에도 시각이 유지된다.
      게임 무결성 검사는 시각을 보므로 「게임 데이터가 손상되었습니다」가 더는 뜨지 않는데,
      게임은 dev_hdd0\\game\\BLJS10335 사본이 있으면 그것을 먼저 읽는다.
      즉 그 오류가 해 주던 "사본을 지워라" 경고가 사라져, 사본을 남긴 사용자는
      오류 없이 패치가 적용되지 않은 상태로 플레이하게 된다.

조치:
  1) 정리 체크박스 기본 켜짐 + 라벨에 (권장)
  2) 정리를 켰지만 RPCS3 경로가 없으면 패치를 막지 않고, 위험을 알린 뒤 선택을 받는다
  3) 정리 없이 진행하는 패치 확인창에 조용한 실패 경고를 넣는다
C# 5 문법만 사용.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent
CS = ROOT / "iso_quickpatch" / "OGMDIsoQuickPatch.cs"
NEW_VERSION = "v20260909c-cleanup-default"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise AssertionError(f"앵커가 유일하지 않음({text.count(old)}건): {old[:70]}")
    return text.replace(old, new, 1)


def main() -> None:
    raw = CS.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    t = raw.decode("utf-8-sig")
    if "설치 데이터 정리 건너뛰기" in t:
        print("이미 적용됨")
        return

    # 1) 기본 켜짐 + 라벨
    t = replace_once(
        t,
        '            deleteInstalledGameCheck.Text = "ISO 패치 성공 후 BLJS10335 설치 데이터와 해당 SPU 캐시만 정리";\n'
        '            deleteInstalledGameCheck.Font = new Font("Segoe UI", 9F, FontStyle.Bold);\n'
        "            deleteInstalledGameCheck.AutoSize = true;\n",
        '            deleteInstalledGameCheck.Text = "ISO 패치 성공 후 BLJS10335 설치 데이터와 해당 SPU 캐시만 정리 (권장)";\n'
        '            deleteInstalledGameCheck.Font = new Font("Segoe UI", 9F, FontStyle.Bold);\n'
        "            deleteInstalledGameCheck.AutoSize = true;\n"
        "            // 설치 데이터 사본이 남아 있으면 게임이 그것을 먼저 읽어 패치가 적용되지 않는다.\n"
        "            // 수정시각 보존 이후로는 그 상황에서 오류도 뜨지 않으므로 기본값을 켜 둔다.\n"
        "            deleteInstalledGameCheck.Checked = true;\n",
    )

    # 2) 경로가 없으면 막지 않고 위험을 알린 뒤 선택을 받는다
    t = replace_once(
        t,
        "                catch (Exception ex)\n"
        "                {\n"
        '                    MessageBox.Show(this, ex.Message, "RPCS3 경로 확인", MessageBoxButtons.OK, MessageBoxIcon.Warning);\n'
        "                    return;\n"
        "                }\n",
        "                catch (Exception ex)\n"
        "                {\n"
        "                    // 정리가 기본값이므로 RPCS3 경로가 없다고 패치 자체를 막지는 않는다.\n"
        "                    DialogResult skip = MessageBox.Show(this,\n"
        '                        ex.Message + "\\r\\n\\r\\n" +\n'
        '                        "설치 데이터 정리를 건너뛰고 ISO만 패치할 수 있습니다.\\r\\n\\r\\n" +\n'
        '                        "[주의] RPCS3에 예전 설치 데이터(dev_hdd0\\\\game\\\\BLJS10335)가 남아 있으면 게임이\\r\\n" +\n'
        '                        "그 사본을 먼저 읽기 때문에 패치가 적용되지 않은 상태로 실행됩니다.\\r\\n" +\n'
        '                        "이때 오류 메시지는 뜨지 않으므로 해당 폴더를 직접 지워 주세요.\\r\\n\\r\\n" +\n'
        '                        "정리 없이 계속하시겠습니까?",\n'
        '                        "설치 데이터 정리 건너뛰기", MessageBoxButtons.YesNo,\n'
        "                        MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2);\n"
        "                    if (skip != DialogResult.Yes)\n"
        "                        return;\n"
        "                    deleteInstalledGame = false;\n"
        "                }\n",
    )

    # 3) 정리 없이 진행하는 확인창에 경고
    t = replace_once(
        t,
        "                    (deleteInstalledGame ?\n"
        '                        "\\r\\n\\r\\n패치 성공 후 다음 설치 폴더만 삭제합니다:\\r\\n" +\n'
        "                        GetInstalledGamePath(rpcs3Path) : String.Empty),\n",
        "                    (deleteInstalledGame ?\n"
        '                        "\\r\\n\\r\\n패치 성공 후 다음 설치 폴더만 삭제합니다:\\r\\n" +\n'
        "                        GetInstalledGamePath(rpcs3Path) :\n"
        '                        "\\r\\n\\r\\n[주의] 설치 데이터 정리를 하지 않습니다.\\r\\n" +\n'
        '                        "예전 dev_hdd0\\\\game\\\\BLJS10335 사본이 남아 있으면 게임이 그것을 먼저 읽어\\r\\n" +\n'
        '                        "패치가 적용되지 않은 상태로 실행됩니다. 오류는 뜨지 않으므로 직접 지워 주세요."),\n',
    )

    # 4) 버전
    t = replace_once(t, 'VersionText = "v20260909b-mtime-hotfix"', f'VersionText = "{NEW_VERSION}"')

    CS.write_bytes((b"\xef\xbb\xbf" if bom else b"") + t.encode("utf-8"))
    print("C# 패치 적용:", CS.name, "->", NEW_VERSION)


if __name__ == "__main__":
    main()
