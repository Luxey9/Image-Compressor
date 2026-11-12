"""Launcher native: memanggil exe tanpa shell di rantai proses.

Dipakai untuk meniru drag & drop (Explorer = native, tanpa console).
Dijalankan lewat `start` dari file .lnk-ish? Tidak — kita pakai
script-runner Python yang di-fork oleh rundll32-like host.

Cara: tulis VBScript, jalankan via wscript.exe (native GUI host, tanpa bash).
VBScript tidak muncul di daftar shell => rantai: exe -> wscript.exe -> explorer.exe
yang berarti from_shell = False (benar untuk drag & drop).
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import tempfile
import time

exe = sys.argv[1]
target = sys.argv[2]
u = ctypes.windll.user32

vbs = os.path.join(tempfile.gettempdir(), "ic_launch.vbs")
with open(vbs, "w", encoding="ascii", errors="ignore") as fh:
    fh.write('Set sh = CreateObject("WScript.Shell")\r\n')
    fh.write(f'sh.Run """{exe}"" ""{target}""", 0, False\r\n')

subprocess.run(["wscript.exe", "//nologo", vbs], check=False)


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


best_px, best_hits = 0, []
for _ in range(45):
    time.sleep(1)
    hits = scan_raw()
    px = max((w * h for _, w, h in hits), default=0)
    if px > best_px:
        best_px, best_hits = px, hits
    if any("selesai" in t for t, _, _ in best_hits):
        break

for t, w, h in best_hits:
    print(f"  {t!r}  {w}x{h}  -> {'GUI' if w > 900 else 'popup'}")

headless_ok = any("selesai" in t and w < 900 for t, w, _ in best_hits)
gui_open = any(w > 900 for _, w, _ in best_hits)
subprocess.run(["taskkill", "-F", "-IM", "ImageCompressor.exe"], capture_output=True)
print("HASIL:", "LOLOS (headless + popup, tanpa GUI)" if (headless_ok and not gui_open)
      else f"GAGAL (headless={headless_ok}, gui={gui_open})")
sys.exit(0 if (headless_ok and not gui_open) else 1)
