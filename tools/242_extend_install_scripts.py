#!/usr/bin/env python3
"""install/verify/restore 스크립트에 제목·아이콘(PS3_GAME 루트 두 파일) 처리를 넣는다.

두 파일은 선택 적용이다. 없거나 원본 해시가 다르면(게임 데이터 사본 등) 그 파일만 건너뛰고
PSARC 4개는 정상 적용한다. 241 에서 import 해서 쓴다.
"""
from __future__ import annotations

from pathlib import Path


def load(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    return raw.decode("utf-8-sig"), raw.startswith(b"\xef\xbb\xbf")


def save(path: Path, text: str, bom: bool) -> None:
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise AssertionError(f"{label}: 앵커 {text.count(old)}건 -> {old[:60]}")
    return text.replace(old, new, 1)


def extra_table(extra: dict) -> str:
    rows = []
    for name, (_, _, source_hash, target_hash, size) in extra.items():
        rows.append(
            f"    '{name}' = @{{\n"
            f"        Size   = {size}\n"
            f"        Source = '{source_hash}'\n"
            f"        Target = '{target_hash}'\n"
            f"        Patch  = '{name}.xdelta'\n"
            f"    }}"
        )
    return ("# PS3_GAME 루트의 제목·아이콘. 선택 적용이며, 없거나 원본 해시가 다르면 건너뜁니다.\n"
            "$EXTRA = [ordered]@{\n" + "\n".join(rows) + "\n}\n")


APPLY_BLOCK = """
# ------------------------------------------------- 8b. 제목·아이콘 (선택 적용)
Write-Step '게임 목록 제목·아이콘 확인'
$gameRoot = Split-Path -Parent (Split-Path -Parent $full)
$extraDone = @()
$extraSkip = @()
if (-not (Test-Path -LiteralPath $gameRoot -PathType Container)) {
    Write-Host "    상위 폴더를 찾지 못해 건너뜁니다: $gameRoot" -ForegroundColor Yellow
} else {
    foreach ($e in $EXTRA.Keys) {
        $ef = Join-Path $gameRoot $e
        $ep = Join-Path $PatchDir $EXTRA[$e].Patch
        if (-not (Test-Path -LiteralPath $ef -PathType Leaf)) {
            $extraSkip += "$e (파일 없음)"
            continue
        }
        if (-not (Test-Path -LiteralPath $ep -PathType Leaf)) {
            $extraSkip += "$e (패치 파일 없음)"
            continue
        }
        $eh = (Get-FileHash -LiteralPath $ef -Algorithm SHA256).Hash
        if ($eh -eq $EXTRA[$e].Target) { $extraSkip += "$e (이미 적용됨)"; continue }
        if ($eh -ne $EXTRA[$e].Source) { $extraSkip += "$e (원본 해시 다름)"; continue }

        if (-not $SkipBackup) {
            Copy-Item -LiteralPath $ef -Destination (Join-Path $backupDir $e) -Force
        }
        $etmp = Join-Path $full ("_extra_tmp_" + $stamp + "_" + $e)
        & $XdeltaPath -d -f -s $ef $ep $etmp
        if ($LASTEXITCODE -ne 0) { Fail "$e xdelta 적용 실패 (exit $LASTEXITCODE)" }
        $eti = Get-Item -LiteralPath $etmp
        if ($eti.Length -ne $EXTRA[$e].Size) { Fail "$e 결과 크기 불일치. 기대 $($EXTRA[$e].Size), 실제 $($eti.Length)" }
        $eth = (Get-FileHash -LiteralPath $etmp -Algorithm SHA256).Hash
        if ($eth -ne $EXTRA[$e].Target) { Fail "$e 결과 해시 불일치.`n  기대: $($EXTRA[$e].Target)`n  실제: $eth" }
        $emtime = (Get-Item -LiteralPath $ef).LastWriteTimeUtc
        Move-Item -LiteralPath $etmp -Destination $ef -Force
        (Get-Item -LiteralPath $ef).LastWriteTimeUtc = $emtime
        $extraDone += $e
        Write-Ok "$e 교체 및 수정시각 복원"
    }
}
if ($extraDone.Count -gt 0) { Write-Ok ("제목·아이콘 적용: " + ($extraDone -join ', ')) }
foreach ($s in $extraSkip) { Write-Host "    건너뜀: $s" -ForegroundColor Yellow }
if ($extraDone.Count -eq 0) {
    Write-Host '    제목·아이콘은 롬(PS3_GAME) 쪽에 적용됩니다. 게임 데이터 사본에는 적용하지 않습니다.' -ForegroundColor Yellow
}
"""

VERIFY_BLOCK = """
# ------------------------------------------------- 제목·아이콘 상태 (선택 항목)
Write-Host ''
Write-Host '[제목·아이콘]'
$gameRoot = Split-Path -Parent (Split-Path -Parent $full)
foreach ($e in $EXTRA.Keys) {
    $ef = Join-Path $gameRoot $e
    if (-not (Test-Path -LiteralPath $ef -PathType Leaf)) {
        Write-Host ("{0,-12} 없음 (이 대상에는 해당 파일이 없습니다)" -f $e) -ForegroundColor Yellow
        continue
    }
    $eh = (Get-FileHash -LiteralPath $ef -Algorithm SHA256).Hash
    if ($eh -eq $EXTRA[$e].Target)     { Write-Host ("{0,-12} 한국어판" -f $e) -ForegroundColor Green }
    elseif ($eh -eq $EXTRA[$e].Source) { Write-Host ("{0,-12} 일본판 원본" -f $e) -ForegroundColor Cyan }
    else                               { Write-Host ("{0,-12} 알 수 없는 판본 $eh" -f $e) -ForegroundColor Yellow }
}
"""

RESTORE_BLOCK = """
# ------------------------------------------------- 제목·아이콘 복구 (백업에 있으면)
$gameRoot = Split-Path -Parent (Split-Path -Parent $full)
foreach ($e in $EXTRA) {
    $bf = Join-Path $BackupDir $e
    $tf = Join-Path $gameRoot $e
    if (-not (Test-Path -LiteralPath $bf -PathType Leaf)) { continue }
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $tf) -PathType Container)) { continue }
    $mt = (Get-Item -LiteralPath $bf).LastWriteTimeUtc
    Copy-Item -LiteralPath $bf -Destination $tf -Force
    (Get-Item -LiteralPath $tf).LastWriteTimeUtc = $mt
    Write-Host "[OK] $e 복구" -ForegroundColor Green
}
"""


def extend(pkg: Path, psarc: dict, extra: dict, old_targets: dict, old_ver: str, new_ver: str) -> None:
    # ---------------- install
    path = pkg / "install_xdelta.ps1"
    text, bom = load(path)
    text = text.replace(f"버전 {old_ver}", f"버전 {new_ver}")
    for name, (_, _, _, target_hash) in psarc.items():
        if old_targets[name] != target_hash:
            text = text.replace(old_targets[name], target_hash)
    anchor = "\n$SPEC = [ordered]@{"
    text = replace_once(text, anchor, "\n" + extra_table(extra) + anchor, "install/표")
    text = replace_once(text, "\n# ---------------------------------------------------------------- 9. 캐시 보존",
                        APPLY_BLOCK + "\n# ---------------------------------------------------------------- 9. 캐시 보존",
                        "install/적용")
    save(path, text, bom)
    print("install_xdelta.ps1 확장")

    # ---------------- verify
    path = pkg / "verify_xdelta.ps1"
    text, bom = load(path)
    for name, (_, _, _, target_hash) in psarc.items():
        if old_targets[name] != target_hash:
            text = text.replace(old_targets[name], target_hash)
    text = text.replace(old_ver, new_ver)
    anchor = "\n$SPEC = [ordered]@{"
    text = replace_once(text, anchor, "\n" + extra_table(extra) + anchor, "verify/표")
    # 요약부는 exit 로 끝나므로 그 앞에 넣는다
    summary = "\nWrite-Host ''\nif ($patched -eq 4) {"
    text = replace_once(text, summary, VERIFY_BLOCK + summary, "verify/요약 앞")
    save(path, text, bom)
    print("verify_xdelta.ps1 확장")

    # ---------------- restore
    path = pkg / "restore_xdelta_backup.ps1"
    text, bom = load(path)
    text = text.replace(old_ver, new_ver)
    names = ", ".join(f"'{n}'" for n in extra)
    text = text.rstrip("\n") + "\n$EXTRA = @(" + names + ")\n" + RESTORE_BLOCK
    save(path, text, bom)
    print("restore_xdelta_backup.ps1 확장")
