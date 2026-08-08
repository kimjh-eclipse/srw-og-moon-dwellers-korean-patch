# 부록: 문서 색상 팔레트

이 문서 사이트와 배포 페이지에 쓰는 색상 조합이다.
『슈퍼로봇대전 OG 더 문 드웰러즈』 타이틀 화면 — 심우주 네이비 배경, 은빛 `OG` 링,
금색 로고, 지구를 감싼 시안 글로우 — 에서 뽑았다.

## 팔레트

| 역할 | 이름 | HEX | 유래 |
|---|---|---|---|
| 배경 (다크) | Deep Space | `#0B1B3A` | 타이틀 배경의 심우주 |
| 표면 | Orbit Navy | `#14315E` | 지구 그림자 쪽 청색 |
| **주조색** | **Glow Cyan** | **`#4FC8F5`** | `PRESS ANY BUTTON` 발광 |
| 강조 | Signal Gold | `#F2B33D` | 로고 상단 금색 |
| 강조 (딥) | Amber Deep | `#D98324` | 로고 하단 그라데이션 |
| 중립 | Steel Silver | `#C6D3E2` | `OG` 링의 은색 |
| 본문 (다크) | Star White | `#F5F9FF` | 별빛 |
| 배경 (라이트) | Paper | `#FFFFFF` | |
| 본문 (라이트) | Ink Navy | `#102A4C` | Deep Space의 명도 조정 |

## 조합 규칙

- **주조색은 Glow Cyan `#4FC8F5`** 로 한다. 링크, 활성 메뉴, 포커스 링에 쓴다.
- **Signal Gold `#F2B33D` 는 강조 하나에만** 쓴다. 경고 박스나 릴리스 배지 정도다.
  시안과 금색을 같은 비중으로 쓰면 화면이 산만해진다.
- Amber Deep은 금색 위의 호버·눌림 상태에만 쓴다.
- 표 헤더와 코드 블록 배경은 Orbit Navy `#14315E` 계열로 낮춰 깔고,
  본문은 Star White로 둔다.
- 빨강·초록은 팔레트에 없다. 성공/실패 표시가 필요하면 시안(정상)과
  Amber Deep(주의)으로 대체한다.

## 명암비

다크 배경 `#0B1B3A` 기준 (WCAG 기준 본문 4.5:1, 큰 글씨 3:1).

| 전경 | 명암비 | 판정 |
|---|---:|---|
| Star White `#F5F9FF` | 약 17.5:1 | 본문 가능 |
| Glow Cyan `#4FC8F5` | 약 8.9:1 | 본문 가능 |
| Signal Gold `#F2B33D` | 약 9.2:1 | 본문 가능 |
| Steel Silver `#C6D3E2` | 약 11.6:1 | 본문 가능 |
| Amber Deep `#D98324` | 약 5.6:1 | 본문 가능, 작은 글씨는 주의 |

라이트 모드에서는 Glow Cyan을 그대로 쓰면 흰 배경에서 대비가 부족하다.
링크색을 `#0E7FA8`(Glow Cyan을 어둡게)로 낮춰 쓴다.

## 적용 방법

GitBook의 테마 색상은 저장소 파일이 아니라 **사이트 설정에서 지정한다.**
이 저장소를 동기화한 뒤 GitBook 공간의 Customization(테마) 설정에서 아래를 넣는다.

```
Primary color (dark)   #4FC8F5
Primary color (light)  #0E7FA8
```

즉 이 페이지는 팔레트의 **기준 문서**이고, 실제 색 반영은 GitBook 쪽 설정에서 이뤄진다.
저장소만으로는 색이 바뀌지 않는다.

블로그나 카페 글에 배너를 만들 때도 위 팔레트를 그대로 쓰면 배포물과 톤이 맞는다.

## CSS 변수 (다른 곳에 옮길 때)

```css
:root {
  --ogmd-bg:        #0B1B3A;
  --ogmd-surface:   #14315E;
  --ogmd-primary:   #4FC8F5;
  --ogmd-accent:    #F2B33D;
  --ogmd-accent-dp: #D98324;
  --ogmd-neutral:   #C6D3E2;
  --ogmd-text:      #F5F9FF;
}

@media (prefers-color-scheme: light) {
  :root {
    --ogmd-bg:      #FFFFFF;
    --ogmd-surface: #EEF3FA;
    --ogmd-primary: #0E7FA8;
    --ogmd-text:    #102A4C;
  }
}
```
