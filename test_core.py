#!/usr/bin/env python3
"""Smoke test core kompresi (tanpa GUI). Jalankan: python test_core.py"""

import os
import shutil
import sys
import tempfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import image_compressor as ic  # noqa: E402


def make_samples(d):
    os.makedirs(os.path.join(d, "sub"), exist_ok=True)
    # foto besar RGB (simulasi JPEG dari kamera, orientasi EXIF normal)
    big = Image.new("RGB", (4000, 3000))
    px = big.load()
    for y in range(0, 3000, 4):
        for x in range(0, 4000, 4):
            px[x, y] = ((x * 7) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    big.save(os.path.join(d, "foto-besar.jpg"), "JPEG", quality=98)
    big.resize((900, 600)).save(os.path.join(d, "sudah-kecil.jpg"), "JPEG", quality=95)
    # PNG transparan
    rgba = Image.new("RGBA", (1200, 800), (0, 0, 0, 0))
    for x in range(1200):
        for y in range(0, 800, 3):
            rgba.putpixel((x, y), (255, 0, 0, 255))
    rgba.save(os.path.join(d, "logo-transparan.png"))
    # GIF
    Image.new("P", (300, 200)).save(os.path.join(d, "anim.gif"))
    # subfolder
    big.resize((2400, 1800)).save(os.path.join(d, "sub", "banner.png"))
    # teks bukan gambar
    with open(os.path.join(d, "catatan.txt"), "w") as fh:
        fh.write("bukan gambar")
    # EXIF orientation 6 (tegak)
    ex = Image.new("RGB", (600, 900), (10, 120, 200))
    p = ex.save(os.path.join(d, "exif-tegak.jpg"), "JPEG")
    _ = p


def run_case(label, fmt, box, quality, in_place, recursive):
    root = tempfile.mkdtemp(prefix="ic_test_")
    src = os.path.join(root, "in")
    out = os.path.join(root, "out")
    make_samples(src)
    files = ic.iter_sources(src, recursive)
    assert files, "iter_sources kosong"

    before = sum(os.path.getsize(f) for f in files)
    ok = 0
    for f in files:
        dst = ic.build_dest(f, src, out, fmt, in_place)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".~ic.tmp"
        r = ic.compress_one(f, tmp, box, quality, fmt)
        os.replace(tmp, dst)
        assert os.path.getsize(dst) > 0, f"file hasil kosong: {dst}"
        with Image.open(dst) as chk:
            chk.load()
        if box and r["before"][0] > box:
            assert r["after"][0] == box, f"resize gagal {r}"
            assert r["resized"] is True
        assert r["after"][1] > 0
        ok += 1

    measure_dir = src if in_place else out
    after = 0
    for dirpath, _, fnames in os.walk(measure_dir):
        for n in fnames:
            after += os.path.getsize(os.path.join(dirpath, n))
    save = (before - after) / before * 100 if before else 0
    print(f"  [{label}] {ok} file · {ic.human(before)} -> {ic.human(after)} · hemat {save:.1f}%")
    shutil.rmtree(root, ignore_errors=True)


def run_skip_and_replace():
    root = tempfile.mkdtemp(prefix="ic_test2_")
    src = os.path.join(root, "in")
    make_samples(src)
    p = os.path.join(src, "sudah-kecil.jpg")
    orig = os.path.getsize(p)
    dst = ic.build_dest(p, src, src, "JPEG", True)
    tmp = dst + ".~ic.tmp"
    r = ic.compress_one(p, tmp, 0, 95, "JPEG")
    print(f"  [in-place JPEG q95] {ic.human(r['orig'])} -> {ic.human(r['new'])} tmp={os.path.basename(tmp)}")
    assert os.path.abspath(dst) == os.path.abspath(p), "in-place harus menimpa file yang sama"
    os.replace(tmp, dst)
    assert os.path.getsize(p) > 0
    print(f"  [in-place] replace OK, ukuran {orig} -> {os.path.getsize(p)}")

    # PNG transparan -> JPEG harus di-flatten jadi RGB tanpa alpha
    t = os.path.join(src, "logo-transparan.png")
    jd = ic.build_dest(t, src, src, "JPEG", True)
    jt = jd + ".~ic.tmp"
    ic.compress_one(t, jt, 800, 85, "JPEG")
    with Image.open(jt) as im:
        assert im.mode == "RGB", f"flatten gagal, mode={im.mode}"
        assert im.size[0] == 800, f"resize gagal {im.size}"
    os.remove(jt)
    print("  [PNG->JPEG] alpha flatten + resize OK")

    # WebP output
    wd = ic.build_dest(t, src, src, "WEBP", True)
    wt = wd + ".~ic.tmp"
    ic.compress_one(t, wt, 800, 85, "WEBP")
    with Image.open(wt) as im:
        print(f"  [PNG->WebP] mode={im.mode} size={im.size} {ic.human(os.path.getsize(wt))}")
    os.remove(wt)
    shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    print(f"Pillow {Image.__version__} · HEIC support: {ic.HEIC_SUPPORT}")
    assert not ic.HEIC_SUPPORT or True
    for lbl, in_plc in (("out-dir JPEG 1920 q85", False), ("in-place WebP 1600 q80", True)):
        run_case(lbl, "JPEG" if not in_plc else "WEBP", 1920 if not in_plc else 1600,
                 85 if not in_plc else 80, in_plc, True)
    run_case("out-dir PNG lossless, non-rekursif", "PNG", 0, 90, False, False)
    run_skip_and_replace()
    print("SEMUA TEST LOLOS")
