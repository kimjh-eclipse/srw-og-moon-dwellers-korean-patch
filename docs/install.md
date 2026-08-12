# 설치 안내

## 적용 대상

PS3 『슈퍼로봇대전 OG 더 문 드웰러즈』 **일본판** — 게임 ID `BLJS10335`

다른 리전판에는 적용할 수 없습니다.

> **원본 게임 데이터는 직접 준비해야 합니다.**
> 이 저장소와 배포물에는 게임 파일이나 ISO가 들어 있지 않으며, 제공하지도 않습니다.

## 1. 준비

1. **RPCS3를 완전히 종료합니다.** 실행 중이면 설치가 거부됩니다.
2. 게임 데이터 폴더를 확인합니다.
   ```
   <RPCS3 폴더>\dev_hdd0\game\BLJS10335\USRDIR\PSARC
   ```
3. 그 안에 다음 네 파일이 있어야 합니다.

   | 파일 | 크기 | 원본 SHA-256 |
   |---|---:|---|
   | `Common.psarc.sdat` | 505,828,992 | `99B298B3…2093BB` |
   | `General2d.psarc.sdat` | 611,585,392 | `04C3D1DA…F16667` |
   | `Logic.psarc.sdat` | 38,399,120 | `AF453B39…F5F181` |
   | `Battle.psarc.sdat` | 1,729,186,848 | `2C5CA16F…F894A844` |

4. 네 파일을 다른 곳에 복사해 두면 더 안전합니다. `install.ps1`도 자동으로 백업합니다.
5. 세이브 데이터를 지울 필요는 없습니다. 다만 백업을 권장합니다.

## 2. 내려받기

[Releases](https://github.com/kimjh-eclipse/srw-og-moon-dwellers-korean-patch/releases/latest)에서
받아 압축을 풉니다.

## 3. 자동 설치 (권장)

압축을 푼 폴더에서 PowerShell을 엽니다.
폴더 빈 곳에서 `Shift` + 마우스 오른쪽 클릭 → "여기에 PowerShell 창 열기".

```powershell
.\install.ps1 -TargetDir "C:\RPCS3\dev_hdd0\game\BLJS10335\USRDIR\PSARC"
```

실행이 막히면 아래를 먼저 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 스크립트가 하는 일

1. RPCS3 실행 여부 확인
2. 대상 경로가 `BLJS10335\USRDIR\PSARC` 인지 확인
3. 원본 네 파일의 크기와 SHA-256 검증
4. 원본을 `backup_original_<날짜시간>` 폴더에 백업
5. **임시 파일**에 패치 적용 — 대상 파일에 직접 쓰지 않습니다
6. 임시 결과의 크기와 SHA-256 검증
7. **검증을 통과한 결과만** 실제 파일로 교체
8. 원래 수정시각 복원
9. 최종 해시 출력

> 검증에 실패하면 게임 파일을 건드리지 않고 중단합니다.
> 실패했다고 원본을 삭제하거나 게임 폴더를 지우지 않습니다.

### 설치 성공 시 해시

| 파일 | SHA-256 |
|---|---|
| `Common.psarc.sdat` | `A331AE43760FD276B1547A84CE9C1D56E71F24CC20FD0BF021641916A9468619` |
| `General2d.psarc.sdat` | `6EC64D6D9407BC06E7A95E179087741BAC0C3DC7868818C70E3A3F66B848E835` |
| `Logic.psarc.sdat` | `689240DB752B50E619AE1D14010A275019A4A7303E427F9A4DCB83FAADDD54B6` |
| `Battle.psarc.sdat` | `12C7D6AAD3B928A640B3FC091FE50B182E9D67CBAE07084102AC49A5A6B803BF` |

## 4. 설치 확인

```powershell
.\verify.ps1 -TargetDir "C:\RPCS3\dev_hdd0\game\BLJS10335\USRDIR\PSARC"
```

네 파일이 모두 `한국어 패치됨`으로 나오면 정상입니다.

## 5. 되돌리기

```powershell
.\restore_backup.ps1 -TargetDir "C:\RPCS3\dev_hdd0\game\BLJS10335\USRDIR\PSARC"
```

`install.ps1`이 만든 백업 폴더를 자동으로 찾습니다.
백업이 **진짜 원본인지 해시로 확인한 뒤에만** 복구하므로 안전합니다.

백업 폴더를 직접 지정할 수도 있습니다.

```powershell
.\restore_backup.ps1 -TargetDir "..." -BackupDir "backup_original_20260808_202401"
```

> **게임 폴더를 통째로 지우지 마세요.** 백업 복구만으로 충분합니다.

## 수동 설치

자동 설치를 쓸 수 없을 때만 사용합니다. 네 파일을 먼저 백업한 뒤 각각 실행합니다.

```powershell
.\xdelta.exe -d -s "<원본>\Common.psarc.sdat" "patches\Common.psarc.sdat.xdelta" "Common.new"
```

`General2d`, `Logic`, `Battle`도 같은 방식으로 처리한 뒤 `.new` 파일로 원래 파일을 덮어씁니다.

수동 설치는 해시 검증을 건너뛰므로, 끝난 뒤 **반드시 `verify.ps1`을 실행**하세요.

## 오류 제보

[Issues](https://github.com/kimjh-eclipse/srw-og-moon-dwellers-korean-patch/issues)에
다음을 함께 올려 주시면 확인이 빠릅니다.

1. 화면 캡처
2. 그 화면까지 들어간 경로 (어떤 메뉴를 거쳤는지)
3. 사용한 패치 버전
4. `verify.ps1` 실행 결과
