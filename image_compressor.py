#!/usr/bin/env python3
"""Image Compressor: kompres & resize massal untuk aset web.

GUI tkinter. Reuse logika compress_gallery.py (Lab AP):
EXIF transpose, resize LANCZOS, flatten transparansi, save optimize.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
import tkinter as tk
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIC_SUPPORT = True
except Exception:
    HEIC_SUPPORT = False

APP_NAME = "Image Compressor"
APP_VER = "1.3.6"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".image_compressor.json")

BASE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
HEIC_EXTS = (".heic", ".heif")
EXTS = BASE_EXTS + HEIC_EXTS

FMT_EXT = {"JPEG": ".jpg", "WEBP": ".webp", "PNG": ".png"}
FMT_LABEL = {
    "JPEG": "JPEG (.jpg): paling kompatibel, paling kecil",
    "WEBP": "WebP (.webp): paling kecil + dukung transparansi",
    "PNG": "PNG (.png): lossless, untuk grafik dan transparansi",
}
LABEL_FMT = {v: k for k, v in FMT_LABEL.items()}

PREVIEW_PX = 300  # lebar panel pratinjau (px)
PREVIEW_PY = 200  # tinggi panel pratinjau (px)


def human(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def pct_text(orig: float, new: float) -> str:
    """Keterangan hemat/membesar yang tidak menyesatkan tandanya."""
    if not orig:
        return ""
    d = (orig - new) / orig * 100.0
    return f"hemat {d:.0f}%" if d >= 0 else f"membesar {abs(d):.0f}%"


def iter_sources(input_dir: str, recursive: bool):
    seen = []
    if recursive:
        for root, dirs, files in os.walk(input_dir):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for f in sorted(files):
                if f.lower().endswith(EXTS):
                    seen.append(os.path.join(root, f))
    else:
        for f in sorted(os.listdir(input_dir)):
            p = os.path.join(input_dir, f)
            if os.path.isfile(p) and f.lower().endswith(EXTS):
                seen.append(p)
    return seen


def build_dest(src: str, input_dir: str, out_dir: str, fmt: str, in_place: bool) -> str:
    stem, _ = os.path.splitext(os.path.basename(src))
    ext = FMT_EXT[fmt]
    if in_place:
        return os.path.join(os.path.dirname(src), stem + ext)
    rel = os.path.relpath(os.path.dirname(src), input_dir)
    target_dir = out_dir if rel == "." else os.path.join(out_dir, rel)
    return os.path.join(target_dir, stem + ext)


def flatten_alpha(im: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        base = Image.new("RGB", im.size, bg)
        base.paste(im, mask=im.convert("RGBA").split()[3])
        return base
    if im.mode != "RGB":
        return im.convert("RGB")
    return im


def compress_one(src: str, tmp: str, box: int, quality: int, fmt: str) -> dict:
    """Tulis hasil ke `tmp`. Return dict hasil (orig, new, w, h, resized)."""
    orig_size = os.path.getsize(src)
    with Image.open(src) as im:
        try:
            im = ImageOps.exif_transpose(im) or im
        except Exception:
            pass

        before_w, before_h = im.size
        im.load()
        resized = False
        if box and before_w > box:
            ratio = box / float(before_w)
            new_h = max(1, int(round(before_h * ratio)))
            im = im.resize((box, new_h), Image.Resampling.LANCZOS)
            resized = True

        if fmt == "JPEG":
            im = flatten_alpha(im)
            im.save(tmp, "JPEG", quality=quality, optimize=True, progressive=True)
        elif fmt == "WEBP":
            if im.mode == "P":
                im = im.convert("RGBA" if "transparency" in im.info else "RGB")
            im.save(tmp, "WEBP", quality=quality, method=6)
        else:
            if im.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                im = im.convert("RGBA")
            im.save(tmp, "PNG", optimize=True, compress_level=9)

        out_w, out_h = im.size

    return {
        "orig": orig_size,
        "new": os.path.getsize(tmp),
        "before": (before_w, before_h),
        "after": (out_w, out_h),
        "resized": resized,
    }


# --------------------------------------------------------------------------- #
# Eksekusi batch: banyak file sekaligus (thread pool; Pillow lepas GIL
# waktu encode/decode, jadi paralel di sini nyata, bukan cuma antre)
# --------------------------------------------------------------------------- #


def avail_ram_mb() -> int | None:
    """RAM yang masih bebas (MB). Dipakai buat membatasi jumlah worker."""
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(st)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return int(st.ullAvailPhys // (1024 * 1024))
    except Exception:
        pass
    return None


def cpu_default() -> int:
    """Jumlah worker paralel.

    Hasil ukur: thread jauh lebih untung daripada proses (Pillow melepas GIL
    waktu encode/decode), dan makin banyak worker makin cepat sampai ~jumlah
    core. Tapi tiap worker memegang satu gambar penuh di memori, jadi jumlahnya
    dibatasi juga oleh RAM yang tersedia.
    """
    cores = os.cpu_count() or 1
    ram = avail_ram_mb()
    if ram:
        by_ram = max(2, ram // 300)  # ~300 MB per worker
        return max(1, min(cores, by_ram))
    return max(1, min(cores, 4))


def make_tmp(dst_dir: str) -> str:
    """Nama file temp unik, aman walau banyak worker menulis bersamaan."""
    return os.path.join(dst_dir, f".~ic-{uuid.uuid4().hex[:10]}.tmp")


def compress_task(t: dict) -> dict:
    """Kerjakan SATU file. Top-level function supaya aman dipakai dari pool.

    Return dict: status ok/skip/error + angka sebelum-sesudah + keterangan.
    """
    src, dst = t["src"], t["dst"]
    label = t.get("label") or os.path.basename(src)
    tmp_dir = t.get("tmp_dir") or os.path.dirname(dst) or "."
    try:
        tmp = make_tmp(tmp_dir)
        r = compress_one(src, tmp, t["box"], t["quality"], t["fmt"])

        if (
            t["skip_bigger"]
            and r["new"] >= r["orig"]
            and os.path.abspath(dst) != os.path.abspath(src)
        ):
            os.remove(tmp)
            return {
                "status": "skip",
                "src": src,
                "dst": dst,
                "label": label,
                "orig": r["orig"],
                "new": r["new"],
                "reason": "hasil tidak lebih kecil",
            }

        # folder bersarang baru dibuat di sini: file yang di-SKIP tidak
        # meninggalkan folder kosong di output
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(tmp, dst)
        deletes = False
        if t["delete_orig"] and os.path.abspath(dst) != os.path.abspath(src):
            try:
                os.remove(src)
                deletes = True
            except OSError:
                pass
        return {
            "status": "ok",
            "src": src,
            "dst": dst,
            "label": label,
            "orig": r["orig"],
            "new": r["new"],
            "before": r["before"],
            "after": r["after"],
            "deleted_orig": deletes,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "src": src,
            "dst": dst,
            "label": label,
            "error": str(exc),
        }


def run_tasks(tasks: list[dict], jobs: int = 0, cancel=None):
    """Jalankan semua task, hasilnya di-`yield` begitu selesai (urut apa saja).

    `cancel` = threading.Event (opsional). Begitu diset, hasil baru berhenti
    di-`yield` dan task yang belum jalan dibatalkan: file yang sedang
    diproses tetap diselesaikan supaya tidak ada file setengah jadi.
    """
    jobs = int(jobs) or cpu_default()
    if jobs <= 1 or len(tasks) <= 1:
        for t in tasks:
            if cancel is not None and cancel.is_set():
                return
            yield compress_task(t)
        return

    ex = ThreadPoolExecutor(max_workers=jobs)
    futures = [ex.submit(compress_task, t) for t in tasks]
    try:
        for fut in as_completed(futures):
            if cancel is not None and cancel.is_set():
                break
            yield fut.result()
    finally:
        # Task yang belum jalan dibatalkan; yang SEDANG jalan ditunggu selesai
        # supaya tidak ada file yang ditulis setengah. Sisa temp dibersihkan
        # di pemanggil lewat drop_leftover_tmp().
        for f in futures:
            f.cancel()
        for f in futures:
            if not f.cancelled():
                try:
                    f.result(timeout=300)
                except Exception:
                    pass
        ex.shutdown(wait=True, cancel_futures=True)


def drop_leftover_tmp(dirs: list[str]):
    """Hapus sisa file temp dari proses yang dihentikan."""
    for d in dirs:
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for n in names:
            if n.startswith(".~ic-") and n.endswith(".tmp"):
                try:
                    os.remove(os.path.join(d, n))
                except OSError:
                    pass


def build_tasks(
    files: list[str],
    src_root: str,
    out_dir: str,
    fmt: str,
    in_place: bool,
    box: int,
    quality: int,
    skip_bigger: bool,
    delete_orig: bool,
) -> list[dict]:
    tasks = []
    for f in files:
        if in_place:
            dst = build_dest(f, src_root or os.path.dirname(f), out_dir, fmt, True)
            label = os.path.basename(f)
        elif src_root:
            dst = build_dest(f, src_root, out_dir, fmt, False)
            label = os.path.relpath(f, src_root)
        else:
            # Mode "file terpilih": file bisa datang dari banyak folder, jadi
            # hasilnya ditulis datar ke out_dir dengan nama aslinya.
            stem, _ = os.path.splitext(os.path.basename(f))
            dst = os.path.join(out_dir, stem + FMT_EXT[fmt])
            label = os.path.basename(f)
        tasks.append({
            "src": f,
            "dst": dst,
            "tmp_dir": out_dir,
            "label": label,
            "box": box,
            "quality": quality,
            "fmt": fmt,
            "skip_bigger": skip_bigger,
            "delete_orig": delete_orig,
        })
    return tasks


class App:
    def __init__(self, root: tk.Tk, preset_dir: str | None = None):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.worker: threading.Thread | None = None
        self.last_out_dir: str | None = None

        root.title(f"{APP_NAME} v{APP_VER}")
        root.minsize(720, 620)

        cfg = self.load_config()
        # Folder sumber SELALU kosong saat app dibuka. Nilainya tidak pernah
        # dipulihkan dari config supaya user memilih sendiri tiap sesi.
        self.var_in = tk.StringVar(value=preset_dir or "")
        # Folder tujuan juga KOSONG saat dibuka: user memilih tiap sesi, baik
        # 'Timpa di tempat' maupun 'Folder lain'. Tidak ada rujukan tersimpan.
        self.var_out = tk.StringVar(value="")
        self.var_mode = tk.StringVar(value=cfg.get("mode", "own"))
        self.var_recursive = tk.BooleanVar(value=cfg.get("recursive", True))
        self.var_skip_bigger = tk.BooleanVar(value=cfg.get("skip_bigger", True))
        self.var_delete_orig = tk.BooleanVar(value=cfg.get("delete_orig", False))
        self.var_open_after = tk.BooleanVar(value=cfg.get("open_after", False))
        self.var_width = tk.IntVar(value=cfg.get("width", 1920))
        self.var_quality = tk.IntVar(value=cfg.get("quality", 85))
        self.var_fmt = tk.StringVar(value=FMT_LABEL.get(cfg.get("fmt", "JPEG"), FMT_LABEL["JPEG"]))
        self.var_jobs = tk.IntVar(value=cfg.get("jobs", 0))

        self.var_status = tk.StringVar(value="Siap.")
        self.var_count = tk.StringVar(value="0 / 0")
        # daftar file spesifik dari 'Pilih File' / drag & drop file
        self.var_files: list[str] = []
        self.lbl_files_var = tk.StringVar(value="")

        # pratinjau sebelum-sesudah
        self.prev_path: str | None = None
        self.prev_busy = False
        self.prev_after_id = None
        self.ph_before = self.ph_after = None
        self.var_prev_info = tk.StringVar(value="Belum ada contoh gambar.")
        self.var_prev_b = tk.StringVar(value="")
        self.var_prev_a = tk.StringVar(value="")

        # konstanta modul diekspos ke GUI v1.2 (gui_v12 baca lewat instance)
        self.APP_VER = APP_VER
        self.APP_NAME = APP_NAME
        self.FMT_LABEL = FMT_LABEL
        self.LABEL_FMT = LABEL_FMT
        self.EXTS = EXTS
        self.HEIC_SUPPORT = HEIC_SUPPORT
        self.human = human
        self.pct_text = pct_text
        self.cpu_default = cpu_default

        self._build_ui()
        self.update_quality_label()
        self.update_jobs_label()
        # trace pratinjau dipasang gui_v12 (_wire); di sini tidak dipasang lagi
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- config ----------
    def load_config(self) -> dict:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def save_config(self):
        # "input" dan "output" sengaja TIDAK disimpan: kedua kolom folder
        # harus kosong tiap buka, user memilih sendiri.
        data = {
            "mode": self.var_mode.get(),
            "recursive": self.var_recursive.get(),
            "skip_bigger": self.var_skip_bigger.get(),
            "delete_orig": self.var_delete_orig.get(),
            "open_after": self.var_open_after.get(),
            "width": self.var_width.get(),
            "quality": self.var_quality.get(),
            "fmt": LABEL_FMT.get(self.var_fmt.get(), "JPEG"),
            "jobs": int(float(self.var_jobs.get() or 0)),
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except Exception:
            pass

    # ---------- ui ----------
    def _build_ui(self):
        """UI v1.2.0 ada di gui_v12.py; App tetap pemilik state + mesin."""
        import gui_v12

        self.ui = gui_v12.GUI(self.root, self)
        self.root.after(120, self.ui.run)


    def sync_mode(self):
        """Widget milik gui_v12; no-op di sini supaya kode lama tetap aman."""
        return

    def update_quality_label(self):
        """Label kualitas digambar gui_v12; sisanya cukup pratinjau ulang."""
        self.schedule_preview()

    def update_jobs_label(self):
        """Label worker digambar gui_v12."""
        return

    # ---------- pratinjau sebelum-sesudah ----------
    def preview_source(self, path: str):
        """Pasang satu gambar sebagai contoh pratinjau (dipanggil juga dari main())."""
        p = os.path.abspath(path)
        if not os.path.isfile(p):
            return
        self.prev_path = p
        self.var_prev_info.set(f"Contoh: {os.path.basename(p)}")
        self.schedule_preview(50)

    def pick_preview(self):
        """Ambil gambar terbesar dari folder sumber sebagai contoh."""
        d = self.var_in.get().strip()
        if d and os.path.isdir(d):
            try:
                found = iter_sources(d, self.var_recursive.get())
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Gagal membaca folder sumber:\n{exc}")
                return
            if found:
                self.preview_source(max(found, key=os.path.getsize))
                return
        messagebox.showinfo(APP_NAME, "Folder sumber belum dipilih atau belum ada gambar di dalamnya.")
        self.pick_preview_file()

    def pick_preview_file(self):
        f = filedialog.askopenfilename(
            title="Pilih gambar contoh",
            filetypes=[("Gambar", "*.jpg *.jpeg *.png *.webp *.heic *.heif *.bmp *.tif *.tiff"),
                       ("Semua file", "*.*")],
        )
        if f:
            self.preview_source(f)

    def schedule_preview(self, delay: int = 400):
        """Tunda sedikit supaya geser slider tidak memicu hitung berkali-kali."""
        if self.prev_after_id:
            try:
                self.root.after_cancel(self.prev_after_id)
            except Exception:
                pass
        self.prev_after_id = self.root.after(delay, self.run_preview)

    def run_preview(self):
        self.prev_after_id = None
        if not self.prev_path or not os.path.isfile(self.prev_path):
            self.var_prev_info.set("Belum ada contoh gambar.")
            return
        if self.worker and self.worker.is_alive():
            self.schedule_preview(600)  # jangan berebut CPU dengan proses kompresi
            return
        if self.prev_busy:
            self.schedule_preview(250)
            return
        self.prev_busy = True
        self.var_prev_info.set("Menghitung pratinjau...")
        o = {
            "src": self.prev_path,
            "box": int(float(self.var_width.get() or 0)),
            "quality": int(float(self.var_quality.get())),
            "fmt": LABEL_FMT.get(self.var_fmt.get(), "JPEG"),
        }
        threading.Thread(target=self._preview_job, args=(o,), daemon=True).start()

    def _preview_job(self, o: dict):
        work = None
        try:
            work = tempfile.mkdtemp(prefix="ic-prev-")
            dst = os.path.join(work, "hasil" + FMT_EXT[o["fmt"]])
            r = compress_one(o["src"], dst, o["box"], o["quality"], o["fmt"])

            def small(path: str):
                im = Image.open(path)
                im = ImageOps.exif_transpose(im)
                im.thumbnail((PREVIEW_PX - 6, PREVIEW_PY - 6))
                return im.convert("RGB")

            self.q.put(("prev", {
                "name": os.path.basename(o["src"]),
                "before": small(o["src"]),
                "after": small(dst),
                "orig": r["orig"],
                "new": r["new"],
                "bdim": r["before"],
                "adim": r["after"],
            }))
        except Exception as exc:
            self.q.put(("prev_err", str(exc)))
        finally:
            if work:
                shutil.rmtree(work, ignore_errors=True)

    def show_preview(self, p: dict):
        """Data pratinjau sampai di GUI utama: teruskan ke widget compare."""
        self.prev_busy = False
        ui = getattr(self, "ui", None)
        if ui is not None:
            ui.show_preview(p)
        else:
            self.var_prev_info.set(f"Contoh: {p['name']}")

    def pick_in(self):
        d = filedialog.askdirectory(title="Pilih folder sumber", initialdir=self.var_in.get() or None)
        if d:
            self.var_in.set(os.path.normpath(d))
            if not self.var_out.get():
                self.var_out.set(os.path.normpath(d))

    def pick_out(self):
        d = filedialog.askdirectory(title="Pilih folder tujuan", initialdir=self.var_out.get() or None)
        if d:
            self.var_out.set(os.path.normpath(d))

    # ---------- logging ----------
    def log(self, line: str):
        self.q.put(("log", line))

    def pump(self):
        """v1.2.0: antrean dibaca gui_v12.GUI.run(). Dipertahankan kosong
        supaya kode lama yang memanggil pump() tidak memicu dua konsumen
        yang berebut isi queue."""
        return

    # ---------- run ----------
    def start(self):
        if self.worker and self.worker.is_alive():
            return
        # Mode file: daftar file spesifik (dari 'Pilih File' atau drag & drop).
        # Kalau tidak ada, baru pakai folder sumber.
        files_mode = [f for f in (self.var_files or []) if os.path.isfile(f)]
        in_dir = self.var_in.get().strip()

        if files_mode:
            return self._start_files(files_mode)

        if not in_dir or not os.path.isdir(in_dir):
            messagebox.showerror(APP_NAME, "Folder sumber belum dipilih / tidak ditemukan.\n\n"
                                           "Pilih folder sumber, atau tekan 'Pilih File'.")
            return
        in_place = self.var_mode.get() == "inplace"
        out_dir = in_dir if in_place else self.var_out.get().strip()
        if not in_place:
            if not out_dir:
                messagebox.showerror(APP_NAME, "Folder tujuan belum dipilih.")
                return
            if os.path.abspath(out_dir) == os.path.abspath(in_dir):
                messagebox.showerror(APP_NAME, "Folder tujuan sama dengan sumber.\nPakai mode 'Timpa di tempat'.")
                return
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Tidak bisa membuat folder tujuan:\n{exc}")
                return

        fmt = LABEL_FMT.get(self.var_fmt.get(), "JPEG")
        opts = {
            "in_dir": in_dir,
            "out_dir": out_dir,
            "in_place": in_place,
            "recursive": self.var_recursive.get(),
            "box": int(float(self.var_width.get() or 0)),
            "quality": int(float(self.var_quality.get())),
            "fmt": fmt,
            "skip_bigger": self.var_skip_bigger.get(),
            "delete_orig": self.var_delete_orig.get(),
            "jobs": int(float(self.var_jobs.get() or 0)),
            # dibaca di sini (main thread) karena run_job jalan di thread lain
            "open_after": self.var_open_after.get(),
        }

        self.cancel.clear()
        self.save_config()

        self.worker = threading.Thread(target=self.run_job, args=(opts,), daemon=True)
        self.worker.start()

    def _start_files(self, files: list[str]) -> None:
        """Kompres daftar file spesifik (bukan seluruh isi folder).

        Tujuan: mode 'inplace' = timpa di samping file asal; mode 'own' =
        tulis ke folder tujuan dengan nama yang sama seperti aslinya
        (tanpa struktur folder, karena file bisa datang dari mana saja).
        """
        in_place = self.var_mode.get() == "inplace"
        out_dir = ""
        if not in_place:
            out_dir = self.var_out.get().strip()
            if not out_dir:
                messagebox.showerror(APP_NAME, "Folder tujuan belum dipilih.\n\n"
                                               "Pilih folder tujuan, atau ubah ke mode 'Timpa di tempat'.")
                return
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Tidak bisa membuat folder tujuan:\n{exc}")
                return

        opts = {
            "files": list(files),
            "in_dir": "",
            "out_dir": out_dir,
            "in_place": in_place,
            "recursive": False,
            "box": int(float(self.var_width.get() or 0)),
            "quality": int(float(self.var_quality.get())),
            "fmt": LABEL_FMT.get(self.var_fmt.get(), "JPEG"),
            "skip_bigger": self.var_skip_bigger.get(),
            "delete_orig": self.var_delete_orig.get(),
            "jobs": int(float(self.var_jobs.get() or 0)),
            "open_after": self.var_open_after.get(),
        }
        self.cancel.clear()
        self.save_config()
        self.worker = threading.Thread(target=self.run_job, args=(opts,), daemon=True)
        self.worker.start()

    def pick_files(self):
        """Pilih satu atau beberapa file gambar lewat dialog."""
        f = filedialog.askopenfilenames(
            title="Pilih file gambar (bisa banyak)",
            filetypes=[
                ("Gambar", "*.jpg *.jpeg *.png *.webp *.gif *.bmp *.tif *.tiff "
                           "*.heic *.heif"),
                ("Semua file", "*.*"),
            ],
        )
        if not f:
            return
        got = [os.path.normpath(p) for p in f]

        # Buang yang tidak didukung, laporkan
        ok = [p for p in got if p.lower().endswith(EXTS)]
        bad = [p for p in got if p not in ok]
        if not ok:
            messagebox.showwarning(APP_NAME, "Tidak ada file gambar yang didukung di pilihan itu.")
            return
        if bad:
            self.log(f"[!] {len(bad)} file dilewati (bukan gambar didukung).")

        self.var_files = ok
        # Kalau semua file dari satu folder yang sama, isi juga folder sumber
        # supaya konteks pratinjau & tombol jelas.
        dirs = {os.path.dirname(p) for p in ok}
        if len(dirs) == 1:
            self.var_in.set(dirs.pop())
        self.refresh_files()
        self.preview_source(max(ok, key=os.path.getsize))
        self.log(f"[i] {len(ok)} file dipilih siap dikompres.")

    def clear_files(self):
        self.var_files = []
        self.refresh_files()

    def refresh_files(self):
        """Beri tahu GUI jumlah file terpilih (label + tombol bersihkan)."""
        ui = getattr(self, "ui", None)
        if ui is not None and hasattr(ui, "show_file_selection"):
            ui.show_file_selection(list(self.var_files))

    def stop(self):
        self.cancel.set()
        self.var_status.set("Menghentikan...")

    def run_job(self, o: dict):
        files_mode = o.get("files")
        if files_mode:
            files = [f for f in files_mode if os.path.isfile(f)]
            if len(files) != len(files_mode):
                self.log(f"[!] {len(files_mode) - len(files)} file hilang/tidak ditemukan, dilewati.")
            mode_txt = "File terpilih"
        else:
            try:
                files = iter_sources(o["in_dir"], o["recursive"])
            except Exception as exc:
                self.log(f"[ERR] Gagal membaca folder: {exc}")
                self.q.put(("done", None))
                return
            mode_txt = "Folder sumber"

        total = len(files)
        jobs = int(o.get("jobs") or 0) or cpu_default()
        if files_mode:
            self.log(f"{mode_txt} : {total} file")
        else:
            self.log(f"{mode_txt} : {o['in_dir']}")
        self.log(f"Folder tujuan : {o['out_dir'] or '(di samping file asal)'}"
                 + ("  (in-place)" if o["in_place"] else ""))
        self.log(f"Format        : {o['fmt']}   Lebar maks: {o['box'] or 'tanpa resize'}   "
                 f"Kualitas: {o['quality']}")
        self.log(f"Paralel       : {jobs} worker" + (" (berurutan)" if jobs <= 1 else ""))
        self.log(f"File ditemukan: {total}")
        self.log("-" * 72)
        if not total:
            self.q.put(("status", "Tidak ada file gambar yang cocok."))
            self.q.put(("done", None))
            return

        tasks = build_tasks(
            files, o["in_dir"], o["out_dir"], o["fmt"], o["in_place"],
            o["box"], o["quality"], o["skip_bigger"], o["delete_orig"],
        )

        sum_before = sum_after = 0
        ok = skip = err = 0
        t0 = time.time()
        done = 0

        for res in run_tasks(tasks, jobs, cancel=self.cancel):
            done += 1
            name = res["label"]
            if res["status"] == "ok":
                ok += 1
                sum_before += res["orig"]
                sum_after += res["new"]
                dim = (f"{res['before'][0]}x{res['before'][1]} -> "
                       f"{res['after'][0]}x{res['after'][1]}")
                tail = "  [asli dihapus]" if res.get("deleted_orig") else ""
                self.log(f"[OK]   {name}  {human(res['orig'])} -> {human(res['new'])}  "
                         f"({pct_text(res['orig'], res['new'])})  {dim}{tail}")
            elif res["status"] == "skip":
                skip += 1
                self.log(f"[SKIP] {name}  ({human(res['orig'])} -> {human(res['new'])}, "
                         "tidak lebih kecil)")
            else:
                err += 1
                self.log(f"[ERR]  {name}: {res['error']}")
            self.q.put(("progress", (done, total, name)))

        cancelled = self.cancel.is_set()
        if cancelled:
            drop_leftover_tmp([o["out_dir"]])
            self.log("[!] Dibatalkan. File yang sudah selesai tetap tersimpan.")

        self.q.put(("progress", (done, total, None)))
        dt = time.time() - t0
        self.log("-" * 72)
        self.log(f"Selesai dalam {dt:.1f}s  |  OK {ok}  |  dilewati {skip}  |  gagal {err}")
        if sum_before:
            self.log(f"Kecepatan     : {sum_before / 1048576 / max(dt, 1e-6):.1f} MB/s")
        if ok:
            self.log(f"Total ukuran  : {human(sum_before)} -> {human(sum_after)}")
            if sum_before:
                self.log(f"Ruang dihemat : {(sum_before - sum_after) / sum_before * 100:.1f}%")
        self.q.put(("status", ("Dihentikan: " if cancelled else "Selesai: ")
                    + f"{ok} file diproses."))
        if files_mode:
            self.last_out_dir = (os.path.dirname(files[0]) if o["in_place"]
                                 else o["out_dir"])
        else:
            self.last_out_dir = o["in_dir"] if o["in_place"] else o["out_dir"]
        if o.get("open_after") and self.last_out_dir and ok:
            self.q.put(("log", f"[i] Membuka {self.last_out_dir}"))
            try:
                os.startfile(self.last_out_dir)  # noqa: S606
            except Exception as exc:
                self.q.put(("log", f"[ERR] Gagal membuka folder: {exc}"))
        self.q.put(("done", None))

    def finish_ui(self):
        self.save_config()

    def on_close(self):
        self.save_config()
        if self.prev_after_id:
            try:
                self.root.after_cancel(self.prev_after_id)
            except Exception:
                pass
        if self.worker and self.worker.is_alive():
            if not messagebox.askokcancel(APP_NAME, "Proses masih berjalan. Hentikan dan keluar?"):
                return
            self.cancel.set()
        self.root.destroy()


# --------------------------------------------------------------------------- #
# Headless mode: drag & drop folder ke .exe, atau --cli dari terminal
# --------------------------------------------------------------------------- #

CLI_DEFAULTS = {
    "recursive": True,
    "box": 1920,
    "quality": 85,
    "fmt": "JPEG",
    "skip_bigger": True,
    "delete_orig": False,
    "jobs": 0,
}

USAGE = f"""{APP_NAME} v{APP_VER}

Pemakaian:
  ImageCompressor.exe                     buka GUI
  ImageCompressor.exe "D:\\foto"          GUI dengan folder sumber terisi
  ImageCompressor.exe --cli "D:\\foto"    proses langsung tanpa GUI (headless)

Opsi headless:
  --out DIR         folder tujuan (default: <folder>_compressed, atau
                    <nama>_compressed.<ext> untuk file yang ditarik langsung)
  --in-place        timpa di tempat (nama file mengikuti format keluaran)
  --width N         lebar maksimal px, 0 = tanpa resize (default: 1920)
  --quality N       kualitas JPEG/WebP 1-100 (default: 85)
  --format FMT      JPEG | WEBP | PNG (default: JPEG)
  --jobs N          jumlah worker paralel, 1 = berurutan (default: otomatis)
  --no-recursive    jangan telusuri subfolder
  --keep-bigger     tetap tulis hasil walau ukurannya tidak lebih kecil
  --delete-orig     hapus file asli setelah konversi format
  -h, --help        tampilkan bantuan ini

Menarik folder ATAU file gambar ke atas .exe = jalankan mode headless otomatis.
"""


def say(text: str) -> None:
    """print() yang aman walau stdout tidak ada (exe windowed tanpa console)."""
    if sys.stdout is None:
        return
    try:
        print(text, flush=True)
    except Exception:
        pass


def popup(title: str, body: str) -> None:
    try:
        r = tk.Tk()
        r.withdraw()
        messagebox.showinfo(title, body)
        r.destroy()
    except Exception:
        pass


def launched_from_shell(argv: list[str]) -> bool:
    """Apakah proses ini dijalankan dari console (cmd/PowerShell/terminal)?

    Exe windowed (`--windows-console-mode=disable`) selalu punya
    `sys.stdout is None`, bahkan waktu dijalankan dari cmd: jadi stdout
    sendirian tidak cukup. Cek dua hal:
      1. proses ini punya console window sendiri, atau
      2. ada console shell (cmd/pwsh/bash/wt) di rantai proses induk.

    Induk langsung Explorer = drag & drop; induk terminal = dijalankan manual.
    """
    if sys.stdout is not None and hasattr(sys.stdout, "fileno"):
        return True
    try:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.windll.kernel32
        if k32.GetConsoleWindow():
            return True

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.CHAR * 260),
            ]

        snap = k32.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
        if not snap or snap == -1:
            return False
        table: dict[int, tuple[int, str]] = {}
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(pe)
        if k32.Process32First(snap, ctypes.byref(pe)):
            while True:
                name = pe.szExeFile.decode(errors="ignore").lower()
                table[pe.th32ProcessID] = (pe.th32ParentProcessID, name)
                if not k32.Process32Next(snap, ctypes.byref(pe)):
                    break
        k32.CloseHandle(snap)

        shells = {
            "cmd.exe", "powershell.exe", "pwsh.exe", "bash.exe", "sh.exe",
            "wt.exe", "windowsterminal.exe", "conhost.exe", "mintty.exe",
            "zsh.exe", "fish.exe", "nu.exe", "wezterm-gui.exe",
            "alacritty.exe", "tabby.exe", "code.exe", "python.exe",
            "pythonw.exe", "uv.exe", "git-bash.exe",
        }
        cur = os.getpid()
        for _ in range(8):
            entry = table.get(cur)
            if not entry:
                return False
            parent = entry[0]
            if not parent:
                return False
            pname = table.get(parent, (0, ""))[1]
            if pname == "explorer.exe":
                return False          # drag & drop dari Explorer
            if pname in shells:
                return True           # ada shell/terminal di rantainya
            cur = parent
        return False
    except Exception:
        # apa pun yang gagal: anggap drag & drop (mode headless): lebih baik
        # memproses file daripada membuka GUI tanpa diminta
        return False


def _split_targets(targets: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Pisahkan target jadi (folder, file gambar, sisanya)."""
    dirs: list[str] = []
    imgs: list[str] = []
    bad: list[str] = []
    for t in targets:
        p = os.path.abspath(t)
        if os.path.isdir(p):
            dirs.append(p)
        elif os.path.isfile(p) and p.lower().endswith(EXTS):
            imgs.append(p)
        else:
            bad.append(p)
    return dirs, imgs, bad


def run_headless(targets, o: dict, interactive: bool | None = None) -> int:
    """Proses folder dan/atau file langsung: mode drag & drop maupun --cli.

    `targets` boleh satu string atau daftar. Folder diproses seperti biasa
    (hasil ke `<folder>_compressed`), file langsung diproses satu-satu dengan
    hasil `<nama>_compressed.<ext>` di folder yang sama.

    `interactive` = True kalau dipicu drag & drop (tidak ada output console),
    jadi ringkasan ditampilkan lewat messagebox.
    """
    if isinstance(targets, str):
        targets = [targets]

    fmt = o["fmt"]
    in_place = o["in_place"]
    if interactive is None:
        interactive = sys.stdout is None  # dipanggil dari Explorer / drag & drop

    dirs, imgs, bad = _split_targets(targets)
    for b in bad:
        say(f"[!] Dilewati (bukan folder atau gambar): {b}")

    if not dirs and not imgs:
        msg = "Tidak ada folder atau file gambar yang bisa diproses."
        say(msg)
        if interactive:
            popup(APP_NAME, msg)
        return 1

    tasks: list[dict] = []
    out_dirs: list[str] = []

    for d in dirs:
        try:
            found = iter_sources(d, o["recursive"])
        except Exception as exc:
            say(f"[ERR] Gagal membaca folder {d}: {exc}")
            continue
        if not found:
            continue
        out_d = d if in_place else (o["out"] or d + "_compressed")
        if not in_place:
            os.makedirs(out_d, exist_ok=True)
        out_dirs.append(out_d)
        tasks += build_tasks(
            found, d, out_d, fmt, in_place, o["box"], o["quality"],
            o["skip_bigger"], o["delete_orig"],
        )

    # File yang ditarik langsung ke exe: hasil di sebelah file aslinya.
    for f in imgs:
        d0 = os.path.dirname(f) or "."
        stem = os.path.splitext(os.path.basename(f))[0]
        ext = FMT_EXT[fmt]
        if o["out"]:
            os.makedirs(o["out"], exist_ok=True)
            dst = os.path.join(o["out"], stem + ext)
        else:
            dst = os.path.join(d0, stem + ("_compressed" if not in_place else "") + ext)
        if os.path.abspath(dst) == os.path.abspath(f):
            dst = os.path.join(d0, stem + "_compressed" + ext)
        tmp_dir = os.path.dirname(dst) or "."
        out_dirs.append(tmp_dir)
        tasks.append(
            {
                "src": f,
                "dst": dst,
                "tmp_dir": tmp_dir,
                "label": os.path.basename(f),
                "box": o["box"],
                "quality": o["quality"],
                "fmt": fmt,
                "skip_bigger": o["skip_bigger"],
                "delete_orig": o["delete_orig"],
            }
        )

    if not tasks:
        msg = "Tidak ada file gambar yang cocok."
        say(msg)
        if interactive:
            popup(APP_NAME, msg)
        return 1

    out_dirs = list(dict.fromkeys(out_dirs))
    jobs = int(o.get("jobs") or 0) or cpu_default()

    say(f"{APP_NAME} v{APP_VER}  |  headless")
    if dirs and imgs:
        say(f"Target        : {len(dirs)} folder + {len(imgs)} file")
    elif dirs:
        say(f"Target        : folder {dirs[0]}" if len(dirs) == 1
            else f"Target        : {len(dirs)} folder")
    else:
        say(f"Target        : {len(imgs)} file")
    say(f"Folder tujuan : {', '.join(out_dirs)}" + ("  (in-place)" if in_place else ""))
    say(f"Format        : {fmt}   Lebar maks: {o['box'] or 'tanpa resize'}   "
        f"Kualitas: {o['quality']}")
    say(f"Paralel       : {jobs} worker" + (" (berurutan)" if jobs <= 1 else ""))
    say(f"File ditemukan: {len(tasks)}")
    say("-" * 72)

    ok = skip = err = 0
    sum_before = sum_after = 0
    failures: list[str] = []
    t0 = time.perf_counter()
    done = 0
    for res in run_tasks(tasks, jobs):
        done += 1
        name = res["label"]
        tag = f"[{done}/{len(tasks)}]"
        if res["status"] == "ok":
            ok += 1
            sum_before += res["orig"]
            sum_after += res["new"]
            tail = "  [asli dihapus]" if res.get("deleted_orig") else ""
            say(f"{tag} OK    {name}  {human(res['orig'])} -> {human(res['new'])}  "
                f"({pct_text(res['orig'], res['new'])}){tail}")
        elif res["status"] == "skip":
            skip += 1
            say(f"{tag} SKIP  {name}  ({human(res['orig'])} -> {human(res['new'])}, "
                "tidak lebih kecil)")
        else:
            err += 1
            failures.append(f"{name}: {res['error']}")
            say(f"{tag} ERR   {name}: {res['error']}")
    dur = time.perf_counter() - t0

    say("-" * 72)
    say(f"Selesai dalam {dur:.1f}s  |  OK {ok}  |  dilewati {skip}  |  gagal {err}")
    if sum_before:
        say(f"Kecepatan     : {sum_before / 1048576 / max(dur, 1e-6):.1f} MB/s")
    if ok:
        say(f"Total ukuran  : {human(sum_before)} -> {human(sum_after)}")
        if sum_before:
            say(f"Ruang dihemat : {(sum_before - sum_after) / sum_before * 100:.1f}%")

    if interactive:
        saved = ""
        if ok and sum_before:
            saved = (f"\nTotal ukuran: {human(sum_before)} -> {human(sum_after)} "
                     f"(hemat {(sum_before - sum_after) / sum_before * 100:.1f}%)")
        body = (f"{ok} berhasil  |  {skip} dilewati  |  {err} gagal  "
                f"(dari {len(tasks)} file){saved}\n\nHasil ada di:\n"
                + "\n".join(out_dirs[:3]))
        if failures:
            body += "\n\nGagal:\n" + "\n".join(failures[:5])
        popup(f"{APP_NAME}: selesai", body)
        for od in out_dirs[:2]:
            try:
                os.startfile(od)  # noqa: S606
            except Exception:
                pass

    return 0 if not err else 1


def parse_cli(argv: list[str]) -> dict | None:
    """Parse argumen headless. Return dict opsi, atau None kalau tidak valid."""
    o = dict(CLI_DEFAULTS)
    o["out"] = None
    o["in_place"] = False
    o["targets"] = []

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--cli":
            i += 1
            continue
        if a in ("--in-place", "--inplace"):
            o["in_place"] = True
        elif a == "--no-recursive":
            o["recursive"] = False
        elif a == "--keep-bigger":
            o["skip_bigger"] = False
        elif a == "--delete-orig":
            o["delete_orig"] = True
        elif a in ("--out", "-o") and i + 1 < len(argv):
            i += 1
            o["out"] = os.path.abspath(argv[i])
        elif a in ("--width", "-w") and i + 1 < len(argv):
            i += 1
            o["box"] = max(0, int(float(argv[i])))
        elif a in ("--quality", "-q") and i + 1 < len(argv):
            i += 1
            o["quality"] = min(100, max(1, int(float(argv[i]))))
        elif a in ("--jobs", "-j") and i + 1 < len(argv):
            i += 1
            o["jobs"] = max(0, int(float(argv[i])))
        elif a == "--format" and i + 1 < len(argv):
            i += 1
            fmt = argv[i].upper()
            if fmt not in FMT_EXT:
                say(f"Format tidak dikenal: {fmt} (pakai JPEG | WEBP | PNG)")
                return None
            o["fmt"] = fmt
        elif a.startswith("-"):
            say(f"Opsi tidak dikenal: {a}\n\n{USAGE}")
            return None
        elif os.path.exists(a):
            o["targets"].append(os.path.abspath(a))
        i += 1

    return o


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if any(a in ("-h", "--help") for a in argv):
        say(USAGE)
        if sys.stdout is None:
            popup(f"{APP_NAME}: bantuan", USAGE)
        return 0
    if any(a in ("-V", "--version") for a in argv):
        say(f"{APP_NAME} v{APP_VER}")
        return 0

    # Drag & drop folder ATAU file gambar ke .exe => langsung proses tanpa GUI.
    # Dijalankan dari console (cmd/PowerShell) => GUI, walaupun exe-nya windowed.
    def _is_target(a: str) -> bool:
        return os.path.isdir(a) or (os.path.isfile(a) and a.lower().endswith(EXTS))

    has_target = any(_is_target(a) for a in argv)
    from_shell = launched_from_shell(argv)
    if "--cli" in argv or (has_target and not from_shell):
        opts = parse_cli(argv)
        if opts is None:
            return 1
        if not opts["targets"]:
            say(USAGE)
            if not from_shell:
                popup(f"{APP_NAME}: bantuan", USAGE)
            return 2
        return run_headless(opts["targets"], opts, interactive=not from_shell)

    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    # Argumen dari console: folder mengisi folder sumber, file gambar mengisi
    # folder sumber. (Tidak otomatis memuat contoh pratinjau: pengguna
    # menyeret gambar sendiri ke panel.)
    preset = None
    for arg in argv:
        if os.path.isdir(arg):
            preset = os.path.abspath(arg)
            break
        if os.path.isfile(arg) and arg.lower().endswith(EXTS):
            preset = os.path.dirname(os.path.abspath(arg))
            break

    root = tk.Tk()
    app = App(root, preset)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
