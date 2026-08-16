<#
  슈퍼로봇대전 OG 문 드웰러즈 (BLJS10335) 원본 복구 스크립트
  install_xdelta.ps1 이 만든 backup_original_* 폴더에서 원본 네 파일을 되돌립니다.

  사용법:
    .\restore_xdelta_backup.ps1 -TargetDir "<...\BLJS10335\USRDIR\PSARC>"
    .\restore_xdelta_backup.ps1 -TargetDir "..." -BackupDir "<backup_original_YYYYMMDD_HHMMSS>"

  -BackupDir 를 생략하면 이 스크립트 위치에서 가장 최근 backup_original_* 폴더를 찾습니다.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetDir,

    [string]$BackupDir
)

$ErrorActionPreference = 'Stop'

$ScriptRoot = $PSScriptRoot
if ([string]::IsNullOrEmpty($ScriptRoot)) { $ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }
if ([string]::IsNullOrEmpty($ScriptRoot)) { $ScriptRoot = (Get-Location).Path }

# 원본 SHA-256 및 원래 수정시각(UTC)
$SPEC = [ordered]@{
    'Common'    = @{ Size = 505828992;  Hash = '99B298B3BBE126647582A8B6201513B5E80E2B2F06BF0D5BB1F0D87D0D2093BB'; Mtime = '2016-05-04T04:37:57Z' }
    'General2d' = @{ Size = 611585392;  Hash = '04C3D1DA43BBE58622FE89499C08A2525CD5AB78C30B830A0D1781ED59F16667'; Mtime = '2016-04-30T02:15:24Z' }
    'Logic'     = @{ Size = 38399120;   Hash = 'AF453B395D358FAB79740310BBA03F400A54F3D86CC6A82FD0A504FF25F5F181'; Mtime = '2016-05-04T10:52:39Z' }
    'Battle'    = @{ Size = 1729186848; Hash = '2C5CA16F75FCE3725E97977F79CD281FD52BF78BC67C9232228E37AFF894A844'; Mtime = '2016-05-04T04:50:11Z' }
}

function Fail($m) {
    Write-Host "[실패] $m" -ForegroundColor Red
    Write-Host '게임 파일은 변경되지 않았습니다.' -ForegroundColor Yellow
    exit 1
}

# RPCS3 실행 확인
$rp = Get-Process -Name 'rpcs3' -ErrorAction SilentlyContinue
if ($rp) { Fail "RPCS3가 실행 중입니다 (PID $($rp.Id -join ', ')). 완전히 종료한 뒤 다시 실행하세요." }

# 대상 확인
if (-not (Test-Path -LiteralPath $TargetDir -PathType Container)) { Fail "대상 폴더가 없습니다: $TargetDir" }
$full = (Resolve-Path -LiteralPath $TargetDir).Path
$isRom      = $full -match 'PS3_GAME[\\/]USRDIR[\\/]PSARC[\\/]?$'
$isGameData = $full -match 'BLJS10335[\\/]USRDIR[\\/]PSARC[\\/]?$'
if (-not ($isRom -or $isGameData)) {
    Fail ("대상 경로가 올바르지 않습니다: $full`n" +
          "  롬(권장)   : ...\BLJS10335\PS3_GAME\USRDIR\PSARC`n" +
          "  게임 데이터: ...\dev_hdd0\game\BLJS10335\USRDIR\PSARC")
}

# 백업 폴더 결정
if ([string]::IsNullOrEmpty($BackupDir)) {
    $cand = Get-ChildItem -LiteralPath $ScriptRoot -Directory -Filter 'backup_original_*' -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending | Select-Object -First 1
    if (-not $cand) {
        Fail "backup_original_* 폴더를 찾을 수 없습니다. -BackupDir 로 직접 지정하세요.`n  찾은 위치: $ScriptRoot"
    }
    $BackupDir = $cand.FullName
}
if (-not (Test-Path -LiteralPath $BackupDir -PathType Container)) { Fail "백업 폴더가 없습니다: $BackupDir" }
Write-Host "백업 폴더: $BackupDir"
Write-Host ''

# 백업 내용 검증 — 원본이 맞는지 먼저 확인한 뒤에만 복구
Write-Host '[*] 백업 파일 검증'
foreach ($n in $SPEC.Keys) {
    $b = Join-Path $BackupDir "$n.psarc.sdat"
    if (-not (Test-Path -LiteralPath $b -PathType Leaf)) { Fail "백업에 파일이 없습니다: $b" }
    $i = Get-Item -LiteralPath $b
    if ($i.Length -ne $SPEC[$n].Size) { Fail "$n 백업 크기 불일치. 기대 $($SPEC[$n].Size), 실제 $($i.Length)" }
    $h = (Get-FileHash -LiteralPath $b -Algorithm SHA256).Hash
    if ($h -ne $SPEC[$n].Hash) {
        Fail "$n 백업이 원본이 아닙니다.`n  기대: $($SPEC[$n].Hash)`n  실제: $h"
    }
    Write-Host ("    {0,-10} OK" -f $n)
}

# 복구
Write-Host ''
Write-Host '[*] 원본 복구'
foreach ($n in $SPEC.Keys) {
    $b = Join-Path $BackupDir "$n.psarc.sdat"
    $t = Join-Path $full "$n.psarc.sdat"
    Copy-Item -LiteralPath $b -Destination $t -Force
    $mt = [datetime]::Parse($SPEC[$n].Mtime, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal)
    (Get-Item -LiteralPath $t).LastWriteTimeUtc = $mt
    Write-Host ("    {0,-10} 복구 완료" -f $n)
}

Write-Host ''
Write-Host '=== 복구 완료 ===' -ForegroundColor Green
foreach ($n in $SPEC.Keys) {
    $t = Join-Path $full "$n.psarc.sdat"
    Write-Host ("{0,-10} {1}" -f $n, (Get-FileHash -LiteralPath $t -Algorithm SHA256).Hash)
}
Write-Host ''
Write-Host '백업 폴더는 지우지 않았습니다. 필요 없으면 직접 삭제하세요.' -ForegroundColor Yellow
