# SDAT 암호 구조

게임 아카이브는 `.psarc.sdat` 확장자를 쓴다. PSARC 아카이브를 SDAT(EDAT 계열) 컨테이너로
암호화한 것이다. 한국어화를 하려면 복호 → 수정 → **재암호화**가 모두 가능해야 한다.

> 2026-09-19 검토. 아래는 이 게임의 관측된 SDAT 플래그·헤더에 대한 설명이며 모든 EDAT/SDAT 변형의 명세가 아니다. 현재 배포 대상과 검증 범위는 [배포 검증](release-validation.md)을 참고한다.

## 대상 파일

`USRDIR/PSARC/` 에 아래 7개가 있다. `PSARCLIST.BIN`이 이 목록을 담은 매니페스트다.

| 파일 | 암호화 | 크기 |
|---|---|---:|
| `Common.psarc.sdat` | O | 505,828,992 |
| `General2d.psarc.sdat` | O | 611,585,392 |
| `General3d.psarc.sdat` | O | 870,220,816 |
| `Logic.psarc.sdat` | O | 38,399,120 |
| `Battle.psarc.sdat` | O | 1,729,186,848 |
| `Sound.psarc` | X | 1,702,664,667 |
| `Movie.psarc` | X | 6,047,320,161 |

`Sound`/`Movie`는 평문 PSARC다. 나머지 5개만 SDAT 컨테이너를 거친다.

## NPD 헤더 (0x000 ~ 0x0FF)

파일 선두 0x100 바이트가 NPD 헤더다.

| 오프셋 | 크기 | 필드 |
|---|---:|---|
| `0x00` | 4 | 매직 `"NPD\0"` |
| `0x04` | 4 | 버전 (BE). 이 게임은 `4` |
| `0x40` | 16 | `digest` — CBC 초기 IV로 사용 |
| `0x50` | 16 | `title_hash` |
| `0x60` | 16 | `dev_hash` — 블록 키 유도의 재료 |
| `0x80` | 4 | `flags` (BE). 이 게임은 `0x0100003C` |
| `0x84` | 4 | `block_size` (BE). 이 게임은 `0x4000` (16 KiB) |
| `0x88` | 8 | `file_size` (BE) — 복호 후 평문 크기 |

`flags & 0x01000000` 이 SDAT 표시다.

## 블록 레이아웃

평문은 `block_size` 단위로 잘려 블록마다 **0x20 메타데이터 + 암호문**으로 저장된다.
암호문은 16바이트 경계로 패딩된다.

```
블록 N의 메타데이터 = 0x100 + N * (0x20 + block_size)
블록 N의 암호문     = 0x100 + N * (0x20 + block_size) + 0x20
블록 총 개수        = ceil(file_size / block_size)
```

마지막 블록의 유효 길이는 `file_size - block_size * (총개수 - 1)` 이다.

## 키 유도

핵심은 **같은 파일의 키 재료를 고정하면 블록 번호별로 키를 독립 유도한다**는 점이다. 키는 블록 번호만이 아니라 아래의 `dev_hash`와 키 상수에도 의존한다.
IV는 모든 블록에서 `digest`로 고정된다.

```
SDAT_KEY   = 0D655EF8E674A98AB8505CFA7D012933
EDAT_KEY_1 = 4CA9C14B01C95309969BEC68AA0BC081

crypt_key  = dev_hash XOR SDAT_KEY
block_key  = dev_hash[0:12] || BE32(N)
key_result = AES_ECB_enc(crypt_key, block_key)
key_final  = AES_ECB_dec(EDAT_KEY_1, key_result)      # ERK 변환 (version >= 2)

plain      = AES_CBC_dec(key_final, IV = digest, cipher)
cipher     = AES_CBC_enc(key_final, IV = digest, plain)
```

### 이 성질이 중요한 이유

SDAT 블록 사이에는 CBC 체이닝이 없다. 같은 헤더·키 재료·IV·패딩 조건이라면 **인덱스 N의 평문이 같을 때 암호문도 같다.** 서로 다른 파일·헤더 사이에 무조건 성립하는 명제는 아니다.

배포용 이진 델타의 크기가 여기서 크게 영향을 받는다. CBC에서는 수정된 평문이 포함된 16바이트 AES 블록부터 해당 SDAT 블록 끝까지 암호문이 달라질 수 있다. 수정 위치 앞의 암호문까지 반드시 바뀌는 것은 아니다. 변경 영향은 다음 SDAT 블록으로 체이닝되지 않는다. 블록 메타데이터도 다시 계산해야 한다. 자세한 활용은 [고정 배치 재빌드](fixed-layout.md)를 참고한다.

## 재암호화와 메타데이터 위조

복호는 위 식을 그대로 뒤집으면 되지만, 재암호화에서는 블록마다 0x20 메타데이터를
다시 만들어야 한다. `flags 0x0100003C`(SDAT + ENCRYPTED_KEY + FLAG_0x10 + FLAG_0x20)
조합에서 이 메타데이터는 암호문의 HMAC-SHA1 해시다.

```
key_result = AES_ECB_enc(crypt_key, dev_hash[0:12] || BE32(N))
hashk      = AES_ECB_enc(crypt_key, key_result)            # FLAG_0x10 = 이중 enc
hash_final = AES_ECB_dec(EDAT_KEY_1, hashk) || 00 00 00 00 # 0x10 → 0x14 로 0 패딩
computed   = HMAC_SHA1(hash_final, cipher)[0:0x14]

meta[0x10:0x20] = computed[0x10:0x14] || 00 * 12
meta[0x00:0x10] = computed[j] XOR meta[0x10 + j]           # FLAG_0x20 = XOR 인코딩
```

즉 `meta[j] XOR meta[j + 0x10]` 이 원래 해시가 되도록 상·하위 16바이트를 나눠 넣는다.
이 메타데이터 재생성은 블록 무결성 검사에 필요하다. 이 계산의 성공만으로 PS3 실기 전체 호환성을 입증하지는 않는다.

헤더는 원본 NPD를 그대로 재사용하고 `0x88`의 `file_size`만 갱신한다.
평문 크기가 원본과 같으면 헤더는 완전히 동일해진다.

## 구현

| 파일 | 역할 |
|---|---|
| `sdat.py` | 복호. `decrypt_stream()`, 랜덤 액세스용 `SDATReader` |
| `sdat_encode.py` | 재암호화. `encode(plain_path, orig_header_bytes, out_path)` |

`SDATReader`는 블록이 독립 복호되는 성질을 이용해 전체를 디스크에 풀지 않고
필요한 구간만 복호한다. 1.7GB짜리 `Battle`을 다룰 때 필수적이다.
