"""Uji tombol Stop: proses harus berhenti, tidak ada file setengah jadi / temp sisa."""
import os
import sys
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import image_compressor as ic  # noqa: E402


def main():
    src = os.path.abspath(sys.argv[1])
    out = os.path.abspath(sys.argv[2])
    cfg_backup = None
    if os.path.exists(ic.CONFIG_PATH):
        with open(ic.CONFIG_PATH, "r", encoding="utf-8") as fh:
            cfg_backup = fh.read()

    root = tk.Tk()
    app = ic.App(root, None)
    app.var_in.set(src)
    app.var_out.set(out)
    app.var_mode.set("own")
    app.var_open_after.set(False)
    app.sync_mode()
    app.var_jobs.set(2)          # pelan sengaja, biar sempat di-Stop
    app.var_quality.set(95)
    root.update()

    app.start()
    t0 = time.time()
    while time.time() - t0 < 20:   # biarkan beberapa file selesai dulu
        root.update()
        time.sleep(0.02)
        if app.var_count.get() not in ("0 / 0", ""):
            done = app.var_count.get().split("/")[0].strip()
            if done.isdigit() and int(done) >= 2:
                break

    app.stop()
    t0 = time.time()
    while time.time() - t0 < 120:
        root.update()
        time.sleep(0.02)
        if not (app.worker and app.worker.is_alive()):
            break
    for _ in range(40):
        root.update()
        time.sleep(0.02)

    print(f"STATUS      : {app.var_status.get()}")
    print(f"JUMLAH      : {app.var_count.get()}")
    log = app.txt.get("1.0", "end")
    print(f"LOG dibatalkan : {'ya' if 'Dibatalkan' in log else 'TIDAK'}")
    made = sorted(os.listdir(out)) if os.path.isdir(out) else []
    tmps = [f for f in made if f.startswith(".~ic-")]
    print(f"OUTPUT      : {len(made)} file, sisa temp: {tmps or 'tidak ada'}")
    root.destroy()
    if os.path.exists(ic.CONFIG_PATH):
        os.remove(ic.CONFIG_PATH)
    if cfg_backup is not None:
        with open(ic.CONFIG_PATH, "w", encoding="utf-8") as fh:
            fh.write(cfg_backup)
    ok = ("Dibatalkan" in log) and not tmps
    print("HASIL UJI   :", "LOLOS" if ok else "GAGAL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
