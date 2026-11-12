"""Uji GUI v1.2.0 end-to-end lewat mesin asli (tanpa klik tangan).

Skenario:
  1. set folder sumber/tujuan ke folder scratch
  2. Mulai Kompres -> tunggu selesai -> cek jumlah file hasil + log
  3. ubah kualitas -> pratinjau ter-update
  4. Stop saat berjalan -> tidak ada file .~ic-*.tmp tertinggal
"""
import os
import shutil
import sys
import tempfile
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import image_compressor as ic
import ui_kit as ui

from PIL import Image, ImageDraw

ui.set_theme("dark")

# --- siapkan bahan ---
work = tempfile.mkdtemp(prefix="icv12-")
src = os.path.join(work, "in")
dst = os.path.join(work, "out")
os.makedirs(src)
for i in range(6):
    im = Image.new("RGB", (2400, 1600), (20 * i, 60, 200 - 10 * i))
    d = ImageDraw.Draw(im)
    for k in range(0, 2400, 40):
        d.line([(k, 0), (k, 1600)], fill=(255, 200, 30), width=3)
    im.save(os.path.join(src, f"img{i}.jpg"), quality=95)

# copy satu file sebagai contoh pratinjau
sample = os.path.join(work, "sample.jpg")
shutil.copy(os.path.join(src, "img0.jpg"), sample)
print("bahan:", src, "->", dst)

root = tk.Tk()
app = ic.App(root, None)
root.update()
gui = app.ui

def pump(sec):
    t0 = time.time()
    while time.time() - t0 < sec:
        root.update()
        time.sleep(0.02)

results = {}

# --- 1. kompresi penuh ---
app.var_in.set(src)
app.var_out.set(dst)
app.var_mode.set("own")
app.var_quality.set(70)
gui.on_mode()
gui._on_q()
pump(0.2)

gui.start()
t0 = time.time()
while (app.worker and app.worker.is_alive()) and time.time() - t0 < 90:
    pump(0.05)
pump(1.0)  # beri waktu "done" masuk queue

outs = sorted(f for f in os.listdir(dst) if f.lower().endswith(".jpg")) if os.path.isdir(dst) else []
log_text = gui.txt.get("1.0", "end")
results["run"] = {
    "out_files": len(outs),
    "btn_go_disabled": gui.btn_go._disabled,
    "btn_stop_disabled": gui.btn_stop._disabled,
    "progress": gui.lbl_count.cget("text"),
    "log_has_ok": "[OK]" in log_text,
    "log_has_selesai": "Selesai dalam" in log_text,
}
print("RUN:", results["run"])

# --- 2. pratinjau ikut kualitas ---
app.preview_source(sample)
pump(2.5)
before_chip = gui.chip_a._text
app.var_quality.set(40)
gui._on_q()
pump(3.0)
results["preview"] = {
    "q70": before_chip,
    "q40": gui.chip_a._text,
    "changed": before_chip != gui.chip_a._text,
}
print("PREVIEW:", results["preview"])

# --- 3. Stop mid-run ---
out2 = os.path.join(work, "out2")
app.var_out.set(out2)
app.var_quality.set(95)      # lambat -> sempat distop
gui._on_q()
gui.start()
pump(0.35)
gui.stop()
t0 = time.time()
while (app.worker and app.worker.is_alive()) and time.time() - t0 < 60:
    pump(0.05)
pump(0.6)
tmp_left = []
if os.path.isdir(out2):
    tmp_left = [f for f in os.listdir(out2) if f.startswith(".~ic-")]
results["stop"] = {
    "tmp_leftover": tmp_left,
    "btn_stop_disabled": gui.btn_stop._disabled,
}
print("STOP:", results["stop"])

# --- 4. drag & drop handler langsung ---
gui.on_drop([src])
pump(0.4)
results["drop"] = {"in": app.var_in.get().endswith("in"),
                   "status": gui.lbl_status.cget("text")}
print("DROP:", results["drop"])

root.destroy()
shutil.rmtree(work, ignore_errors=True)

ok = (
    results["run"]["out_files"] == 6
    and results["run"]["log_has_ok"]
    and results["run"]["log_has_selesai"]
    and not results["run"]["btn_go_disabled"]
    and results["run"]["btn_stop_disabled"]
    and results["preview"]["changed"]
    and not results["stop"]["tmp_leftover"]
    and results["drop"]["in"]
)
print("\nHASIL:", "LOLOS" if ok else "GAGAL")
sys.exit(0 if ok else 1)
