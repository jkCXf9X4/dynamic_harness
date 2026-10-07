"""Vision asset: a 4-digit code rendered into a PNG, plus its decoder.

The image is drawn with a tiny built-in 5x7 bitmap font (pure Python — no
image libraries): :func:`render_code_image` on the probe side,
:func:`decode_code_image` on the verifier side. Because the verifier
recovers the code by template-matching the digit cells against the same
font, the ground truth lives only in the rendered pixels — there is no
answer literal in the source tree to grep, and the verifier recomputes it
from the workspace image, exactly like the other benchmark tasks recompute
theirs from workspace files.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

#: Number of digits drawn by :func:`render_code_image` (and expected by the decoder).
VISION_DIGITS = 4

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_BG = (16, 16, 16)    # scanline background
_FG = (230, 230, 230)  # digit ink

# 5x7 bitmap font, one string per row ('1' = ink). Deliberately plain glyphs
# (no anti-aliasing, no slash inside '0') so template matching is exact.
_FONT: dict[str, tuple[str, ...]] = {
    "0": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
}


def _geometry(scale: int) -> tuple[int, int, int, int]:
    """(width, height, margin, gap) for a given pixel scale."""
    margin, gap = 2 * scale, scale
    width = 2 * margin + VISION_DIGITS * 5 * scale + (VISION_DIGITS - 1) * gap
    height = 2 * margin + 7 * scale
    return width, height, margin, gap


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data)) + tag + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _encode_png(px: bytearray, width: int, height: int) -> bytes:
    stride = 3 * width
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0 (None) per scanline
        raw += px[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (
        _PNG_SIGNATURE
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw)))
        + _chunk(b"IEND", b"")
    )


def render_code_image(path: Path, code: str, *, scale: int = 8) -> None:
    """Write ``code`` (exactly :data:`VISION_DIGITS` digits, 0-9) as a PNG."""
    if len(code) != VISION_DIGITS or any(ch not in _FONT for ch in code):
        raise ValueError(f"code must be {VISION_DIGITS} digits 0-9, got {code!r}")
    width, height, margin, gap = _geometry(scale)
    px = bytearray(bytes(_BG) * (width * height))
    for i, ch in enumerate(code):
        x0 = margin + i * (5 * scale + gap)
        for r, row in enumerate(_FONT[ch]):
            for c, bit in enumerate(row):
                if bit != "1":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        off = 3 * ((margin + r * scale + dy) * width
                                   + x0 + c * scale + dx)
                        px[off:off + 3] = bytes(_FG)
    path.write_bytes(_encode_png(px, width, height))


def decode_code_image(path: Path, *, scale: int = 8) -> str:
    """Recover the code from a :func:`render_code_image` PNG (verifier side)."""
    width, height, margin, gap = _geometry(scale)
    data = path.read_bytes()
    if not data.startswith(_PNG_SIGNATURE):
        raise ValueError(f"{path} is not a PNG file")

    idat = bytearray()
    pos = 8
    while pos + 8 <= len(data):
        (length,) = struct.unpack_from(">I", data, pos)
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if tag == b"IHDR":
            w, h, depth, ctype = struct.unpack_from(">IIBB", body)
            if (w, h) != (width, height) or depth != 8 or ctype != 2:
                raise ValueError("unexpected PNG geometry (expected 8-bit RGB)")
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
        pos += 12 + length
    if not idat:
        raise ValueError(f"{path} has no image data")

    raw = zlib.decompress(bytes(idat))
    stride = 3 * width
    if len(raw) != height * (stride + 1):
        raise ValueError("unexpected raw scanline size")

    def lit(x: int, y: int) -> bool:
        off = y * (stride + 1) + 1 + 3 * x
        return (raw[off] + raw[off + 1] + raw[off + 2]) / 3 > 127

    out: list[str] = []
    for i in range(VISION_DIGITS):
        x0 = margin + i * (5 * scale + gap)
        glyph = tuple(
            "".join(
                "1" if lit(x0 + c * scale + scale // 2, margin + r * scale + scale // 2) else "0"
                for c in range(5)
            )
            for r in range(7)
        )
        for digit, font in _FONT.items():
            if font == glyph:
                out.append(digit)
                break
        else:
            raise ValueError(f"unrecognized digit glyph at position {i}")
    return "".join(out)
