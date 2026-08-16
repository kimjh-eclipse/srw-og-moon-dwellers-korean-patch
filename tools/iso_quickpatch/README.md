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

range pack 을 먼저 만들고, 그것을 리소스로 묶어 실행 파일을 만듭니다.

```
python build_range_pack.py
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

`build.ps1` 은 Visual Studio의 Roslyn `csc.exe` 를 먼저 찾고, 없으면
`%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe` 를 씁니다. 둘 다 통과합니다.

리소스 이름은 반드시 `OGMD_ISO_ranges.bin` 이어야 합니다.
소스의 `PatchResourceName` 상수와 다르면 실행할 때
`실행 파일 내부 패치 데이터를 찾을 수 없습니다.` 로 끝납니다.

| 옵션 | 기본값 |
|---|---|
| `-RangePack` | 같은 폴더의 `OGMD_ISO_ranges.bin` |
| `-OutputPath` | 같은 폴더의 `OGMD_ISO_QuickPatch.exe` |
| `-Platform` | `anycpu` (`x64`, `x86` 지정 가능) |

### 재현 빌드

이 스크립트로 나온 실행 파일은 **릴리스에 올라간 것과 바이트 단위로 같지 않습니다.**
배포본 25,719,808 바이트에 대해 약 1.5KB 차이가 납니다. Win32 매니페스트 쪽 차이로
보이는데, 배포본을 만들 때 쓴 빌드 설정이 파일로 남아 있지 않아 그대로 되살리지
못했습니다. 동작과 내장 range pack 은 동일합니다.

배포본과 같은 것을 쓰시려면 [Releases](../../../releases/latest) 의 ZIP 안에 든
실행 파일을 그대로 쓰시고, 해시는 릴리스 노트에 적힌 값과 대조하세요.

## 주의

- 복호화된 일본판 `BLJS10335` 만 대상으로 합니다
- ISO 빠른 패처와 xdelta 방식을 **같은 원본에 중복 적용하지 않습니다**
- 세이브 데이터와 PPU/SPU/셰이더 캐시는 건드리지 않습니다
- 패치 후 `dev_hdd0\game\BLJS10335` 에 남아 있는 설치 데이터는 정리해야 새 내용이 쓰입니다
