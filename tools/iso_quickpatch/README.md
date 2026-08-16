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

`OGMDIsoQuickPatch.cs` 는 .NET WinForms 단일 파일 소스입니다.
range pack 을 먼저 만든 뒤 함께 묶어 단일 실행 파일로 게시합니다.

```
python build_range_pack.py          # OGMD_ISO_ranges.bin 생성
```

생성된 range pack 을 리소스로 포함해 빌드하면 배포용 실행 파일이 나옵니다.

## 주의

- 복호화된 일본판 `BLJS10335` 만 대상으로 합니다
- ISO 빠른 패처와 xdelta 방식을 **같은 원본에 중복 적용하지 않습니다**
- 세이브 데이터와 PPU/SPU/셰이더 캐시는 건드리지 않습니다
- 패치 후 `dev_hdd0\game\BLJS10335` 에 남아 있는 설치 데이터는 정리해야 새 내용이 쓰입니다
