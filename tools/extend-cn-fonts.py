#!/usr/bin/env python3
"""Append requested Chinese glyphs to the built-in TX16S fonts offline.
Retain every original glyph bitmap and its metrics at every existing size.
Input layout: EdgeTX v2.12.4, LV_FONT_FMT_TXT_LARGE=0.
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


def array_body(source, name):
    match = re.search(r"\b" + re.escape(name) + r"\[\]\s*=\s*\{(.*?)\};", source, re.S)
    if not match:
        raise ValueError("Missing array: " + name)
    return match

def numbers(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return [int(v, 0) for v in re.findall(r"0x[0-9a-fA-F]+|\b\d+\b", text)]

def c_mapping(source):
    mapping = {}
    for entry in re.findall(r"\{([^{}]*)\}", array_body(source, "cmaps")[1]):
        values = dict(re.findall(r"\.(\w+)\s*=\s*([^,}\n]+)", entry))
        start, length, first = [int(values[k].strip(), 0)
                                for k in ("range_start", "range_length", "glyph_id_start")]
        kind = values["type"].strip()
        if kind.endswith("SPARSE_TINY"):
            offsets = numbers(array_body(source, values["unicode_list"].strip())[1])
            for i, offset in enumerate(offsets):
                mapping[start + offset] = first + i
        elif kind.endswith("FORMAT0_TINY"):
            for i in range(length):
                mapping[start + i] = first + i
        else:
            raise ValueError("Unsupported generated cmap: " + kind)
    return mapping

def c_glyphs(source):
    bitmap = bytes(numbers(array_body(source, "glyph_bitmap")[1]))
    descriptors = []
    for entry in re.findall(r"\{([^{}]*)\}", array_body(source, "glyph_dsc")[1]):
        values = dict(re.findall(r"\.(\w+)\s*=\s*(-?\d+)", entry))
        descriptors.append(tuple(int(values[k]) for k in
                                 ("bitmap_index", "adv_w", "box_w", "box_h", "ofs_x", "ofs_y")))
    glyphs = {}
    for cp, index in c_mapping(source).items():
        offset, advance, width, height, x, y = descriptors[index]
        size = (width * height + 1) // 2
        if offset + size > len(bitmap):
            raise ValueError("C glyph exceeds bitmap")
        glyphs[cp] = (advance, width, height, x, y, bitmap[offset:offset + size])
    return glyphs

def compressed_glyphs(lib, source):
    for key, expected in [("bpp", 4), ("kern_classes", 0),
                          ("bitmap_format", 0), ("cmap_num", 1),
                          ("glyph_id_start", 1), ("type", 3)]:
        if field(source, key) != expected:
            raise ValueError("Unsupported compressed font layout: " + key)
    match = ARRAY.search(source)
    packed = bytes(int(v, 16) for v in re.findall(r"0x([0-9a-fA-F]{2})", match[2]))
    if len(packed) != field(source, "comp_size"):
        raise ValueError("Compressed byte count mismatch")
    raw = decompress(lib, packed, field(source, "uncomp_size"))
    count = field(source, "list_length")
    unicode_start = field(source, "unicode_list")
    bitmap_start = field(source, "glyph_bitmap")
    if unicode_start != (count + 1) * 8 or bitmap_start != unicode_start + count * 2:
        raise ValueError("Unsupported descriptor/cmap layout")
    base = field(source, "range_start")
    glyphs = {}
    for i in range(count):
        cp = base + struct.unpack_from("<H", raw, unicode_start + i * 2)[0]
        word, width, height, x, y = struct.unpack_from("<IBBbb", raw, (i + 1) * 8)
        offset, advance = word & OFFSET_MASK, word >> 20
        size = (width * height + 1) // 2
        if bitmap_start + offset + size > len(raw):
            raise ValueError("Compressed glyph exceeds bitmap")
        glyphs[cp] = (advance, width, height, x, y,
                      raw[bitmap_start + offset:bitmap_start + offset + size])
    return glyphs, raw

def hex_lines(values, width=16):
    return "\n".join("    " + ", ".join("0x%02x" % n for n in values[i:i + width]) + ","
                     for i in range(0, len(values), width))

def replace_array(source, name, body):
    match = array_body(source, name)
    return source[:match.start(1)] + "\n" + body + "\n" + source[match.end(1):]

def pack_glyphs(glyphs):
    bitmap = bytearray()
    descriptors = [(0, 0, 0, 0, 0, 0)]
    for cp in sorted(glyphs):
        advance, width, height, x, y, pixels = glyphs[cp]
        offset = len(bitmap)
        if offset > OFFSET_MASK or advance >= 4096:
            raise ValueError("Glyph descriptor exceeds supported bit fields")
        descriptors.append((offset, advance, width, height, x, y))
        bitmap.extend(pixels)
    return descriptors, bytes(bitmap)

def write_c_font(source, glyphs):
    descriptors, bitmap = pack_glyphs(glyphs)
    keys = ("bitmap_index", "adv_w", "box_w", "box_h", "ofs_x", "ofs_y")
    records = ["    {" + ", ".join(".%s = %d" % p for p in zip(keys, record)) + "},"
               for record in descriptors]
    source = replace_array(source, "glyph_bitmap", hex_lines(list(bitmap)))
    source = replace_array(source, "glyph_dsc", "\n".join(records))
    codes = sorted(glyphs)
    source = replace_array(source, "unicode_list_0", hex_lines([cp - codes[0] for cp in codes], 8))
    for key, value in [("range_start", codes[0]), ("range_length", codes[-1] - codes[0] + 1),
                       ("list_length", len(codes))]:
        source = replace_field(source, key, value)
    return source

def write_compressed_font(lib, source, glyphs, original_raw):
    descriptors, bitmap = pack_glyphs(glyphs)
    codes = sorted(glyphs)
    descriptor_data = b"".join(struct.pack("<IBBbb", offset | (advance << 20), w, h, x, y)
                               for offset, advance, w, h, x, y in descriptors)
    unicode_data = b"".join(struct.pack("<H", cp - codes[0]) for cp in codes)
    raw = descriptor_data + unicode_data + bitmap
    packed = compress(lib, raw)
    match = ARRAY.search(source)
    source = source[:match.start(2)] + "\n" + hex_lines(list(packed)) + "\n" + source[match.end(2):]
    overhead = field(source, "lvglFontBufSize") - len(original_raw)
    for key, value in [("comp_size", len(packed)), ("uncomp_size", len(raw)),
                       ("unicode_list", len(descriptor_data)),
                       ("glyph_bitmap", len(descriptor_data) + len(unicode_data)),
                       ("lvglFontBufSize", len(raw) + overhead),
                       ("range_start", codes[0]),
                       ("range_length", codes[-1] - codes[0] + 1),
                       ("list_length", len(codes))]:
        source = replace_field(source, key, value)
    return source

def extend(lib, converter, root, work, filename, size, bold, wanted):
    path = root / "radio/src/fonts/lvgl/std" / filename
    source = path.read_text()
    compressed = ARRAY.search(source) is not None
    if compressed:
        original, original_raw = compressed_glyphs(lib, source)
    else:
        original = c_glyphs(source)
        original_raw = None
    missing = sorted(wanted - original.keys())
    if not missing:
        print(filename + ": all requested characters already present")
        return
    generated = work / "extra.c"
    face = root / "radio/src/fonts/Noto" / ("NotoSansCJKsc-Bold.otf" if bold else "NotoSansCJKsc-Regular.otf")
    subprocess.run([converter, "--no-prefilter", "--bpp", "4", "--size", str(size),
                    "--no-compress", "--format", "lvgl", "--force-fast-kern-format",
                    "--font", str(face), "-r", ",".join(hex(cp) for cp in missing),
                    "--lv-font-name", "pinyin_extra", "-o", str(generated)], check=True)
    extra = c_glyphs(generated.read_text())
    if set(extra) != set(missing):
        raise ValueError("Generated font omitted a requested character")
    merged = dict(original)
    merged.update(extra)
    if compressed:
        result = write_compressed_font(lib, source, merged, original_raw)
        verified, _ = compressed_glyphs(lib, result)
    else:
        result = write_c_font(source, merged)
        verified = c_glyphs(result)
    # Compare advance, dimensions, bearings and every original bitmap byte,
    # indexed by Unicode (glyph IDs may change when new characters are inserted).
    if verified != merged or any(verified[cp] != glyph for cp, glyph in original.items()):
        raise ValueError("Existing glyph data changed")
    if any(cp not in verified for cp in wanted):
        raise ValueError("Missing required glyph")
    path.write_text(result)
    if compressed:
        print("%s: %d -> %d glyphs; original glyphs unchanged; Flash data %d -> %d bytes; RAM buffer %d -> %d bytes"
              % (filename, len(original), len(verified), field(source, "comp_size"),
                 field(result, "comp_size"), field(source, "lvglFontBufSize"),
                 field(result, "lvglFontBufSize")))
    else:
        print("%s: %d -> %d glyphs; original glyphs unchanged; bitmap %d -> %d bytes"
              % (filename, len(original), len(verified),
                 len(numbers(array_body(source, "glyph_bitmap")[1])),
                 len(numbers(array_body(result, "glyph_bitmap")[1]))))

def main():
    parser = argparse.ArgumentParser(description="Append pinyin glyphs without changing original font rendering")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--font-converter", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    config = (root / "radio/src/gui/colorlcd/lv_conf.h").read_text()
    if not re.search(r"^#define LV_FONT_FMT_TXT_LARGE 0$", config, re.M):
        raise ValueError("Only the v2.12.4 small font descriptor layout is supported")
    wanted = {ord(c) for c in "穿越纸三四五六"}
    with tempfile.TemporaryDirectory(prefix="edgetx-font-") as directory:
        work = Path(directory)
        lib = load_lz4(root, work, False)
        for filename, size, bold in [
                ("lv_font_cn_XXS.c", 9, False),
                ("lv_font_cn_XS.c", 13, False),
                ("lv_font_cn_STD.c", 16, False),
                ("lv_font_cn_bold_STD.c", 16, True),
                ("lv_font_cn_L.c", 24, False),
                ("lv_font_cn_bold_XL.c", 32, True)]:
            extend(lib, args.font_converter, root, work, filename, size, bold, wanted)

if __name__ == "__main__":
    main()
