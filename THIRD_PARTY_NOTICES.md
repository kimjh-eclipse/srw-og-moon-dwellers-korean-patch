# 서드파티 고지 / Third-Party Notices

이 저장소는 아래 서드파티 소프트웨어를 포함합니다.
해당 파일에는 이 저장소의 [Apache License 2.0](LICENSE)이 적용되지 않으며,
각자의 원 라이선스가 적용됩니다.

---

## xdelta3 (`xdelta.exe`)

| | |
|---|---|
| 이름 | xdelta3 |
| 버전 | 3.1.0 |
| 저작권 | Copyright (C) Joshua MacDonald |
| 라이선스 | GNU General Public License (GPL) |
| 원 소스 | https://github.com/jmacd/xdelta |

포함된 `xdelta.exe`는 **수정하지 않은 공식 빌드**이며, 이진 델타의 생성과 적용에만 사용됩니다.

GPL에 따라 해당 소프트웨어의 소스 코드는 위 원 저장소에서 받을 수 있습니다.

이 저장소에 포함하지 않고 직접 받아 쓰고 싶다면, `install.ps1` 실행 시
`-XdeltaPath` 인자로 위치를 지정할 수 있습니다.

```powershell
.\install.ps1 -TargetDir "<...\BLJS10335\USRDIR\PSARC>" -XdeltaPath "C:\경로\xdelta3.exe"
```

---

## 게임 데이터에 관하여

`patches/` 폴더의 `.xdelta` 파일은 원본 게임 데이터를 포함하지 않는 **이진 차분 파일**입니다.
적용하려면 사용자가 정당하게 보유한 원본 파일이 반드시 있어야 합니다.

이 저장소는 게임 원본 파일, ISO, 실행 파일을 배포하지 않습니다.

*슈퍼로봇대전 OG 더 문 드웰러즈* 및 관련 상표·저작물의 권리는 각 권리자에게 있습니다.
이 프로젝트는 비공식 팬 번역이며 권리자와 아무 관련이 없습니다.
