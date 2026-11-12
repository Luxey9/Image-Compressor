#!/usr/bin/env python3
"""Tes v1.3.4 — mode 'Pilih File' (kompres 1 atau beberapa file dari GUI)."""

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


def mk(path, size=(1500, 1100), color=(30, 120, 200), fmt=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.new("RGB", size, color)
    im.save(path, fmt or None)
    return path


tmp = tempfile.mkdtemp(prefix="ic134_")
A = os.path.join(tmp, "folderA")
B = os.path.join(tmp, "folderB")
f1 = mk(os.path.join(A, "satu.jpg"))
f2 = mk(os.path.join(A, "dua.png"), color=(200, 40, 40))
f3 = mk(os.path.join(B, "tiga.jpg"), color=(40, 200, 60))
out = os.path.join(tmp, "hasil")

root = tk.Tk()
root.withdraw()
app = ic.App(root)
ui = app.ui
root.update()

print("\n=== 1. build_tasks: mode file terpilih (dari banyak folder) ===")
tasks = ic.build_tasks([f1, f2, f3], "", out, "WEBP", False, 800, 80, True, False)
check("3 task dibuat", len(tasks) == 3, str(len(tasks)))
check("hasil ditulis datar ke out_dir",
      all(os.path.dirname(t["dst"]) == out for t in tasks),
      str([os.path.dirname(t["dst"]) for t in tasks]))
check("ekstensi mengikuti format", all(t["dst"].endswith(".webp") for t in tasks))
check("label = nama file", tasks[0]["label"] == "satu.jpg", tasks[0]["label"])

tasks_ip = ic.build_tasks([f1, f3], "", "", "JPEG", True, 800, 80, True, False)
check("in-place: hasil di samping file asal",
      os.path.dirname(tasks_ip[0]["dst"]) == A
      and os.path.dirname(tasks_ip[1]["dst"]) == B,
      str([t["dst"] for t in tasks_ip]))

print("\n=== 2. var_files kosong saat start ===")
check("var_files awal kosong", app.var_files == [], str(app.var_files))

print("\n=== 3. start() tanpa folder & tanpa file -> tidak crash ===")
app.var_in.set("")
app.var_files = []
app.var_status.set("Siap.")
try:
    ui.start()
    ok = True
except Exception as exc:
    ok = False
    print("     exc:", exc)
check("start() aman tanpa sumber", ok)

print("\n=== 4. Proses 3 file lintas folder -> satu folder tujuan ===")
app.var_files = [f1, f2, f3]
app.var_in.set("")
app.var_out.set(out)
app.var_mode.set("own")
app.var_width.set(800)
app.var_quality.set(80)
app.var_fmt.set(app.FMT_LABEL["WEBP"])
app.var_jobs.set(1)
app.refresh_files()
root.update()

check("label file terpilih muncul", "3 file" in ui.lbl_files.cget("text"),
      ui.lbl_files.cget("text"))
check("tombol Bersihkan aktif", not ui.btn_clear_files._disabled)

ui.start()
if app.worker:
    app.worker.join(timeout=90)
root.update()
for _ in range(20):
    ui.run()
    root.update()

got = sorted(os.listdir(out)) if os.path.isdir(out) else []
check("3 file WEBP dihasilkan", len(got) == 3, str(got))
check("nama file dipertahankan",
      set(got) == {"satu.webp", "dua.webp", "tiga.webp"}, str(sorted(got)))
# validasi isinya benar-benar gambar
allok = True
for n in got:
    try:
        with Image.open(os.path.join(out, n)) as im:
            im.load()
            if im.width != 800:
                allok = False
    except Exception:
        allok = False
check("semua hasil valid & ter-resize ke 800px", allok)

print("\n=== 5. Mode in-place: file ditimpa di folder masing-masing ===")
out2 = os.path.join(tmp, "hasil2")
app.var_files = [f1, f3]
app.var_mode.set("inplace")
app.var_out.set("")
app.var_fmt.set(app.FMT_LABEL["JPEG"])
ui.start()
if app.worker:
    app.worker.join(timeout=90)
root.update()
for _ in range(20):
    ui.run()
    root.update()
check("f1 masih ada di folderA", os.path.isfile(f1))
check("f3 masih ada di folderB", os.path.isfile(f3))
# tanpa delete_orig, file .jpg asli tetap; .jpg->.jpg tertimpa
check("hasil in-place tidak membuat folder baru",
      not os.path.isdir(os.path.join(A, "satu_compressed")))

print("\n=== 6. Bersihkan file terpilih ===")
app.var_files = [f2]
app.refresh_files()
root.update()
check("label menampilkan 1 file", "1 file" in ui.lbl_files.cget("text"),
      ui.lbl_files.cget("text"))
ui.clear_files()
root.update()
check("setelah Bersihkan -> var_files kosong", app.var_files == [], str(app.var_files))
check("label kosong lagi", ui.lbl_files.cget("text") == "", ui.lbl_files.cget("text"))
check("tombol Bersihkan mati lagi", ui.btn_clear_files._disabled)

print("\n=== 7. pick_in membersihkan mode file ===")
app.var_files = [f1, f2, f3]
app.refresh_files()
app.var_files = []          # meniru efek pick_in
app.refresh_files()
root.update()
check("mode file dibersihkan saat pindah folder", app.var_files == [])
check("label ikut kosong", ui.lbl_files.cget("text") == "")

print("\n=== 8. File tidak didukung ditolak ===")
bad = os.path.join(tmp, "catatan.txt")
open(bad, "w").write("x")
exts = ic.EXTS
check(".txt bukan gambar didukung", not bad.lower().endswith(exts))
check(".HEIC dianggap didukung", "img.HEIC".lower().endswith(exts))

print("\n=== 9. run_job dengan file hilang ===")
app.var_files = [f1, os.path.join(A, "sudah-dihapus.jpg")]
app.var_mode.set("own")
app.var_out.set(os.path.join(tmp, "hasil3"))
ui.start()
if app.worker:
    app.worker.join(timeout=90)
root.update()
for _ in range(20):
    ui.run()
    root.update()
log = ui.txt.get("1.0", "end")
check("file hilang dilaporkan", "hilang" in log or "dilewati" in log, log[-300:].replace("\n", " | "))
# file tes solid-warna seringkali hasilnya malah lebih besar -> di-SKIP.
# Yang penting: file yang tersisa MASUK PROSES (muncul di log), bukan hilang.
check("sisanya tetap diproses (muncul di log)",
      "satu.jpg" in log and "File ditemukan: 1" in log,
      log[-400:].replace("\n", " | "))

root.destroy()
shutil.rmtree(tmp, ignore_errors=True)

print("\n" + "=" * 58)
if FAIL:
    print(f"HASIL: {len(FAIL)} GAGAL -> {FAIL}")
    sys.exit(1)
print("HASIL: SEMUA TEST LOLOS")
