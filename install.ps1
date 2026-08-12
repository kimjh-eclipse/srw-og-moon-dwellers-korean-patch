<#
  슈퍼로봇대전 OG 문 드웰러즈 (BLJS10335) 한국어 패치 설치 스크립트
  버전 v20260813

  - 원본 4개 파일을 검증한 뒤 백업하고, xdelta 패치를 적용합니다.
  - 임시 파일에 적용해 해시를 검증한 뒤에만 실제 파일을 교체합니다.
  - 교체 후 이 게임의 SPU 캐시를 삭제합니다. (남아 있으면 화면이 하얗게 보일 수 있습니다)
  - 실패해도 원본이나 게임 폴더를 절대 삭제하지 않습니다.

  사용법:
    .\install.ps1 -TargetDir "<...\BLJS10335\USRDIR\PSARC>"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetDir,

    [string]$XdeltaPath,
    [string]$PatchDir,
    # 백업은 게임 데이터 폴더 밖(기본값: 이 스크립트 위치)에 만듭니다.
    [string]$BackupRoot,
    [switch]$SkipBackup,
    # SPU 캐시를 지우지 않습니다. 권장하지 않습니다.
    [switch]$KeepSpuCache
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
        Target = 'A331AE43760FD276B1547A84CE9C1D56E71F24CC20FD0BF021641916A9468619'
        Mtime  = '2016-05-04T04:37:57Z'
    }
    'General2d' = @{
        Size   = 611585392
        Source = '04C3D1DA43BBE58622FE89499C08A2525CD5AB78C30B830A0D1781ED59F16667'
        Target = '6EC64D6D9407BC06E7A95E179087741BAC0C3DC7868818C70E3A3F66B848E835'
        Mtime  = '2016-04-30T02:15:24Z'
    }
    'Logic' = @{
        Size   = 38399120
        Source = 'AF453B395D358FAB79740310BBA03F400A54F3D86CC6A82FD0A504FF25F5F181'
        Target = '689240DB752B50E619AE1D14010A275019A4A7303E427F9A4DCB83FAADDD54B6'
        Mtime  = '2016-05-04T10:52:39Z'
    }
    'Battle' = @{
        Size   = 1729186848
        Source = '2C5CA16F75FCE3725E97977F79CD281FD52BF78BC67C9232228E37AFF894A844'
        Target = '12C7D6AAD3B928A640B3FC091FE50B182E9D67CBAE07084102AC49A5A6B803BF'
        Mtime  = '2016-05-04T04:50:11Z'
    }
}

function Write-Step($m) { Write-Host "[*] $m" -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Fail($m) {
    Write-Host "[실패] $m" -ForegroundColor Red
    Write-Host ""
    Write-Host "게임 파일은 변경되지 않았거나, 백업 폴더에 원본이 남아 있습니다." -ForegroundColor Yellow
    Write-Host "복구가 필요하면 restore_backup.ps1 을 사용하세요." -ForegroundColor Yellow
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
if ($full -notmatch 'BLJS10335[\\/]USRDIR[\\/]PSARC[\\/]?$') {
    Fail "대상 경로가 BLJS10335\USRDIR\PSARC 로 끝나지 않습니다: $full"
}
if (-not (Test-Path -LiteralPath $XdeltaPath -PathType Leaf)) { Fail "xdelta.exe 를 찾을 수 없습니다: $XdeltaPath" }
if (-not (Test-Path -LiteralPath $PatchDir  -PathType Container)) { Fail "패치 폴더를 찾을 수 없습니다: $PatchDir" }
foreach ($n in $SPEC.Keys) {
    $pf = Join-Path $PatchDir "$n.psarc.sdat.xdelta"
    if (-not (Test-Path -LiteralPath $pf -PathType Leaf)) { Fail "패치 파일이 없습니다: $pf" }
}
Write-Ok "대상: $full"

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

# ---------------------------------------------------------------- 9. SPU 캐시 삭제
# 게임 데이터를 교체한 뒤 예전 SPU 캐시가 남아 있으면 화면이 하얗게 보일 수 있습니다.
# PPU 캐시와 셰이더 캐시는 건드리지 않습니다.
if ($KeepSpuCache) {
    Write-Host '[!] -KeepSpuCache 지정됨. SPU 캐시를 남깁니다.' -ForegroundColor Yellow
    Write-Host '    화면이 하얗게 보이면 RPCS3 게임 목록에서 해당 게임 우클릭 →' -ForegroundColor Yellow
    Write-Host '    Remove → Remove SPU Cache 를 실행하세요.' -ForegroundColor Yellow
} else {
    Write-Step 'SPU 캐시 삭제'
    # <RPCS3>\dev_hdd0\game\BLJS10335\USRDIR\PSARC 에서 RPCS3 루트로 거슬러 올라갑니다.
    $rpcs3Root = $full
    for ($i = 0; $i -lt 5; $i++) { $rpcs3Root = Split-Path -Parent $rpcs3Root }
    $cacheDir = Join-Path $rpcs3Root 'cache\BLJS10335'
    if (Test-Path -LiteralPath $cacheDir -PathType Container) {
        $spu = @(Get-ChildItem -LiteralPath $cacheDir -Recurse -File -Filter 'spu-*.dat' -ErrorAction SilentlyContinue)
        if ($spu.Count -eq 0) {
            Write-Host '    삭제할 SPU 캐시가 없습니다.'
        } else {
            foreach ($f in $spu) {
                Remove-Item -LiteralPath $f.FullName -Force
                Write-Host ("    삭제 {0} ({1:N0} bytes)" -f $f.Name, $f.Length)
            }
        }
        Write-Ok 'SPU 캐시 정리 완료'
        Write-Host '    플레이를 계속하면 캐시가 다시 쌓여 화면이 하얗게 보일 수 있습니다.' -ForegroundColor Yellow
        Write-Host '    그때는 RPCS3 게임 목록에서 우클릭 -> Remove -> Remove SPU Cache 하세요.' -ForegroundColor Yellow
    } else {
        Write-Host "    캐시 폴더가 없습니다: $cacheDir"
        Write-Host '    (아직 이 게임을 실행한 적이 없으면 정상입니다)'
    }
}

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
