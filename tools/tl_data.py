#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""번역 대역표 로더.

빌드 스크립트에 인라인으로 박혀 있던 원문→번역 대역표를 소스에서 분리해
`tools/data/<스크립트이름>.json` 으로 옮겼다. 이 데이터는 게임 원문을 담고 있어
저장소에 포함하지 않는다.

따라서 대역표를 쓰는 스크립트는 이 저장소만 받아서는 그대로 실행되지 않는다.
자기 번역 데이터를 같은 형식으로 만들어 `tools/data/` 에 두면 동작한다.

형식
----
`tools/data/<stem>.json` 은 {테이블이름: 값} 매핑이다.
키 타입(int/tuple 등)을 JSON에서 잃지 않도록 아래 래퍼를 쓴다.

    {"__kind__": "dict",  "pairs": [[key, value], ...]}
    {"__kind__": "tuple", "items": [...]}
    {"__kind__": "set",   "items": [...]}

리스트와 스칼라는 그대로 둔다. `_INLINE` 은 소스에 흩어져 있던 문자열 상수를
등장 순서대로 모은 리스트이며 `load_table("_INLINE")[N]` 으로 참조된다.
"""
import inspect
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

_cache = {}


def _decode(obj):
    if isinstance(obj, dict):
        kind = obj.get('__kind__')
        if kind == 'dict':
            return {_decode(k): _decode(v) for k, v in obj['pairs']}
        if kind == 'tuple':
            return tuple(_decode(v) for v in obj['items'])
        if kind == 'set':
            return {_decode(v) for v in obj['items']}
        return {k: _decode(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decode(v) for v in obj]
    return obj


def _caller_stem():
    """load_table() 을 부른 스크립트의 파일 이름(확장자 제외)."""
    for frame in inspect.stack()[1:]:
        path = frame.filename
        if os.path.abspath(path) != os.path.abspath(__file__):
            return os.path.splitext(os.path.basename(path))[0]
    raise RuntimeError('호출한 스크립트를 알 수 없습니다')


def load_table(name, stem=None):
    """이름으로 대역표를 읽는다. stem 을 주면 그 파일에서 찾는다."""
    stem = stem or _caller_stem()
    if stem not in _cache:
        path = os.path.join(DATA_DIR, stem + '.json')
        if not os.path.exists(path):
            raise FileNotFoundError(
                '번역 대역표가 없습니다: %s\n'
                '\n'
                '이 데이터는 게임 원문을 담고 있어 저장소에 포함되지 않습니다.\n'
                '자기 번역 데이터를 같은 형식으로 만들어 위 경로에 두세요.\n'
                '형식 설명은 tools/tl_data.py 의 독스트링을 참고하세요.' % path)
        with open(path, encoding='utf-8') as fh:
            _cache[stem] = json.load(fh)
    payload = _cache[stem]
    if name not in payload:
        raise KeyError('%s.json 에 테이블 %r 이 없습니다. 있는 것: %s'
                       % (stem, name, ', '.join(sorted(payload))))
    return _decode(payload[name])
