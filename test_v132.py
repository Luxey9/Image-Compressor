#!/usr/bin/env python3
"""Tes v1.3.2 — folder sumber kosong + drag & drop benar-benar bereaksi.

Jalankan: .venv/Scripts/python.exe test_v132.py
"""

import json
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


def make_images(d, n=3, size=(900, 700)):
    os.makedirs(d, exist_ok=True)
    out = []
    for i in range(n):
        p = os.path.join(d, f"foto{i}.jpg")
        im = Image.new("RGB", size, ((i * 60) % 256, 90, 200))
        im.save(p, "JPEG", quality=95)
        out.append(p)
    return out


# --------------------------------------------------------------------- #
print("\n=== A. Folder sumber kosong saat app dibuka ===")

tmp = tempfile.mkdtemp(prefix="ic132_")
src = os.path.join(tmp, "sumber")
make_images(src, 2)

# tulis config yang MENGHASILKAN folder sumber terisi (perilaku lama)
with open(ic.CONFIG_PATH, "w", encoding="utf-8") as fh:
    json.dump({"input": src, "output": os.path.join(tmp, "out"), "quality": 70}, fh)

root = tk.Tk()
root.withdraw()
app = ic.App(root)
root.update_idletasks()

check("var_in kosong walau config berisi 'input'", app.var_in.get() == "",
      f"nilai='{app.var_in.get()}'")
check("output SENGAJA dikosongkan", app.var_out.get() == "", f"'{app.var_out.get()}'")
check("kualitas tetap dimuat", int(float(app.var_quality.get())) == 70,
      str(app.var_quality.get()))

print("\n=== A2. save_config tidak menulis 'input' ===")
app.var_in.set(src)
app.save_config()
saved = json.load(open(ic.CONFIG_PATH, encoding="utf-8"))
check("'input' tidak ada di config tersimpan", "input" not in saved, str(list(saved)))
check("'output' juga tidak tersimpan", "output" not in saved, str(list(saved)))

print("\n=== A3. preset_dir (argumen CLI) tetap boleh mengisi ===")
root2 = tk.Tk(); root2.withdraw()
app2 = ic.App(root2, preset_dir=src)
root2.update_idletasks()
check("preset_dir mengisi folder sumber", app2.var_in.get() == src, app2.var_in.get())
root2.destroy()

# --------------------------------------------------------------------- #
print("\n=== B. Deskripsi lama sudah hilang ===")
g = open(os.path.join(HERE, "gui_v12.py"), encoding="utf-8").read()
check("'Kompres & resize massal untuk aset web' tidak ada",
      "Kompres & resize massal untuk aset web" not in g)
check("'Kompres & resize massal aset gambar untuk web' tidak ada",
      "Kompres & resize massal aset gambar untuk web" not in g)

# --------------------------------------------------------------------- #
print("\n=== C. Drag & drop benar-benar bereaksi ===")

d1 = os.path.join(tmp, "dropFolder")
imgs = make_images(d1, 4)
img1 = imgs[0]

app.ui.on_drop([d1])
root.update_idletasks()
check("folder drop -> folder sumber terisi", app.var_in.get() == os.path.normpath(d1),
      app.var_in.get())
check("folder drop -> pratinjau dijadwalkan (prev_path terisi)",
      app.prev_path is not None, str(app.prev_path))
check("folder drop -> info pratinjau menyebut file",
      "Contoh:" in app.var_prev_info.get(), app.var_prev_info.get())
st = app.ui.lbl_status.cget("text")
check("folder drop -> status menyebut jumlah gambar siap kompres",
      "4 gambar siap dikompres" in st, st)

# drop dua folder + file gambar sekaligus
d2 = os.path.join(tmp, "dropFolder2")
make_images(d2, 2)
app.ui.on_drop([d2, img1])
root.update_idletasks()
check("multi-drop -> folder pertama dipakai", app.var_in.get() == os.path.normpath(d2),
      app.var_in.get())
st2 = app.ui.lbl_status.cget("text")
check("multi-drop -> status sebut folder + gambar", "1 folder" in st2 and "1 gambar" in st2, st2)

# drop file gambar saja -> folder sumber = folder induknya
app.ui.on_drop([img1])
root.update_idletasks()
check("drop gambar saja -> folder sumber = folder induk",
      app.var_in.get() == os.path.dirname(img1), app.var_in.get())

# drop sesuatu yang bukan gambar
bukan = os.path.join(tmp, "catatan.txt")
open(bukan, "w").write("x")
app.ui.on_drop([bukan])
root.update_idletasks()
st3 = app.ui.lbl_status.cget("text")
check("drop file non-gambar -> dilaporkan 'dilewati'", "dilewati" in st3, st3)

# folder kosong
kosong = os.path.join(tmp, "kosong")
os.makedirs(kosong, exist_ok=True)
app.ui.on_drop([kosong])
root.update_idletasks()
st4 = app.ui.lbl_status.cget("text")
check("drop folder kosong -> diberi tahu belum ada gambar",
      "belum ada gambarnya" in st4, st4)

# hook benar-benar terpasang di OS?
import gui_v12  # noqa: E402
check("hook WM_DROPFILES terpasang", gui_v12.drop_installed())
check("self.drop_ok True", getattr(app.ui, "drop_ok", False) is True)

root.destroy()

# --------------------------------------------------------------------- #
print("\n=== D. HEIC benar-benar didukung ===")
check("HEIC_SUPPORT True", ic.HEIC_SUPPORT)
try:
    from pillow_heif import register_heif_opener  # noqa: F401
    from PIL import Image as I
    heic_dir = os.path.join(tmp, "heic")
    os.makedirs(heic_dir, exist_ok=True)
    hp = os.path.join(heic_dir, "foto-iphone.heic")
    I.new("RGB", (1200, 900), (200, 40, 60)).save(hp, format="HEIF", quality=80)
    got = os.path.getsize(hp)
    dst = os.path.join(heic_dir, "hasil.jpg")
    r = ic.compress_one(hp, dst, 800, 80, "JPEG")
    with I.open(dst) as chk:
        chk.load()
        dims = chk.size
    check("file .heic dibuat & terbaca", got > 0 and dims[0] == 800,
          f"{got} B -> {dims}")
    check("file .heic masuk daftar sumber",
          any(p.lower().endswith((".heic", ".heif"))
              for p in ic.iter_sources(heic_dir, False)))
except Exception as exc:
    check("uji HEIC", False, repr(exc))

shutil.rmtree(tmp, ignore_errors=True)
try:
    os.remove(ic.CONFIG_PATH)
except Exception:
    pass

print("\n" + "=" * 56)
if FAIL:
    print(f"HASIL: {len(FAIL)} GAGAL -> {FAIL}")
    sys.exit(1)
print("HASIL: SEMUA TEST LOLOS")
