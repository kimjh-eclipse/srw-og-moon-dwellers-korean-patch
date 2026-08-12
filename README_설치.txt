========================================================================
 슈퍼로봇대전 OG 문 드웰러즈 한국어 패치 (PS3 일본판)
 버전 v20260813
========================================================================

■ 적용 대상

  슈퍼로봇대전 OG 더 문 드웰러즈 일본판
  게임 ID : BLJS10335

  이 패치는 위 일본판에만 적용됩니다. 다른 리전판에는 쓸 수 없습니다.

  원본 게임 데이터는 본인이 직접 준비해야 합니다.
  이 배포물에는 게임 파일이나 ISO가 들어 있지 않으며, 제공하지도 않습니다.


■ 배포물 구성

  install.ps1            자동 설치 (권장)
  verify.ps1             현재 설치 상태 확인
  restore_backup.ps1     원본 복구
  xdelta.exe             패치 적용 도구 (xdelta3 3.1.0)
  patches\               패치 파일 4개
  README_설치.txt        이 문서
  README_알려진문제.txt  알려진 제한 사항 — 설치 전에 꼭 읽으세요
  CHANGELOG.txt          변경 내역
  SHA256SUMS.txt         전체 파일 해시 목록


■ 설치 전 준비

  1. RPCS3를 완전히 종료합니다. 실행 중이면 설치가 거부됩니다.

  2. 게임 데이터 폴더 위치를 확인합니다. 아래와 같은 형태입니다.

     <RPCS3 폴더>\dev_hdd0\game\BLJS10335\USRDIR\PSARC

     이 폴더 안에 다음 네 파일이 있어야 합니다.

       Common.psarc.sdat       505,828,992 바이트
       General2d.psarc.sdat    611,585,392 바이트
       Logic.psarc.sdat         38,399,120 바이트
       Battle.psarc.sdat     1,729,186,848 바이트

  3. 네 파일을 다른 곳에 복사해 두는 것을 권장합니다.
     install.ps1 이 자동으로 백업하지만, 별도 백업이 있으면 더 안전합니다.

  4. 세이브 데이터를 지울 필요는 없습니다.
     다만 만일을 대비해 백업해 두시길 권합니다.


■ 자동 설치 (권장)

  1. 이 폴더에서 PowerShell을 엽니다.
     (폴더 빈 곳에서 Shift + 마우스 오른쪽 클릭 → "여기에 PowerShell 창 열기")

  2. 아래 명령을 실행합니다. 경로는 본인 환경에 맞게 바꾸세요.

     .\install.ps1 -TargetDir "C:\RPCS3\dev_hdd0\game\BLJS10335\USRDIR\PSARC"

     실행이 막히면 아래를 먼저 실행하세요.

     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

  3. 스크립트가 다음 순서로 동작합니다.

       RPCS3 실행 여부 확인
       대상 경로 확인
       원본 네 파일의 크기와 SHA-256 검증
       원본을 backup_original_<날짜시간> 폴더에 백업
       임시 파일에 패치를 적용
       임시 결과의 해시를 검증
       검증을 통과한 결과만 실제 파일로 교체
       원래 수정시각 복원
       최종 해시 출력

     검증에 실패하면 게임 파일을 건드리지 않고 중단합니다.

  4. 패치 적용 후 이 게임의 SPU 캐시를 자동으로 삭제합니다.
     예전 캐시가 남아 있으면 화면이 하얗게 보일 수 있습니다.

  5. 마지막에 출력되는 네 해시가 아래와 같으면 정상입니다.

       Common     A331AE43760FD276B1547A84CE9C1D56E71F24CC20FD0BF021641916A9468619
       General2d  6EC64D6D9407BC06E7A95E179087741BAC0C3DC7868818C70E3A3F66B848E835
       Logic      689240DB752B50E619AE1D14010A275019A4A7303E427F9A4DCB83FAADDD54B6
       Battle     12C7D6AAD3B928A640B3FC091FE50B182E9D67CBAE07084102AC49A5A6B803BF


■ 수동 설치

  자동 설치를 쓸 수 없을 때만 사용하세요.
  네 파일을 먼저 백업한 뒤, 각 파일에 대해 아래를 실행합니다.

    xdelta.exe -d -s "<원본>\Common.psarc.sdat" "patches\Common.psarc.sdat.xdelta" "Common.new"

  General2d, Logic, Battle도 같은 방식으로 처리한 뒤,
  생성된 .new 파일로 원래 파일을 덮어씁니다.

  수동 설치는 해시 검증을 건너뛰게 되므로, 끝난 뒤 반드시 verify.ps1 을 실행하세요.

  그리고 RPCS3 게임 목록에서 해당 게임을 우클릭 -> Remove -> Remove SPU Cache
  를 반드시 실행하세요. 예전 캐시가 남으면 화면이 하얗게 보일 수 있습니다.


■ 설치 확인

    .\verify.ps1 -TargetDir "C:\RPCS3\dev_hdd0\game\BLJS10335\USRDIR\PSARC"

  네 파일이 모두 "한국어 패치됨"으로 나오면 정상입니다.


■ 원본으로 되돌리기

    .\restore_backup.ps1 -TargetDir "C:\RPCS3\dev_hdd0\game\BLJS10335\USRDIR\PSARC"

  install.ps1 이 만든 backup_original_* 폴더에서 자동으로 복구합니다.
  백업이 진짜 원본인지 해시로 확인한 뒤에만 복구하므로 안전합니다.

  백업 폴더를 직접 지정할 수도 있습니다.

    .\restore_backup.ps1 -TargetDir "..." -BackupDir "backup_original_20260808_202401"


■ 번역 범위

  - 주요 스토리 및 전투 대사
  - 메뉴 및 인터페이스
  - 파일럿 및 기체 정보
  - 에이스 보너스, 특수기, 정신 커맨드

  전투 대사는 기계 번역 결과를 그대로 쓰지 않고, 캐릭터별 성향과 말투를
  고려해 직접 검토했습니다.

  완전한 100% 한글화는 아닙니다. 남아 있는 제한은
  README_알려진문제.txt 를 반드시 읽어 주세요.


■ 오류 제보

  다음 정보를 함께 보내 주시면 확인이 빠릅니다.

    1. 화면 캡처
    2. 그 화면까지 들어간 경로 (어떤 메뉴를 거쳤는지)
    3. 사용한 패치 버전 (v20260813)
    4. verify.ps1 실행 결과


■ 도구 라이선스 고지

  포함된 xdelta.exe 는 xdelta3 3.1.0 으로 GPL 라이선스입니다.
  원본 소스는 아래에서 받을 수 있습니다.

    https://github.com/jmacd/xdelta

  이 패치 배포물의 나머지 구성물은 게임 원본 데이터를 포함하지 않습니다.
