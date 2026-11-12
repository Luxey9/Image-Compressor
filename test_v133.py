#!/usr/bin/env python3
"""Tes v1.3.3 — zoom/pan preview + layout panel kanan.

Jalankan: .venv/Scripts/python.exe test_v133.py
"""

import os
import shutil
import sys
import tempfile
import tkinter as tk

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import image_compressor as ic  # noqa: E402
import gui_v12  # noqa: E402

FAIL = []


def check(label, cond, extra=""):
    print(f"  {'OK  ' if cond else 'GAGAL'} {label}" + (f"  [{extra}]" if extra else ""))
    if not cond:
        FAIL.append(label)


tmp = tempfile.mkdtemp(prefix="ic133_")
big = os.path.join(tmp, "besar.jpg")
im = Image.new("RGB", (2400, 1600))
px = im.load()
for y in range(0, 1600, 2):
    for x in range(0, 2400, 2):
        px[x, y] = ((x * 3) % 256, (y * 5) % 256, ((x + y) * 2) % 256)
im.save(big, "JPEG", quality=92)

root = tk.Tk()
root.geometry("1300x860")
root.update()
app = ic.App(root)
root.update()
ui = app.ui
cp = ui.compare
cp.update()
root.update()

# ------------------------------------------------------------------ #
print("\n=== 1. Zoom dasar ===")
before_img = Image.new("RGB", (2400, 1600), (10, 10, 10))
after_img = Image.open(big).copy()
cp.set_images(before_img, after_img)
cp.update()
root.update()
check("zoom awal = 1.0", abs(cp._zoom - 1.0) < 1e-9, str(cp._zoom))

cp.zoom_by(1.5)
root.update()
check("zoom 1.5x", abs(cp._zoom - 1.5) < 1e-6, f"{cp._zoom:.3f}")

cp.zoom_by(1 / 1.5)
root.update()
check("kembali ke 1.0", abs(cp._zoom - 1.0) < 1e-6, f"{cp._zoom:.3f}")

# batas
for _ in range(60):
    cp.zoom_by(1.15)
check("batas atas 8.0", abs(cp._zoom - 8.0) < 1e-6, f"{cp._zoom:.3f}")
for _ in range(120):
    cp.zoom_by(1 / 1.15)
check("batas bawah 0.2", abs(cp._zoom - 0.2) < 1e-6, f"{cp._zoom:.3f}")

cp.reset_zoom()
root.update()
check("reset -> 1.0 & pan 0", abs(cp._zoom - 1.0) < 1e-9
      and cp._pan_x == 0 and cp._pan_y == 0, f"{cp._zoom} {cp._pan_x} {cp._pan_y}")

print("\n=== 2. Zoom di titik kursor (anchor) ===")
cp.reset_zoom()
root.update()
# zoom masuk dengan anchor di kiri-atas -> titik itu harus tetap di posisi
ax, ay = 60.0, 60.0
w0 = cp.winfo_width()
cp.set_zoom(2.0, (ax, ay))
root.update()
gx = w0 / 2 + cp._pan_x
check("kursor di kiri -> pan_x bergeser positif (gambar ikut ke kiri)", cp._pan_x > 0,
      f"pan_x={cp._pan_x:.1f}")
check("pan_y bergeser positif", cp._pan_y > 0, f"pan_y={cp._pan_y:.1f}")

print("\n=== 3. Pan & clamp ===")
cp.reset_zoom()
root.update()
mx, my = cp._max_pan()
check("saat fit, batas pan = 0", mx == 0 and my == 0, f"{mx:.1f},{my:.1f}")
cp.zoom_by(3.0)
root.update()
mx, my = cp._max_pan()
check("setelah zoom, batas pan > 0", mx > 0 and my > 0, f"{mx:.1f},{my:.1f}")
cp._pan_x = 99999
cp._pan_y = -99999
cp._clamp_pan()
check("clamp menahan pan di batas", abs(cp._pan_x - mx) < 1e-6 and abs(cp._pan_y + my) < 1e-6,
      f"{cp._pan_x:.1f},{cp._pan_y:.1f}")

print("\n=== 4. Roda mouse ===")


class Ev:
    def __init__(self, x, y, delta, state=0):
        self.x, self.y, self.delta, self.state = x, y, delta, state


cp.reset_zoom()
cp._wheel(Ev(100, 100, 120))
check("roda atas -> zoom masuk", cp._zoom > 1.0, f"{cp._zoom:.3f}")
cp._wheel(Ev(100, 100, -120))
check("roda bawah -> zoom keluar", abs(cp._zoom - 1.0) < 1e-6, f"{cp._zoom:.3f}")

cp.set_zoom(3.0)
root.update()
p0 = cp._pan_x
cp._wheel(Ev(100, 100, 120, state=0x0004))   # Ctrl
check("Ctrl+roda -> pan horizontal", cp._pan_x != p0, f"{p0:.1f} -> {cp._pan_x:.1f}")
p1 = cp._pan_y
cp._wheel(Ev(100, 100, 120, state=0x0001))   # Shift
check("Shift+roda -> pan vertikal", cp._pan_y != p1, f"{p1:.1f} -> {cp._pan_y:.1f}")

print("\n=== 5. Slider pembatas tetap jalan saat zoom ===")
cp.reset_zoom()
root.update()
# atur lewat rasio (koordinat gambar), bukan px kanvas
L0, T0, GW0, GH0 = cp._geom()
cp._set_split(L0 + GW0 * 0.25)
s1 = cp._split
check("split awal = 0.25", abs(s1 - 0.25) < 0.01, f"{s1:.3f}")
cp.zoom_by(2.5)
root.update()
Lz, Tz, GWz, GHz = cp._geom()
check("rasio split TIDAK berubah saat zoom", abs(cp._split - s1) < 1e-9,
      f"{s1:.3f} -> {cp._split:.3f}")
# masih bisa diubah saat zoom, pakai koordinat gambar yang baru
cp._set_split(Lz + GWz * 0.7)
check("split tetap bisa diubah saat zoom", abs(cp._split - 0.7) < 0.01,
      f"{cp._split:.3f}")
crop = cp._crop_before_scaled(0.5, GWz, GHz)
check("crop 'sebelum' dihasilkan saat zoom", crop is not None)
cp.reset_zoom()
root.update()
L2, T2, GW2, GH2 = cp._geom()
crop2 = cp._crop_before_scaled(0.5, GW2, GH2)
check("crop 'sebelum' dihasilkan saat fit", crop2 is not None)

print("\n=== 6. Tombol zoom di canvas ===")
cp.reset_zoom()
root.update()
cp._zoom_click("zin")
check("tombol + -> zoom masuk", cp._zoom > 1.0, f"{cp._zoom:.3f}")
cp._zoom_click("zout")
check("tombol − -> kembali fit", abs(cp._zoom - 1.0) < 1e-6, f"{cp._zoom:.3f}")
cp.zoom_by(2.0)
cp._zoom_click("zfit")
check("tombol Fit -> reset", abs(cp._zoom - 1.0) < 1e-9 and cp._pan_x == 0)

print("\n=== 7. Layout panel kanan (tombol folder tujuan) ===")
side = ui.card_side if hasattr(ui, "card_side") else None
# tombol folder tujuan harus ada, terlihat, dan punya lebar > 0
btn = ui.btn_out
btn.update()
root.update()
check("btn_out ada", btn is not None)
check("btn_out tidak disabled", not btn._disabled,
      f"disabled={btn._disabled}")
check("btn_out terlihat (winfo_ismapped)", bool(btn.winfo_ismapped()))
check("btn_out punya lebar > 0", btn.winfo_width() > 0, f"{btn.winfo_width()}px")

# posisi kanan tombol harus masih di dalam lebar window
rx = btn.winfo_rootx() - root.winfo_rootx() + btn.winfo_width()
check("tombol folder tujuan masih di dalam jendela", rx <= root.winfo_width(),
      f"tepi kanan tombol={rx} vs lebar jendela={root.winfo_width()}")
check("x panel kanan + entry tujuan ada", ui.e_out.winfo_width() > 0,
      f"entry={ui.e_out.winfo_width()}px")

print("\n=== 8. Window sempit (bukan maximize) ===")
root.geometry("1080x780")
root.update()
root.update_idletasks()
rx2 = btn.winfo_rootx() - root.winfo_rootx() + btn.winfo_width()
check("di 1080px, tombol tujuan tetap di dalam jendela", rx2 <= root.winfo_width(),
      f"tepi kanan={rx2} vs lebar={root.winfo_width()}")
check("entry tujuan masih punya lebar", ui.e_out.winfo_width() > 0,
      f"{ui.e_out.winfo_width()}px")
root.geometry("1300x860")
root.update()

print("\n=== 9. Klik tombol tujuan saat mode 'Timpa di tempat' ===")
ic.CONFIG_PATH
core = app
core.var_mode.set("inplace")
ui.on_mode()
root.update()
check("entry tujuan ter-disable saat inplace", str(ui.e_out.cget("state")) == "disabled",
      str(ui.e_out.cget("state")))
check("tombol folder tujuan TETAP aktif", not ui.btn_out._disabled,
      f"disabled={ui.btn_out._disabled}")

# simulasi: pindah mode otomatis (tanpa membuka dialog)
core.var_mode.set("own")
ui.on_mode()
root.update()
check("setelah pindah mode, entry tujuan aktif kembali",
      str(ui.e_out.cget("state")) == "normal", str(ui.e_out.cget("state")))

root.destroy()
shutil.rmtree(tmp, ignore_errors=True)

print("\n" + "=" * 58)
if FAIL:
    print(f"HASIL: {len(FAIL)} GAGAL -> {FAIL}")
    sys.exit(1)
print("HASIL: SEMUA TEST LOLOS")
