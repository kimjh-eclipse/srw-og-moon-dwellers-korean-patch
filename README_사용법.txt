슈퍼로봇대전 OG 문 드웰러즈 한국어 패치 v20260822b
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

최종 PSARC SHA-256
Common     16C45C456DA86DD17B5C05BD8735433873C37503984C1C58A96C613FDA5CD2B2
General2d  29EC56DB773F1ADD358D883ECC522AC28FACC2BEC124F947B28FCBA280282D1E
Logic      3CB73CD83E946070995A0EA4529F7C3BF2CB101B9FD24C3D36E38719360B079F
Battle     B5CB66BBA32BBF066E4846886E5394FF42C6789B814B9F1282A374E4DDA4113E
