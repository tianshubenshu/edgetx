/* Copyright (C) EdgeTX. License GPLv2. */
#pragma once

#include <cstring>

// Prototype dictionary: exact, toneless syllables; BMP characters covered by
// the built-in Chinese font plus the verified pinyin extension.
inline const char* pinyinCandidates(const char* syllable)
{
  struct Entry { const char* syllable; const char* characters; };
  static const Entry entries[] = {
    {"an", "安按"},
    {"bai", "白"},
    {"ce", "测侧"},
    {"chuan", "穿"},
    {"da", "大"},
    {"dian", "电点"},
    {"ding", "定"},
    {"dong", "动"},
    {"er", "二"},
    {"fei", "飞"},
    {"feng", "风"},
    {"gao", "高"},
    {"gu", "固"},
    {"hang", "航"},
    {"hao", "号"},
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
    {"yue", "越"},
    {"zhi", "直纸"},
    {"zhou", "轴"},
  };
  for (const auto& entry : entries)
    if (strcmp(syllable, entry.syllable) == 0) return entry.characters;
  return "";
}
