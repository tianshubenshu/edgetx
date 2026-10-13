#!/usr/bin/env python3
"""Generate a built-in pinyin dictionary from every available Han glyph."""
import importlib.util
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("font_extension", ROOT / "tools/extend-cn-fonts.py")
fonts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fonts)
glyphs = fonts.c_glyphs((ROOT / "radio/src/fonts/lvgl/std/lv_font_cn_STD.c").read_text())
characters = {chr(cp) for cp in glyphs if 0x4E00 <= cp <= 0x9FFF}
readings = {}
for line in (ROOT / "tools/pinyin-font-readings.tsv").read_text().splitlines():
    if not line or line.startswith("#"):
        continue
    character, syllable = line.split("\t")
    readings[character] = syllable
if characters - readings.keys():
    raise ValueError("Missing pinned readings for available glyphs")
path = ROOT / "radio/src/gui/colorlcd/libui/pinyin_dictionary.h"
seed = re.findall(r'\{"([a-z]+)", "([^"]+)"\}', path.read_text())
if not seed:
    seed = re.findall(r'"([a-z]+)\\0([^"]+)\\0"', path.read_text())
preferred = "穿越机纸飞机固定翼号航模多旋直升滑翔测试新大小快慢前后上下左右中高低风电动一二三四五六七八九十红蓝绿白黑"
priority = {c: i for i, c in reversed(list(enumerate(preferred)))}
dictionary = defaultdict(list)

def add(syllable, character):
    if character not in characters:
        raise ValueError("Candidate without glyph: " + character)
    if not re.fullmatch("[a-z]{1,6}", syllable):
        raise ValueError("Unsupported pinyin: " + syllable)
    if character not in dictionary[syllable]:
        dictionary[syllable].append(character)

for syllable, candidates in seed:
    for character in candidates:
        add(syllable, character)
for character in sorted(characters, key=lambda c: (priority.get(c, 10000), ord(c))):
    syllable = readings[character]
    add(syllable, character)
for syllable, candidates in {
        "hang": "行", "chong": "重", "zhang": "长", "chang": "长",
        "tiao": "调", "diao": "调", "jiao": "校", "xiao": "校",
        "yue": "乐", "le": "乐", "cha": "差", "chai": "差"}.items():
    for character in candidates:
        if character in characters:
            add(syllable, character)
covered = {c for values in dictionary.values() for c in values}
if covered != characters:
    raise ValueError("Pinyin coverage differs from built-in Han glyph coverage")
source = """/* Copyright (C) EdgeTX. License GPLv2. */
#pragma once
#include <cstring>

// Generated offline. Toneless syllables, v for ü.
// Packed strings avoid a pointer pair for every entry; all data stays in Flash.
// No runtime dictionary allocation or SD access.
inline const char* pinyinCandidates(const char* syllable)
{
  static const char dictionary[] =
"""
for syllable in sorted(dictionary):
    source += '    "%s\\0%s\\0"\n' % (syllable, "".join(dictionary[syllable]))
source += """    ;
  const char* entry = dictionary;
  while (*entry) {
    const char* candidates = entry + strlen(entry) + 1;
    if (strcmp(syllable, entry) == 0) return candidates;
    entry = candidates + strlen(candidates) + 1;
  }
  return "";
}
"""
path.write_text(source)
print("Pinyin dictionary: %d syllables; %d distinct Han candidates; %d pronunciation entries; longest candidate list %d"
      % (len(dictionary), len(covered), sum(len(v) for v in dictionary.values()),
         max(len(v) for v in dictionary.values())))
