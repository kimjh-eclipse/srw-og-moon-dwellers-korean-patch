# SDAT 암호 구조

게임 아카이브는 `.psarc.sdat` 확장자를 쓴다. PSARC 아카이브를 SDAT(EDAT 계열) 컨테이너로
암호화한 것이다. 한국어화를 하려면 복호 → 수정 → **재암호화**가 모두 가능해야 한다.

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

핵심은 **블록마다 키가 다르고, 그 키가 블록 번호에서만 유도된다**는 점이다.
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

블록끼리 체이닝이 없다. 따라서 **인덱스 N의 평문이 같으면 암호문도 반드시 같다.**

배포용 이진 델타의 크기가 여기서 결정된다. 어떤 블록의 평문이 1바이트라도 바뀌면
그 블록의 암호문 16 KiB 전체가 무작위에 가깝게 달라지지만, 바뀌지 않은 블록은
암호문까지 그대로 남는다. 자세한 활용은 [고정 배치 재빌드](fixed-layout.md)를 참고한다.

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
이 위조가 정확해야 에뮬레이터·실기가 블록을 거부하지 않는다.

헤더는 원본 NPD를 그대로 재사용하고 `0x88`의 `file_size`만 갱신한다.
평문 크기가 원본과 같으면 헤더는 완전히 동일해진다.

## 구현

| 파일 | 역할 |
|---|---|
| `sdat.py` | 복호. `decrypt_stream()`, 랜덤 액세스용 `SDATReader` |
| `sdat_encode.py` | 재암호화. `encode(plain_path, orig_header_bytes, out_path)` |

`SDATReader`는 블록이 독립 복호되는 성질을 이용해 전체를 디스크에 풀지 않고
필요한 구간만 복호한다. 1.7GB짜리 `Battle`을 다룰 때 필수적이다.
