<#
    OGMD_ISO_QuickPatch.exe 빌드.

    OGMDIsoQuickPatch.cs 와 range pack 을 묶어 단일 실행 파일을 만든다.
    range pack 은 저장소에 없으므로 build_range_pack.py 로 먼저 만들어야 한다.

        python build_range_pack.py
        powershell -ExecutionPolicy Bypass -File .\build.ps1

    소스가 C# 5 문법만 쓰므로 Visual Studio 없이 Windows 기본 .NET Framework
    컴파일러로 빌드된다. 배포된 실행 파일도 이 컴파일러로 만들었다.
#>
[CmdletBinding()]
param(
    [string] $RangePack,
    [string] $OutputPath,
    # 배포본은 후보 파일로 먼저 만든 뒤 검증하고 정본으로 복사했다.
    # 어셈블리 이름이 실행 파일 이름에서 나오므로, 이 값을 바꾸면 산출물 바이트도 바뀐다.
    [string] $AssemblyName = 'OGMD_ISO_QuickPatch'
)

$ErrorActionPreference = 'Stop'

# param 기본값에서는 $PSScriptRoot 가 비어 있을 수 있어 본문에서 정한다.
$here = $PSScriptRoot
if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $RangePack) { $RangePack = Join-Path $here 'OGMD_ISO_ranges.bin' }
if (-not $OutputPath) { $OutputPath = Join-Path $here ($AssemblyName + '.exe') }

$source = Join-Path $here 'OGMDIsoQuickPatch.cs'
if (-not (Test-Path -LiteralPath $source)) {
    throw "소스를 찾을 수 없습니다: $source"
}

if (-not (Test-Path -LiteralPath $RangePack)) {
    throw @"
range pack 이 없습니다: $RangePack

이 파일은 게임 데이터에서 뽑아낸 패치 페이로드라 저장소에 포함되지 않습니다.
같은 폴더에서 아래를 먼저 실행해 만드세요. NumPy 가 필요합니다.

    python -m pip install numpy
    python build_range_pack.py
"@
}

# .NET Framework 4.x 의 csc.exe. 배포본을 만든 컴파일러이며, Roslyn 으로 바꾸면
# 산출물이 달라진다.
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $csc)) {
    throw "C# 컴파일러를 찾지 못했습니다: $csc"
}

Write-Host "컴파일러   $csc"
Write-Host ("range pack {0:N0} bytes" -f (Get-Item -LiteralPath $RangePack).Length)

# 리소스 이름은 소스의 PatchResourceName 상수와 정확히 같아야 한다. 다르면 실행 시
# "실행 파일 내부 패치 데이터를 찾을 수 없습니다." 로 실패한다.
$resourceName = 'OGMD_ISO_ranges.bin'

# /target:winexe 라야 일반 실행 때 콘솔 창이 뜨지 않는다.
$arguments = @(
    '/nologo'
    '/optimize+'
    '/target:winexe'
    "/out:$OutputPath"
    '/reference:System.Windows.Forms.dll'
    '/reference:System.Drawing.dll'
    "/resource:$RangePack,$resourceName"
    $source
)

& $csc $arguments
if ($LASTEXITCODE -ne 0) {
    throw "빌드 실패 (csc 종료코드 $LASTEXITCODE)"
}

$built = Get-Item -LiteralPath $OutputPath
Write-Host ''
Write-Host ("완료       {0}" -f $built.FullName)
Write-Host ("크기       {0:N0} bytes" -f $built.Length)
Write-Host ("SHA-256    {0}" -f (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash)
Write-Host ''
Write-Host '해시는 빌드할 때마다 달라집니다. README 의 재현 빌드 항목을 참고하세요.'
