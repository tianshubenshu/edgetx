/* Copyright (C) EdgeTX. License GPLv2. */
#pragma once

#include <cstring>

// Prototype dictionary: exact, toneless syllables; BMP characters covered by
// the v2.12.4 standard Chinese font. Expand together with the font subset.
inline const char* pinyinCandidates(const char* syllable)
{
  struct Entry { const char* syllable; const char* characters; };
  static const Entry entries[] = {
    {"an", "安按"},
    {"bai", "白"},
    {"ce", "测侧"},
    {"da", "大"},
    {"dian", "电点"},
    {"dong", "动"},
    {"er", "二"},
    {"fei", "飞"},
    {"feng", "风"},
    {"gao", "高"},
    {"hang", "航"},
    {"hong", "红"},
    {"hua", "滑"},
    {"ji", "机级计"},
    {"kong", "空控"},
    {"lan", "蓝"},
    {"lv", "绿"},
    {"mo", "模"},
    {"ping", "平"},
    {"quan", "全"},
    {"sheng", "升"},
    {"su", "速"},
    {"tian", "天"},
    {"xiang", "向"},
    {"xiao", "小"},
    {"xin", "新"},
    {"xing", "型行"},
    {"yi", "一翼"},
    {"zhi", "直"},
    {"zhou", "轴"},
  };
  for (const auto& entry : entries)
    if (strcmp(syllable, entry.syllable) == 0) return entry.characters;
  return "";
}
