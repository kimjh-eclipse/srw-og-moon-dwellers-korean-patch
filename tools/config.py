#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""환경별 경로 설정.

스크립트에 박혀 있던 절대 경로를 여기로 모았다. 환경변수로 지정하거나,
값을 직접 고쳐 쓴다.

    set OGMD_ISO=D:\\games\\moon_dwellers.iso
    set OGMD_GAME_DIR=D:\\RPCS3\\dev_hdd0\\game\\BLJS10335\\USRDIR\\PSARC
    set OGMD_WORK=D:\\work_ogmd

경로가 필요한 시점에 없으면 `require()` 가 무엇을 설정해야 하는지 알려주며 멈춘다.
"""
import os

#: 원본 게임 ISO. 추출·분석 스크립트가 사용한다.
ISO = os.environ.get('OGMD_ISO', '')

#: 설치된 게임 데이터 폴더 (``...\BLJS10335\USRDIR\PSARC``).
GAME_DIR = os.environ.get('OGMD_GAME_DIR', '')

#: 추출물·빌드 산출물을 두는 작업 폴더. 기본값은 이 저장소의 상위 폴더.
WORK_ROOT = os.environ.get(
    'OGMD_WORK',
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: 한글 글리프를 그릴 때 쓰는 트루타입 폰트.
KOREAN_FONT = os.environ.get('OGMD_FONT', 'C:/Windows/Fonts/malgun.ttf')
KOREAN_FONT_BOLD = os.environ.get('OGMD_FONT_BOLD', 'C:/Windows/Fonts/malgunbd.ttf')

_ENV_OF = {
    'ISO': 'OGMD_ISO',
    'GAME_DIR': 'OGMD_GAME_DIR',
    'WORK_ROOT': 'OGMD_WORK',
    'KOREAN_FONT': 'OGMD_FONT',
    'KOREAN_FONT_BOLD': 'OGMD_FONT_BOLD',
}


def require(name):
    """설정값을 읽되, 비어 있거나 존재하지 않으면 안내와 함께 중단한다."""
    value = globals().get(name, '')
    env = _ENV_OF.get(name, 'OGMD_' + name)
    if not value:
        raise SystemExit(
            '%s 경로가 설정되지 않았습니다.\n'
            '  환경변수 %s 를 지정하거나 tools/config.py 의 값을 고치세요.' % (name, env))
    if not os.path.exists(value):
        raise SystemExit(
            '%s 경로를 찾을 수 없습니다: %s\n'
            '  환경변수 %s 를 확인하세요.' % (name, value, env))
    return value


def game_file(filename):
    """게임 데이터 폴더 안의 파일 경로."""
    return os.path.join(require('GAME_DIR'), filename)


def work_path(*parts):
    """작업 폴더 기준 경로. 상위 폴더는 필요하면 만든다."""
    path = os.path.join(WORK_ROOT, *parts)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return path
