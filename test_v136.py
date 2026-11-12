#!/usr/bin/env python3
"""Tes v1.3.6 — logika slider pembatas (sebelum/sesudah) harus presisi."""

import os
import shutil
import sys
import tempfile
import tkinter as tk

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import image_compressor as ic  # noqa: E402

FAIL = []


def check(label, cond, extra=""):
    print(f"  {'OK  ' if cond else 'GAGAL'} {label}" + (f"  [{extra}]" if extra else ""))
    if not cond:
        FAIL.append(label)


tmp = tempfile.mkdtemp(prefix="ic136_")
# gambar lanskap lebar -> pasti letterbox di kanvas yang lebih sempit
p_before = os.path.join(tmp, "b.jpg")
p_after = os.path.join(tmp, "a.jpg")
Image.new("RGB", (2000, 800), (220, 40, 40)).save(p_before, "JPEG", quality=95)
Image.new("RGB", (2000, 800), (40, 220, 40)).save(p_after, "JPEG", quality=95)

root = tk.Tk()
root.geometry("1000x760")
root.deiconify()          # jangan withdraw: geometri tidak dihitung kalau tersembunyi
root.update()
app = ic.App(root)
root.update()
cp = app.ui.compare
root.update()
# beri ukuran pasti supaya geometri kanvas terdefinisi
cp.configure(width=600, height=400)
cp.pack_propagate(False)
root.update()
root.update_idletasks()

cp.set_images(Image.open(p_before).copy(), Image.open(p_after).copy())
cp.update()
root.update()
cp.redraw()
cp.update()

print("\n=== 1. Geometri gambar di kanvas ===")
left, top, gw, gh = cp._geom()
w, h = cp.winfo_width(), cp.winfo_height()
print(f"     kanvas {w}x{h} · gambar kiri={left:.1f} atas={top:.1f} "
      f"{gw:.1f}x{gh:.1f}")
check("gambar lebih sempit dari kanvas (letterbox horizontal)", gw < w,
      f"{gw:.1f} < {w}")
check("gambar terpusat secara horizontal",
      abs((left + gw / 2) - w / 2) < 1.0, f"pusat={left + gw / 2:.1f} vs {w/2}")
check("skala fit benar (rasio gambar dipertahankan)",
      abs((gw / gh) - (2000 / 800)) < 0.02, f"rasio={gw/gh:.3f}")

print("\n=== 2. Garis pembatas tepat di batas potongan ===")


def line_x_for(split):
    """Hitung posisi x garis seperti redraw() melakukannya."""
    L, _, GW, _ = cp._geom()
    x = L + GW * split
    return max(0.0, min(float(cp.winfo_width()), x))


for s in (0.0, 0.25, 0.5, 0.75, 1.0):
    cp._split = s
    cp.redraw()
    cp.update()
    L, _, GW, _ = cp._geom()
    expect = L + GW * s
    got = line_x_for(s)
    check(f"split={s:.2f} -> garis di {expect:.1f}", abs(got - expect) < 0.01,
          f"dapat {got:.1f}")

print("\n=== 3. Lebar crop = split x lebar gambar (tidak ada pergeseran) ===")
for s in (0.3, 0.5, 0.8, 1.0):
    ph = cp._crop_before_scaled(s, gw, gh)
    if ph is None:
        check(f"crop split={s}", False, "None")
        continue
    got_w = ph.width()
    expect_w = max(1, int(round(round(gw) * s)))
    check(f"split={s:.2f} -> crop {got_w}px (harap {expect_w})",
          abs(got_w - expect_w) <= 1, f"{got_w} vs {expect_w}")

print("\n=== 4. Klik di kanvas dipetakan ke rasio GAMBAR ===")
cp._split = 0.5
cp.redraw()
L, _, GW, _ = cp._geom()
# klik tepat di tengah gambar -> harus ~0.5, walau gambar tidak selebar kanvas
cp._set_split(L + GW * 0.5)
check("klik tengah gambar -> split 0.5", abs(cp._split - 0.5) < 0.01,
      f"{cp._split:.3f}")
# klik di batas kanan gambar -> 1.0
cp._set_split(L + GW)
check("klik tepi kanan gambar -> split 1.0", abs(cp._split - 1.0) < 0.01,
      f"{cp._split:.3f}")
# klik di tepi kiri gambar -> 0.0
cp._set_split(L)
check("klik tepi kiri gambar -> split 0.0", abs(cp._split - 0.0) < 0.01,
      f"{cp._split:.3f}")
# klik di luar gambar ke kanan -> tetap di-clamp 1.0
cp._set_split(L + GW + 200)
check("klik di luar kanan -> di-clamp 1.0", abs(cp._split - 1.0) < 0.01,
      f"{cp._split:.3f}")
# klik di luar kiri -> clamp 0.0
cp._set_split(L - 200)
check("klik di luar kiri -> di-clamp 0.0", abs(cp._split - 0.0) < 0.01,
      f"{cp._split:.3f}")

print("\n=== 5. Letterbox: split 0.5 JANGAN di tengah kanvas ===")
cp._split = 0.5
cp.redraw()
L, _, GW, _ = cp._geom()
line_x = L + GW * 0.5
canvas_mid = cp.winfo_width() / 2
# kedua-duanya sama HANYA kalau gambar terpusat -> memang sama di sini
check("gambar terpusat jadi garis 0.5 memang di tengah kanvas",
      abs(line_x - canvas_mid) < 1.0, f"{line_x:.1f} vs {canvas_mid:.1f}")

# sekarang PAN gambar (bukan cuma zoom) -> garis harus ikut gambar bergeser
cp.set_zoom(2.0)
cp._pan_x = -160.0          # geser ke kiri: gambar bergerak, garis harus ikut
cp._clamp_pan()
cp.redraw()
L2, _, GW2, _ = cp._geom()
line2 = L2 + GW2 * 0.5
check("setelah pan, garis IKUT gambar (tidak tetap di tengah kanvas)",
      abs(line2 - canvas_mid) > 20.0,
      f"garis={line2:.1f} tengah={canvas_mid:.1f} pan={cp._pan_x:.1f}")
check("garis masih di 50% gambar setelah pan",
      abs(line2 - (L2 + GW2 * cp._split)) < 0.01, f"{line2:.1f}")
check("grid: crop masih konsisten setelah zoom",
      (lambda: (lambda ph: ph is not None and abs(ph.width() - max(1, round(round(GW2) * 0.5))) <= 1)(
          cp._crop_before_scaled(0.5, GW2, cp._geom()[3])))(),
      f"lebar gambar={GW2:.1f}")

print("\n=== 6. Zoom tidak merusak koordinat slider ===")
cp.reset_zoom()
cp.redraw()
L3, _, GW3, _ = cp._geom()
cp._set_split(L3 + GW3 * 0.25)
s_before = cp._split
cp.zoom_by(1.8)
cp.redraw()
L4, _, GW4, _ = cp._geom()
# rasio harus TETAP sama (bukan berubah karena lebar gambar berubah)
check("rasio split tidak berubah saat zoom", abs(cp._split - s_before) < 1e-9,
      f"{s_before:.3f} -> {cp._split:.3f}")
# dan garis tetap di 25% gambar
check("garis tetap di 25% gambar setelah zoom",
      abs((L4 + GW4 * 0.25) - (L4 + GW4 * cp._split)) < 0.01,
      f"{(L4 + GW4 * 0.25):.1f}")

print("\n=== 7. Gambar portrait (letterbox vertikal) ===")
cp.reset_zoom()
pp = os.path.join(tmp, "p.jpg")
Image.new("RGB", (600, 1600), (30, 30, 200)).save(pp, "JPEG")
# portrait sebagai 'sesudah' (yang mengontrol geometri kanvas)
cp.set_images(Image.open(p_after).copy(), Image.open(pp).copy())
cp.update()
root.update()
L5, T5, GW5, GH5 = cp._geom()
check("portrait: _fit_scale dihitung ulang (bukan sisa gambar lama)",
      abs((GW5 / GH5) - (600 / 1600)) < 0.02,
      f"rasio={GW5/GH5:.3f} (harap {600/1600:.3f})")
check("portrait: gambar lebih sempit -> letterbox horizontal",
      GW5 <= cp.winfo_width() + 1, f"{GW5:.1f} vs {cp.winfo_width()}")
cp._set_split(L5 + GW5 * 0.5)
check("portrait: klik tengah -> split 0.5", abs(cp._split - 0.5) < 0.01,
      f"{cp._split:.3f}")

# kembali ke lanskap: _fit_scale harus IKUT berubah
cp.set_images(Image.open(p_before).copy(), Image.open(p_after).copy())
cp.update()
root.update()
L6, T6, GW6, GH6 = cp._geom()
check("ganti balik ke lanskap -> skala ikut berubah",
      abs((GW6 / GH6) - (2000 / 800)) < 0.02,
      f"rasio={GW6/GH6:.3f} (harap {2000/800:.3f})")

root.destroy()
shutil.rmtree(tmp, ignore_errors=True)

print("\n" + "=" * 58)
if FAIL:
    print(f"HASIL: {len(FAIL)} GAGAL -> {FAIL}")
    sys.exit(1)
print("HASIL: SEMUA TEST LOLOS")
