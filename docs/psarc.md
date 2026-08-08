# PSARC 아카이브 구조

SDAT을 복호하면 PSARC 1.4 아카이브가 나온다. 소니 표준 포맷이며 이 게임은 zlib 압축을 쓴다.

## 헤더 (32 바이트, 전부 빅엔디안)

| 오프셋 | 크기 | 필드 | 이 게임의 값 |
|---|---:|---|---|
| `0x00` | 4 | 매직 `"PSAR"` | |
| `0x04` | 2 | 메이저 버전 | `1` |
| `0x06` | 2 | 마이너 버전 | `4` |
| `0x08` | 4 | 압축 방식 | `"zlib"` |
| `0x0C` | 4 | TOC 전체 길이 | |
| `0x10` | 4 | 엔트리 크기 | `30` |
| `0x14` | 4 | 엔트리 개수 | |
| `0x18` | 4 | 블록 크기 | `65536` |
| `0x1C` | 4 | 아카이브 플래그 | |

## TOC 엔트리 (30 바이트)

| 오프셋 | 크기 | 필드 |
|---|---:|---|
| `0x00` | 16 | 경로 문자열의 MD5 |
| `0x10` | 4 | `block_idx` — 블록 크기 테이블의 시작 인덱스 |
| `0x14` | 5 | `orig_size` — 비압축 크기 (40비트 BE) |
| `0x19` | 5 | `offset` — 아카이브 내 데이터 시작 위치 (40비트 BE) |

크기와 오프셋이 **5바이트 40비트**라는 점에 주의한다. 4바이트로 읽으면 어긋난다.

엔트리 0은 파일명 목록을 담은 매니페스트다. 개행으로 구분된 경로 문자열이 들어 있고,
나머지 엔트리는 이 목록의 순서와 대응한다.

## 블록 크기 테이블

TOC 뒤에 각 압축 블록의 크기가 이어진다. 원소 폭은 `block_size`에 따라 정해진다.

```
block_size <= 0x100     -> 1 바이트
block_size <= 0x10000   -> 2 바이트   (이 게임: 65536 이므로 2)
block_size <= 0x1000000 -> 3 바이트
그 외                   -> 4 바이트

원소 개수 = (toc_len - 32 - 엔트리개수 * 엔트리크기) / 원소폭
```

크기가 `0`인 원소는 **비압축(stored) 블록**을 뜻하며, 그대로 `block_size` 만큼 읽는다.
`0`이 아니면 그 바이트 수만큼 읽어 zlib 압축을 푼다. 실제 데이터는 `0x78`로 시작하는
zlib 스트림이지만, 압축 이득이 없어 원본이 그대로 저장된 블록도 있으므로
선두 바이트를 확인하고 분기하는 편이 안전하다.

## 엔트리 읽기 절차

```
1. entry.offset 으로 이동
2. bi = entry.block_idx
3. 누적 길이가 entry.orig_size 에 도달할 때까지:
     csize = block_table[bi]; bi += 1
     csize == 0 이면 block_size 만큼 그대로 읽기
     아니면 csize 만큼 읽어 zlib 해제
4. orig_size 로 잘라서 반환
```

블록 테이블을 넘어서거나 한 회차에 아무것도 읽지 못하면 중단해야 한다.
그렇지 않으면 손상된 아카이브에서 무한 루프에 빠진다.

## PSARCLIST.BIN

`USRDIR/PSARC/PSARCLIST.BIN`은 180바이트짜리 아카이브 매니페스트다.

```
"PSAL" | count(1) = 7 | [ flag(1) | namelen(1) | name | 0x00 ] * 7
```

`flag`는 `1`이면 암호화된 `.sdat`, `0`이면 평문 `.psarc`다.

```
1 17 PSARC/Common.psarc.sdat
1 17 PSARC/Battle.psarc.sdat
1 1A PSARC/General2d.psarc.sdat
1 16 PSARC/Logic.psarc.sdat
1 1A PSARC/General3d.psarc.sdat
0 11 PSARC/Sound.psarc
0 11 PSARC/Movie.psarc
```

## ISO 상의 배치

원본 ISO(`PS3_GAME/USRDIR/PSARC/`)에서 큰 파일은 ISO9660 **다중 익스텐트**로 저장된다.
같은 이름의 디렉터리 레코드가 순서대로 여러 개 나오고, 마지막을 제외한 모든 레코드에
플래그 `0x80`이 서 있다. 추출할 때 이들을 순서대로 이어붙여야 한다.

| 파일 | 익스텐트 | 합계 |
|---|---:|---:|
| `BATTLE_PSARC.SDAT` | 2 | 1,729,186,848 |
| `SOUND.PSARC` | 2 | 1,702,664,667 |
| `MOVIE.PSARC` | 6 | 6,047,320,161 |

이어붙인 `BATTLE_PSARC.SDAT`의 크기가 HDD 설치본의 `Battle.psarc.sdat`과 정확히 일치하는지
확인하면 추출 로직을 자체 검증할 수 있다.

## 구현

| 파일 | 역할 |
|---|---|
| `psarc.py` | 파서. `entries`, `block_table`, `read_entry(i)` |
| `psarc_write.py` | 표준 재패킹 |
| `psarc_fixed_blocks.py` | 원본 배치를 보존하는 재빌드 ([고정 배치 재빌드](fixed-layout.md)) |
