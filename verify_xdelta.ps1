<#
  슈퍼로봇대전 OG 문 드웰러즈 (BLJS10335) 한국어 패치 검증 스크립트
  설치된 네 파일의 크기와 SHA-256을 확인해 현재 상태를 알려줍니다.
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

$SPEC = [ordered]@{
    'Common' = @{
        Size   = 505828992
        Source = '99B298B3BBE126647582A8B6201513B5E80E2B2F06BF0D5BB1F0D87D0D2093BB'
        Target = '577C02A7BBEDA1CC981D5EB7F042827D3FDE0E0B5C60DB708E5527CA0DA212D4'
    }
    'General2d' = @{
        Size   = 611585392
        Source = '04C3D1DA43BBE58622FE89499C08A2525CD5AB78C30B830A0D1781ED59F16667'
        Target = '871F3E10DADFB6DBA2431AF5BF3D0B597BE140B601A0D299B8FE640BEE68F94B'
    }
    'Logic' = @{
        Size   = 38399120
        Source = 'AF453B395D358FAB79740310BBA03F400A54F3D86CC6A82FD0A504FF25F5F181'
        Target = 'C89D69E2CC103716ADC5FD08ECDEB1104427E680F877B2445C9F10752EC88EE1'
    }
    'Battle' = @{
        Size   = 1729186848
        Source = '2C5CA16F75FCE3725E97977F79CD281FD52BF78BC67C9232228E37AFF894A844'
        Target = '04D212340C7F627B61C1CCFDB3E9F8CE82D0D2DDC6FE37A37525329E53575792'
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

Write-Host ''
if ($patched -eq 4) {
    Write-Host '=> 네 파일 모두 한국어 패치가 정상 적용된 상태입니다.' -ForegroundColor Green
    exit 0
} elseif ($original -eq 4) {
    Write-Host '=> 네 파일 모두 원본 상태입니다. install_xdelta.ps1 로 패치를 적용하세요.' -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "=> 상태가 섞여 있습니다. 패치됨 $patched / 원본 $original / 알 수 없음 $unknown" -ForegroundColor Red
    Write-Host '   restore_xdelta_backup.ps1 로 원본을 복구한 뒤 다시 설치하는 것을 권합니다.' -ForegroundColor Red
    exit 1
}
