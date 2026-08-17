# ISO 빠른 패처

복호화된 PS3 ISO 안의 필요한 구간만 직접 고쳐 한국어 패치를 적용하는 도구입니다.
ISO 전체 11.8GB를 다시 만들지 않습니다.

배포되는 실행 파일은 [Releases](../../../releases/latest) 의 ZIP 안에 들어 있습니다.
여기에는 그 실행 파일을 만드는 소스만 둡니다.

## 파일

| 파일 | 역할 |
|---|---|
| `OGMDIsoQuickPatch.cs` | 패처 본체. WinForms GUI, ISO 구간 쓰기, 백업·복구, RPCS3 경로 검사 |
| `build_range_pack.py` | 원본 ISO와 최종 PSARC를 비교해 바뀐 구간만 모은 range pack 생성기 |
| `build.ps1` | 위 둘을 묶어 실행 파일을 만드는 빌드 스크립트 |

## 동작 방식

PSARC 4개를 통째로 바꾸지 않고, **바뀐 바이트 구간만** ISO에 덮어씁니다.

1. `build_range_pack.py` 가 원본 ISO와 최종 PSARC를 비교해 변경 구간 목록과 데이터를
   `OGMD_ISO_ranges.bin` 으로 만듭니다.
2. 그 range pack 을 실행 파일에 내장합니다.
3. 패처는 대상 ISO에서 해당 구간만 찾아 덮어씁니다.

ISO 안의 PSARC는 크기가 바뀌지 않으므로 파일 배치가 밀리지 않습니다.
이 성질은 [고정 배치 재빌드](../../docs/fixed-layout.md) 와 같은 원리에 기대고 있습니다.

## 저장소에 없는 것

- **빌드된 실행 파일** — 하나에 약 25MB이고 릴리스 자산으로 배포됩니다
- **`OGMD_ISO_ranges.bin`** — 게임 데이터에서 뽑아낸 패치 페이로드입니다.
  `build_range_pack.py` 로 다시 만들 수 있습니다

패치 대역표와 마찬가지로 게임 원문이 들어가는 산출물은 공개하지 않습니다.

## 빌드

`OGMDIsoQuickPatch.cs` 는 .NET Framework WinForms 단일 파일 소스입니다.
C# 5 문법만 쓰므로 Visual Studio 없이 Windows에 기본으로 있는 컴파일러로 빌드됩니다.

### 1. range pack 생성

PSARC가 바뀌었을 때만 하면 됩니다. UI 코드만 고쳤다면 건너뜁니다.
NumPy가 필요합니다.

```
python -m pip install numpy
python build_range_pack.py
```

`OGMD_ISO_ranges.bin` 이 만들어집니다. 스크립트가 자기 위치를 기준으로 경로를 잡으므로
어느 폴더에서 실행해도 됩니다.

### 2. 컴파일

```
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

`build.ps1` 이 하는 일은 아래 한 줄과 같습니다.

```
%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
  /nologo /optimize+ /target:winexe
  /out:OGMD_ISO_QuickPatch.exe
  /reference:System.Windows.Forms.dll
  /reference:System.Drawing.dll
  /resource:OGMD_ISO_ranges.bin,OGMD_ISO_ranges.bin
  OGMDIsoQuickPatch.cs
```

바꾸면 안 되는 것이 셋 있습니다.

- `/target:winexe` — 빼면 일반 실행 때 콘솔 창이 같이 뜹니다
- 리소스 이름 `OGMD_ISO_ranges.bin` — 소스의 `PatchResourceName` 상수와 달라지면
  실행할 때 `실행 파일 내부 패치 데이터를 찾을 수 없습니다.` 로 끝납니다
- 컴파일러 — Roslyn(Visual Studio)으로 바꾸면 산출물이 달라집니다

| 옵션 | 기본값 |
|---|---|
| `-RangePack` | 같은 폴더의 `OGMD_ISO_ranges.bin` |
| `-OutputPath` | 같은 폴더의 `<AssemblyName>.exe` |
| `-AssemblyName` | `OGMD_ISO_QuickPatch` |

### 재현 빌드

이 소스와 절차로 **배포된 실행 파일이 그대로 재현됩니다.** 아래는 v20260816b
배포본으로 확인한 내용이며, v20260818 배포본(크기 55,884,800 바이트,
내장 range pack 55,839,294 바이트)도 같은 절차로 빌드했습니다.

| 항목 | 결과 (v20260816b 기준) |
|---|---|
| 크기 | 19,488,768 바이트로 정확히 일치 |
| 내장 range pack 19,443,733바이트 | 같은 위치에 바이트 단위로 동일 |
| 다른 바이트 | 전체에서 **18개** |

다른 18바이트는 컴파일할 때마다 달라지는 값입니다. PE 헤더의 타임스탬프와
모듈 GUID(MVID) 16바이트입니다. 이 컴파일러에는 결정적 빌드 옵션이 없어 없앨 수 없습니다.

어셈블리 이름은 산출물에 들어가므로 `-AssemblyName` 을 바꾸면 그만큼 달라집니다.
배포본은 기본값인 `OGMD_ISO_QuickPatch.exe` 로 빌드한 것입니다.

해시까지 같은 파일이 필요하면 [Releases](../../../releases/latest) 의 ZIP 안에 든
실행 파일을 쓰시고, 릴리스 노트에 적힌 값과 대조하세요.

## 주의

- 복호화된 일본판 `BLJS10335` 만 대상으로 합니다
- ISO 빠른 패처와 xdelta 방식을 **같은 원본에 중복 적용하지 않습니다**
- 세이브 데이터와 PPU/SPU/셰이더 캐시는 건드리지 않습니다
- 패치 후 `dev_hdd0\game\BLJS10335` 에 남아 있는 설치 데이터는 정리해야 새 내용이 쓰입니다
