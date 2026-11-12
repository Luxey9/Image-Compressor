#!/usr/bin/env python3
"""Tes v1.3.6 — radio 'Folder lain' bertumpuk vertikal & selalu terlihat."""

import os
import shutil
import sys
import tempfile
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import image_compressor as ic  # noqa: E402

FAIL = []


def check(label, cond, extra=""):
    print(f"  {'OK  ' if cond else 'GAGAL'} {label}" + (f"  [{extra}]" if extra else ""))
    if not cond:
        FAIL.append(label)


tmp = tempfile.mkdtemp(prefix="ic136b_")
root = tk.Tk()
root.geometry("1120x760")
root.deiconify()
root.update()
app = ic.App(root)
root.update()
ui = app.ui
root.update()

print("\n=== 1. Kedua radio terlihat ===")
ui.rb_inplace.update()
ui.rb_own.update()
root.update()
check("rb_inplace terlihat", bool(ui.rb_inplace.winfo_ismapped()))
check("rb_own terlihat", bool(ui.rb_own.winfo_ismapped()))

print("\n=== 2. Bertumpuk VERTIKAL (bukan berdampingan) ===")
x_i, y_i = ui.rb_inplace.winfo_rootx(), ui.rb_inplace.winfo_rooty()
x_o, y_o = ui.rb_own.winfo_rootx(), ui.rb_own.winfo_rooty()
check("'Folder lain' DI BAWAH 'Timpa di tempat'", y_o > y_i, f"y {y_i} -> {y_o}")
check("keduanya rata kiri (x hampir sama)", abs(x_i - x_o) <= 4, f"x {x_i} vs {x_o}")
check("jarak vertikal wajar (>10px)", (y_o - y_i) > 10, f"{y_o - y_i}px")

print("\n=== 3. Terlihat juga di jendela sempit ===")
for w_px, h_px in ((1120, 700), (1120, 780), (1400, 900)):
    root.geometry(f"{w_px}x{h_px}")
    root.update()
    root.update_idletasks()
    inside = (ui.rb_own.winfo_rootx() - root.winfo_rootx() + ui.rb_own.winfo_width()
              <= root.winfo_width())
    check(f"{w_px}x{h_px}: rb_own terlihat & di dalam jendela",
          bool(ui.rb_own.winfo_ismapped()) and inside,
          f"ismapped={ui.rb_own.winfo_ismapped()}")

print("\n=== 4. Label lebih jelas ===")
check("teks radio menyebut folder tujuan", "Folder lain" in ui.rb_own._text,
      ui.rb_own._text)
check("teks menyebut 'pilih folder tujuan' untuk kejelasan",
      "folder tujuan" in ui.rb_own._text.lower(), ui.rb_own._text)
check("radio pertama menyebut timpa",
      "timpa" in ui.rb_inplace._text.lower(), ui.rb_inplace._text)

print("\n=== 5. Fungsi radio tetap normal ===")
app.var_mode.set("inplace")
ui.on_mode()
root.update()
check("mode inplace -> entry tujuan disabled",
      str(ui.e_out.cget("state")) == "disabled", str(ui.e_out.cget("state")))
check("tombol folder tujuan tetap aktif", not ui.btn_out._disabled)

app.var_mode.set("own")
ui.on_mode()
root.update()
check("mode own -> entry tujuan aktif",
      str(ui.e_out.cget("state")) == "normal", str(ui.e_out.cget("state")))

print("\n=== 6. Tombol folder tujuan masih di dalam jendela ===")
root.geometry("1120x760")
root.update()
bx = ui.btn_out.winfo_rootx() - root.winfo_rootx() + ui.btn_out.winfo_width()
check("btn_out di dalam jendela", bx <= root.winfo_width(),
      f"tepi={bx} vs lebar={root.winfo_width()}")

print("\n=== 7. Tidak ada tabrakan row ===")
card_body = ui.side_holder.winfo_children()[0].winfo_children()[0]
rows = {}
for w in card_body.grid_slaves():
    r = w.grid_info().get("row")
    rows.setdefault(r, []).append(w.__class__.__name__)
dupes = {r: v for r, v in rows.items() if len(v) > 1}
check("tidak ada widget bertumpuk", not dupes, str(dupes))

root.destroy()
shutil.rmtree(tmp, ignore_errors=True)

print("\n" + "=" * 58)
if FAIL:
    print(f"HASIL: {len(FAIL)} GAGAL -> {FAIL}")
    sys.exit(1)
print("HASIL: SEMUA TEST LOLOS")
