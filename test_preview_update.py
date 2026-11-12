"""Buktikan pratinjau ikut berubah saat lebar/kualitas/format diubah."""
import os
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
        time.sleep(0.03)


def settle(root, app, timeout=30):
    """Tunggu sampai pratinjau benar-benar dihitung ulang (bukan sekadar 'tidak sibuk')."""
    t0 = time.time()
    saw_busy = False
    while time.time() - t0 < timeout:
        root.update()
        time.sleep(0.03)
        if app.prev_busy or "Menghitung" in app.var_prev_info.get():
            saw_busy = True
        if saw_busy and not app.prev_busy and "Menghitung" not in app.var_prev_info.get():
            return True
        if not saw_busy and time.time() - t0 > 3.0:
            return False  # tidak pernah dijadwalkan
    return False


def main():
    src = os.path.abspath(sys.argv[1])
    cfg_backup = None
    if os.path.exists(ic.CONFIG_PATH):
        with open(ic.CONFIG_PATH, "r", encoding="utf-8") as fh:
            cfg_backup = fh.read()

    root = tk.Tk()
    app = ic.App(root, None)
    app.var_in.set(src)
    app.var_width.set(1920)
    app.var_quality.set(85)
    biggest = max(ic.iter_sources(src, True), key=os.path.getsize)
    app.preview_source(biggest)
    settle(root, app)
    print(f"q85  w1920 JPEG : {app.ui.chip_a._text}")

    cases = [
        ("kualitas 45", lambda: app.var_quality.set(45)),
        ("kualitas 95", lambda: app.var_quality.set(95)),
        ("lebar 800", lambda: app.var_width.set(800)),
        ("format WEBP", lambda: app.var_fmt.set(ic.FMT_LABEL["WEBP"])),
        ("format PNG", lambda: app.var_fmt.set(ic.FMT_LABEL["PNG"])),
    ]
    seen = [app.ui.chip_a._text]
    for label, act in cases:
        act()
        time.sleep(0.1)
        ok = settle(root, app)
        line = app.ui.chip_a._text
        changed = line != seen[-1]
        print(f"{label:<15}: {line}   [{'BERUBAH' if changed else 'TIDAK BERUBAH'}]"
              f"{'' if ok else '  (timeout!)'}")
        seen.append(line)

    root.destroy()
    if os.path.exists(ic.CONFIG_PATH):
        os.remove(ic.CONFIG_PATH)
    if cfg_backup is not None:
        with open(ic.CONFIG_PATH, "w", encoding="utf-8") as fh:
            fh.write(cfg_backup)

    uniq = len(set(seen))
    print(f"KESIMPULAN      : {uniq} hasil berbeda dari {len(seen)} pengaturan — "
          f"{'LOLOS' if uniq >= 5 else 'GAGAL'}")
    return 0 if uniq >= 5 else 1


if __name__ == "__main__":
    sys.exit(main())
