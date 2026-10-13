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

#include "keyboard_text.h"

#include "textedit.h"
#include "pinyin_dictionary.h"
#include "fonts.h"
#include <cstdio>

constexpr coord_t PINYIN_PANEL_HEIGHT = 70;

constexpr coord_t KEYBOARD_HEIGHT = LCD_H * 2 / 5;
TextKeyboard* TextKeyboard::_instance = nullptr;

TextKeyboard::TextKeyboard() : Keyboard(KEYBOARD_HEIGHT)
{
  pinyinPanel = lv_obj_create(lvobj);
  lv_obj_set_pos(pinyinPanel, 0, 0);
  lv_obj_set_size(pinyinPanel, LCD_W, PINYIN_PANEL_HEIGHT);
  lv_obj_set_style_pad_all(pinyinPanel, 0, 0);
  lv_obj_clear_flag(pinyinPanel, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_add_flag(pinyinPanel, LV_OBJ_FLAG_HIDDEN);

  auto modeButton = lv_btn_create(pinyinPanel);
  lv_obj_set_pos(modeButton, 0, 0);
  lv_obj_set_size(modeButton, 65, 30);
  lv_obj_clear_flag(modeButton, LV_OBJ_FLAG_CLICK_FOCUSABLE);
  lv_group_remove_obj(modeButton);
  modeLabel = lv_label_create(modeButton);
  lv_label_set_text(modeLabel, "ABC");
  lv_obj_center(modeLabel);
  lv_obj_add_event_cb(modeButton, pinyinModeEvent, LV_EVENT_CLICKED, this);

  pinyinInput = lv_textarea_create(pinyinPanel);
  lv_obj_set_pos(pinyinInput, 70, 0);
  lv_obj_set_size(pinyinInput, 140, 30);
  lv_textarea_set_one_line(pinyinInput, true);
  lv_textarea_set_max_length(pinyinInput, 6);
  lv_textarea_set_accepted_chars(pinyinInput,
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ");
  lv_textarea_set_placeholder_text(pinyinInput, "pinyin");
  lv_obj_clear_flag(pinyinInput, LV_OBJ_FLAG_CLICK_FOCUSABLE);
  lv_group_remove_obj(pinyinInput);
  lv_obj_add_event_cb(pinyinInput, pinyinTextEvent, LV_EVENT_VALUE_CHANGED, this);

  pinyinStatus = lv_label_create(pinyinPanel);
  lv_obj_set_pos(pinyinStatus, 215, 5);
  lv_label_set_text(pinyinStatus, "English");

  previousPage = lv_btn_create(pinyinPanel);
  nextPage = lv_btn_create(pinyinPanel);
  for (unsigned i = 0; i < 2; ++i) {
    auto button = i == 0 ? previousPage : nextPage;
    lv_obj_set_pos(button, LCD_W - 92 + i * 46, 0);
    lv_obj_set_size(button, 40, 30);
    lv_obj_clear_flag(button, LV_OBJ_FLAG_CLICK_FOCUSABLE);
    lv_group_remove_obj(button);
    auto label = lv_label_create(button);
    lv_label_set_text(label, i == 0 ? "<" : ">");
    lv_obj_center(label);
    lv_obj_add_event_cb(button, pinyinPageEvent, LV_EVENT_CLICKED, this);
    lv_obj_add_flag(button, LV_OBJ_FLAG_HIDDEN);
  }

  for (unsigned i = 0; i < 5; ++i) {
    candidateButtons[i] = lv_btn_create(pinyinPanel);
    lv_obj_set_pos(candidateButtons[i], i * (LCD_W / 5), 35);
    lv_obj_set_size(candidateButtons[i], LCD_W / 5 - 4, 30);
    lv_obj_clear_flag(candidateButtons[i], LV_OBJ_FLAG_CLICK_FOCUSABLE);
    lv_group_remove_obj(candidateButtons[i]);
    candidateLabels[i] = lv_label_create(candidateButtons[i]);
    lv_label_set_text(candidateLabels[i], "");
    lv_obj_set_style_text_font(candidateLabels[i], getFont(FONT(STD)), 0);
    lv_obj_center(candidateLabels[i]);
    lv_obj_add_event_cb(candidateButtons[i], pinyinCandidateEvent,
                        LV_EVENT_CLICKED, this);
    lv_obj_add_flag(candidateButtons[i], LV_OBJ_FLAG_HIDDEN);
  }
}

void TextKeyboard::configurePinyin(uint8_t byteLimit)
{
  nameByteLimit = byteLimit;
#if !defined(TRANSLATIONS_CN)
  // This prototype uses the existing CN font subset.
  nameByteLimit = 0;
#endif
  pinyinMode = false;
  nameTextArea = field ? field->getLvObj() : nullptr;
  lv_textarea_set_text(pinyinInput, "");
  lv_label_set_text(modeLabel, "ABC");
  lv_label_set_text(pinyinStatus, "English");
  if (nameByteLimit)
    lv_obj_clear_flag(pinyinPanel, LV_OBJ_FLAG_HIDDEN);
  else
    lv_obj_add_flag(pinyinPanel, LV_OBJ_FLAG_HIDDEN);
  refreshCandidates();
}

void TextKeyboard::togglePinyin()
{
  if (!nameTextArea || !nameByteLimit) return;
  pinyinMode = !pinyinMode;
  lv_textarea_set_text(pinyinInput, "");
  lv_label_set_text(modeLabel, pinyinMode ? "PY" : "ABC");
  lv_label_set_text(pinyinStatus, pinyinMode ? "Pinyin" : "English");
  lv_keyboard_set_mode(keyboard, LV_KEYBOARD_MODE_TEXT_LOWER);
  lv_keyboard_set_textarea(keyboard, pinyinMode ? pinyinInput : nameTextArea);
  refreshCandidates();
}

void TextKeyboard::refreshCandidates()
{
  char syllable[7] = {};
  const char* input = lv_textarea_get_text(pinyinInput);
  for (unsigned i = 0; i < 6 && input[i]; ++i)
    syllable[i] = input[i] >= 'A' && input[i] <= 'Z'
                    ? input[i] + ('a' - 'A') : input[i];
  const char* chars = pinyinMode ? pinyinCandidates(syllable) : "";
  candidateCount = strlen(chars) / 3;
  if (candidateOffset >= candidateCount) candidateOffset = 0;
  chars += candidateOffset * 3;
  if (pinyinMode && candidateCount > 5) {
    lv_obj_clear_flag(previousPage, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(nextPage, LV_OBJ_FLAG_HIDDEN);
    if (candidateOffset == 0) lv_obj_add_state(previousPage, LV_STATE_DISABLED);
    else lv_obj_clear_state(previousPage, LV_STATE_DISABLED);
    if (candidateOffset + 5 >= candidateCount) lv_obj_add_state(nextPage, LV_STATE_DISABLED);
    else lv_obj_clear_state(nextPage, LV_STATE_DISABLED);
  } else {
    lv_obj_add_flag(previousPage, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(nextPage, LV_OBJ_FLAG_HIDDEN);
  }
  for (unsigned i = 0; i < 5; ++i) {
    candidates[i][0] = '\0';
    if (*chars) {
      // All prototype dictionary characters are three-byte BMP ideographs.
      memcpy(candidates[i], chars, 3);
      candidates[i][3] = '\0';
      chars += 3;
      lv_label_set_text(candidateLabels[i], candidates[i]);
      lv_obj_clear_flag(candidateButtons[i], LV_OBJ_FLAG_HIDDEN);
    } else {
      lv_obj_add_flag(candidateButtons[i], LV_OBJ_FLAG_HIDDEN);
    }
  }
  if (pinyinMode) {
    if (candidateCount > 5) {
      char status[24];
      snprintf(status, sizeof(status), "Pinyin %u/%u",
               candidateOffset / 5 + 1, (candidateCount + 4) / 5);
      lv_label_set_text(pinyinStatus, status);
    } else {
      lv_label_set_text(pinyinStatus,
        *lv_textarea_get_text(pinyinInput) && !candidates[0][0]
          ? "No match" : "Pinyin");
    }
  }
}

void TextKeyboard::commitCandidate(unsigned index)
{
  if (!pinyinMode || !nameTextArea || index >= 5 || !candidates[index][0])
    return;
  if (strlen(lv_textarea_get_text(nameTextArea)) + 3 > nameByteLimit) {
    lv_label_set_text(pinyinStatus, "Name full");
    return;
  }
  lv_textarea_add_text(nameTextArea, candidates[index]);
  lv_textarea_set_text(pinyinInput, "");
}

void TextKeyboard::pinyinModeEvent(lv_event_t* event)
{
  static_cast<TextKeyboard*>(lv_event_get_user_data(event))->togglePinyin();
}

void TextKeyboard::pinyinTextEvent(lv_event_t* event)
{
  auto self = static_cast<TextKeyboard*>(lv_event_get_user_data(event));
  self->candidateOffset = 0;
  self->refreshCandidates();
}

void TextKeyboard::pinyinPageEvent(lv_event_t* event)
{
  auto self = static_cast<TextKeyboard*>(lv_event_get_user_data(event));
  if (!self->pinyinMode) return;
  if (lv_event_get_target(event) == self->previousPage && self->candidateOffset >= 5)
    self->candidateOffset -= 5;
  else if (lv_event_get_target(event) == self->nextPage &&
           self->candidateOffset + 5 < self->candidateCount)
    self->candidateOffset += 5;
  self->refreshCandidates();
}

void TextKeyboard::pinyinCandidateEvent(lv_event_t* event)
{
  auto self = static_cast<TextKeyboard*>(lv_event_get_user_data(event));
  for (unsigned i = 0; i < 5; ++i)
    if (lv_event_get_target(event) == self->candidateButtons[i]) {
      self->commitCandidate(i);
      return;
    }
}

TextKeyboard::~TextKeyboard() { _instance = nullptr; }

#if defined(HARDWARE_KEYS)

void TextKeyboard::changeMode()
{
  // Change keyboard mode
  lv_keyboard_mode_t mode = lv_keyboard_get_mode(keyboard);
  mode = (mode + 1) & 3;
  lv_keyboard_set_mode(keyboard, mode);
}

void TextKeyboard::backspace()
{
  lv_keyboard_t* kb = (lv_keyboard_t*)keyboard;
  // Backspace
  lv_textarea_del_char(kb->ta);
}

void TextKeyboard::toggleCase()
{
  lv_keyboard_t* kb = (lv_keyboard_t*)keyboard;
  // Toggle case
  const char* cursor = lv_textarea_get_text(kb->ta);
  int32_t position = lv_textarea_get_cursor_pos(kb->ta);
  while (*cursor && position-- > 0) {
    ++cursor;
    while ((*cursor & 0xC0) == 0x80) ++cursor;
  }
  char c = *cursor;
  if (((c >= 'A') && (c <= 'Z')) || ((c >= 'a') && (c <= 'z'))) {
    c ^= 0x20;
    lv_textarea_del_char_forward(kb->ta);
    lv_textarea_add_char(kb->ta, c);
    lv_textarea_cursor_left(kb->ta);
  }
}

void TextKeyboard::deleteChar()
{
  lv_keyboard_t* kb = (lv_keyboard_t*)keyboard;
  // Delete
  lv_textarea_del_char_forward(kb->ta);
}

void TextKeyboard::cursorLeft()
{
  lv_keyboard_t* kb = (lv_keyboard_t*)keyboard;
  // Cursor left
  lv_textarea_cursor_left(kb->ta);
}

void TextKeyboard::cursorRight()
{
  lv_keyboard_t* kb = (lv_keyboard_t*)keyboard;
  // Cursor right
  lv_textarea_cursor_right(kb->ta);
}

void TextKeyboard::cursorStart()
{
  lv_keyboard_t* kb = (lv_keyboard_t*)keyboard;
  // Cursor to start
  while (lv_textarea_get_cursor_pos(kb->ta) > 0)
    lv_textarea_cursor_left(kb->ta);
}

void TextKeyboard::cursorEnd()
{
  lv_keyboard_t* kb = (lv_keyboard_t*)keyboard;
  // Cursor to end
  lv_textarea_set_cursor_pos(kb->ta, LV_TEXTAREA_CURSOR_LAST);
}

#if (defined(KEYS_GPIO_REG_PAGEUP) || defined(USE_HATS_AS_KEYS)) && \
    !defined(PCBX12S)
// Radios with both PGUP and PGDN buttons except X12S
void TextKeyboard::onPressSYS() { changeMode(); }
void TextKeyboard::onLongPressSYS() {}
void TextKeyboard::onPressMDL() {}
void TextKeyboard::onLongPressMDL() { backspace(); }
void TextKeyboard::onPressTELE() { toggleCase(); }
void TextKeyboard::onLongPressTELE() { deleteChar(); }
void TextKeyboard::onPressPGUP() { cursorLeft(); }
void TextKeyboard::onPressPGDN() { cursorRight(); }
void TextKeyboard::onLongPressPGUP() { cursorStart(); }
void TextKeyboard::onLongPressPGDN() { cursorEnd(); }
#else
// Radios witb only a single PGUP/DN button or X12S
void TextKeyboard::onPressSYS() { cursorLeft(); }
void TextKeyboard::onLongPressSYS() { cursorStart(); }
void TextKeyboard::onPressMDL() { changeMode(); }
void TextKeyboard::onLongPressMDL() { backspace(); }
void TextKeyboard::onPressTELE() { cursorRight(); }
void TextKeyboard::onLongPressTELE() { cursorEnd(); }
#if defined(PCBX12S)
void TextKeyboard::onPressPGUP() { toggleCase(); }
#else
void TextKeyboard::onPressPGUP() { deleteChar(); }
#endif
void TextKeyboard::onPressPGDN() { toggleCase(); }
void TextKeyboard::onLongPressPGUP() {}
void TextKeyboard::onLongPressPGDN() { deleteChar(); }
#endif
#endif

void TextKeyboard::open(FormField* field, uint8_t nameByteLimit)
{
  if (!_instance) _instance = new TextKeyboard();

  lv_obj_clear_flag(_instance->lvobj, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(_instance->keyboard, LV_OBJ_FLAG_HIDDEN);
  lv_keyboard_set_mode(_instance->keyboard, LV_KEYBOARD_MODE_TEXT_LOWER);

#if !defined(TRANSLATIONS_CN)
  nameByteLimit = 0;
#endif
  const coord_t extraHeight = nameByteLimit ? PINYIN_PANEL_HEIGHT : 0;
  _instance->setHeight(KEYBOARD_HEIGHT + extraHeight);
  lv_obj_set_pos(_instance->keyboard, 0, extraHeight);
  lv_obj_set_size(_instance->keyboard, LCD_W, KEYBOARD_HEIGHT);
  _instance->setField(field);
  _instance->configurePinyin(nameByteLimit);
}
