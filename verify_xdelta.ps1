<#
  슈퍼로봇대전 OG 문 드웰러즈 (BLJS10335) 한국어 패치 검증 스크립트
  설치된 다섯 PSARC 파일의 크기와 SHA-256을 확인해 현재 상태를 알려줍니다.
  파일을 수정하지 않습니다. 읽기만 합니다.

  사용법:
    .\verify_xdelta.ps1 -TargetDir "<...\BLJS10335\USRDIR\PSARC>"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetDir
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

if (-not (Test-Path -LiteralPath $TargetDir -PathType Container)) {
    Write-Host "[실패] 대상 폴더가 없습니다: $TargetDir" -ForegroundColor Red
    exit 1
}
$full = (Resolve-Path -LiteralPath $TargetDir).Path

Write-Host "대상: $full"
Write-Host ''

$patched = 0
$original = 0
$unknown = 0

foreach ($n in $SPEC.Keys) {
    $f = Join-Path $full "$n.psarc.sdat"
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) {
        Write-Host ("{0,-10} [없음] 파일이 없습니다" -f $n) -ForegroundColor Red
        $unknown++
        continue
    }
    $i = Get-Item -LiteralPath $f
    $h = (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash

    if ($h -eq $SPEC[$n].Target) {
        Write-Host ("{0,-10} [한국어 패치됨] {1}" -f $n, $h) -ForegroundColor Green
        $patched++
    } elseif ($h -eq $SPEC[$n].Source) {
        Write-Host ("{0,-10} [원본]          {1}" -f $n, $h) -ForegroundColor Yellow
        $original++
    } else {
        Write-Host ("{0,-10} [알 수 없음]    {1}" -f $n, $h) -ForegroundColor Red
        Write-Host ("           크기 {0:N0} (기대 {1:N0})" -f $i.Length, $SPEC[$n].Size)
        $unknown++
    }
}

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

Write-Host ''
if ($patched -eq $SPEC.Count) {
    Write-Host '=> 다섯 PSARC 파일 모두 한국어 패치가 정상 적용된 상태입니다.' -ForegroundColor Green
    exit 0
} elseif ($original -eq $SPEC.Count) {
    Write-Host '=> 다섯 PSARC 파일 모두 원본 상태입니다. install_xdelta.ps1 로 패치를 적용하세요.' -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "=> 상태가 섞여 있습니다. 패치됨 $patched / 원본 $original / 알 수 없음 $unknown" -ForegroundColor Red
    Write-Host '   restore_xdelta_backup.ps1 로 원본을 복구한 뒤 다시 설치하는 것을 권합니다.' -ForegroundColor Red
    exit 1
}
