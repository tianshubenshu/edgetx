#!/usr/bin/env python3
"""Repack TX16S 24/32px CN LZ4 fonts at 2bpp; retain metrics and Unicode maps.

Input layout is EdgeTX v2.12.4, LV_FONT_FMT_TXT_LARGE=0 (8-byte glyph
descriptors, 20-bit bitmap offsets). This is an offline build step.
"""
import argparse
import ctypes
import ctypes.util
import re
import struct
import subprocess
import tempfile
from pathlib import Path

ARRAY = re.compile(r"(static const uint8_t lz4FontData\[\] __FLASH = \{)(.*?)(\};)", re.S)
OFFSET_MASK = (1 << 20) - 1

def field(source, name):
    match = re.search(r"\." + name + r"\s*=\s*(\d+)", source)
    if match is None:
        raise ValueError("Missing font field: " + name)
    return int(match[1])

def replace_field(source, name, value):
    result, count = re.subn(r"(\." + name + r"\s*=\s*)\d+", lambda m: m[1] + str(value), source)
    if count != 1:
        raise ValueError("Ambiguous font field: " + name)
    return result

def load_lz4(root, work, use_system):
    if use_system:
        library = ctypes.util.find_library("lz4")
        if not library:
            raise RuntimeError("System liblz4 unavailable")
    else:
        # Use the repository's compressor, not an unpinned package.
        sources = root / "radio/src/thirdparty/lz4"
        library = str(work / "libfont_lz4.so")
        subprocess.run(["gcc", "-shared", "-fPIC", "-O2",
                        str(sources / "lz4.c"), str(sources / "lz4hc.c"),
                        "-o", library], check=True)
    lib = ctypes.CDLL(library)
    lib.LZ4_decompress_safe.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_int, ctypes.c_int]
    lib.LZ4_decompress_safe.restype = ctypes.c_int
    lib.LZ4_compressBound.argtypes = [ctypes.c_int]
    lib.LZ4_compressBound.restype = ctypes.c_int
    lib.LZ4_compress_HC.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.LZ4_compress_HC.restype = ctypes.c_int
    return lib

def decompress(lib, data, size):
    src = ctypes.create_string_buffer(data)
    out = ctypes.create_string_buffer(size)
    result = lib.LZ4_decompress_safe(src, out, len(data), size)
    if result != size:
        raise ValueError("LZ4 decompression size mismatch")
    return out.raw

def compress(lib, data):
    src = ctypes.create_string_buffer(data)
    capacity = lib.LZ4_compressBound(len(data))
    out = ctypes.create_string_buffer(capacity)
    result = lib.LZ4_compress_HC(src, out, len(data), capacity, 12)
    if result <= 0:
        raise ValueError("LZ4 compression failed")
    packed = out.raw[:result]
    if decompress(lib, packed, len(data)) != data:
        raise ValueError("LZ4 round-trip failed")
    return packed

def convert(lib, path):
    source = path.read_text()
    if field(source, "bpp") == 2:
        print(path.name + ": already compact")
        return
    if field(source, "bpp") != 4 or field(source, "kern_classes") != 0:
        raise ValueError("Unsupported bpp or kerning layout")
    if field(source, "bitmap_format") != 0 or field(source, "cmap_num") != 1:
        raise ValueError("Unsupported bitmap or cmap format")
    match = ARRAY.search(source)
    if not match:
        raise ValueError("Missing compressed byte array")
    packed = bytes(int(n, 16) for n in re.findall(r"0x([0-9a-fA-F]{2})", match[2]))
    if len(packed) != field(source, "comp_size"):
        raise ValueError("Compressed array size mismatch")
    original = decompress(lib, packed, field(source, "uncomp_size"))
    bitmap_start = field(source, "glyph_bitmap")
    # CN fonts have one sparse map starting at glyph 1; glyph 0 is reserved.
    count = field(source, "glyph_id_start") + field(source, "list_length")
    unicode_start = field(source, "unicode_list")
    if unicode_start != count * 8 or bitmap_start != unicode_start + (count - 1) * 2:
        raise ValueError("Unexpected 8-byte descriptor / sparse-map layout")
    metadata = bytearray(original[:bitmap_start])
    bitmap = bytearray()
    expected_offsets = []
    for index in range(count):
        record = index * 8
        packed_descriptor = struct.unpack_from("<I", original, record)[0]
        old_offset = packed_descriptor & OFFSET_MASK
        width, height = original[record + 4:record + 6]
        pixels = width * height
        if bitmap_start + old_offset + (pixels + 1) // 2 > len(original):
            raise ValueError("Glyph bitmap exceeds source")
        new_offset = len(bitmap)
        if new_offset > OFFSET_MASK:
            raise ValueError("Compact bitmap offset exceeds 20 bits")
        expected_offsets.append(new_offset)
        struct.pack_into("<I", metadata, record,
                         (packed_descriptor & ~OFFSET_MASK) | new_offset)
        glyph = bytearray((pixels + 3) // 4)
        for pixel in range(pixels):
            byte = original[bitmap_start + old_offset + pixel // 2]
            level = (byte >> (4 if pixel % 2 == 0 else 0)) & 15
            quantized = (level + 2) // 5
            glyph[pixel // 4] |= quantized << (6 - 2 * (pixel % 4))
        bitmap.extend(glyph)
    converted = bytes(metadata + bitmap)
    # Verify unchanged advances, dimensions, bearings and Unicode map, plus
    # every destination pixel (not just sampled glyphs).
    if converted[count * 8:bitmap_start] != original[count * 8:bitmap_start]:
        raise ValueError("Unicode map changed")
    for index in range(count):
        record = index * 8
        old_word = struct.unpack_from("<I", original, record)[0]
        new_word = struct.unpack_from("<I", converted, record)[0]
        if (old_word & ~OFFSET_MASK) != (new_word & ~OFFSET_MASK):
            raise ValueError("Glyph advance changed")
        if original[record + 4:record + 8] != converted[record + 4:record + 8]:
            raise ValueError("Glyph geometry changed")
        old_offset = old_word & OFFSET_MASK
        new_offset = new_word & OFFSET_MASK
        if new_offset != expected_offsets[index]:
            raise ValueError("Glyph offset changed")
        pixels = original[record + 4] * original[record + 5]
        for pixel in range(pixels):
            value = original[bitmap_start + old_offset + pixel // 2]
            old_level = (value >> (4 if pixel % 2 == 0 else 0)) & 15
            value = converted[bitmap_start + new_offset + pixel // 4]
            new_level = (value >> (6 - 2 * (pixel % 4))) & 3
            if new_level != (old_level + 2) // 5:
                raise ValueError("Glyph pixel mismatch")
    new_packed = compress(lib, converted)
    if len(new_packed) >= len(packed):
        raise ValueError("Compact font is not smaller")
    lines = [",".join("0x%02x" % b for b in new_packed[i:i + 16]) + ","
             for i in range(0, len(new_packed), 16)]
    result = source[:match.start(2)] + "\n" + "\n".join(lines) + "\n" + source[match.end(2):]
    overhead = field(source, "lvglFontBufSize") - len(original)
    for name, value in [("bpp", 2), ("comp_size", len(new_packed)),
                        ("uncomp_size", len(converted)),
                        ("lvglFontBufSize", len(converted) + overhead)]:
        result = replace_field(result, name, value)
    path.write_text(result)
    print("%s: %d glyphs, Flash data %d -> %d bytes; font buffer %d -> %d bytes"
          % (path.name, count - 1, len(packed), len(new_packed),
             len(original) + overhead, len(converted) + overhead))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--system-lz4", action="store_true",
                        help="For local checks only; CI compiles the bundled LZ4")
    args = parser.parse_args()
    root = args.root.resolve()
    config = root / "radio/src/gui/colorlcd/lv_conf.h"
    if config.exists() and not re.search(r"^#define LV_FONT_FMT_TXT_LARGE 0$", config.read_text(), re.M):
        raise ValueError("Only LV_FONT_FMT_TXT_LARGE=0 is supported")
    with tempfile.TemporaryDirectory(prefix="edgetx-font-") as directory:
        lib = load_lz4(root, Path(directory), args.system_lz4)
        fonts = root / "radio/src/fonts/lvgl/std"
        for name in ["lv_font_cn_L.c", "lv_font_cn_bold_XL.c"]:
            convert(lib, fonts / name)

if __name__ == "__main__":
    main()
