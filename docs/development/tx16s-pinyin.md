# TX16S MkII pinyin prototype

Base: official EdgeTX v2.12.4, commit def35ad324896b45d6607d4778536b1bc5360d20.
Development branch: tx16s-pinyin in the personal fork.

## Input

Open the model name editor. The existing keyboard now has an ABC/PY button.
ABC edits the name directly. PY sends letters to a separate composition buffer;
touch a candidate to insert its UTF-8 character at the name cursor.
Switching mode or closing the keyboard discards unselected composition.
Backspace edits the currently active buffer. No second keyboard is opened.

The prototype is enabled in CN builds and only for the model name field.
The model name keeps the upstream 15-byte storage capacity: at most five
three-byte Chinese characters, or a mixture of Chinese and ASCII within 15 bytes.
An insertion that exceeds the byte capacity is rejected.
The dictionary is deliberately small: 35 exact, toneless syllables using
characters already present in the standard CN font. It is not a full pinyin
dictionary and has no phrase prediction or user learning.
For example, enter fei, touch 飞, enter ji, and touch 机.

Dictionary: radio/src/gui/colorlcd/libui/pinyin_dictionary.h.
Before adding candidates, extend and regenerate all required Chinese font sizes
if the existing font subset lacks those characters. The font-generation entry
point is radio/src/fonts/lvgl/make_fonts.sh; its CN subset comes from cn.h via
get_char_ck.py. Runtime keyboard code does not generate fonts.

## Cloud build

.github/workflows/tx16s-pinyin.yml builds only this branch, using
ghcr.io/edgetx/edgetx-dev:2.12 and tools/build-gh.sh with FLAVOR=tx16s and
TRANSLATIONS=CN. The upstream target maps to PCB=X10 and PCBREV=TX16S, including
TX16S MkII. Firmware is uploaded as an Actions artifact. No flashing step exists.

The workflow runs on relevant branch pushes. Manual workflow dispatch requires
GitHub to recognize the workflow from the repository's default branch; push
triggering works without copying this workflow onto main.

## Validation before radio use

A successful cloud build proves compilation, not touchscreen behavior.
In the simulator, check ABC/PY switching, candidate touch selection, cursor
insertion, deleting Chinese characters, the 15-byte boundary, closing/reopening
the keyboard, other text fields, and model-name save/reload.
Keep existing LED changes on their current branch; bring them into this branch
separately after reviewing their commits.

## Aircraft-name glyph extension

The original standard CN fonts contain 622 Han characters and one punctuation
glyph. The build adds 穿, 越, 纸, 三, 四, 五 and 六 at all six existing CN font styles/sizes,
yielding 629 Han characters plus the original punctuation. Original glyph
bitmaps, advances, dimensions, bearings, grayscale and font metrics are verified
unchanged; generated additions use the original bundled Noto faces at 4bpp.
The dictionaries now offer 44 distinct candidates over 35 syllables, including
穿越机, 纸飞机, 固定翼 and 号. Input remains syllable-by-syllable, not phrase prediction.
Examples such as 穿越机1号 fit the unchanged 15-byte model-name capacity.

The custom firmware workflow installs lv_font_conv 1.5.3, invokes
tools/extend-cn-fonts.py before building, then uploads the generated font sources,
font checks and size log alongside the firmware. For a manual build, install
that converter and run the same script before CMake. Existing checked-in font
sources remain untouched; only their build-workspace copies receive appended
glyphs. No runtime font-file loading is added.

## Complete coverage of the available glyph subset

The firmware workflow generates a packed, built-in dictionary from every Han
character in the verified extended standard CN font (629 distinct Han glyphs).
It uses pinned primary readings derived from pypinyin 0.53.0, keeps the hand-selected seed candidates
first, and includes common alternative readings. This is coverage of the
available glyph subset, not a complete general-purpose Chinese dictionary.

Use the < and > buttons to page through five candidates at a time. Editing the
syllable resets to page one. v represents ü. The model-name byte capacity stays
15 bytes. The generated dictionary has no runtime heap allocation or SD access.
For manual builds, run tools/extend-cn-fonts.py, then run tools/generate-pinyin-dictionary.py before invoking CMake.

The CI artifact contains the actual generated header and count report; the
checked-in header is the human-selected seed. A post-build check rejects
firmware leaving less than 24 KiB of the 2 MiB Flash capacity. This is a
development reserve, not proof of flight-control timing or operational safety.
