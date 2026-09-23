# 설치 안내

2026-09-23 갱신 · 배포 기준 **v20260923**

## 준비

PS3 일본판 『슈퍼로봇대전 OG 더 문 드웰러즈』(`BLJS10335`)의 복호화된 ISO 또는 폴더형 원본이 필요합니다. 게임 원본은 제공하지 않습니다. RPCS3를 종료하고, 원본 및 세이브를 백업한 다음 진행하세요.

- [최신 릴리즈](https://github.com/kimjh-eclipse/srw-og-moon-dwellers-korean-patch/releases/latest)
- [v20260923 ZIP 다운로드](https://github.com/kimjh-eclipse/srw-og-moon-dwellers-korean-patch/releases/download/v20260923/OGMD_KR_v20260923.zip)
- ZIP 크기: **107,431,851 바이트**
- ZIP SHA-256: `B4C8FC1AE7B2ACDD1FE2124B4E6C184CD57F970C0BA4760AA0E594998B59B3C2`

```powershell
Get-FileHash .\OGMD_KR_v20260923.zip -Algorithm SHA256
```

ZIP을 전부 풀어 사용하세요. EXE만 따로 옮기지 마세요. 백업과 임시 출력 파일을 저장할 여유 공간이 필요합니다.

### 이전 버전에서 업데이트

이미 패치된 파일 위에 무조건 덮어쓰지 마세요. 먼저 **이전 버전의 도구와 그때 만든 백업**으로 원본을 복구하고, 새 버전으로 검사·적용하세요. 이번 버전에는 `General3d`가 추가되어 과거 6개 대상 백업과 현재 7개 대상 백업을 동일하게 취급할 수 없습니다. 새 백업은 별도 경로에 보관하세요.

## 설치 방식 선택 — 하나만 사용

| 방식 | 대상 | 도구 |
|---|---|---|
| A. ISO 패치 | 복호화된 ISO | `OGMD_ISO_QuickPatch.exe` |
| B. 폴더 직접 패치 | 폴더형 게임 또는 RPCS3 설치 데이터 | 같은 EXE의 폴더 기능 |
| C. PowerShell 설치 | 폴더형 게임 또는 RPCS3 설치 데이터 | `install_xdelta.ps1` |

B와 C는 같은 폴더에 연속 적용하는 절차가 아니라 선택 가능한 대안입니다.

## A. ISO 빠른 패처

1. `OGMD_ISO_QuickPatch.exe`를 실행합니다.
2. 대상 ISO와 백업 저장 경로를 지정합니다.
3. **ISO 원본 검사**로 적용 가능한 원본인지 확인합니다.
4. **ISO에 한국어 패치 적용**을 누릅니다.
5. 성공 로그를 확인하고 백업을 보관합니다.
6. 아래의 설치 데이터·SPU 캐시 정리를 확인한 뒤 RPCS3에서 실행합니다.

ISO는 직접 변경됩니다. **원본으로 복구** 버튼은 ISO용 백업으로 ISO를 복구하는 기능입니다. 폴더 백업을 복구하는 버튼이 아닙니다.

**ISO 패치 성공 후 BLJS10335 설치 데이터와 해당 SPU 캐시만 정리 (권장)** 옵션은 ISO 패치에 적용됩니다. 유효한 RPCS3 경로가 필요하며, 경로가 없으면 정리를 건너뛸 수 있습니다. 옵션을 켰다는 이유만으로 정리가 모두 완료되었다고 판단하지 말고 로그를 확인하세요.

## B. EXE로 폴더 직접 패치

1. 게임 폴더 또는 RPCS3 경로를 지정합니다. 게임 루트, `PS3_GAME`, `USRDIR\PSARC` 및 RPCS3 루트에서 대상을 찾을 수 있습니다.
2. **폴더 게임 상태 검사**를 누르고 실제로 선택된 대상 경로를 확인합니다.
3. **폴더 직접 패치 전 원본 PSARC 5개 자동 백업 (권장)**을 켜 둡니다.
4. **RPCS3 / 폴더 게임에 직접 패치**를 누르고 성공 로그와 백업 경로를 확인합니다.

원본 PSARC의 수정시각을 보존합니다. 제목·아이콘 파일은 존재 여부와 적용 가능한 원본인지에 따라 처리되므로 로그도 확인하세요.

**ISO용 정리 옵션은 폴더 직접 패치에는 적용되지 않습니다.** SPU 캐시는 따로 정리하세요. 특히 `dev_hdd0\game\BLJS10335`를 직접 패치했다면 그 폴더를 삭제하면 방금 적용한 패치도 없어집니다. 설치 데이터를 다시 만들면 디스크 쪽 데이터로 돌아가므로 지속적으로 사용하려면 ISO 또는 폴더형 원본에도 패치해야 합니다.

## C. PowerShell로 폴더 설치

압축을 푼 배포 폴더에서 실행합니다. 경로는 자신의 게임 위치로 바꾸세요.

```powershell
powershell -ExecutionPolicy Bypass -File .\install_xdelta.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"
```

대상은 PSARC **5개**와 제목·아이콘 **2개**, 총 7개입니다.

| PSARC 파일 | 일본판 원본 크기(바이트) |
|---|---:|
| Common.psarc.sdat | 505,828,992 |
| General2d.psarc.sdat | 611,585,392 |
| General3d.psarc.sdat | 870,220,816 |
| Logic.psarc.sdat | 38,399,120 |
| Battle.psarc.sdat | 1,729,186,848 |

스크립트는 원본 해시 검사, 백업, 임시 출력 생성 및 출력 해시 검증 후 파일을 교체하고 수정시각을 보존합니다. `PARAM.SFO`와 `ICON0.PNG`는 파일이 없거나 지원하는 원본 해시와 다르면 건너뛸 수 있습니다. PSARC 성공만으로 제목·아이콘까지 적용되었다고 판단하지 마세요.

이 스크립트는 RPCS3 설치 데이터나 SPU 캐시를 자동 정리하지 않습니다. 작업 중 중단이나 디스크 오류에 대비해 백업을 유지하세요.

## 설치 데이터와 SPU 캐시

**ISO 또는 폴더형 원본을 패치한 경우:** 기존 설치 데이터가 남아 있으면 예전 파일을 읽을 수 있습니다. RPCS3를 종료하고 `<RPCS3>\dev_hdd0\game\BLJS10335`만 별도 위치로 백업·이동한 뒤 재설치하세요. RPCS3 전체나 `dev_hdd0` 전체를 삭제하지 마세요. `dev_hdd0\home`의 세이브는 정리 대상이 아닙니다.

**hdd0 설치 데이터를 직접 패치한 경우:** 위 설치 데이터 폴더를 삭제하지 마세요. SPU 캐시만 정리합니다.

SPU 캐시는 RPCS3 게임 목록의 해당 게임 우클릭 메뉴에서 **Remove → Remove SPU Cache**로 정리할 수 있습니다. UI 언어에 따라 이름은 다를 수 있습니다.

현재 EXE의 자동 정리는 `cache\BLJS10335\spu-safe-v1-tane.dat`를 대상으로 하며, 하위 `ppu-…-EBOOT.BIN` 폴더의 `spu*.dat`까지 재귀적으로 정리하지 않습니다. 자동 정리 로그에서 캐시가 없다고 나와도 위 메뉴로 해당 게임의 SPU 캐시를 확인·정리하세요. PPU·셰이더 캐시와 세이브는 이 안내의 삭제 대상이 아닙니다.

## 설치 확인과 복구

폴더 설치 확인:

```powershell
powershell -ExecutionPolicy Bypass -File .\verify_xdelta.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"
```

PSARC 5개 결과와 제목·아이콘 처리 결과를 각각 확인하세요. 게임의 실제 표시까지 확인하는 검사는 아닙니다.

폴더 복구:

```powershell
powershell -ExecutionPolicy Bypass -File .\restore_xdelta_backup.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC" -BackupDir "C:\백업\backup_original_날짜시간"
```

폴더 복구에는 해당 설치 때 생성한 신뢰할 수 있는 **백업 디렉터리**를 지정합니다. ISO용 `.ogmd-backup` 파일과 혼용하지 마세요. 이전 버전 백업은 이전 버전 복구 도구로 복구합니다. 원본 디스크 쪽을 복구했다면 설치 데이터와 SPU 캐시도 위 기준에 따라 정리하세요.

## 선택 사항: 아카이브 재생 중지 확인창

아카이브 재생 중지 확인창의 한글화는 ISO에 포함된 EBOOT 수정이 아니라 **별도 RPCS3 패치**입니다.

1. 배포물의 `RPCS3_optional/OGMD_archive_popup_patch.yml`을 RPCS3 패치 관리자에서 가져옵니다.
2. `OGMD archive replay-question Korean 20260918` 패치를 활성화합니다.
3. 대상 실행 파일의 PPU 해시가 `e429bb11d03c2e6a046775179d21169cba555c47`인지 확인합니다.

기존 `patch.yml`이나 설정 파일 전체를 이 파일로 덮어쓰지 마세요. 이 선택 패치를 활성화하지 않으면 해당 확인창은 일본어로 남습니다. 정적 검증과 별개로 실제 화면 테스트가 필요합니다.

## 실행 후 확인

기존 Save State 대신 게임을 새로 부팅해 확인하세요. 패치 이전에 저장된 세이브 목록 문구는 그대로 남을 수 있습니다. EXE의 세이브 목록 한글화 기능은 별도 선택 기능이므로 백업과 처리 로그를 확인하고 사용하세요.

v20260923는 파일 해시·패치/복구 검증을 통과했지만 모든 변경 장면의 게임 실행 검증을 완료했다는 뜻은 아닙니다. [알려진 제한](known-issues.md)도 확인하세요. 문제 제보 시 버전, 게임 ID, ISO/폴더/hdd0 중 적용 경로, 검사 로그 및 화면을 [이슈](https://github.com/kimjh-eclipse/srw-og-moon-dwellers-korean-patch/issues)에 첨부해 주세요.
