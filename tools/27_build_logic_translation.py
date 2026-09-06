#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a LOGIC dialogue PoC or all translations that fit existing fields."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psarc import PSARC
from psarc_write import compress_blocks, enable_zopfli, entry_nblocks, rebuild
from sdat import SDATReader
from sdat_encode import encode


POC_UID = 9048
OBJECTIVE_OVERRIDE_UIDS = {9926, 9927, 9928, 9943, 9944, 9945}
# These strings are passed to the PS3 system dialog instead of the game's
# custom text renderer.  They must remain real Unicode Hangul; proxy glyphs
# are only meaningful to the patched in-game font.
RAW_SYSTEM_DIALOG_UIDS = {4977, 4984, 5276}
TRANSLATION_OVERRIDES = {
    # Scenario-objective records use an ideographic space after the item
    # number.  In the Korean font path that space can be rendered as a stray
    # Hangul glyph (reported as "토").  Keep these early-stage objectives
    # compact and use only ordinary ASCII punctuation/spacing.
    9926: "1. 적 전멸.",
    9927: "1. 에 셀다 격추.",
    9928: "없음.",
    9943: "1. 컴패티블 카이저의 HP를 #0 이하로 만든다.",
    9944: "1. 아키미 격추.",
    9945: "소울 세이버 FF가 피격되지 않고 승리 조건을 달성한다.",
    # Early OGMD scenario title stored in StageData.dat.
    # Must stay within the original 27-byte StageData title field.
    5562: "아버지와 아들, 숙명",
    # Six Hangul syllables plus one syllable is exactly the fixed 21-byte
    # unit-name field; a visible space would overflow this record.
    4021: "바이오로이드병",
    # Bottom key-guide labels have a fixed twelve-byte field.  Keep these
    # compact and do not use spaces so no text is truncated.
    1851: "원호전환",
    1853: "반격설정",
    1855: "방향전환",
    # Unit-name spelling displayed on the battle/action screen.
    6151: "그라시드 류",
    4977: "게임을 계속하시겠습니까?",
    4984: "저장이 끝났습니다.\n게임을 계속하시겠습니까?",
    5307: "미행동 유닛이 %d기 있습니다.@페이즈를 종료하시겠습니까?",
    5308: "페이즈를 종료합니다.@계속하시겠습니까?",
    5276: "게임을 계속하시겠습니까?",
    9054: "「진상이라니…… 동화 계획 말입니까？」",
    9057: "「더는 여유가 없다」",
    9095: "「잠깐, 함부로 나가지 마라」",
    9100: "「소동을 눈치채고 앞질러 간 모양이다」",
    # E-Selda's line fits the byte field as-is, but the literal draft is much
    # too wide for the dialogue frame.  Keep the father's "battle / true
    # self" contrast while shortening both visual lines.
    9520: "「잘 봐라, 토우야…@　아버지의 싸움과 진실한 모습을…!」",
    # もしもし here is a mildly sarcastic call for attention, not a phone
    # greeting.  Translate each occurrence according to its surrounding line.
    13805: "「있잖아? 우리도 그걸 갖고 싶은데?」",
    24201: "「잠깐만? 한창 달아오른 데 미안하지만@　뭘 걸 생각이야, 쿄스케?」",
    # Early-game dialogue and location cards that contain visible dictionary
    # links.  The links must retain <...>, but their contents are ordinary
    # on-screen text and therefore need Korean terms too.
    3118: "버닝 PT",
    # Location headers use the normal text renderer.  Never leave U+3000 in
    # these records: the Korean proxy font can render it as a visible "토".
    # The same caption is duplicated in several scenario talk archives.
    34153: "삿포로 근교",
    34161: "일본 삿포로 근교",
    34639: "일본 삿포로 근교",
    35082: "일본 삿포로 근교",
    57681: "삿포로 근교",
    65597: "삿포로 근교",
    65605: "일본 삿포로 근교",
    65636: "삿포로 근교",
    9193: "고교 교내",
    9194: "「…… 졸려 보이네, 토우야.@ 또 늦게까지 <버닝 PT>를 하고 있었어?」",
    9223: "모가미 중공 시험장 내부",
    9311: (
        "「<테슬라 라이히 연구소>나 <마오 인더스트리>,@ "
        "<이스루기 중공>의 로봇과 경쟁하려면@ "
        "비용과 정비성, 견실함으로 승부해야지.」"
    ),
    9312: "「진푸 씨 일행은 소울 세이버를@ <지구연방군>에 팔 생각이야?」",
    20600: "「그래. 난 고등학생 때@ <버닝 PT> 실력을 인정받아@ SRX 팀에 들어왔어」",
    24183: "「버닝 PT는 꽤 파고들었으니까……」",
    16595: "「황가의 주인과, 그 근위대장을@　대대로 맡아 온 시운 가문의 수장뿐입니다」",
    22126: "「즉, 황가의 주인과@　그 근위대장을 대대로 맡아 온@　슌 가문의 수장뿐입니다」",
    # Opening / flashback roll captions live in LOGIC CSB files and were not
    # part of the normal dialogue extraction batches.
    26582: (
        "신서력이라 불리는 시대.\n\n"
        "인류가 우주로 본격 진출한 지 약 2세기가 지났지만, 생활상은 "
        "21세기 초와 크게 다르지 않았다. 두 차례의 운석 낙하가 남긴 "
        "피해와 혼란으로 인류의 발전이 한동안 멈췄기 때문이다.\n\n"
        "그리고 신서력 179년.\n\n"
        "세 번째 운석 메테오3가 남태평양 마케사스 제도 근해에 떨어졌다. "
        "조사 결과, 그 운석은 인공물이었으며 인류에게 미지의 물질과 "
        "기술 정보가 봉인되어 있었다. 사람들은 그것을 EOT라 부르며 "
        "연구를 시작했다.\n\n"
        "천재 과학자 비안 졸다크는 연구 결과를 바탕으로 외계 지성체의 "
        "침략 가능성을 경고했고, 이를 계기로 대외계 전투용 인형 기동병기의 "
        "개발이 시작되었다.\n\n"
        "그 뒤 비안 박사가 이끄는 군사 결사 DC가 연방 정부에 선전포고하며 "
        "DC 전쟁이 시작됐다. 이어 에어로게이터, 인스트, 섀도우 미러, "
        "인스펙터, 수라 등 수많은 위협이 지구권을 덮쳤다.\n\n"
        "연방군은 적을 물리쳤지만, 하늘에는 이세계로 통하는 거대한 "
        "크로스게이트가 남았다. 그리고 그 문은 불길한 움직임을 보이기 시작했다."
    ),
    26583: "언제부턴가 같은 꿈을 꾸었다.",
    26584: "어둠 속에 홀로 앉아,",
    26585: "기도하듯 나를 바라보는 소녀의 꿈이었다.",
    26586: "너무도 아름답고 슬픈 눈을 한 그녀는,",
    26587: "늘 같은 말을 했다.\n",
    26588: "「용서해 주세요… 부디 용서를……",
    26589: "　또다시 금기를 범했습니다……」",
    26590: "「이 세계에 재앙을 불러오고 말았습니다……",
    26591: "　설령 정해진 운명이었다 해도,\n　그 죄는 저희에게 있습니다……」",
    26592: "「열쇠는 황가의 검……",
    26593: "　당신에게 무거운 짐을 지우게 될지도 모르는\n　저를……」",
    26594: "「무력한 저를… 용서해 주세요…」",
    26595: "눈을 뜨면",
    26596: "언제나 그녀의 말을 거의 잊어버리고 만다.",
    26597: "기억에 남는 것은 오직,",
    26598: "투명한 머리카락 주위로 반짝이는 빛의 입자와,",
    26599: "슬퍼 보이던 그 눈동자뿐.",
    26600: "그것이 싸움의 전조였다는 사실을,",
    26601: "그때는 아직 알 수 없었다…….",
}

# ``uid`` is not globally unique in the game's string extraction: a dialogue
# record can share its UID with an unrelated weapon, bonus-description, or
# archive byte sequence.  Never apply an override solely because a UID
# matches.  The exact source text keeps the UI/dialogue corrections scoped to
# the records they were written for.
OVERRIDE_SOURCE_TEXT = {
    9926: "１．　敵の全滅。",
    9927: "１．　エ＝セルダの撃墜。",
    9928: "・無し。",
    9943: "１．　コンパチブルカイザーのＨＰを#0以下にする。",
    9944: "１．　アキミの撃墜。",
    9945: "・ソウルセイバーＦＦが被弾せずに、勝利条件を満たす。",
    5562: "父と子、そして宿命",
    4021: "バイオロイド兵",
    1851: "援護切換",
    1853: "反撃設定",
    1855: "矢印切換",
    6151: "グラシドゥ＝リュ",
    4977: "セーブ画面を終了します。\nよろしいですか？",
    4984: "セーブが終了しました。\nゲームを続けますか？",
    5307: "行動終了していないユニットが%d体あります。@フェイズを終了しますか？",
    5308: "フェイズを終了します。@よろしいですか？",
    5276: "前回、中断した場面から再生しますか？",
    9054: "「真相……同化計画の、ですか？」",
    9057: "「もはや猶予はない」",
    9095: "「待て、迂闊に外へ出るな」",
    9100: "「騒動に気づき、先回りしたようだ」",
    9520: "「見ているがいい、トーヤ……@　父の戦いを、父の真実の姿を……！」",
    13805: "「もしもし？　私達はあれも欲しいんだけどぉ？」",
    24201: "「もしもし？　盛り上がってるとこ悪いけど、@　何を賭ける気かしら、キョウスケ？」",
    3118: "バーニングＰＴ",
    34153: "日本　札幌近郊",
    34161: "日本　札幌地区近郊",
    34639: "日本　札幌地区近郊",
    35082: "日本　札幌地区近郊",
    57681: "日本　札幌近郊",
    65597: "日本　札幌近郊",
    65605: "日本　札幌地区近郊",
    65636: "札幌地区近郊",
    9193: "高校　校内",
    9194: "「……眠そうだな、トーヤ。@　また遅くまで<バーニングＰＴ>やってたのか？」",
    9223: "モガミ重工　試験場施設内",
    9311: (
        "「<テスラ・ライヒ研究所>や<マオ・インダストリー>、@　"
        "<イスルギ重工>のロボットとタメを張るには、@　"
        "コストや整備性、質実剛健さで勝負しなきゃな」"
    ),
    9312: "「ジンプウさん達は、ソウルセイバーを@　<地球連邦軍>に売り込む気なのか？」",
    16595: "「皇家の主と、その近衛である聖禁士長を@　代々務めるシューン家の長のみです」",
    20600: "「ああ。俺は高校生の時、@　<バーニングＰＴ>の腕を見込まれて、@　ＳＲＸチームに入ったんだ」",
    22126: "「すなわち、皇家の主と@　その近衛……聖禁士長を代々務める@　シューン家の長のみです」",
    24183: "「バーニングＰＴは結構やり込んでたから……」",
}


def normalize_translation(text: str) -> str:
    """Apply project-wide terminology fixes before proxy encoding."""
    # Angle brackets in these resources are visible keyword delimiters, not
    # control codes.  Translate their contents as well, while preserving the
    # delimiters themselves for the in-game dictionary links.
    replacements = (
        # Canonical series terminology.  Normalize every spelling variant,
        # including dialogue and dictionary fragments.
        ("콤파치블", "컴패터블"),
        ("컴파치블", "컴패터블"),
        ("콤패티블", "컴패터블"),
        ("컴패티블", "컴패터블"),
        # Japanese series terms that survived inside otherwise translated
        # dialogue and glossary records.
        ("Ｄコン", "D-Con"),
        ("ダークブレイン", "다크브레인"),
        # Fixed-width help/effect strings: use the UI's concise noun style.
        ("자신 부대의", "아군"),
        ("자신 기체의", "자기"),
        ("무기와 맵병기 이외 무기의", "일반 무기의"),
        ("최종 명중률", "명중"),
        ("최종 회피율", "회피"),
        ("명중률 보정치", "명중보정"),
        ("공격력", "위력"),
        ("최대탄수", "탄수"),
        ("발생률", "발생"),
        ("을 나타냅니다.", " 표시"),
        ("를 나타냅니다.", " 표시"),
        ("가 나타납니다.", " 표시"),
        ("을 표시합니다.", " 표시"),
        ("를 표시합니다.", " 표시"),
        ("할 수 있습니다.", "가능"),
        ("하지 않습니다.", "불가"),
        ("하지 않음을", "불참"),
        ("원래대로", "초기화"),
        ("서브 정보", "보조정보"),
        ("표시 전환", "표시전환"),
        ("항목 전환", "항목전환"),
        ("능력 입력", "능력입력"),
        ("분류 전환", "분류전환"),
        ("무기 분류 전환", "무기분류"),
        ("장비 기체 확인", "장비확인"),
        ("매각 실행", "매각"),
        ("변형 확인", "변형"),
        ("개조치 입력", "개조입력"),
        ("검색 설정", "검색설정"),
        ("검색 전환", "검색전환"),
        ("부대 변경", "부대변경"),
        ("전 무기의", "전무기"),
        ("격투 무기의", "격투무기"),
        ("사격 무기의", "사격무기"),
        ("고정 무기의", "고정무기"),
        ("환장 무기의", "환장무기"),
        ("염동계 무기의", "염동무기"),
        ("탄수계 고정 무기의", "탄수고정무기"),
        ("기체의", "기체"),
        ("무기의", "무기"),
        ("아군 사거리 １ 무기와 맵병기 이외 무기의", "아군 사거리1·맵병기 외 무기"),
        ("사거리 １ 무기와 맵병기 이외 무기의", "사거리1·맵병기 외 무기"),
        ("특수기 ", "특수기"),
        ("정신기 ", "정신기"),
        # Short, fixed-width UI labels and database names.
        ("ＨＰ 회복", "HP회복"),
        ("ＥＮ 회복", "EN회복"),
        ("어둠의 영역", "어둠 영역"),
        ("감시의 눈", "감시안"),
        ("신복의 방패", "신복 방패"),
        ("신의 방패", "신방패"),
        ("신수방패", "신수 방패"),
        ("단독 분리", "단독분리"),
        ("수리 장치", "수리장치"),
        ("보급 장치", "보급장치"),
        ("방패 장비", "방패장비"),
        ("사정거리", "사거리"),
        ("운동성", "운동"),
        ("지휘 효과", "지휘"),
        ("특수 스킬", "특수기"),
        ("정신 커맨드", "정신기"),
        ("최대 ", "최대"),
        ("모든 ", "전 "),
        ("자신 기체", "자기"),
        # Residual glossary fragments in the original draft.  These often
        # occur inside <...> dictionary links and sometimes straddle two
        # extracted rows, so retain both full terms and safe fragments.
        ("封印戦争", "봉인 전쟁"),
        ("新西暦", "신서력"),
        ("旧西暦", "구서력"),
        ("地球連邦政府", "지구연방정부"),
        ("地球連邦軍", "지구연방군"),
        ("連邦軍", "연방군"),
        ("連邦", "연방"),
        ("DC戦争", "DC 전쟁"),
        ("L5戦役", "L5 전역"),
        ("鋼龍戦隊", "강룡전대"),
        ("鋼龍", "강룡"),
        ("龍戦隊", "용전대"),
        ("ファブラ・フォレース", "파브라 포레스"),
        ("ファブラ・", "파브라 "),
        ("フォレース", "포레스"),
        ("ルイーナ", "루이나"),
        ("アイドネウス島", "아이도네우스 섬"),
        ("メテオ３", "메테오 3"),
        ("トロニウム", "트로니움"),
        ("インスペクター事件", "인스펙터 사건"),
        ("インスペクター", "인스펙터"),
        ("アインスト", "아인스트"),
        ("オペレーション・プランタジネット", "오퍼레이션 플랜타지넷"),
        ("オペレーションＳＲＷ", "오퍼레이션 SRW"),
        ("エアロゲイター", "에어로게이터"),
        ("イングラム・プリスケン", "잉그램 프리스켄"),
        ("ガイアセイバーズ", "가이아 세이버즈"),
        ("ユ－ゼス", "유제스"),
        ("アードルム・エクステリオル", "아돌름 엑스테리오르"),
        ("マシンセル", "머신 셀"),
        ("メリアオルエッセ", "메리오르 에세"),
        ("シュンパティア", "심파티아"),
        ("テスラ・ドライブ", "테슬라 드라이브"),
        ("テスラ", "테슬라"),
        ("ラ・ギアス", "라 기아스"),
        ("神聖ラングラン王国", "신성 랑그란 왕국"),
        ("アーマードモジュール", "아머드 모듈"),
        ("ゾヴォーグ", "조보그"),
        ("ブーステッド・チルドレン", "부스티드 칠드런"),
        ("ユニバーサル・コネクター", "유니버설 커넥터"),
        ("特殊戦技教導隊", "특수전기교도대"),
        ("ハガネ", "하가네"),
        ("ヒリュウ改", "히류 개"),
        ("ヒリュウ", "히류"),
        ("フル改造から暫定取得", "풀 개조 시 임시 획득"),
        ("バーニングＰＴ", "버닝 PT"),
        ("テスラ・ライヒ研究所", "테슬라 라이히 연구소"),
        ("マオ・インダストリー", "마오 인더스트리"),
        ("イスルギ重工", "이스루기 중공업"),
        ("地球連邦軍", "지구연방군"),
        ("修羅の乱", "수라의 난"),
        ("修羅神", "수라신"),
        ("修羅", "수라"),
        ("日本　札幌地区近郊", "일본 삿포로 근교"),
        ("日本　札幌近郊", "삿포로 근교"),
        ("日本東北地方近郊", "도호쿠 인근"),
        ("高校　校内", "고교 교내"),
        ("モガミ重工　試験場施設内", "모가미 중공 시험장 내부"),
        ("성금사장", "근위대장"),
        ("금사의 장", "근위대장"),
        ("금사장", "근위대장"),
        ("금사단", "근위기사단"),
        ("금사들", "근위기사들"),
        ("성금사", "근위기사"),
        ("금사", "근위기사"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    # Scenario objectives frequently retain the Japanese full-width item
    # prefix (for example ``１．　``).  Besides wasting fixed-slot bytes, the
    # ideographic space is not safe in the Korean mission-objective renderer.
    # Normalize every numbered objective so later stages cannot show the same
    # stray leading glyph.
    for fullwidth, ascii_digit in zip("１２３４５６７８９", "123456789"):
        text = text.replace(f"{fullwidth}．　", f"{ascii_digit}. ")
    # Some legacy rows kept faction labels in literal angle brackets.  These
    # are not control codes and must render as ordinary Korean text.
    text = text.replace("ゲスト", "게스트")
    text = re.sub(r"(?<=[가-힣])[=＝][ ]*(?=[가-힣])", " ", text)
    return text


def compact_fixeddata_translation(text: str, file_path: str) -> str:
    """Shorten only database/help prose when a fixed UTF-8 field overflows.

    Dialogue is deliberately excluded: changing its sentence endings globally
    would make a character's voice inconsistent.  These substitutions are
    confined to static help, ability and dictionary records where concise
    declarative wording is appropriate.
    """
    if "/Dat/FixedData/" not in file_path:
        return text
    replacements = (
        ("할 수 있습니다", "가능합니다"),
        ("하고 있습니다", "중입니다"),
        ("되어 있습니다", "있습니다"),
        ("것입니다", "겁니다"),
        ("것은", "건"),
        ("것이", "게"),
        ("것을", "걸"),
        ("그리고", "또한"),
        ("있습니다", "있다"),
        ("없습니다", "없다"),
        ("됩니다", "된다"),
        ("합니다", "한다"),
        ("하겠습니다", "한다"),
        ("겠습니다", "겠다"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    return text


def fit_translation(
    text: str, capacity: int, mapping: dict[str, str], file_path: str = ""
) -> str:
    """Compact only typography until an otherwise-overflowing line fits."""
    candidates = [
        text,
        text.replace("@　", "@"),
    ]
    candidates.append(
        candidates[-1].translate(
            str.maketrans("！？（）［］", "!?()[]")
        )
    )
    candidates.append(candidates[-1].replace("……", "…"))
    if candidates[-1].startswith("「") and candidates[-1].endswith("」"):
        candidates.append(candidates[-1][1:-1])
    # Frequently duplicated scenario labels and objective strings.  These are
    # exact, meaning-preserving shortenings for retail fixed slots; keeping
    # them here resolves every duplicate consistently without truncation.
    exact_short = {
        "휴식의 시간": "휴식",
        "<W=63>　</W>또한 젤라니오는 ＨＰ가 #0 이하가 되면 철수한다.":
            "<W=63>　</W>젤라니오는 ＨＰ가 #0 이하면 철수한다.",
        "·하가네가 피격되지 않게 한다.": "·하가네 피격 금지.",
        "[ＤＭ]-Ｆ 로아": "[ＤＭ]-Ｆ로아",
        "１．　데브데다비데의 ＨＰ를 #1 이하로 만든다.":
            "１．　데브데다비데의 ＨＰ를 #1 이하로 한다.",
        "일제 포격": "일제포격",
        "초보자 마크": "초보 마크",
        "[ＤＭ]-테츠야 ２": "[ＤＭ]-테츠야２",
    }
    candidates.append(exact_short.get(candidates[-1], candidates[-1]))
    # Apply semantic shortening only after the lossless typography options.
    # This keeps the normal Korean wording whenever it already fits.
    candidates.append(compact_fixeddata_translation(candidates[-1], file_path))
    for candidate in candidates:
        if len(proxy_encode(candidate, mapping)) <= capacity:
            return candidate
    return text


def unescape_tsv(text: str) -> str:
    output = []
    index = 0
    while index < len(text):
        if text[index] != "\\" or index + 1 >= len(text):
            output.append(text[index])
            index += 1
            continue
        code = text[index + 1]
        if code == "n":
            output.append("\n")
        elif code == "t":
            output.append("\t")
        elif code == "\\":
            output.append("\\")
        else:
            output.extend(("\\", code))
        index += 2
    return "".join(output)


def load_translations(folder: Path) -> dict[int, str]:
    result = {}
    for path in sorted(folder.glob("batch_*.tsv")):
        for line in path.read_text(encoding="utf-8").splitlines():
            uid, text = line.split("\t", 1)
            result[int(uid)] = unescape_tsv(text)
    return result


def load_manual_fits(folder: Path) -> dict[tuple[int, str, str], str]:
    """Load reviewed fixed-slot translations using a collision-safe key."""
    result: dict[tuple[int, str, str], str] = {}
    for path in sorted(folder.glob("logic_*_manual_fit.jsonl")):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            key = (int(row["uid"]), row["file"], row["source"])
            target = row["new_target"]
            previous = result.get(key)
            if previous is not None and previous != target:
                raise ValueError(
                    f"conflicting manual fit for {key} at {path}:{line_number}"
                )
            result[key] = target
    return result


def build_keyword_link_map(
    master: list[dict],
    translations: dict[int, str],
    manual_fits: dict[tuple[int, str, str], str],
    mapping: dict[str, str],
) -> dict[str, str]:
    """Map every original ``<keyword>`` target to its final Korean title.

    The game resolves glossary links by the visible text inside angle
    brackets.  Translating a keyword title but leaving an old Japanese target
    in dialogue or glossary prose therefore makes the link disappear.  Build
    the mapping from the actual KeyWordData title records so every reference
    uses exactly the same spelling and spacing as its destination.
    """
    keyword_rows = [
        row
        for row in master
        if row.get("file") == "/Dat/FixedData/KeyWordData.dat"
    ]
    all_targets = {
        target
        for row in master
        for target in re.findall(r"<([^<>]+)>", row["text"])
    }
    keyword_titles = {row["text"] for row in keyword_rows}
    # Angle brackets are also used by renderer controls such as <C=...>,
    # </C>, <W>, and <X>.  Only labels that actually have a KeyWordData
    # title record are glossary links.
    referenced = all_targets & keyword_titles
    title_rows: dict[str, dict] = {}
    for row in keyword_rows:
        source = row["text"]
        if source not in referenced:
            continue
        if source in title_rows:
            raise ValueError(f"duplicate keyword title: {source!r}")
        title_rows[source] = row

    result = {}
    for source, row in title_rows.items():
        title = normalize_translation(
            translated_text(row, translations, manual_fits)
        )
        title = fit_translation(
            title, row["blen"], mapping, row.get("file", "")
        )
        if "<" in title or ">" in title:
            raise ValueError(f"invalid translated keyword title: {title!r}")
        result[source] = title
    return result


def synchronize_keyword_links(
    source: str, translated: str, keyword_link_map: dict[str, str]
) -> str:
    """Replace translated link labels with the exact destination titles."""
    source_targets = re.findall(r"<([^<>]+)>", source)
    if not source_targets:
        return translated
    translated_targets = re.findall(r"<([^<>]+)>", translated)
    if len(source_targets) != len(translated_targets):
        raise ValueError(
            "keyword link count changed: "
            f"{source_targets!r} -> {translated_targets!r}"
        )
    replacements = iter(
        keyword_link_map.get(target) for target in source_targets
    )

    def replace(match: re.Match[str]) -> str:
        replacement = next(replacements)
        if replacement is None:
            # Renderer control, not a glossary link.
            return match.group(0)
        return f"<{replacement}>"

    return re.sub(r"<[^<>]+>", replace, translated)


def load_roll_caption_rows(path: Path) -> list[dict]:
    """Load only the explicitly translated CSB roll-caption records.

    ``master.jsonl`` intentionally omits these non-dialogue LOGIC resources;
    keep their inclusion narrow so unrelated binary strings remain untouched.
    """
    wanted = set(range(26582, 26602))
    rows = []
    with path.open("rb") as stream:
        for raw in stream:
            try:
                row = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if row.get("uid") in wanted and row.get("psarc") == "LOGIC":
                rows.append(row)
    if {row["uid"] for row in rows} != wanted:
        raise ValueError("opening roll-caption records were not found")
    return rows


# Scene-transition keys used by /Dat/logic/ scripts.  Never translate these.
SCENE_TRANSITION_KEYS = frozenset({"ゲームオーバー", "エンディング", "タイトル"})


def translated_text(
    row: dict,
    translations: dict[int, str],
    manual_fits: dict[tuple[int, str, str], str] | None = None,
) -> str:
    """Return only source-matched overrides; UID collisions are common here."""
    uid = row["uid"]
    manual_key = (uid, row.get("file", ""), row["text"])
    if (
        row.get("text") in SCENE_TRANSITION_KEYS
        and row.get("file", "").startswith("/Dat/logic/")
    ):
        # Scenario scripts use these values as scene-transition keys that the
        # engine matches by string: "ゲームオーバー" (defeat), "エンディング"
        # (ending), "タイトル" (title).  Translating one makes the game hang at
        # that transition -- the defeat key broke every scenario (fixed by 68),
        # and the ending key froze the staff roll (2026-09-06, scr00047).
        # User-facing labels with the same wording in other resources remain
        # eligible for translation.
        text = row["text"]
    elif (
        uid in OBJECTIVE_OVERRIDE_UIDS
        and row.get("text") == OVERRIDE_SOURCE_TEXT.get(uid)
    ):
        # User-reviewed mission objectives take precedence over the older
        # byte-fit review table, which otherwise supplies stale wording.
        text = TRANSLATION_OVERRIDES[uid]
    elif manual_fits is not None and manual_key in manual_fits:
        text = manual_fits[manual_key]
    elif 26582 <= uid <= 26601:
        # These roll captions are unique non-dialogue records loaded outside
        # the regular TSV batches.
        text = TRANSLATION_OVERRIDES[uid]
    elif (
        uid in TRANSLATION_OVERRIDES
        and row.get("text") == OVERRIDE_SOURCE_TEXT.get(uid)
    ):
        text = TRANSLATION_OVERRIDES[uid]
    elif uid in TRANSLATION_OVERRIDES:
        # This is an unrelated record that happens to reuse the UID.  Keeping
        # its original bytes is safer than injecting a short UI label into a
        # weapon name or a long dictionary description.
        text = row["text"]
    else:
        text = translations[uid]
    if uid == 26582:
        # The opening roll centers each physical line.  Long Korean paragraphs
        # otherwise extend beyond both screen edges, so wrap them explicitly.
        paragraphs = text.split("\n\n")
        text = "\n\n".join(
            "\n".join(
                textwrap.wrap(
                    paragraph,
                    # These roll captions use a wide proportional font and
                    # are center-aligned; 32 Korean glyphs still clip beyond
                    # both edges at 1920px.  Twenty fits with visible margins.
                    width=20,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
            for paragraph in paragraphs
        )
    return text


def load_proxy_map(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as stream:
        return {
            row["hangul"]: row["proxy"]
            for row in csv.DictReader(stream, delimiter="\t")
        }


def proxy_encode(text: str, mapping: dict[str, str]) -> bytes:
    encoded_text = "".join(mapping.get(ch, ch) for ch in text)
    missing = {
        ch
        for ch in encoded_text
        if 0xAC00 <= ord(ch) <= 0xD7A3 or 0x3130 <= ord(ch) <= 0x318F
    }
    if missing:
        raise ValueError(f"missing Korean proxies: {sorted(missing)}")
    encoded = encoded_text.encode("utf-8")
    if len(encoded) > len(text.encode("utf-8")):
        raise AssertionError("proxy encoding increased UTF-8 byte length")
    return encoded


def pad_file(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise ValueError(f"{path} is too large: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("poc", "fit", "full", "fullfixed"),
        default="poc",
    )
    parser.add_argument(
        "--require-zlib-fit",
        action="store_true",
        help=(
            "fail if the normal zlib rebuild exceeds the retail PSARC size; "
            "do not retry with Zopfli"
        ),
    )
    parser.add_argument(
        "--include-roll-captions",
        action="store_true",
        help=(
            "translate the two CSB roll-caption resources; disabled by "
            "default because the translated CSBs can hang the ending roll"
        ),
    )
    args = parser.parse_args()

    root = Path("work_ogmd")
    build = root / "korean_build_v3"
    source_psarc = root / "LOGIC.psarc"
    source_sdat = root / "original_backups" / "Logic.psarc.sdat.orig"
    tag = {
        "poc": "dialogue_poc",
        "fit": "fit_all",
        "full": "full_all",
        "fullfixed": "full_fixed",
    }[args.mode]
    out_psarc = build / f"LOGIC_{tag}.psarc"
    out_sdat = build / f"Logic_{tag}.psarc.sdat"

    master = [
        json.loads(line)
        for line in (root / "extract" / "master.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    if args.include_roll_captions:
        master.extend(
            load_roll_caption_rows(root / "extract_all" / "master_all.jsonl")
        )
    translations = load_translations(root / "translated")
    manual_fits = load_manual_fits(root / "review_v1")
    proxy_map = load_proxy_map(build / "korean_font_map.tsv")
    compact_map = build / "compact_aliases.tsv"
    if compact_map.exists():
        proxy_map.update(load_proxy_map(compact_map))
    keyword_link_map = build_keyword_link_map(
        master, translations, manual_fits, proxy_map
    )
    selected = [
        row
        for row in master
        if row["psarc"] == "LOGIC"
        and (
            args.mode in ("fit", "full", "fullfixed")
            or row["uid"] == POC_UID
        )
    ]

    psarc = PSARC(str(source_psarc))
    grouped = defaultdict(list)
    for row in selected:
        grouped[row["entry"]].append(row)

    modified = {}
    applied_by_entry = {}
    applied = 0
    overflow = 0
    source_mismatch = 0
    duplicate = 0
    seen_locations = set()
    for entry, rows in sorted(grouped.items()):
        original_entry = psarc.read_entry(entry)
        patched = bytearray(original_entry)
        changed = False
        for row in sorted(rows, key=lambda item: item["off"]):
            location = (entry, row["off"], row["blen"])
            if location in seen_locations:
                duplicate += 1
                continue
            seen_locations.add(location)
            translated = normalize_translation(
                translated_text(row, translations, manual_fits)
            )
            translated = synchronize_keyword_links(
                row["text"], translated, keyword_link_map
            )
            translated = fit_translation(
                translated, row["blen"], proxy_map, row.get("file", "")
            )
            encoded = (
                translated.encode("utf-8")
                if row["uid"] in RAW_SYSTEM_DIALOG_UIDS
                else proxy_encode(translated, proxy_map)
            )
            if len(encoded) > row["blen"]:
                overflow += 1
                continue
            start = row["off"]
            end = start + row["blen"]
            if original_entry[start:end] != row["text"].encode("utf-8"):
                source_mismatch += 1
                continue
            patched[start:end] = encoded + b"\0" * (row["blen"] - len(encoded))
            applied += 1
            changed = True
        if changed:
            modified[entry] = bytes(patched)
            applied_by_entry[entry] = sum(
                1
                for row in rows
                if (entry, row["off"], row["blen"]) in seen_locations
                and len(
                    proxy_encode(
                        fit_translation(
                            synchronize_keyword_links(
                                row["text"],
                                normalize_translation(
                                    translated_text(
                                        row, translations, manual_fits
                                    )
                                ),
                                keyword_link_map,
                            ),
                            row["blen"],
                            proxy_map,
                            row.get("file", ""),
                        ),
                        proxy_map,
                    )
                )
                <= row["blen"]
                and original_entry[
                    row["off"] : row["off"] + row["blen"]
                ]
                == row["text"].encode("utf-8")
            )

    if args.mode == "poc" and applied != 2:
        raise AssertionError(f"expected 2 PoC occurrences, applied {applied}")

    budget_skipped_entries = 0
    budget_skipped_occurrences = 0
    entry_stats = []
    selected_entries = set(modified)
    if args.mode == "fit":
        entry_stats = []
        for entry, data in modified.items():
            psarc_entry = psarc.entries[entry]
            block_index = psarc_entry["block_idx"]
            block_count = entry_nblocks(psarc, entry)
            original_data = psarc.read_entry(entry)
            delta = 0
            for local_block in range(block_count):
                start = local_block * psarc.block_size
                new_chunk = data[start : start + psarc.block_size]
                old_chunk = original_data[start : start + psarc.block_size]
                if new_chunk == old_chunk:
                    continue
                table_size = psarc.block_table[block_index + local_block]
                old_size = table_size if table_size else psarc.block_size
                _csizes, blobs = compress_blocks(new_chunk, psarc.block_size)
                delta += len(blobs[0]) - old_size
            entry_stats.append(
                {
                    "entry": entry,
                    "delta": delta,
                    "occurrences": applied_by_entry[entry],
                }
            )

        selected_entries = {
            stat["entry"] for stat in entry_stats if stat["delta"] <= 0
        }
        # Keep a small reserve for PSARC boundary/accounting differences that
        # are not represented by the per-entry compressed-byte sum.
        compression_safety_reserve = 1024
        remaining = max(
            0,
            -sum(
                stat["delta"]
                for stat in entry_stats
                if stat["delta"] <= 0
            )
            - compression_safety_reserve,
        )
        positive = sorted(
            (stat for stat in entry_stats if stat["delta"] > 0),
            key=lambda stat: (
                -(stat["occurrences"] / stat["delta"]),
                stat["delta"],
            ),
        )
        deferred = []
        for stat in positive:
            if stat["delta"] <= remaining:
                selected_entries.add(stat["entry"])
                remaining -= stat["delta"]
            else:
                deferred.append(stat)
        # Use any leftover bytes on the smallest deferred entries.
        for stat in sorted(deferred, key=lambda item: item["delta"]):
            if stat["delta"] <= remaining:
                selected_entries.add(stat["entry"])
                remaining -= stat["delta"]

        skipped = [
            stat for stat in entry_stats if stat["entry"] not in selected_entries
        ]
        budget_skipped_entries = len(skipped)
        budget_skipped_occurrences = sum(
            stat["occurrences"] for stat in skipped
        )
        modified = {
            entry: data
            for entry, data in modified.items()
            if entry in selected_entries
        }
        applied -= budget_skipped_occurrences

    if args.mode == "fullfixed" and args.require_zlib_fit:
        compression_deltas = []
        for entry, data in modified.items():
            psarc_entry = psarc.entries[entry]
            block_index = psarc_entry["block_idx"]
            block_count = entry_nblocks(psarc, entry)
            original_data = psarc.read_entry(entry)
            delta = 0
            changed_blocks = 0
            for local_block in range(block_count):
                start = local_block * psarc.block_size
                new_chunk = data[start : start + psarc.block_size]
                old_chunk = original_data[start : start + psarc.block_size]
                if new_chunk == old_chunk:
                    continue
                changed_blocks += 1
                table_size = psarc.block_table[block_index + local_block]
                old_size = table_size if table_size else psarc.block_size
                _csizes, blobs = compress_blocks(new_chunk, psarc.block_size)
                delta += len(blobs[0]) - old_size
            compression_deltas.append(
                {
                    "entry": entry,
                    "delta": delta,
                    "occurrences": applied_by_entry[entry],
                    "changed_blocks": changed_blocks,
                }
            )
        compression_deltas.sort(key=lambda item: item["delta"], reverse=True)
        (root / "review_v1" / "logic_compression_deltas.json").write_text(
            json.dumps(compression_deltas, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    rebuild(str(source_psarc), modified, str(out_psarc))
    compression_backend = "zlib"
    compressed_psarc_size = out_psarc.stat().st_size
    # LOGIC must retain the retail archive's logical size because the outer
    # SDAT and the game's integrity checks are size-sensitive.  Korean proxy
    # text can make a small number of changed zlib blocks slightly larger than
    # their retail counterparts even though every entry keeps its original
    # length and every pointer remains valid.  Retry only those changed blocks
    # with the bundled Zopfli encoder when the fast zlib pass does not fit.
    # Zopfli produces a standard zlib stream; this changes compression only,
    # never strings, entry sizes, block indices, pointers, or unmodified data.
    if (
        args.mode == "fullfixed"
        and compressed_psarc_size > source_psarc.stat().st_size
    ):
        if args.require_zlib_fit:
            excess = compressed_psarc_size - source_psarc.stat().st_size
            raise RuntimeError(
                "normal zlib rebuild exceeds the retail PSARC size by "
                f"{excess} bytes"
            )
        enable_zopfli()
        rebuild(str(source_psarc), modified, str(out_psarc))
        compression_backend = "zopfli"
        compressed_psarc_size = out_psarc.stat().st_size
    if args.mode == "fit" and out_psarc.stat().st_size > source_psarc.stat().st_size:
        removable = sorted(
            (
                stat
                for stat in entry_stats
                if stat["entry"] in selected_entries and stat["delta"] > 0
            ),
            key=lambda stat: (
                stat["occurrences"] / stat["delta"],
                -stat["delta"],
            ),
        )
        removed = []
        excess = out_psarc.stat().st_size - source_psarc.stat().st_size
        reclaimed = 0
        for stat in removable:
            removed.append(stat)
            reclaimed += stat["delta"]
            if reclaimed >= excess + 1024:
                break
        if not removed:
            raise AssertionError("no removable entries for PSARC size overrun")
        for stat in removed:
            modified.pop(stat["entry"], None)
            selected_entries.discard(stat["entry"])
        budget_skipped_entries += len(removed)
        removed_occurrences = sum(stat["occurrences"] for stat in removed)
        budget_skipped_occurrences += removed_occurrences
        applied -= removed_occurrences
        rebuild(str(source_psarc), modified, str(out_psarc))

    if args.mode != "full":
        pad_file(out_psarc, source_psarc.stat().st_size)
    encode(str(out_psarc), source_sdat.read_bytes()[:0x100], str(out_sdat))
    if args.mode != "full":
        pad_file(out_sdat, source_sdat.stat().st_size)

    with out_sdat.open("rb") as stream:
        readback_psarc = PSARC(SDATReader(stream, 0))
        for entry, expected in modified.items():
            if readback_psarc.read_entry(entry) != expected:
                raise AssertionError(f"readback mismatch at entry {entry}")

    report = {
        "mode": args.mode,
        "selected_occurrences": len(selected),
        "modified_entries": len(modified),
        "applied_occurrences": applied,
        "overflow_occurrences": overflow,
        "source_mismatch": source_mismatch,
        "duplicate_locations": duplicate,
        "budget_skipped_entries": budget_skipped_entries,
        "budget_skipped_occurrences": budget_skipped_occurrences,
        "compression_backend": compression_backend,
        "compressed_psarc_size_before_padding": compressed_psarc_size,
        "psarc_size": out_psarc.stat().st_size,
        "sdat_size": out_sdat.stat().st_size,
        "sdat_sha256": hashlib.sha256(out_sdat.read_bytes()).hexdigest(),
    }
    (build / f"logic_{tag}_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
