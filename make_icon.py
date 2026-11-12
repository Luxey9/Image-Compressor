#!/usr/bin/env python3
"""Generate app.ico (multi-resolusi) untuk ImageCompressor.exe."""

import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")
SIZE = 256
BG = (24, 28, 38, 255)
ACCENT = (94, 197, 255, 255)
FG = (245, 248, 252, 255)


def rounded(draw, box, r, fill):
    draw.rounded_rectangle(box, radius=r, fill=fill)


def render() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rounded(d, (8, 8, SIZE - 8, SIZE - 8), 52, BG)

    # dua batang panah turun (simbol kompres) di kiri-atas
    d.rounded_rectangle((70, 54, 100, 60), radius=6, fill=ACCENT)          # baris panjang
    d.rounded_rectangle((70, 82, 88, 88), radius=6, fill=ACCENT)           # baris pendek
    d.rounded_rectangle((70, 110, 104, 116), radius=6, fill=ACCENT)        # baris sedang

    # panah turun besar di kanan
    d.polygon([(150, 46), (206, 46), (206, 96), (232, 96), (178, 150),
               (124, 96), (150, 96)], fill=FG)

    # tray / garis dasar
    rounded(d, (60, 178, 196, 190), 6, FG)
    rounded(d, (104, 204, 152, 214), 5, ACCENT)
    return img


def main():
    img = render()
    sizes = [(s, s) for s in (256, 128, 64, 48, 32, 24, 16)]
    img.save(OUT, format="ICO", sizes=sizes)
    print(f"OK -> {OUT}  ({os.path.getsize(OUT)} bytes, {len(sizes)} resolusi)")


if __name__ == "__main__":
    main()
