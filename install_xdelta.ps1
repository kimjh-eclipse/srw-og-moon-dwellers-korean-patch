<#
  슈퍼로봇대전 OG 문 드웰러즈 (BLJS10335) 한국어 패치 설치 스크립트
  버전 v20260819

  - 원본 4개 파일을 검증한 뒤 백업하고, xdelta 패치를 적용합니다.
  - 임시 파일에 적용해 해시를 검증한 뒤에만 실제 파일을 교체합니다.
  - 게임 캐시는 자동으로 삭제하거나 이동하지 않습니다.
  - 실패해도 원본이나 게임 폴더를 절대 삭제하지 않습니다.

  사용법:
    .\install_xdelta.ps1 -TargetDir "<...\BLJS10335\USRDIR\PSARC>"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetDir,

    [string]$XdeltaPath,
    [string]$PatchDir,
    # 백업은 게임 데이터 폴더 밖(기본값: 이 스크립트 위치)에 만듭니다.
    [string]$BackupRoot,
    [switch]$SkipBackup
)

$ErrorActionPreference = 'Stop'

$ScriptRoot = $PSScriptRoot
if ([string]::IsNullOrEmpty($ScriptRoot)) { $ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }
if ([string]::IsNullOrEmpty($ScriptRoot)) { $ScriptRoot = (Get-Location).Path }

if ([string]::IsNullOrEmpty($XdeltaPath)) { $XdeltaPath = Join-Path $ScriptRoot 'xdelta.exe' }
if ([string]::IsNullOrEmpty($PatchDir))   { $PatchDir   = Join-Path $ScriptRoot 'patches' }
if ([string]::IsNullOrEmpty($BackupRoot)) { $BackupRoot = $ScriptRoot }

# name = 원본 SHA256 / 패치 후 SHA256 / 크기 / 원래 수정시각(UTC)
$SPEC = [ordered]@{
    'Common' = @{
        Size   = 505828992
        Source = '99B298B3BBE126647582A8B6201513B5E80E2B2F06BF0D5BB1F0D87D0D2093BB'
        Target = '16C45C456DA86DD17B5C05BD8735433873C37503984C1C58A96C613FDA5CD2B2'
        Mtime  = '2016-05-04T04:37:57Z'
    }
    'General2d' = @{
        Size   = 611585392
        Source = '04C3D1DA43BBE58622FE89499C08A2525CD5AB78C30B830A0D1781ED59F16667'
        Target = '2B93DC5F3067BA94379429553699A978A63E8BB8AB7105B5286F912FB4E19332'
        Mtime  = '2016-04-30T02:15:24Z'
    }
    'Logic' = @{
        Size   = 38399120
        Source = 'AF453B395D358FAB79740310BBA03F400A54F3D86CC6A82FD0A504FF25F5F181'
        Target = '88805060C4D910749A926199D96B6DE11EC2BD5F49FA422E28C759407834BB45'
        Mtime  = '2016-05-04T10:52:39Z'
    }
    'Battle' = @{
        Size   = 1729186848
        Source = '2C5CA16F75FCE3725E97977F79CD281FD52BF78BC67C9232228E37AFF894A844'
        Target = '4841F5801429D74B06DFCE71B4FBBDD0F8635D88BE72F17B5D9069EF77980420'
        Mtime  = '2016-05-04T04:50:11Z'
    }
}

function Write-Step($m) { Write-Host "[*] $m" -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Fail($m) {
    Write-Host "[실패] $m" -ForegroundColor Red
    Write-Host ""
    Write-Host "게임 파일은 변경되지 않았거나, 백업 폴더에 원본이 남아 있습니다." -ForegroundColor Yellow
    Write-Host "복구가 필요하면 restore_xdelta_backup.ps1 을 사용하세요." -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------------- 1. RPCS3 확인
Write-Step 'RPCS3 실행 여부 확인'
$rp = Get-Process -Name 'rpcs3' -ErrorAction SilentlyContinue
if ($rp) {
    Fail "RPCS3가 실행 중입니다 (PID $($rp.Id -join ', ')). 완전히 종료한 뒤 다시 실행하세요."
}
Write-Ok 'RPCS3 종료 상태'

# ---------------------------------------------------------------- 2. 경로 확인
Write-Step '대상 경로 확인'
if (-not (Test-Path -LiteralPath $TargetDir -PathType Container)) {
    Fail "대상 폴더가 없습니다: $TargetDir"
}
$full = (Resolve-Path -LiteralPath $TargetDir).Path

# 대상은 두 종류가 있습니다.
#   롬(권장)      ...\PS3_GAME\USRDIR\PSARC
#   게임 데이터    ...\dev_hdd0\game\BLJS10335\USRDIR\PSARC
# 게임 데이터는 게임이 첫 실행 때 롬에서 복사해 만드는 사본입니다. 이쪽만 바꾸면
# 게임이 무결성 검사에서 걸려 "게임 데이터가 손상되었습니다" 가 뜰 수 있습니다.
$isRom      = $full -match 'PS3_GAME[\\/]USRDIR[\\/]PSARC[\\/]?$'
$isGameData = $full -match 'BLJS10335[\\/]USRDIR[\\/]PSARC[\\/]?$'
if (-not ($isRom -or $isGameData)) {
    Fail ("대상 경로가 올바르지 않습니다: $full`n" +
          "  롬(권장)   : ...\BLJS10335\PS3_GAME\USRDIR\PSARC`n" +
          "  게임 데이터: ...\dev_hdd0\game\BLJS10335\USRDIR\PSARC")
}
if (-not (Test-Path -LiteralPath $XdeltaPath -PathType Leaf)) { Fail "xdelta.exe 를 찾을 수 없습니다: $XdeltaPath" }
if (-not (Test-Path -LiteralPath $PatchDir  -PathType Container)) { Fail "패치 폴더를 찾을 수 없습니다: $PatchDir" }
foreach ($n in $SPEC.Keys) {
    $pf = Join-Path $PatchDir "$n.psarc.sdat.xdelta"
    if (-not (Test-Path -LiteralPath $pf -PathType Leaf)) { Fail "패치 파일이 없습니다: $pf" }
}
Write-Ok "대상: $full"
if ($isRom) {
    Write-Host '    (롬 쪽입니다 — 권장 대상)' -ForegroundColor Green
} else {
    Write-Host '    (게임 데이터 쪽입니다)' -ForegroundColor Yellow
    Write-Host '    이 폴더는 게임이 롬에서 복사해 만든 사본입니다.' -ForegroundColor Yellow
    Write-Host '    여기만 바꾸면 게임이 "게임 데이터가 손상되었습니다" 로 막을 수 있습니다.' -ForegroundColor Yellow
    Write-Host '    롬 쪽(...\PS3_GAME\USRDIR\PSARC)에 적용하는 편이 안전합니다.' -ForegroundColor Yellow
}

# ---------------------------------------------------------------- 3. 원본 검증
Write-Step '원본 4개 파일 크기 / SHA-256 검증'
foreach ($n in $SPEC.Keys) {
    $f = Join-Path $full "$n.psarc.sdat"
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { Fail "파일이 없습니다: $f" }
    $item = Get-Item -LiteralPath $f
    if ($item.Length -ne $SPEC[$n].Size) {
        Fail "$n 크기 불일치. 기대 $($SPEC[$n].Size), 실제 $($item.Length)"
    }
    $h = (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash
    if ($h -eq $SPEC[$n].Target) {
        Fail "$n 은 이미 이 버전의 한국어 패치가 적용된 파일입니다. 먼저 원본으로 복원한 뒤 실행하세요."
    }
    if ($h -ne $SPEC[$n].Source) {
        Fail "$n 원본 해시가 다릅니다.`n  기대: $($SPEC[$n].Source)`n  실제: $h`n  일본판 BLJS10335 원본이 맞는지, 다른 버전 패치가 적용돼 있지 않은지 확인하세요."
    }
    Write-Host ("    {0,-10} OK  {1}" -f $n, $h)
}
Write-Ok '원본 4개 확인 완료'

# ---------------------------------------------------------------- 4. 백업
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupDir = Join-Path $BackupRoot "backup_original_$stamp"
if ($SkipBackup) {
    Write-Host '[!] -SkipBackup 지정됨. 백업을 건너뜁니다.' -ForegroundColor Yellow
} else {
    Write-Step "원본 백업 -> $backupDir"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    foreach ($n in $SPEC.Keys) {
        Copy-Item -LiteralPath (Join-Path $full "$n.psarc.sdat") -Destination (Join-Path $backupDir "$n.psarc.sdat") -Force
        Write-Host "    $n.psarc.sdat 백업"
    }
    Write-Ok '백업 완료'
}

# ---------------------------------------------------------------- 5~8. 패치 적용
$tempDir = Join-Path $full "_patch_tmp_$stamp"
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

try {
    foreach ($n in $SPEC.Keys) {
        Write-Step "$n 패치 적용"
        $src  = Join-Path $full "$n.psarc.sdat"
        $pf   = Join-Path $PatchDir "$n.psarc.sdat.xdelta"
        $tmp  = Join-Path $tempDir "$n.psarc.sdat"

        & $XdeltaPath -d -f -s $src $pf $tmp
        if ($LASTEXITCODE -ne 0) { Fail "$n xdelta 적용 실패 (exit $LASTEXITCODE)" }

        $ti = Get-Item -LiteralPath $tmp
        if ($ti.Length -ne $SPEC[$n].Size) {
            Fail "$n 결과 크기 불일치. 기대 $($SPEC[$n].Size), 실제 $($ti.Length)"
        }
        $th = (Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash
        if ($th -ne $SPEC[$n].Target) {
            Fail "$n 결과 해시 불일치.`n  기대: $($SPEC[$n].Target)`n  실제: $th"
        }
        Write-Host ("    검증 OK  {0}" -f $th)

        # 검증된 결과만 교체
        Move-Item -LiteralPath $tmp -Destination $src -Force

        # 수정시각 복원 — 달라지면 부팅/로딩 문제가 생길 수 있습니다.
        $mt = [datetime]::Parse($SPEC[$n].Mtime, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal)
        (Get-Item -LiteralPath $src).LastWriteTimeUtc = $mt
        Write-Ok "$n 교체 및 수정시각 복원"
    }
}
finally {
    if (Test-Path -LiteralPath $tempDir) {
        Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------- 9. 캐시 보존
Write-Step '게임 캐시 보존'
Write-Host '    설치 스크립트는 cache\BLJS10335, PPU, SPU, 셰이더 캐시를 변경하지 않습니다.'
Write-Host '    화면이 하얗게 보일 때만 RPCS3의 Remove SPU Cache 기능을 사용하세요.' -ForegroundColor Yellow
Write-Host '    cache\BLJS10335 전체나 v8-kusa-*.obj.gz 파일은 직접 삭제하지 마세요.' -ForegroundColor Yellow
Write-Ok '캐시 변경 없음'

# ---------------------------------------------------------------- 10. 최종 출력
Write-Host ''
Write-Host '=== 설치 완료 ===' -ForegroundColor Green
foreach ($n in $SPEC.Keys) {
    $f = Join-Path $full "$n.psarc.sdat"
    $i = Get-Item -LiteralPath $f
    Write-Host ("{0,-10} {1,13:N0}  {2}  {3}" -f $n, $i.Length, $i.LastWriteTimeUtc.ToString('yyyy-MM-ddTHH:mm:ssZ'), (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash)
}
Write-Host ''
if (-not $SkipBackup) {
    Write-Host "원본 백업 위치: $backupDir" -ForegroundColor Yellow
    Write-Host '문제가 생기면 이 폴더의 파일을 다시 덮어쓰면 원상복구됩니다.' -ForegroundColor Yellow
}

if ($isRom) {
    Write-Host ''
    Write-Host '=== 남은 한 단계 ===' -ForegroundColor Cyan
    Write-Host '롬을 패치했습니다. 예전에 만들어진 게임 데이터가 남아 있으면 그것이 먼저 쓰입니다.'
    Write-Host '아래 폴더가 있으면 통째로 삭제하거나 다른 곳으로 옮긴 뒤 게임을 실행하세요.'
    Write-Host ''
    Write-Host '    <RPCS3 폴더>\dev_hdd0\game\BLJS10335' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '게임이 데이터를 다시 설치하고, 그 뒤 한국어로 표시됩니다.'
    Write-Host '세이브 데이터는 이 폴더가 아니라 dev_hdd0\home\00000001\savedata 에 있으므로 안전합니다.'
}
