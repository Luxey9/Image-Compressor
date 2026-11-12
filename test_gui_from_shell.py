"""Uji: argumen folder dari console harus membuka GUI (bukan headless)."""
import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import time

MODE = sys.argv[1]              # "exe" atau "src"
TARGET = sys.argv[2]            # exe path atau image_compressor.py
folder = sys.argv[3]

if MODE == "exe":
    cmd = [TARGET, folder]
else:
    cmd = [sys.executable, TARGET, folder]

u = ctypes.windll.user32


def scan_raw():
    found = []
    cb_t = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _l):
        if u.IsWindowVisible(h):
            n = ctypes.create_unicode_buffer(512)
            u.GetWindowTextW(h, n, 512)
            if n.value and "Image Compressor" in n.value:
                r = wt.RECT()
                u.GetWindowRect(h, ctypes.byref(r))
                found.append((n.value, r.right - r.left, r.bottom - r.top))
        return True

    u.EnumWindows(cb_t(cb), None)
    return found


proc = subprocess.Popen(cmd)     # induk = python (dianggap shell)

# tunggu jendela benar-benar selesai di-render (onefile unpack + ttk build)
best_px, best_hits = 0, []
for _ in range(45):
    time.sleep(1)
    hits = scan_raw()
    px = max((w * h for _, w, h in hits), default=0)
    if px > best_px:
        best_px, best_hits = px, hits
    if best_px > 400_000:
        break

for t, w, h in best_hits:
    print(f"  {t!r}  {w}x{h}  -> {'GUI' if w > 900 else 'popup'}")
gui = any(w > 900 for _, w, _ in best_hits)

proc.terminate()
try:
    proc.wait(timeout=15)
except Exception:
    proc.kill()
time.sleep(1)
subprocess.run(["taskkill", "-F", "-IM", "ImageCompressor.exe"], capture_output=True)
print("HASIL:", "LOLOS (GUI terbuka)" if gui else "GAGAL (mode headless)")
sys.exit(0 if gui else 1)
