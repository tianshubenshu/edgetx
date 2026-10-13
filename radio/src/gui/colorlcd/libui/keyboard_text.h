/*
 * Copyright (C) EdgeTX
 *
 * Based on code named
 *   libopenui - https://github.com/opentx/libopenui
 *
 * License GPLv2: http://www.gnu.org/licenses/gpl-2.0.html
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 */

#pragma once

#include "keyboard_base.h"

#define KEYBOARD_SPACE         "\t"
#define KEYBOARD_ENTER         "\n"
#define KEYBOARD_BACKSPACE     "\200"
#define KEYBOARD_SET_UPPERCASE "\201"
#define KEYBOARD_SET_LOWERCASE "\202"
#define KEYBOARD_SET_LETTERS   "\203"
#define KEYBOARD_SET_NUMBERS   "\204"

#define KEYBOARD_OFFSET_Y 15
#define KEYBOARD_ROW_HEIGHT 40
#define KEYBOARD_CHAR_WIDTH 30
#define KEYBOARD_SPACE_WIDTH 135
#define KEYBOARD_ENTER_WIDTH 80
#define KEYBOARD_BITMAP_WIDTH 45

class TextKeyboard : public Keyboard
{
 public:
  TextKeyboard();
  ~TextKeyboard() override;

#if defined(DEBUG_WINDOWS)
  std::string getName() const override { return "TextKeyboard"; }
#endif

  static void open(FormField* field, uint8_t nameByteLimit = 0);

 protected:
#if defined(HARDWARE_KEYS)
  void changeMode();
  void cursorLeft();
  void cursorRight();
  void cursorStart();
  void cursorEnd();
  void toggleCase();
  void deleteChar();
  void backspace();

  void onPressSYS() override;
  void onLongPressSYS() override;
  void onPressMDL() override;
  void onLongPressMDL() override;
  void onPressTELE() override;
  void onLongPressTELE() override;
  void onPressPGUP() override;
  void onPressPGDN() override;
  void onLongPressPGUP() override;
  void onLongPressPGDN() override;
#endif

  void configurePinyin(uint8_t byteLimit);
  void togglePinyin();
  void refreshCandidates();
  void commitCandidate(unsigned index);
  static void pinyinModeEvent(lv_event_t* event);
  static void pinyinTextEvent(lv_event_t* event);
  static void pinyinCandidateEvent(lv_event_t* event);

  lv_obj_t* pinyinPanel = nullptr;
  lv_obj_t* pinyinInput = nullptr;
  lv_obj_t* modeLabel = nullptr;
  lv_obj_t* pinyinStatus = nullptr;
  lv_obj_t* candidateButtons[5] = {};
  lv_obj_t* candidateLabels[5] = {};
  lv_obj_t* nameTextArea = nullptr;
  char candidates[5][4] = {};
  uint8_t nameByteLimit = 0;
  bool pinyinMode = false;

  static TextKeyboard* _instance;
};
