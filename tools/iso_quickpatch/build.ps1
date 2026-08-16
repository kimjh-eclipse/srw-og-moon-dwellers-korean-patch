<#
    OGMD_ISO_QuickPatch.exe 빌드.

    OGMDIsoQuickPatch.cs 와 range pack 을 묶어 단일 실행 파일을 만든다.
    range pack 은 저장소에 없으므로 build_range_pack.py 로 먼저 만들어야 한다.

        python build_range_pack.py
        powershell -ExecutionPolicy Bypass -File .\build.ps1

    C# 5 문법만 쓰므로 Visual Studio 없이 Windows 기본 .NET Framework 컴파일러로 빌드된다.
#>
[CmdletBinding()]
param(
    [string] $RangePack,
    [string] $OutputPath,
    [ValidateSet('anycpu', 'x64', 'x86')]
    [string] $Platform = 'anycpu'
)

$ErrorActionPreference = 'Stop'

# param 기본값에서는 $PSScriptRoot 가 비어 있을 수 있어 본문에서 정한다.
$here = $PSScriptRoot
if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $RangePack) { $RangePack = Join-Path $here 'OGMD_ISO_ranges.bin' }
if (-not $OutputPath) { $OutputPath = Join-Path $here 'OGMD_ISO_QuickPatch.exe' }

$source = Join-Path $here 'OGMDIsoQuickPatch.cs'
if (-not (Test-Path -LiteralPath $source)) {
    throw "소스를 찾을 수 없습니다: $source"
}

if (-not (Test-Path -LiteralPath $RangePack)) {
    throw @"
range pack 이 없습니다: $RangePack

이 파일은 게임 데이터에서 뽑아낸 패치 페이로드라 저장소에 포함되지 않습니다.
같은 폴더에서 아래를 먼저 실행해 만드세요.

    python build_range_pack.py
"@
}

# 컴파일러 찾기 — Visual Studio 의 Roslyn 이 있으면 우선 쓰고, 없으면 .NET Framework 기본 컴파일러.
$csc = $null
foreach ($root in @("${env:ProgramFiles}\Microsoft Visual Studio", "${env:ProgramFiles(x86)}\Microsoft Visual Studio")) {
    if (Test-Path -LiteralPath $root) {
        $found = Get-ChildItem -LiteralPath $root -Recurse -Filter 'csc.exe' -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -like '*\MSBuild\*\Bin\Roslyn\csc.exe' } |
            Select-Object -First 1
        if ($found) { $csc = $found.FullName; break }
    }
}
if (-not $csc) {
    $fallback = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    if (Test-Path -LiteralPath $fallback) { $csc = $fallback }
}
if (-not $csc) {
    throw 'C# 컴파일러(csc.exe)를 찾지 못했습니다. .NET Framework 4 이상이 필요합니다.'
}

Write-Host "컴파일러  $csc"
Write-Host ("range pack {0:N0} bytes" -f (Get-Item -LiteralPath $RangePack).Length)

# 리소스 이름은 소스의 PatchResourceName 상수와 정확히 같아야 한다. 다르면 실행 시
# "실행 파일 내부 패치 데이터를 찾을 수 없습니다." 로 실패한다.
$resourceName = 'OGMD_ISO_ranges.bin'

$arguments = @(
    '/nologo'
    '/target:winexe'
    "/platform:$Platform"
    '/optimize+'
    "/out:$OutputPath"
    "/resource:$RangePack,$resourceName"
    '/reference:System.dll'
    '/reference:System.Core.dll'
    '/reference:System.Drawing.dll'
    '/reference:System.Windows.Forms.dll'
    $source
)

& $csc $arguments
if ($LASTEXITCODE -ne 0) {
    throw "빌드 실패 (csc 종료코드 $LASTEXITCODE)"
}

$built = Get-Item -LiteralPath $OutputPath
$hash = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash

Write-Host ''
Write-Host ("완료      {0}" -f $built.FullName)
Write-Host ("크기      {0:N0} bytes" -f $built.Length)
Write-Host ("SHA-256   {0}" -f $hash)
Write-Host ''
Write-Host '배포된 실행 파일과 해시가 같지는 않습니다. 아래 README 의 재현 빌드 항목을 참고하세요.'
