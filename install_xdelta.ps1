<#
  슈퍼로봇대전 OG 문 드웰러즈 (BLJS10335) 한국어 패치 설치 스크립트
  버전 v20260919

  - 원본 5개 파일을 검증한 뒤 백업하고, xdelta 패치를 적용합니다.
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
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
if (-not (Get-Command Get-FileHash -ErrorAction SilentlyContinue)) {
    function Get-FileHash {
        param(
            [Parameter(Mandatory = $true)][string]$LiteralPath,
            [string]$Algorithm = 'SHA256'
        )
        if ($Algorithm -ne 'SHA256') { throw "지원하지 않는 해시 알고리즘: $Algorithm" }
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $stream = [System.IO.File]::OpenRead($LiteralPath)
        try {
            $value = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '')
        }
        finally {
            $stream.Dispose()
            $sha.Dispose()
        }
        [pscustomobject]@{ Algorithm = 'SHA256'; Hash = $value; Path = $LiteralPath }
    }
}

$ScriptRoot = $PSScriptRoot
if ([string]::IsNullOrEmpty($ScriptRoot)) { $ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }
if ([string]::IsNullOrEmpty($ScriptRoot)) { $ScriptRoot = (Get-Location).Path }

if ([string]::IsNullOrEmpty($XdeltaPath)) { $XdeltaPath = Join-Path $ScriptRoot 'xdelta.exe' }
if ([string]::IsNullOrEmpty($PatchDir))   { $PatchDir   = Join-Path $ScriptRoot 'patches' }
if ([string]::IsNullOrEmpty($BackupRoot)) { $BackupRoot = $ScriptRoot }

# name = 원본 SHA256 / 패치 후 SHA256 / 크기
# 수정시각은 대상 파일에서 읽어 교체 후 그대로 복원합니다.
# PS3_GAME 루트의 제목·아이콘. 선택 적용이며, 없거나 원본 해시가 다르면 건너뜁니다.
$EXTRA = [ordered]@{
    'PARAM.SFO' = @{
        Size   = 1040
        Source = '0A876ACFABB16CEAA017EDD51A700079678AA8E61C0B7AEFE0B59CB19B59FF22'
        Target = 'B7ABDFE7FED52FB9EEEDDE02FBD33475A449C20B4EE6099E59BC025E1F32DE54'
        Patch  = 'PARAM.SFO.xdelta'
    }
    'ICON0.PNG' = @{
        Size   = 114574
        Source = '9B2E67DC606CEF3CD269E13DDA425445820A65F034DE4B3BC000435EA0B9B136'
        Target = '0B038E45343B203DE00D1323247FD5AFFFF3AB61AF35A8206010EA5601948A00'
        Patch  = 'ICON0.PNG.xdelta'
    }
}

$SPEC = [ordered]@{
    'General3d' = @{ Size = 870220816; Source = 'A702DB1295871F38B83827B87A5A36FBC5715E456E9C5E85A875E03EF002B412'; Target = '025EB16CFE6139893332AA575812F43AF2A51F036585EF32DF6961409710B77E' }
    'Common' = @{
        Size   = 505828992
        Source = '99B298B3BBE126647582A8B6201513B5E80E2B2F06BF0D5BB1F0D87D0D2093BB'
        Target = '52FFAF183FD89A2A0967A492CA369E6131CA121E403EC1E0E4FB941633B90373'
    }
    'General2d' = @{
        Size   = 611585392
        Source = '04C3D1DA43BBE58622FE89499C08A2525CD5AB78C30B830A0D1781ED59F16667'
        Target = '035267C098547C23AC8D4B20F69054966A463FFCA44A682943439790C58A666D'
    }
    'Logic' = @{
        Size   = 38399120
        Source = 'AF453B395D358FAB79740310BBA03F400A54F3D86CC6A82FD0A504FF25F5F181'
        Target = 'A34FBBA71611C48DDCFEC71F292D343E29F3AA8D56012A9C3D74255D326F14E1'
    }
    'Battle' = @{
        Size   = 1729186848
        Source = '2C5CA16F75FCE3725E97977F79CD281FD52BF78BC67C9232228E37AFF894A844'
        Target = 'E7F07D0CED655852CEFD144679829ED3EAEFFF6C06A232D861E1514ACADA66B3'
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
$isDirectPsarc = (Split-Path -Leaf $full) -eq 'PSARC'
if (-not ($isRom -or $isGameData -or $isDirectPsarc)) {
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
} elseif ($isGameData) {
    Write-Host '    (게임 데이터 쪽입니다)' -ForegroundColor Yellow
    Write-Host '    이 폴더는 게임이 롬에서 복사해 만든 사본입니다.' -ForegroundColor Yellow
    Write-Host '    여기만 바꾸면 게임이 "게임 데이터가 손상되었습니다" 로 막을 수 있습니다.' -ForegroundColor Yellow
    Write-Host '    롬 쪽(...\PS3_GAME\USRDIR\PSARC)에 적용하는 편이 안전합니다.' -ForegroundColor Yellow
} else {
    Write-Host '    (직접 선택한 PSARC 폴더입니다 — 파일 해시로 판본을 검증합니다)' -ForegroundColor Cyan
}

# ---------------------------------------------------------------- 3. 원본 검증
Write-Step '원본 5개 파일 크기 / SHA-256 검증'
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
Write-Ok '원본 PSARC 5개 확인 완료'

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

        # ISO와 RPCS3 설치 데이터의 시각이 다르므로 대상의 실제 값을 보존합니다.
        $sourceMtimeUtc = (Get-Item -LiteralPath $src).LastWriteTimeUtc

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

        # 패치 전 대상 파일의 수정시각을 정확히 복원합니다.
        (Get-Item -LiteralPath $src).LastWriteTimeUtc = $sourceMtimeUtc
        Write-Ok "$n 교체 및 수정시각 복원"
    }
}
finally {
    if (Test-Path -LiteralPath $tempDir) {
        Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

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
