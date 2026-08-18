슈퍼로봇대전 OG 문 드웰러즈 한국어 패치 v20260819
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

[B. 폴더형 게임/추출 PSARC]
PowerShell에서 다음 명령을 실행합니다.

powershell -ExecutionPolicy Bypass -File .\install_xdelta.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"

상태 확인:
powershell -ExecutionPolicy Bypass -File .\verify_xdelta.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"

백업 복구:
powershell -ExecutionPolicy Bypass -File .\restore_xdelta_backup.ps1 -TargetDir "C:\RPCS3\games\BLJS10335\PS3_GAME\USRDIR\PSARC"

주의: 패치 후 RPCS3 저장 상태(Save State)로 이어하지 마세요.
저장 상태는 패치 전 폰트와 메모리를 복원할 수 있습니다.
정상 부팅 후 게임 내부 세이브를 사용하세요.

[화면이 하얗게 보일 때]

타이틀이나 메뉴 화면이 흰색으로 보이는 경우가 있습니다. 커서 이동과 소리는
정상인데 그림만 나오지 않는 상태입니다.

순서가 중요합니다. 1단계를 건너뛰고 캐시만 지우면 다시 하얗게 보입니다.

1단계. 게임 우클릭 → Change Custom Configuration → Advanced 탭 →
Firmware Libraries 목록에서 libvdec.sprx를 체크합니다. 기본값은 HLE이고
체크하면 LLE가 됩니다. 저장하고 닫습니다.

2단계. RPCS3 게임 목록에서 해당 게임 우클릭 → Remove → Remove SPU Cache
하신 뒤 다시 켜면 정상으로 돌아옵니다.

1단계는 한 번만 하면 됩니다. 초반에 뜨는 오류 표시도 이 설정으로 함께 사라집니다.

2단계는 한 번 지웠다고 끝나지 않습니다. 플레이를 계속하면 캐시가 다시 쌓이면서
재발합니다. 증상이 보이면 그때마다 2단계를 다시 하시면 됩니다.

캐시 폴더 전체를 지우지는 마세요. Remove SPU Cache만 쓰시면 됩니다.

이 현상은 한국어 패치와 무관합니다. 패치하지 않은 원본에서도 발생하고 RPCS3
버전을 바꿔도 같습니다. 설치 스크립트와 빠른 패처는 캐시도 세이브도 지우지 않습니다.

최종 PSARC SHA-256
Common     16C45C456DA86DD17B5C05BD8735433873C37503984C1C58A96C613FDA5CD2B2
General2d  2B93DC5F3067BA94379429553699A978A63E8BB8AB7105B5286F912FB4E19332
Logic      88805060C4D910749A926199D96B6DE11EC2BD5F49FA422E28C759407834BB45
Battle     4841F5801429D74B06DFCE71B4FBBDD0F8635D88BE72F17B5D9069EF77980420
