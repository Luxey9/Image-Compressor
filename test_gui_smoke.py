"""Uji asap GUI: pratinjau sebelum-sesudah + kompresi paralel dari dalam App.

Dipompa manual lewat root.update() supaya bisa diverifikasi tanpa klik.
"""
import os
import shutil
import sys
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import image_compressor as ic  # noqa: E402


def pump(root, secs):
    t0 = time.time()
    while time.time() - t0 < secs:
        root.update()
        time.sleep(0.05)


def main():
    src = os.path.abspath(sys.argv[1])
    out = os.path.abspath(sys.argv[2])

    cfg_backup = None
    if os.path.exists(ic.CONFIG_PATH):
        with open(ic.CONFIG_PATH, "r", encoding="utf-8") as fh:
            cfg_backup = fh.read()

    root = tk.Tk()
    app = ic.App(root, src)
    app.var_in.set(src)
    app.var_out.set(out)
    app.var_mode.set("own")
    app.sync_mode()
    app.var_open_after.set(False)
    app.var_recursive.set(True)
    app.var_width.set(1920)
    app.var_quality.set(85)
    pump(root, 1.0)
    print(f"QUALITY     : {app.var_quality.get()}  jobs={app.var_jobs.get()}  "
          f"({app.lbl_jobs.cget('text')})")

    biggest = max(ic.iter_sources(src, True), key=os.path.getsize)
    print(f"CONTOH      : {os.path.basename(biggest)}")
    app.preview_source(biggest)

    t0 = time.time()
    while time.time() - t0 < 30:
        root.update()
        time.sleep(0.05)
        if app.ph_before is not None and app.ph_after is not None:
            break
    print(f"PREV info   : {app.var_prev_info.get()}")
    print(f"PREV sumber : {app.var_prev_b.get()}")
    print(f"PREV hasil  : {app.var_prev_a.get()}")
    print(f"PREV gambar : before={'ada' if app.ph_before else 'TIDAK ADA'} "
          f"after={'ada' if app.ph_after else 'TIDAK ADA'}")
    ok_prev = app.ph_before is not None and app.ph_after is not None

    # geser kualitas -> pratinjau harus dihitung ulang
    app.var_quality.set(45)
    time.sleep(0.2)
    t0 = time.time()
    while time.time() - t0 < 30:
        root.update()
        time.sleep(0.05)
        if "45" not in app.var_prev_a.get() and app.var_prev_a.get() and not app.prev_busy:
            if "Menghitung" not in app.var_prev_info.get():
                break
    print(f"PREV q45    : {app.var_prev_a.get()}")

    app.var_quality.set(85)
    pump(root, 3)

    # jalankan kompresi dari GUI
    app.start()
    t0 = time.time()
    while time.time() - t0 < 300:
        root.update()
        time.sleep(0.05)
        if not (app.worker and app.worker.is_alive()):
            break
    pump(root, 2.0)

    log = app.txt.get("1.0", "end")
    print("-" * 72)
    print(log.strip())
    print("-" * 72)
    print("STATUS      :", app.var_status.get())
    print("Jumlah      :", app.var_count.get())

    made = sorted(os.listdir(out)) if os.path.isdir(out) else []
    tmps = [f for f in made if f.startswith(".~ic-")]
    print(f"OUTPUT      : {len(made)} entri, sisa temp: {tmps or 'tidak ada'}")

    root.destroy()
    if os.path.exists(ic.CONFIG_PATH):
        os.remove(ic.CONFIG_PATH)
    if cfg_backup is not None:
        with open(ic.CONFIG_PATH, "w", encoding="utf-8") as fh:
            fh.write(cfg_backup)

    bad = (not ok_prev) or not made or bool(tmps) or "ERR" in log
    print("HASIL UJI   :", "GAGAL" if bad else "LOLOS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
