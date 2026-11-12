#!/usr/bin/env python3
"""Image Compressor — kompres & resize massal untuk aset web.

GUI tkinter. Reuse logika compress_gallery.py (Lab AP):
EXIF transpose, resize LANCZOS, flatten transparansi, save optimize.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIC_SUPPORT = True
except Exception:
    HEIC_SUPPORT = False

APP_NAME = "Image Compressor"
APP_VER = "1.0.0"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".image_compressor.json")

BASE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
HEIC_EXTS = (".heic", ".heif")
EXTS = BASE_EXTS + HEIC_EXTS

FMT_EXT = {"JPEG": ".jpg", "WEBP": ".webp", "PNG": ".png"}
FMT_LABEL = {
    "JPEG": "JPEG (.jpg) — paling kompatibel, paling kecil",
    "WEBP": "WebP (.webp) — paling kecil + dukung transparansi",
    "PNG": "PNG (.png) — lossless, untuk grafik/transparansi",
}
LABEL_FMT = {v: k for k, v in FMT_LABEL.items()}


def human(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


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
        self.var_in = tk.StringVar(value=preset_dir or cfg.get("input", ""))
        self.var_out = tk.StringVar(value=cfg.get("output", ""))
        self.var_mode = tk.StringVar(value=cfg.get("mode", "own"))
        self.var_recursive = tk.BooleanVar(value=cfg.get("recursive", True))
        self.var_skip_bigger = tk.BooleanVar(value=cfg.get("skip_bigger", True))
        self.var_delete_orig = tk.BooleanVar(value=cfg.get("delete_orig", False))
        self.var_open_after = tk.BooleanVar(value=cfg.get("open_after", False))
        self.var_width = tk.IntVar(value=cfg.get("width", 1920))
        self.var_quality = tk.IntVar(value=cfg.get("quality", 85))
        self.var_fmt = tk.StringVar(value=FMT_LABEL.get(cfg.get("fmt", "JPEG"), FMT_LABEL["JPEG"]))

        self.var_status = tk.StringVar(value="Siap.")
        self.var_count = tk.StringVar(value="0 / 0")

        self._build_ui()
        self.sync_mode()
        self.update_quality_label()
        self.root.after(120, self.pump)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- config ----------
    def load_config(self) -> dict:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def save_config(self):
        data = {
            "input": self.var_in.get(),
            "output": self.var_out.get(),
            "mode": self.var_mode.get(),
            "recursive": self.var_recursive.get(),
            "skip_bigger": self.var_skip_bigger.get(),
            "delete_orig": self.var_delete_orig.get(),
            "open_after": self.var_open_after.get(),
            "width": self.var_width.get(),
            "quality": self.var_quality.get(),
            "fmt": LABEL_FMT.get(self.var_fmt.get(), "JPEG"),
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except Exception:
            pass

    # ---------- ui ----------
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("TLabelframe.Label", font=("Segoe UI Semibold", 10))
        style.configure("Go.TButton", font=("Segoe UI Semibold", 10))
        style.configure("Hdr.TLabel", font=("Segoe UI Semibold", 12))

        pad = {"padx": 10, "pady": 6}
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)

        ttk.Label(outer, text=APP_NAME, style="Hdr.TLabel").grid(row=0, column=0, sticky="w")
        sub = "HEIC/iPhone: didukung" if HEIC_SUPPORT else "HEIC/iPhone: tidak didukung di build ini"
        ttk.Label(outer, text=f"Kompres & resize massal untuk aset web  ·  {sub}",
                  foreground="#666").grid(row=1, column=0, sticky="w", pady=(0, 8))

        # Sumber
        f_in = ttk.LabelFrame(outer, text="1 · Folder sumber")
        f_in.grid(row=2, column=0, sticky="ew", **pad)
        f_in.columnconfigure(0, weight=1)
        self.e_in = ttk.Entry(f_in, textvariable=self.var_in)
        self.e_in.grid(row=0, column=0, sticky="ew", padx=(8, 6), pady=8)
        ttk.Button(f_in, text="Pilih Folder…", command=self.pick_in).grid(row=0, column=1, padx=(0, 8), pady=8)
        ttk.Checkbutton(f_in, text="Sertakan subfolder (rekursif)", variable=self.var_recursive).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))

        # Tujuan
        f_out = ttk.LabelFrame(outer, text="2 · Folder tujuan")
        f_out.grid(row=3, column=0, sticky="ew", **pad)
        f_out.columnconfigure(0, weight=1)
        ttk.Radiobutton(f_out, text="Timpa di tempat (hasil menimpa folder sumber)",
                        variable=self.var_mode, value="inplace", command=self.sync_mode).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 2))
        ttk.Radiobutton(f_out, text="Folder lain (sumber tidak disentuh)",
                        variable=self.var_mode, value="own", command=self.sync_mode).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=8, pady=2)
        self.e_out = ttk.Entry(f_out, textvariable=self.var_out)
        self.e_out.grid(row=2, column=0, sticky="ew", padx=(28, 6), pady=(2, 8))
        self.btn_out = ttk.Button(f_out, text="Pilih Folder…", command=self.pick_out)
        self.btn_out.grid(row=2, column=1, padx=(0, 8), pady=(2, 8))

        # Pengaturan
        f_set = ttk.LabelFrame(outer, text="3 · Pengaturan")
        f_set.grid(row=4, column=0, sticky="ew", **pad)
        f_set.columnconfigure(1, weight=1)
        f_set.columnconfigure(3, weight=1)

        ttk.Label(f_set, text="Lebar maksimal (px, 0 = tanpa resize)").grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        ttk.Spinbox(f_set, from_=0, to=12000, increment=80, width=8,
                    textvariable=self.var_width).grid(row=0, column=1, sticky="w", padx=6, pady=(8, 4))

        ttk.Label(f_set, text="Format keluaran").grid(row=0, column=2, sticky="w", padx=(18, 4), pady=(8, 4))
        combo = ttk.Combobox(f_set, textvariable=self.var_fmt, state="readonly",
                             values=list(FMT_LABEL.values()), width=44)
        combo.grid(row=0, column=3, sticky="ew", padx=(6, 8), pady=(8, 4))

        ttk.Label(f_set, text="Kualitas (JPEG/WebP)").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        qrow = ttk.Frame(f_set)
        qrow.grid(row=1, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        qrow.columnconfigure(0, weight=1)
        self.scale_q = ttk.Scale(qrow, from_=30, to=100, orient="horizontal",
                                 variable=self.var_quality, command=lambda _=None: self.update_quality_label())
        self.scale_q.grid(row=0, column=0, sticky="ew")
        ttk.Label(qrow, textvariable=tk.StringVar(), width=0).grid(row=0, column=2)
        self.lbl_q = ttk.Label(qrow, text="", width=18)
        self.lbl_q.grid(row=0, column=1, sticky="w", padx=8)

        opts = ttk.Frame(f_set)
        opts.grid(row=2, column=0, columnspan=4, sticky="w", padx=6, pady=(2, 8))
        ttk.Checkbutton(opts, text="Lewati jika hasil tidak lebih kecil",
                        variable=self.var_skip_bigger).grid(row=0, column=0, sticky="w", padx=2)
        ttk.Checkbutton(opts, text="Hapus file asli setelah konversi format",
                        variable=self.var_delete_orig).grid(row=1, column=0, sticky="w", padx=2)
        ttk.Checkbutton(opts, text="Buka folder hasil setelah selesai",
                        variable=self.var_open_after).grid(row=2, column=0, sticky="w", padx=2)

        # Aksi + progress
        f_run = ttk.Frame(outer)
        f_run.grid(row=5, column=0, sticky="nsew", **pad)
        f_run.columnconfigure(0, weight=1)
        f_run.rowconfigure(3, weight=1)

        bar = ttk.Frame(f_run)
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)
        self.btn_go = ttk.Button(bar, text="Mulai Kompres", style="Go.TButton", command=self.start)
        self.btn_go.grid(row=0, column=0, sticky="w")
        self.btn_stop = ttk.Button(bar, text="Stop", command=self.stop, state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=6)
        ttk.Label(bar, textvariable=self.var_count, width=14, anchor="e").grid(row=0, column=2, padx=(6, 0))

        self.pb = ttk.Progressbar(f_run, mode="determinate", maximum=100)
        self.pb.grid(row=1, column=0, sticky="ew", pady=(8, 2))
        ttk.Label(f_run, textvariable=self.var_status, foreground="#333").grid(row=2, column=0, sticky="w")

        logf = ttk.LabelFrame(f_run, text="Log")
        logf.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        logf.columnconfigure(0, weight=1)
        logf.rowconfigure(0, weight=1)
        self.txt = tk.Text(logf, height=10, wrap="none", font=("Consolas", 9),
                           background="#fbfbfb", relief="flat")
        self.txt.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        sb = ttk.Scrollbar(logf, orient="vertical", command=self.txt.yview)
        sb.grid(row=0, column=1, sticky="ns", pady=6, padx=(0, 6))
        self.txt.configure(yscrollcommand=sb.set, state="disabled")

    def sync_mode(self):
        own = self.var_mode.get() == "own"
        state = "normal" if own else "disabled"
        self.e_out.configure(state=state)
        self.btn_out.configure(state=state)

    def update_quality_label(self):
        f = LABEL_FMT.get(self.var_fmt.get(), "JPEG")
        q = int(float(self.var_quality.get()))
        note = "" if f in ("JPEG", "WEBP") else " (PNG lossless)"
        self.lbl_q.configure(text=f"nilai: {q}{note}")

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
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.txt.configure(state="normal")
                    self.txt.insert("end", payload + "\n")
                    self.txt.see("end")
                    self.txt.configure(state="disabled")
                elif kind == "progress":
                    done, total, name = payload
                    pct = 0 if not total else done * 100.0 / total
                    self.pb.configure(value=pct)
                    self.var_count.set(f"{done} / {total}")
                    if name:
                        self.var_status.set(f"{pct:.0f}%  ·  {name}")
                elif kind == "status":
                    self.var_status.set(payload)
                elif kind == "done":
                    self.finish_ui()
        except queue.Empty:
            pass
        self.root.after(120, self.pump)

    # ---------- run ----------
    def start(self):
        if self.worker and self.worker.is_alive():
            return
        in_dir = self.var_in.get().strip()
        if not in_dir or not os.path.isdir(in_dir):
            messagebox.showerror(APP_NAME, "Folder sumber belum dipilih / tidak ditemukan.")
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
        }

        self.cancel.clear()
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")
        self.pb.configure(value=0)
        self.btn_go.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.save_config()

        self.worker = threading.Thread(target=self.run_job, args=(opts,), daemon=True)
        self.worker.start()

    def stop(self):
        self.cancel.set()
        self.var_status.set("Menghentikan…")

    def run_job(self, o: dict):
        try:
            files = iter_sources(o["in_dir"], o["recursive"])
        except Exception as exc:
            self.log(f"[ERR] Gagal membaca folder: {exc}")
            self.q.put(("done", None))
            return

        total = len(files)
        self.log(f"Folder sumber : {o['in_dir']}")
        self.log(f"Folder tujuan : {o['out_dir']}" + ("  (in-place)" if o["in_place"] else ""))
        self.log(f"Format        : {o['fmt']}   Lebar maks: {o['box'] or 'tanpa resize'}   "
                 f"Kualitas: {o['quality']}")
        self.log(f"File ditemukan: {total}")
        self.log("-" * 72)
        if not total:
            self.q.put(("status", "Tidak ada file gambar yang cocok."))
            self.q.put(("done", None))
            return

        sum_before = sum_after = 0
        ok = skip = err = 0
        t0 = __import__("time").time()

        for idx, src in enumerate(files, 1):
            if self.cancel.is_set():
                self.log("-" * 72)
                self.log("[!] Dibatalkan oleh pengguna.")
                break
            name = os.path.relpath(src, o["in_dir"])
            self.q.put(("progress", (idx - 1, total, name)))
            dst = build_dest(src, o["in_dir"], o["out_dir"], o["fmt"], o["in_place"])
            tmp = os.path.join(o["out_dir"], f".~ic-{idx}.tmp")
            try:
                r = compress_one(src, tmp, o["box"], o["quality"], o["fmt"])
                if o["skip_bigger"] and r["new"] >= r["orig"] and os.path.abspath(dst) != os.path.abspath(src):
                    os.remove(tmp)
                    skip += 1
                    self.log(f"[SKIP] {name}  ({human(r['orig'])} -> {human(r['new'])}, tidak lebih kecil)")
                    continue

                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.replace(tmp, dst)
                ok += 1
                sum_before += r["orig"]
                sum_after += r["new"]
                save = (r["orig"] - r["new"]) / r["orig"] * 100 if r["orig"] else 0.0
                dim = f"{r['before'][0]}x{r['before'][1]} -> {r['after'][0]}x{r['after'][1]}"
                tail = ""
                if o["delete_orig"] and os.path.abspath(dst) != os.path.abspath(src):
                    try:
                        os.remove(src)
                        tail = "  [asli dihapus]"
                    except Exception as exc:
                        tail = f"  [gagal hapus asli: {exc}]"
                self.log(f"[OK]   {name}  {human(r['orig'])} -> {human(r['new'])}  "
                         f"(-{save:.0f}%)  {dim}{tail}")
            except Exception as exc:
                err += 1
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
                self.log(f"[ERR]  {name}: {exc}")

        self.q.put(("progress", (total, total, None)))
        dt = __import__("time").time() - t0
        self.log("-" * 72)
        self.log(f"Selesai dalam {dt:.1f}s  ·  OK {ok}  ·  dilewati {skip}  ·  gagal {err}")
        if ok:
            self.log(f"Total ukuran  : {human(sum_before)} -> {human(sum_after)}")
            if sum_before:
                self.log(f"Ruang dihemat : {(sum_before - sum_after) / sum_before * 100:.1f}%")
        self.q.put(("status", f"Selesai — {ok} file diproses."))
        self.last_out_dir = o["in_dir"] if o["in_place"] else o["out_dir"]
        if self.var_open_after.get() and self.last_out_dir:
            self.q.put(("log", f"[i] Membuka {self.last_out_dir}"))
            try:
                os.startfile(self.last_out_dir)  # noqa: S606
            except Exception as exc:
                self.q.put(("log", f"[ERR] Gagal membuka folder: {exc}"))
        self.q.put(("done", None))

    def finish_ui(self):
        self.btn_go.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.save_config()

    def on_close(self):
        self.save_config()
        if self.worker and self.worker.is_alive():
            if not messagebox.askokcancel(APP_NAME, "Proses masih berjalan. Hentikan dan keluar?"):
                return
            self.cancel.set()
        self.root.destroy()


# --------------------------------------------------------------------------- #
# Headless mode — drag & drop folder ke .exe, atau --cli dari terminal
# --------------------------------------------------------------------------- #

CLI_DEFAULTS = {
    "recursive": True,
    "box": 1920,
    "quality": 85,
    "fmt": "JPEG",
    "skip_bigger": True,
    "delete_orig": False,
}

USAGE = f"""{APP_NAME} v{APP_VER}

Pemakaian:
  ImageCompressor.exe                     buka GUI
  ImageCompressor.exe "D:\\foto"          GUI dengan folder sumber terisi
  ImageCompressor.exe --cli "D:\\foto"    proses langsung tanpa GUI (headless)

Opsi headless:
  --out DIR         folder tujuan (default: <folder>_compressed)
  --in-place        timpa di tempat (nama file mengikuti format keluaran)
  --width N         lebar maksimal px, 0 = tanpa resize (default: 1920)
  --quality N       kualitas JPEG/WebP 1-100 (default: 85)
  --format FMT      JPEG | WEBP | PNG (default: JPEG)
  --no-recursive    jangan telusuri subfolder
  --keep-bigger     tetap tulis hasil walau ukurannya tidak lebih kecil
  --delete-orig     hapus file asli setelah konversi format
  -h, --help        tampilkan bantuan ini

Menarik folder ke atas .exe = jalankan mode headless otomatis.
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


def run_headless(src_dir: str, o: dict) -> int:
    src_dir = os.path.abspath(src_dir)
    if not os.path.isdir(src_dir):
        say(f"Bukan folder: {src_dir}")
        if sys.stdout is None:
            popup(APP_NAME, f"Bukan folder:\n{src_dir}")
        return 2

    fmt = o["fmt"]
    in_place = o["in_place"]
    out_dir = src_dir if in_place else (o["out"] or src_dir + "_compressed")
    interactive = sys.stdout is None  # dijalankan dari Explorer / drag & drop

    try:
        files = iter_sources(src_dir, o["recursive"])
    except Exception as exc:
        say(f"[ERR] Gagal membaca folder: {exc}")
        if interactive:
            popup(APP_NAME, f"Gagal membaca folder:\n{exc}")
        return 1

    if not files:
        say("Tidak ada file gambar yang cocok.")
        if interactive:
            popup(APP_NAME, f"Tidak ada file gambar di:\n{src_dir}")
        return 1

    if not in_place:
        os.makedirs(out_dir, exist_ok=True)

    say(f"{APP_NAME} v{APP_VER}  ·  headless")
    say(f"Folder sumber : {src_dir}")
    say(f"Folder tujuan : {out_dir}" + ("  (in-place)" if in_place else ""))
    say(f"Format        : {fmt}   Lebar maks: {o['box'] or 'tanpa resize'}   "
        f"Kualitas: {o['quality']}")
    say(f"File ditemukan: {len(files)}")
    say("-" * 72)

    ok = skip = err = 0
    sum_before = sum_after = 0
    failures: list[str] = []

    for idx, src in enumerate(files, 1):
        name = os.path.relpath(src, src_dir)
        dst = build_dest(src, src_dir, out_dir, fmt, in_place)
        tmp = os.path.join(out_dir, f".~ic-{idx}.tmp")
        try:
            r = compress_one(src, tmp, o["box"], o["quality"], fmt)
            if o["skip_bigger"] and r["new"] >= r["orig"] and os.path.abspath(dst) != os.path.abspath(src):
                os.remove(tmp)
                skip += 1
                say(f"[{idx}/{len(files)}] SKIP  {name}  ({human(r['orig'])} -> {human(r['new'])}, "
                    "tidak lebih kecil)")
                continue

            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.replace(tmp, dst)
            ok += 1
            sum_before += r["orig"]
            sum_after += r["new"]
            save = (r["orig"] - r["new"]) / r["orig"] * 100 if r["orig"] else 0.0
            tail = ""
            if o["delete_orig"] and os.path.abspath(dst) != os.path.abspath(src):
                try:
                    os.remove(src)
                    tail = "  [asli dihapus]"
                except Exception as exc:
                    tail = f"  [gagal hapus asli: {exc}]"
            say(f"[{idx}/{len(files)}] OK    {name}  {human(r['orig'])} -> {human(r['new'])}  "
                f"(-{save:.0f}%){tail}")
        except Exception as exc:
            err += 1
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass
            failures.append(f"{name}: {exc}")
            say(f"[{idx}/{len(files)}] ERR   {name}: {exc}")

    say("-" * 72)
    say(f"Selesai  ·  OK {ok}  ·  dilewati {skip}  ·  gagal {err}")
    if ok:
        say(f"Total ukuran  : {human(sum_before)} -> {human(sum_after)}")
        if sum_before:
            say(f"Ruang dihemat : {(sum_before - sum_after) / sum_before * 100:.1f}%")

    if interactive:
        saved = ""
        if ok and sum_before:
            saved = (f"\nTotal ukuran: {human(sum_before)} -> {human(sum_after)} "
                     f"(hemat {(sum_before - sum_after) / sum_before * 100:.1f}%)")
        body = (f"{ok} berhasil  ·  {skip} dilewati  ·  {err} gagal  "
                f"(dari {len(files)} file){saved}\n\nHasil ada di:\n{out_dir}")
        if failures:
            body += "\n\nGagal:\n" + "\n".join(failures[:5])
        popup(f"{APP_NAME} — selesai", body)
        try:
            os.startfile(out_dir)  # noqa: S606
        except Exception:
            pass

    return 0 if not err else 1


def parse_cli(argv: list[str]) -> dict | None:
    """Parse argumen headless. Return dict opsi, atau None kalau tidak valid."""
    o = dict(CLI_DEFAULTS)
    o["out"] = None
    o["in_place"] = False
    o["dir"] = None

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
        elif os.path.isdir(a):
            o["dir"] = os.path.abspath(a)
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
            popup(f"{APP_NAME} — bantuan", USAGE)
        return 0
    if any(a in ("-V", "--version") for a in argv):
        say(f"{APP_NAME} v{APP_VER}")
        return 0

    # Drag & drop folder ke .exe => tidak ada console (stdout None) => langsung proses.
    has_dir = any(os.path.isdir(a) for a in argv)
    if "--cli" in argv or (has_dir and sys.stdout is None):
        opts = parse_cli(argv)
        if opts is None:
            return 1
        if not opts["dir"]:
            say(USAGE)
            if sys.stdout is None:
                popup(f"{APP_NAME} — bantuan", USAGE)
            return 2
        return run_headless(opts["dir"], opts)

    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    preset = None
    for arg in argv:
        if os.path.isdir(arg):
            preset = os.path.abspath(arg)
            break

    root = tk.Tk()
    App(root, preset)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
