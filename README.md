# 슈퍼로봇대전 OG 문 드웰러즈 한국어 패치

**슈퍼로봇대전 OG 더 문 드웰러즈** 일본판(PS3, `BLJS10335`) 한국어 패치입니다.

주요 스토리와 전투 대사, 메뉴, 파일럿·기체 정보, 에이스 보너스를 한글화했습니다.
전투 대사는 기계 번역 결과를 그대로 쓰지 않고 캐릭터별 성향과 말투를 고려해 직접 검토했습니다.

> **📦 패치 다운로드: [Releases](../../releases/latest)**
> — xdelta 패치 + 설치·검증·복구 스크립트 + 검증 해시 동봉. 원본 게임 데이터는 포함되지 않습니다.
>
> **📖 문서 사이트: https://kimjh-eclipse.github.io/srw-og-moon-dwellers-korean-patch/**
> (설치 안내 · 알려진 문제 · SDAT 암호 구조 · PSARC 레이아웃 · 고정 배치 재빌드 · 빌드 파이프라인)
> — 소스는 [docs/](docs/_sidebar.md)에 있습니다.

| | |
|---|---|
| 버전 | `v20260808` |
| 대상 | 일본판 `BLJS10335` |
| 배포 형식 | xdelta 패치 4개 (합계 약 7.3 MiB) |
| 검증 환경 | RPCS3 v0.0.42-19699 (Vulkan) |

> **원본 게임 데이터는 직접 준비해야 합니다.**
> 이 저장소에는 게임 파일이나 ISO가 들어 있지 않으며, 제공하지도 않습니다.

---

## 설치

### 1. 준비

- RPCS3를 **완전히 종료**합니다. 실행 중이면 설치가 거부됩니다.
- 게임 데이터 폴더를 확인합니다.
  ```
  <RPCS3 폴더>\dev_hdd0\game\BLJS10335\USRDIR\PSARC
  ```
- 그 안에 다음 네 파일이 있어야 합니다.

  | 파일 | 크기 |
  |---|---:|
  | `Common.psarc.sdat` | 505,828,992 |
  | `General2d.psarc.sdat` | 611,585,392 |
  | `Logic.psarc.sdat` | 38,399,120 |
  | `Battle.psarc.sdat` | 1,729,186,848 |

### 2. 내려받기

이 저장소의 [Code → Download ZIP] 또는 [Releases](../../releases)에서 받아 압축을 풉니다.

### 3. 설치 실행

압축을 푼 폴더에서 PowerShell을 열고 실행합니다. 경로는 본인 환경에 맞게 바꾸세요.

```powershell
.\install.ps1 -TargetDir "C:\RPCS3\dev_hdd0\game\BLJS10335\USRDIR\PSARC"
```

실행이 막히면 아래를 먼저 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

`install.ps1`은 다음 순서로 동작하며, **검증에 실패하면 게임 파일을 건드리지 않고 중단**합니다.

1. RPCS3 실행 여부 확인
2. 대상 경로 확인
3. 원본 네 파일의 크기와 SHA-256 검증
4. 원본을 `backup_original_<날짜시간>` 폴더에 백업
5. **임시 파일**에 패치 적용
6. 임시 결과의 해시 검증
7. 검증을 통과한 결과만 실제 파일로 교체
8. 원래 수정시각 복원

### 4. 확인

```powershell
.\verify.ps1 -TargetDir "C:\RPCS3\dev_hdd0\game\BLJS10335\USRDIR\PSARC"
```

네 파일이 모두 `한국어 패치됨`으로 나오면 정상입니다.

### 되돌리기

```powershell
.\restore_backup.ps1 -TargetDir "C:\RPCS3\dev_hdd0\game\BLJS10335\USRDIR\PSARC"
```

백업이 진짜 원본인지 해시로 확인한 뒤에만 복구합니다.
**게임 폴더를 통째로 지우지 마세요.** 백업 복구만으로 충분합니다.

---

## 알려진 제한

완전 무결한 100% 한글화가 아닙니다. 자세한 내용은 [README_알려진문제.txt](README_알려진문제.txt)를 읽어 주세요.

### 1. 화면이 하얗게 보일 때 — SPU 캐시를 지우세요

타이틀이나 메뉴 화면이 흰색으로 보일 수 있습니다. 커서 이동과 소리는 정상인데
그림만 안 나오는 상태입니다. RPCS3의 **SPU 캐시가 쌓이면서** 생기는 현상입니다.

> **해결 방법**
> RPCS3 게임 목록에서 해당 게임을 우클릭 → **Remove** → **Remove SPU Cache**
> 그 뒤 다시 실행하면 정상으로 돌아옵니다.

**한 번 지웠다고 끝나지 않습니다.** 플레이를 계속하면 캐시가 다시 쌓이면서 재발합니다.
증상이 보이면 그때마다 같은 방법으로 지우면 됩니다.

PPU 캐시와 셰이더 캐시는 건드릴 필요 없습니다.
(다음 버전부터는 `install.ps1`이 설치 시점의 SPU 캐시를 자동으로 지웁니다)

**패치를 적용하지 않은 원본 상태에서도 동일하게 발생**하며, RPCS3 버전을 바꿔도 같습니다.
이 패치 때문에 생기는 문제가 아닙니다.

> 이전 버전 문서는 이 현상의 원인을 "로고 뒤 흰 화면에서의 조기 입력"으로 안내했습니다.
> **그 안내는 틀렸습니다.** 원인 추적 기록은 [실기 검증과 오판 정정](docs/verification.md)에 있습니다.

### 2. 옵션 화면의 `트`, `특` 글자

옵션 화면 오른쪽에 `트`, `특`이 단독으로 남습니다.
해당 아이콘을 비우면 첫 메인 메뉴가 흰색으로 표시되는 문제가 재현되어,
부팅 안정성을 위해 제거를 포기했습니다. 게임 진행에는 영향이 없습니다.

### 3. 지형 표시의 한자

일부 화면에서 지형이 `空` `陸` `海` `宇`로 표시됩니다.
공/지/해/우로 바꾸면 글자가 사라지거나 다른 화면이 깨지는 문제가 있어 한자 유지를 결정했습니다.

---

## 세이브 데이터

이 패치는 세이브 데이터 삭제를 요구하지 않습니다. 기존 세이브를 그대로 사용할 수 있습니다.
다만 만일을 대비해 설치 전 백업을 권장합니다.

## 검증 정보

패치 적용 후 정상 설치된 파일의 SHA-256입니다. 전체 목록은 [SHA256SUMS.txt](SHA256SUMS.txt) 참고.

| 파일 | SHA-256 |
|---|---|
| `Common.psarc.sdat` | `4DEA959A59D1114BED0A5546B1146B78BB4DFEE5F57D8EDAC32061F33C2DAB68` |
| `General2d.psarc.sdat` | `1E10F52E2FFEC46E8BBE81AA4177E6D6E198794606A5669B6892934A21B206AC` |
| `Logic.psarc.sdat` | `199AA123E527A3AD1FBDA77E85A94E334893F2298D5907E52E1E43B0F160D9BE` |
| `Battle.psarc.sdat` | `1656789FB69AA8C5570CFC62C1CF098ECE1E63F054785F3F631DD6DCE56CEE24` |

네 패치 모두 원본에 적용해 위 결과가 바이트 단위로 재현되는 것을 확인했습니다(왕복 검증 4/4 통과).

## 오류 제보

[Issues](../../issues)에 다음을 함께 올려 주시면 확인이 빠릅니다.

1. 화면 캡처
2. 그 화면까지 들어간 경로 (어떤 메뉴를 거쳤는지)
3. 사용한 패치 버전
4. `verify.ps1` 실행 결과

## 문서

### 기술 문서

역공학으로 규명한 SDAT 암호 구조, PSARC 레이아웃, 그리고 배포 패치를 667.7MB에서
7.32MiB로 줄인 고정 배치 재빌드 기법을 정리했습니다.
읽기 좋은 형태는 **[문서 사이트](https://kimjh-eclipse.github.io/srw-og-moon-dwellers-korean-patch/)**,
소스는 [`docs/`](docs/home.md)에 있습니다.

| 문서 | 내용 |
|---|---|
| [SDAT 암호 구조](docs/sdat.md) | NPD 헤더, 블록 단위 AES 키 유도, 메타데이터 위조 |
| [PSARC 아카이브 구조](docs/psarc.md) | TOC·블록 테이블 레이아웃, `PSARCLIST.BIN` |
| [고정 배치 재빌드](docs/fixed-layout.md) | 델타를 87배 줄인 기법과 측정치 |
| [빌드 파이프라인](docs/pipeline.md) | 추출 → 번역 → 재조립 → 검증 절차 |
| [실기 검증과 오판 정정](docs/verification.md) | 타이틀 백화 원인 추적 기록 |

### 배포물 문서

- [설치 안내 (전문)](README_설치.txt)
- [알려진 문제 (전문)](README_알려진문제.txt)
- [변경 내역](CHANGELOG.txt)
- [파일 해시 목록](SHA256SUMS.txt)

## 라이선스

이 저장소의 문서와 스크립트는 [Apache License 2.0](LICENSE)을 따릅니다.

포함된 `xdelta.exe`는 별도 라이선스(GPL)입니다. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)를 참고하세요.

패치 파일은 원본 게임 데이터를 포함하지 않으며, 원본 파일이 있어야만 적용됩니다.
