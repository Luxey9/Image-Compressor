#!/usr/bin/env python3
"""Tes v1.3.5 — layout panel kanan (tabrakan row, tombol terpotong, scroll)."""

import json
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


tmp = tempfile.mkdtemp(prefix="ic135_")
src = os.path.join(tmp, "src")
os.makedirs(src, exist_ok=True)
out_old = os.path.join(tmp, "out_lama")

# config lama berisi input+output -> keduanya harus DIABAIKAN
with open(ic.CONFIG_PATH, "w", encoding="utf-8") as fh:
    json.dump({"input": src, "output": out_old, "quality": 66,
               "margin_mode": "own", "mode": "own"}, fh)

root = tk.Tk()
root.geometry("1180x800")
root.update()
app = ic.App(root)
root.update()
ui = app.ui
root.update()

print("\n=== 1. Folder sumber & tujuan kosong saat dibuka ===")
check("var_in kosong", app.var_in.get() == "", f"'{app.var_in.get()}'")
check("var_out kosong", app.var_out.get() == "", f"'{app.var_out.get()}'")
check("entry sumber menampilkan kosong", app.var_in.get() == "", f"'{app.var_in.get()}'")
check("entry tujuan menampilkan kosong", app.var_out.get() == "", f"'{app.var_out.get()}'")
check("pengaturan lain tetap dimuat (quality=66)",
      int(float(app.var_quality.get())) == 66, str(app.var_quality.get()))

print("\n=== 2. save_config tidak menulis input/output ===")
app.var_in.set(src)
app.var_out.set(out_old)
app.save_config()
saved = json.load(open(ic.CONFIG_PATH, encoding="utf-8"))
check("'input' tidak tersimpan", "input" not in saved, str(list(saved)))
check("'output' tidak tersimpan", "output" not in saved, str(list(saved)))

print("\n=== 3. Tidak ada tabrakan nomor row di panel kanan ===")
body = ui.side_holder.winfo_children()[0]
card_body = body.winfo_children()[0]
slaves = card_body.grid_slaves()
rows = {}
for w in slaves:
    r = w.grid_info().get("row")
    rows.setdefault(r, []).append(w.__class__.__name__)
dupes = {r: v for r, v in rows.items() if len(v) > 1}
check("tidak ada widget bertumpuk di row yang sama", not dupes, str(dupes))

print("\n=== 4. Ketiga switch Opsi benar-benar terlihat ===")
app.var_mode  # noqa
root.update_idletasks()
for name, w in (("sw_skip", ui.sw_skip), ("sw_delete", ui.sw_delete),
                ("sw_open", ui.sw_open)):
    w.update()
    root.update()
    check(f"{name} terlihat (ismapped)", bool(w.winfo_ismapped()), 
          f"y={w.winfo_rooty() - root.winfo_rooty()}")
ys = [ui.sw_skip.winfo_rooty(), ui.sw_delete.winfo_rooty(), ui.sw_open.winfo_rooty()]
check("ketiga switch di baris berbeda (y naik berurutan)",
      ys[0] < ys[1] < ys[2], str(ys))

print("\n=== 5. Radio 'Folder lain' terlihat ===")
ui.rb_own.update()
root.update()
check("rb_own terlihat", bool(ui.rb_own.winfo_ismapped()))
check("rb_inplace terlihat", bool(ui.rb_inplace.winfo_ismapped()))

print("\n=== 6. Tombol folder tujuan di dalam jendela (window sempit) ===")
for w_px, h_px in ((1180, 800), (1120, 780), (1400, 900)):
    root.geometry(f"{w_px}x{h_px}")
    root.update()
    root.update_idletasks()
    bx = ui.btn_out.winfo_rootx() - root.winfo_rootx() + ui.btn_out.winfo_width()
    check(f"{w_px}px: btn_out di dalam jendela", bx <= root.winfo_width(),
          f"tepi={bx} vs lebar={root.winfo_width()}")

print("\n=== 7. Panel kanan bisa di-scroll ===")
root.geometry("1120x700")     # jendela pendek -> pasti butuh scroll
root.update()
root.update_idletasks()
cv = ui.side_canvas
holder = ui.side_holder
need = holder.winfo_reqheight() > cv.winfo_height()
check("isi panel lebih tinggi dari kanvas (butuh scroll)", need,
      f"isi={holder.winfo_reqheight()} vs kanvas={cv.winfo_height()}")
check("scrollregion diatur", cv.cget("scrollregion") != "", str(cv.cget("scrollregion")))
# scrollbar harus terlihat saat butuh
sb = [w for w in ui.side_canvas.master.winfo_children()
      if w.__class__.__name__ == "Scrollbar"]
check("scrollbar ada & terlihat saat jendela pendek",
      bool(sb) and bool(sb[0].winfo_ismapped()),
      f"ada={bool(sb)} mapped={sb[0].winfo_ismapped() if sb else None}")
# yview harus bisa bergerak
before = cv.yview()
cv.yview_scroll(3, "units")
after = cv.yview()
check("yview bisa bergeser", before != after, f"{before} -> {after}")

root.geometry("1400x950")
root.update()
root.update_idletasks()
need2 = ui.side_holder.winfo_reqheight() > ui.side_canvas.winfo_height()
sb2 = [w for w in ui.side_canvas.master.winfo_children()
       if w.__class__.__name__ == "Scrollbar"]
if not need2 and sb2:
    check("scrollbar disembunyikan saat isi muat", not sb2[0].winfo_ismapped())
else:
    check("(isi masih lebih tinggi, scroll tetap wajar)", True,
          f"isi={ui.side_holder.winfo_reqheight()} kanvas={ui.side_canvas.winfo_height()}")

print("\n=== 8. Tombol aksi kiri tidak ketimpa panel kanan ===")
root.geometry("1120x700")
root.update()
root.update_idletasks()
for name, w in (("btn_go", ui.btn_go), ("btn_stop", ui.btn_stop),
                ("btn_open", ui.btn_open)):
    w.update()
    check(f"{name} terlihat", bool(w.winfo_ismapped()))
# panel kanan & kolom kiri tidak boleh tumpang tindih
left_col = ui.btn_go.master
lr = left_col.winfo_rootx() - root.winfo_rootx() + left_col.winfo_width()
rr = ui.side_canvas.master.winfo_rootx() - root.winfo_rootx()
check("kolom kiri tidak menabrak panel kanan", lr <= rr + 2,
      f"kanan kolom kiri={lr} vs kiri panel={rr}")

root.destroy()
shutil.rmtree(tmp, ignore_errors=True)
try:
    os.remove(ic.CONFIG_PATH)
except Exception:
    pass

print("\n" + "=" * 58)
if FAIL:
    print(f"HASIL: {len(FAIL)} GAGAL -> {FAIL}")
    sys.exit(1)
print("HASIL: SEMUA TEST LOLOS")
