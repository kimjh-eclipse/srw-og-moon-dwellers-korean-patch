슈퍼로봇대전 OG 문 드웰러즈 한국어 패치 v20260907b
대상: PS3 일본판 BLJS10335

두 설치 방식 중 하나만 사용하세요. 같은 대상에 두 방식을 중복 적용하지 마세요.

[A. 복호화 ISO]
1. RPCS3와 ISO 마운트 프로그램을 종료합니다.
2. OGMD_ISO_QuickPatch.exe를 실행합니다.
3. 복호화된 일본판 ISO를 선택하고 [원본 검사]를 실행합니다.
4. 안내를 확인한 뒤 패치를 적용합니다.

원본 ISO 입력 시 같은 위치에 .iso.ogmd-backup 백업을 남깁니다.
정리 옵션을 선택한 경우에만 dev_hdd0\game\BLJS10335 설치 데이터와
cache\BLJS10335\spu-safe-v1-tane.dat를 정리합니다.
PPU·셰이더 캐시, 세이브, savestate는 삭제하지 않습니다.

[B. RPCS3/폴더형 게임 — UI 직접 패치]
1. RPCS3를 완전히 종료합니다.
2. OGMD_ISO_QuickPatch.exe를 실행합니다.
3. `RPCS3 / 폴더형 게임 경로`에서 다음 중 하나를 선택합니다.
   - BLJS10335 폴더형 게임 루트
   - PS3_GAME 폴더
   - USRDIR\PSARC 폴더
   - RPCS3 루트(설치 데이터 자동 탐색)
4. `폴더 게임 상태 검사`로 상태를 확인합니다.
5. 주의사항에 동의한 뒤 `RPCS3 / 폴더 게임에 직접 패치`를 누릅니다.

원본 PSARC 4개 자동 백업 옵션은 켜 두는 것을 권장합니다.
백업은 패처 폴더의 backup_original_날짜_시간 폴더에 생성됩니다.

[C. 폴더형 게임/추출 PSARC — PowerShell]
PowerShell에서 다음 명령을 실행합니다.

powershell -ExecutionPolicy Bypass -File .\install_xdelta.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"

상태 확인:
powershell -ExecutionPolicy Bypass -File .\verify_xdelta.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"

백업 복구:
powershell -ExecutionPolicy Bypass -File .\restore_xdelta_backup.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"

주의: 패치 후 RPCS3 저장 상태(Save State)로 이어하지 마세요.
저장 상태는 패치 전 폰트와 메모리를 복원할 수 있습니다.
정상 부팅 후 게임 내부 세이브를 사용하세요.

[D. 세이브 목록 한글화]
RPCS3 세이브 목록에서 시나리오 제목·루트·톱 에이스가 한자처럼 깨져 보이면
1. RPCS3를 완전히 종료합니다.
2. OGMD_ISO_QuickPatch.exe의 `RPCS3 / 폴더형 게임 경로`에 RPCS3 폴더를 지정합니다.
3. `세이브 목록 한글화 (PARAM.SFO)`를 누릅니다.
명령줄: OGMD_ISO_QuickPatch.exe --save-hangul "C:\RPCS3"

세이브 폴더의 PARAM.SFO 안 표시용 문자열만 바꾸고 세이브 본체는 건드리지 않습니다.
원본 PARAM.SFO 는 dev_hdd0\home\<사용자>\ogmd_sfo_backup_<시각>\ 에 백업됩니다.
게임이 새로 저장하면 그 세이브는 다시 깨져 보이므로 필요할 때마다 다시 실행하세요.

최종 PSARC SHA-256
Common     16C45C456DA86DD17B5C05BD8735433873C37503984C1C58A96C613FDA5CD2B2
General2d  699C18FDF5F2E6F5650D4D08669C3168A941E8E587137833341D861ED066C473
Logic      1AFD7A9AE89CBDE7D6F5B329B8A36EDEDA9045C690E3CB6530A26F8DE4A0235B
Battle     48C356CA87C6BBF9BB0B32424EA46FB8B01FEE3FC6EAF29B698FCEF7300C1523
