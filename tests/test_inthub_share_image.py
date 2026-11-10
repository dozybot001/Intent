"""Product standard 1.9: link previews and home-screen icons show IntHub's own mark, as opaque PNGs."""

from pathlib import Path
import re
import struct
import zlib

STATIC_DIR = Path(__file__).resolve().parents[1] / "apps" / "inthub_web" / "static"


def _png(name):
    """Return (width, height, colour type, rows of RGB tuples) for an 8-bit PNG."""
    data = (STATIC_DIR / name).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", name
    chunks, at = {}, 8
    while at < len(data):
        size, kind = struct.unpack(">I4s", data[at:at + 8])
        chunks[kind] = chunks.get(kind, b"") + data[at + 8:at + 8 + size]
        at += 12 + size
    width, height, depth, colour = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
    assert depth == 8 and colour == 2, f"{name} is an opaque 8-bit RGB PNG"
    raw, stride, rows, prev = zlib.decompress(chunks[b"IDAT"]), width * 3, [], bytearray(width * 3)
    for y in range(height):
        kind, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a, b, c = line[i - 3] if i >= 3 else 0, prev[i], prev[i - 3] if i >= 3 else 0
            p = a + b - c
            pred = (0, a, b, (a + b) // 2, a if abs(p - a) <= min(abs(p - b), abs(p - c)) else b if abs(p - b) <= abs(p - c) else c)[kind]
            line[i] = (line[i] + pred) & 0xFF
        rows.append([tuple(line[i:i + 3]) for i in range(0, stride, 3)])
        prev = line
    return width, height, colour, rows


def test_the_share_image_is_the_mark_centred_so_a_square_crop_keeps_it():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<meta property="og:image" content="https://[^"/]+/og\.png">', html)
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    width, height, _, rows = _png("og.png")
    assert width >= 512 and height >= 512
    side, background = min(width, height), rows[0][0]
    left = (width - side) // 2
    outside = {pixel for row in rows for x, pixel in enumerate(row) if x < left or x >= left + side}
    assert outside == {background}, "nothing outside the central square, so it is not a page screenshot"
    centre = {pixel for row in rows[side // 4:side * 3 // 4] for pixel in row[left + side // 4:left + side * 3 // 4]}
    assert {(0x18, 0x18, 0x18), (0x85, 0x85, 0x85)} <= centre, "the IntHub mark's two folds fill the middle"


def test_the_home_screen_icon_is_an_opaque_180_png():
    width, height, _, _ = _png("apple-touch-icon.png")
    assert (width, height) == (180, 180)
