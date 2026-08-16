========================================================================
 슈퍼로봇대전 OG 문 드웰러즈 한국어 패치 v20260816
 대상: PS3 일본판 BLJS10335
========================================================================

이 배포본은 설치 환경에 맞춰 두 가지 방식을 제공합니다.
두 방식의 최종 한국어 데이터는 동일합니다. 한 가지만 선택해 사용하세요.


========================================================================
 방법 A — ISO 빠른 패처 (복호화된 ISO 사용자에게 권장)
========================================================================

사용 파일
  OGMD_ISO_QuickPatch.exe

1. RPCS3를 완전히 종료합니다.
2. OGMD_ISO_QuickPatch.exe를 실행합니다.
3. 복호화된 일본판 BLJS10335 ISO와 백업 파일 경로를 지정합니다.
4. 필요하면 RPCS3 경로도 지정합니다.
5. [원본 검사]로 ISO와 RPCS3 경로의 검사 결과를 확인합니다.
6. 주의사항 확인란을 체크한 뒤 [ISO에 한국어 패치 적용]을 누릅니다.

빠른 패처는 선택한 ISO 자체의 필요한 구간만 수정합니다.
ISO 전체 11.8GB를 새로 복사하지 않습니다.

원본 ISO에서 처음 패치할 때는 복구용 .ogmd-backup 파일을 만듭니다.
이미 정상 백업이 있으면 그 백업을 사용해 원본 검사와 버전 갱신을 빠르게 처리합니다.
백업 파일은 원상복구와 다음 버전 갱신에 필요하므로 보관하세요.

패치 후 예전에 설치된 게임 데이터가 남아 있으면 새 ISO 내용이 사용되지 않습니다.
빠른 패처에서 RPCS3 경로를 지정했다면 패치 작업 중 다음 폴더만 선택적으로
삭제할 수 있습니다.

  <RPCS3 폴더>\dev_hdd0\game\BLJS10335

세이브 데이터와 PPU/SPU/셰이더 캐시는 삭제하지 않습니다.


========================================================================
 방법 B — 기존 xdelta 방식 (폴더형 게임/추출 PSARC 사용자)
========================================================================

사용 파일
  install_xdelta.ps1
  verify_xdelta.ps1
  restore_xdelta_backup.ps1
  xdelta.exe
  patches 폴더

권장 패치 대상
  ...\BLJS10335\PS3_GAME\USRDIR\PSARC

1. RPCS3를 완전히 종료합니다.
2. 이 배포 폴더의 빈 곳에서 PowerShell을 엽니다.
3. 아래 명령을 실행합니다. 경로는 본인의 게임 경로로 바꾸세요.

  powershell -ExecutionPolicy Bypass -File .\install_xdelta.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"

스크립트는 원본 4개 파일을 SHA-256으로 확인하고, 이 배포 폴더에
backup_original_날짜시간 폴더를 만든 뒤 임시 파일에 패치를 적용합니다.
결과 해시가 정확할 때만 실제 PSARC를 교체하고 원래 수정시각을 복원합니다.

설치 상태 확인

  powershell -ExecutionPolicy Bypass -File .\verify_xdelta.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"

원본 복구

  powershell -ExecutionPolicy Bypass -File .\restore_xdelta_backup.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"

복구할 백업 폴더를 직접 지정하려면 다음처럼 실행합니다.

  powershell -ExecutionPolicy Bypass -File .\restore_xdelta_backup.ps1 -TargetDir "...\PSARC" -BackupDir "...\backup_original_YYYYMMDD_HHMMSS"

xdelta 방식으로 롬 폴더를 패치한 뒤에도 다음 기존 설치 데이터는 삭제하거나
다른 곳으로 옮겨 게임이 새로 설치하게 해야 합니다.

  <RPCS3 폴더>\dev_hdd0\game\BLJS10335

이 폴더는 세이브 폴더가 아닙니다. 세이브는 dev_hdd0\home 아래에 있습니다.


========================================================================
 공통 주의사항
========================================================================

1. 복호화된 일본판 BLJS10335만 지원합니다.
2. RPCS3와 ISO 마운트 프로그램을 완전히 종료한 뒤 작업하세요.
3. ISO 빠른 패처와 xdelta 방식을 같은 원본에 중복 적용하지 마세요.
4. 패치 중 프로그램을 강제 종료하거나 저장장치를 분리하지 마세요.
5. 문제가 생기면 게임 폴더 전체를 지우지 말고 먼저 백업으로 복구하세요.
6. 화면이 하얗게 보일 때만 RPCS3의 Remove SPU Cache를 사용하세요.
7. cache\BLJS10335 전체, PPU 캐시, 셰이더 캐시, 세이브 데이터는 지우지 마세요.


========================================================================
 최종 PSARC SHA-256
========================================================================

Common.psarc.sdat
  4F21D176D0BF8A4B28B6476ECC87DD2BA005622691D6700635DE7FC7F077873D

General2d.psarc.sdat
  1FB69D19FF325E81D513C1F267A9A61A3A785D865A6235CF07A64965F4623003

Logic.psarc.sdat
  E3499F062C63BDA904E5164768B9FC775F6AD31F1ED5D948DB5D3355C46FE519

Battle.psarc.sdat
  6B2D03568EF0C86ABB07F945392C71E9D899DE62C0E1AB26979F1158B9F49FDB

