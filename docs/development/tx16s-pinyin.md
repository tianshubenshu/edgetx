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
The dictionary is deliberately small: 30 exact, toneless syllables using
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

## Built-in font compaction

Before building this branch manually, run:

```sh
python3 tools/compact-cn-fonts.py
```

The custom firmware workflow runs this automatically. It repacks only the
standard-display 24px CN regular and 32px CN bold fonts from 4bpp (16 gray
levels) to 2bpp (4 gray levels), retaining every glyph, advance, bearing,
Unicode map and font size. The 16px candidate/menu font remains unchanged.
Large Chinese text loses some edge smoothing; inspect legibility in the
simulator and on the display before relying on the build.

The checked-in original font arrays remain the reproducible source; the
script overwrites their build-workspace copies before compilation. It uses
the repository's bundled LZ4 code, checks the v2.12.4 descriptor layout,
verifies every transformed pixel and unchanged geometry/map, then verifies
the compressed data round-trip. Repeating it on 2bpp output is a no-op.
There is no new runtime loader or SD font access; fonts remain built into
the firmware and use the existing decompressor, with smaller RAM buffers.
