# 설치 안내

## 적용 대상

PS3 『슈퍼로봇대전 OG 더 문 드웰러즈』 **일본판** — 게임 ID `BLJS10335`

다른 리전판에는 적용할 수 없습니다.

> **원본 게임 데이터는 직접 준비해야 합니다.**
> 이 저장소와 배포물에는 게임 파일이나 ISO가 들어 있지 않으며, 제공하지도 않습니다.

## 설치 방식 두 가지 — 하나만 고르세요

v20260816부터 방식이 둘입니다. 두 방식이 만드는 최종 한국어 데이터는 같습니다.


| 방식 | 대상 | 사용 파일 |
|---|---|---|
| **A. ISO 빠른 패처** | 복호화된 ISO | `OGMD_ISO_QuickPatch.exe` |
| **B. xdelta** | 폴더형 게임 / 추출 PSARC | `install_xdelta.ps1` + `patches` |

> **같은 원본에 두 방식을 겹쳐 적용하지 마세요.**

### 방법 A — ISO 빠른 패처

1. RPCS3를 완전히 종료합니다.
2. `OGMD_ISO_QuickPatch.exe` 를 실행합니다.
3. 복호화된 일본판 `BLJS10335` ISO와 백업 파일 경로를 지정합니다.
4. 필요하면 RPCS3 경로도 지정합니다.
5. **[원본 검사]** 로 ISO와 RPCS3 경로를 확인합니다.
6. 주의사항 확인란을 체크하고 **[ISO에 한국어 패치 적용]** 을 누릅니다.

ISO 안의 PSARC는 패치해도 크기가 바뀌지 않으므로, 전체 11.8GB를 다시 만들지 않고
필요한 구간만 고칩니다.

처음 패치할 때 복구용 `.ogmd-backup` 파일을 만듭니다. 원상복구와 다음 버전 갱신에
필요하니 보관하세요.

패치가 끝나면 아래 **4. 게임 데이터 폴더 삭제** 로 이어집니다.

아래 내용은 **방법 B (xdelta)** 기준입니다.

## ⚠️ 어디에 패치할 것인가 — 가장 중요합니다

관련 폴더가 두 곳입니다. 헷갈리기 쉬우니 먼저 확인하세요.

```
롬 (여기에 패치)     ...\BLJS10335\PS3_GAME\USRDIR\PSARC
게임 데이터 (아님)   <RPCS3 폴더>\dev_hdd0\game\BLJS10335\USRDIR\PSARC
```

게임 데이터는 게임이 첫 실행 때 롬에서 복사해 만드는 **사본**입니다.
사본만 바꾸면 게임이 무결성 검사에서 걸려
**`게임 데이터가 손상되었습니다`** 가 뜨고 진행되지 않습니다.

반드시 **롬 쪽에 패치**하고, **게임 데이터 폴더는 삭제**해서 게임이 다시 만들도록 하세요.

## 1. 준비

1. **RPCS3를 완전히 종료합니다.** 실행 중이면 설치가 거부됩니다.
2. 롬의 PSARC 폴더를 확인합니다.
   ```
   <롬 폴더>\BLJS10335\PS3_GAME\USRDIR\PSARC
   ```
3. 그 안에 다음 네 파일이 있어야 합니다.

   | 파일 | 크기 | 원본 SHA-256 |
   |---|---:|---|
   | `Common.psarc.sdat` | 505,828,992 | `99B298B3…2093BB` |
   | `General2d.psarc.sdat` | 611,585,392 | `04C3D1DA…F16667` |
   | `Logic.psarc.sdat` | 38,399,120 | `AF453B39…F5F181` |
   | `Battle.psarc.sdat` | 1,729,186,848 | `2C5CA16F…F894A844` |

4. 네 파일을 다른 곳에 복사해 두면 더 안전합니다. `install_xdelta.ps1`도 자동으로 백업합니다.
5. 세이브 데이터를 지울 필요는 없습니다. 다만 백업을 권장합니다.

## 2. 내려받기

[OGMD_KR_v20260816b.zip](https://github.com/kimjh-eclipse/srw-og-moon-dwellers-korean-patch/releases/download/v20260816b/OGMD_KR_v20260816b.zip)
을 받아 압축을 풉니다. 최신판은
[Releases](https://github.com/kimjh-eclipse/srw-og-moon-dwellers-korean-patch/releases/latest)
에서 확인하세요.

```
OGMD_KR_v20260816b.zip   31,818,753 바이트
SHA-256: 39523AF19A4133E6D779BD8744BB57DB6313B905ACA76D141158E93909590DC2
```

```powershell
Get-FileHash .\OGMD_KR_v20260816b.zip -Algorithm SHA256
```

압축을 풀면 아래 파일이 나옵니다. 방법 A는 `OGMD_ISO_QuickPatch.exe` 하나만 쓰고,
방법 B는 나머지를 씁니다.

```
OGMD_ISO_QuickPatch.exe          방법 A
install_xdelta.ps1               방법 B
verify_xdelta.ps1
restore_xdelta_backup.ps1
xdelta.exe
patches\                         Common / General2d / Logic / Battle
README_사용법.txt
CHANGELOG.txt
SHA256SUMS.txt
```

이 ZIP은 감싸는 폴더 없이 파일이 바로 들어 있습니다. 빈 폴더를 하나 만들어 그 안에
푸시는 편이 정리하기 좋습니다. 아래 명령은 모두 압축을 푼 폴더 안에서 실행합니다.

## 3. 자동 설치 (권장)

압축을 푼 폴더에서 PowerShell을 엽니다.
폴더 빈 곳에서 `Shift` + 마우스 오른쪽 클릭 → "여기에 PowerShell 창 열기".

```powershell
.\install_xdelta.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"
```

실행이 막히면 아래를 먼저 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 스크립트가 하는 일

1. RPCS3 실행 여부 확인
2. 대상이 롬인지 게임 데이터인지 판별하고 알려줌
3. 원본 네 파일의 크기와 SHA-256 검증
4. 원본을 `backup_original_<날짜시간>` 폴더에 백업
5. **임시 파일**에 패치 적용 — 대상 파일에 직접 쓰지 않습니다
6. 임시 결과의 크기와 SHA-256 검증
7. **검증을 통과한 결과만** 실제 파일로 교체
8. 원래 수정시각 복원
9. 최종 해시 출력

> 검증에 실패하면 게임 파일을 건드리지 않고 중단합니다.
> 실패했다고 원본을 삭제하거나 게임 폴더를 지우지 않습니다.

> 스크립트는 `cache\BLJS10335`, PPU·SPU·셰이더 캐시, 세이브 데이터를 건드리지 않습니다.
> 화면이 하얗게 보일 때만 RPCS3의 `Remove SPU Cache` 를 쓰세요.

### 설치 성공 시 해시

| 파일 | SHA-256 |
|---|---|
| `Common.psarc.sdat` | `CF7BB5AA952697A21334F5D31A0B74DBC6BBAF5DAD5FADB792DE41474533D821` |
| `General2d.psarc.sdat` | `D5D69DBC19AA86FE1C3D1121610350A80DA971B9BC686F04A81B3549A2361E63` |
| `Logic.psarc.sdat` | `7F78792487C03CA423936C9951835ABBC79F8B49A4B131687610E033F236D368` |
| `Battle.psarc.sdat` | `12C7D6AAD3B928A640B3FC091FE50B182E9D67CBAE07084102AC49A5A6B803BF` |

## 4. 게임 데이터 폴더 삭제

롬을 패치했으니, 예전에 만들어진 게임 데이터가 남아 있으면 그것이 먼저 쓰입니다.
아래 폴더를 삭제하거나 다른 곳으로 옮긴 뒤 게임을 실행하세요.

```
<RPCS3 폴더>\dev_hdd0\game\BLJS10335
```

게임이 데이터를 다시 설치하고, 그 뒤 한국어로 표시됩니다.
세이브 데이터는 `dev_hdd0\home\00000001\savedata` 에 따로 있으므로 안전합니다.

### 권장 설정

게임 우클릭 → **Change Custom Configuration** → **Advanced** 탭 →
Firmware Libraries 에서 **`libvdec.sprx`** 를 체크하면 초반 오류 표시가 생략됩니다.

## 5. 설치 확인

```powershell
.\verify_xdelta.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"
```

네 파일이 모두 `한국어 패치됨`으로 나오면 정상입니다.

## 6. 되돌리기

```powershell
.\restore_xdelta_backup.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"
```

`install_xdelta.ps1`이 만든 백업 폴더를 자동으로 찾습니다.
백업이 **진짜 원본인지 해시로 확인한 뒤에만** 복구하므로 안전합니다.

백업 폴더를 직접 지정할 수도 있습니다.

```powershell
.\restore_xdelta_backup.ps1 -TargetDir "..." -BackupDir "backup_original_20260808_202401"
```

> **게임 폴더를 통째로 지우지 마세요.** 백업 복구만으로 충분합니다.

## 수동 설치

자동 설치를 쓸 수 없을 때 사용합니다.

1. RPCS3를 완전히 종료합니다.
2. 압축을 푼 폴더의 `xdelta.exe` 와 `patches` 폴더를 **롬의 PSARC 폴더 안에** 복사합니다.
3. 그 PSARC 폴더에서 PowerShell을 엽니다.
   (폴더 빈 곳에서 `Shift` + 마우스 오른쪽 클릭 → "여기에 PowerShell 창 열기")
4. 아래 네 줄을 차례로 실행합니다. 경로는 본인 롬 위치로 바꾸세요.

```powershell
.\xdelta.exe -d -s "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC\Common.psarc.sdat" "patches\Common.psarc.sdat.xdelta" "Common.new"

.\xdelta.exe -d -s "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC\Battle.psarc.sdat" "patches\Battle.psarc.sdat.xdelta" "Battle.new"

.\xdelta.exe -d -s "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC\General2d.psarc.sdat" "patches\General2d.psarc.sdat.xdelta" "General2d.new"

.\xdelta.exe -d -s "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC\Logic.psarc.sdat" "patches\Logic.psarc.sdat.xdelta" "Logic.new"
```

5. 만들어진 `.new` 파일 네 개를 원래 이름으로 바꿔 덮어씁니다.
   원본은 먼저 다른 곳에 백업해 두시길 권합니다.

   | 만들어진 파일 | 바꿀 이름 |
   |---|---|
   | `Common.new` | `Common.psarc.sdat` |
   | `Battle.new` | `Battle.psarc.sdat` |
   | `General2d.new` | `General2d.psarc.sdat` |
   | `Logic.new` | `Logic.psarc.sdat` |

6. `<RPCS3 폴더>\dev_hdd0\game\BLJS10335` 폴더를 삭제합니다.
7. 게임 목록에서 해당 게임 우클릭 → **Remove** → **Remove SPU Cache**
8. 게임을 실행합니다.

수동 설치는 해시 검증을 건너뛰므로, 끝난 뒤 **반드시 `verify_xdelta.ps1`을 실행**하세요.

## 오류 제보

[Issues](https://github.com/kimjh-eclipse/srw-og-moon-dwellers-korean-patch/issues)에
다음을 함께 올려 주시면 확인이 빠릅니다.

1. 화면 캡처
2. 그 화면까지 들어간 경로 (어떤 메뉴를 거쳤는지)
3. 사용한 패치 버전
4. `verify_xdelta.ps1` 실행 결과

## 감사

**박호울**님께 감사드립니다. 이 안내는 박호울님이 정리해 주신 내용을 따랐습니다.
게임 데이터가 아니라 롬 쪽에 패치해야 한다는 점, 수동 설치 절차, SPU 캐시 삭제,
`libvdec.sprx` 설정까지 직접 확인해 알려 주셨습니다.

> https://naver.me/Gy3MRaii

설치 절차와 관련한 내용은 모두 박호울님 안내를 따랐습니다.
