"""GUI v1.3.6 — tema cerah, panel pratinjau sebelum-sesudah, drag & drop.

Layout:
  [+------------------------------------+-----------------------+
   |  Header + pratinjau                |  1 PENGATURAN         |
   |  +--------------- +---------------+ |     folder sumber     |
   |  | Pratinjau Interaktif (slider) | |     folder tujuan     |
   |  +-------------------------------+ |  2 KUALITAS           |
   |  [ Mulai Kompres ] [ Stop ] [ ... ]|     lebar, format, q  |
   |  progress + status + log           |     worker paralel    |
   |                                    |  3 OPSI               |
   +------------------------------------+-----------------------+

Widget custom ada di ui_kit.py. File ini hanya mengurus susunan + perilaku.
"""

from __future__ import annotations

import os
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

import ui_kit as ui

from image_compressor import EXTS, iter_sources

APP_NAME = "Image Compressor"

PREVIEW_PX = 520   # lebar kanvas pratinjau
PREVIEW_PY = 340   # tinggi kanvas pratinjau


def _ico_path() -> str | None:
    """Lokasi app.ico: di folder skrip saat source, atau dalam bundle Nuitka."""
    import sys
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(base, "app.ico")
    return p if os.path.exists(p) else None


# --------------------------------------------------------------------------- #
# Drag & drop asli Windows (WM_DROPFILES) — tanpa dependensi tambahan
# --------------------------------------------------------------------------- #


def enable_drop(target: tk.Misc, on_drop) -> bool:
    """Terima file/folder yang ditarik ke window. Return False kalau gagal.

    Tk tidak punya hook untuk WM_DROPFILES, jadi kita tambal WndProc-nya
    lewat ctypes. Layar High-DPI: DropFiles pakai koordinat fisik, jadi
    titiknya dikembalikan dalam koordinat canvas.
    """
    try:
        import ctypes
        from ctypes import wintypes

        target.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(wintypes.HWND(target.winfo_id())) or target.winfo_id()
        ctypes.windll.shell32.DragAcceptFiles(hwnd, True)

        user32 = ctypes.windll.user32
        GWLP_WNDPROC = -4
        WM_DROPFILES = 0x0233

        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
            wintypes.WPARAM, wintypes.LPARAM,
        )

        def _read_paths(hdrop) -> list[str]:
            shell32 = ctypes.windll.shell32
            # ABI: tanpa restype/argtypes, hdrop/HANDLE 64-bit dipotong jadi
            # int32 -> DragQueryFileW mengembalikan sampah / crash.
            shell32.DragQueryFileW.restype = wintypes.UINT
            shell32.DragQueryFileW.argtypes = [
                ctypes.c_void_p, wintypes.UINT, ctypes.c_wchar_p,
                wintypes.UINT,
            ]
            shell32.DragFinish.argtypes = [ctypes.c_void_p]
            shell32.DragFinish.restype = None

            h = ctypes.c_void_p(hdrop)
            n = shell32.DragQueryFileW(h, 0xFFFFFFFF, None, 0)
            out = []
            for i in range(n):
                need = shell32.DragQueryFileW(h, i, None, 0) + 1
                buf = ctypes.create_unicode_buffer(need)
                if shell32.DragQueryFileW(h, i, buf, need):
                    out.append(buf.value)
            return out

        box = {"old": None}   # prosedur asli; diisi sesudah subclass terpasang

        def _proc(h, msg, wp, lp):
            if msg == WM_DROPFILES:
                paths = []
                try:
                    paths = _read_paths(wp)
                except Exception:
                    paths = []
                finally:
                    try:
                        ctypes.windll.shell32.DragFinish(ctypes.c_void_p(wp))
                    except Exception:
                        pass
                if paths:
                    target.after(1, lambda: on_drop(paths))
                return 0
            old = box["old"]
            if old is None:
                return user32.DefWindowProcW(h, msg, wp, lp)
            return user32.CallWindowProcW(old, h, msg, wp, lp)

        # ABI: tanpa restype/argtypes, pointer 64-bit dipotong jadi int32
        # -> access violation. Set eksplisit sebelum dipakai.
        user32.CallWindowProcW.restype = ctypes.c_ssize_t
        user32.CallWindowProcW.argtypes = [
            ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
            wintypes.WPARAM, wintypes.LPARAM,
        ]
        user32.DefWindowProcW.restype = ctypes.c_ssize_t
        user32.DefWindowProcW.argtypes = user32.CallWindowProcW.argtypes
        try:
            set_long = user32.SetWindowLongPtrW
        except AttributeError:      # 32-bit: namanya SetWindowLongW
            set_long = user32.SetWindowLongW
        set_long.restype = ctypes.c_void_p
        set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]

        proc = WNDPROC(_proc)
        box["old"] = set_long(hwnd, GWLP_WNDPROC, ctypes.cast(proc, ctypes.c_void_p))
        target._drop_proc = proc    # cegah GC
        target._drop_old = box["old"]
        # Daftarkan HWND yang sudah dipasangi drop supaya pemanggil bisa cek.
        _INSTALLED.add(hwnd)
        return True
    except Exception:
        return False


_INSTALLED: set = set()


def drop_installed() -> bool:
    """True kalau hook WM_DROPFILES berhasil dipasang di setidaknya satu window."""
    return bool(_INSTALLED)


# --------------------------------------------------------------------------- #
# Panel pratinjau interaktif: gambar "sesudah" + slider pembanding
# --------------------------------------------------------------------------- #


class ComparePanel(tk.Canvas):
    """Kanvas yang menampilkan 'sesudah' penuh, 'sebelum' terpotong slider."""

    def __init__(self, master, width: int = PREVIEW_PX, height: int = PREVIEW_PY):
        super().__init__(master, width=width, height=height, highlightthickness=0,
                         bd=0, bg=ui.theme()["chip"])
        self._img_b = None            # PIL Image (asli, belum di-resize)
        self._img_a = None
        self._ph_b = self._ph_a = None   # PhotoImage
        self._keep = {}               # semua PhotoImage hidup (anti-GC)
        self._split = 0.5
        self._drag = False
        self._empty_text = "Tarik gambar ke sini"
        self._hover = False

        # --- zoom & pan ---
        self._zoom = 1.0          # 1.0 = pas (fit). >1 = diperbesar.
        self._pan_x = 0.0         # offset geser dalam px gambar
        self._pan_y = 0.0
        self._panning = False
        self._pan_from = (0, 0)
        self._fit_scale = 1.0     # skala fit yang dihitung ulang tiap redraw

        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        # roda = zoom, Ctrl+roda = pan horizontal, Shift roda = pan vertikal
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Control-MouseWheel>", self._wheel)
        self.bind("<Shift-MouseWheel>", self._wheel)
        # klik tengah = reset ke fit
        self.bind("<ButtonPress-2>", lambda _e: self.reset_zoom())
        self.bind("<Control-ButtonPress-1>", self._pan_press)
        self.bind("<Control-B1-Motion>", self._pan_move)
        self.bind("<Control-ButtonRelease-1>", self._pan_release)
        self.configure(cursor="sb_h_double_arrow")
        ui.register(self)

    # --- zoom & pan ---
    def set_zoom(self, z: float, anchor: tuple[float, float] | None = None) -> None:
        """Ubah zoom, pertahankan titik `anchor` (koordinat layar) tetap di tempat.

        Rumus: titik gambar di bawah kursor harus punya koordinat gambar yang
        sama sebelum dan sesudah zoom, sehingga bagian yang dilihat tidak
        'melompat'. Dengan gx = w/2 + pan_x dan Gx = (ax - gx)/zoom:

            (ax - gx') / z'  ==  (ax - gx) / z
            gx' = ax - (ax - gx) * (z'/z)
            pan_x' = gx' - w/2 = (ax - w/2) - (ax - w/2 - pan_x) * k
        """
        z = max(0.2, min(8.0, float(z)))
        if abs(z - self._zoom) < 1e-6:
            return
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        ax, ay = anchor if anchor else (w / 2, h / 2)
        k = z / self._zoom
        self._pan_x = (ax - w / 2) - (ax - w / 2 - self._pan_x) * k
        self._pan_y = (ay - h / 2) - (ay - h / 2 - self._pan_y) * k
        self._zoom = z
        self._clamp_pan()
        self._crop_key = None
        self.redraw()

    def zoom_by(self, factor: float, anchor=None) -> None:
        self.set_zoom(self._zoom * factor, anchor)

    def reset_zoom(self) -> None:
        self._zoom = 1.0
        self._pan_x = self._pan_y = 0.0
        self._crop_key = None
        self.redraw()

    def _max_pan(self) -> tuple[float, float]:
        """Batas geser supaya gambar tidak bisa lepas dari kanvas."""
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        sc = getattr(self, "_fit_scale", 1.0) or 1.0
        iw = getattr(self, "_img_a", None)
        if iw is None:
            return 0.0, 0.0
        gw = iw.width * sc * self._zoom
        gh = iw.height * sc * self._zoom
        return max(0.0, (gw - w) / 2), max(0.0, (gh - h) / 2)

    def _clamp_pan(self) -> None:
        mx, my = self._max_pan()
        self._pan_x = max(-mx, min(mx, self._pan_x))
        self._pan_y = max(-my, min(my, self._pan_y))

    def _wheel(self, e):
        if self._ph_a is None:
            return
        ctrl = bool(e.state & 0x0004)
        shift = bool(e.state & 0x0001)
        if ctrl:
            self._pan_x += 40 if e.delta > 0 else -40
        elif shift:
            self._pan_y += 40 if e.delta > 0 else -40
        else:
            step = 1.15 if e.delta > 0 else 1 / 1.15
            self.zoom_by(step, (e.x, e.y))
            return
        self._clamp_pan()
        self._crop_key = None
        self.redraw()

    def _pan_press(self, e):
        if self._ph_a is None:
            return
        self._panning = True
        self._pan_from = (e.x, e.y)
        self.configure(cursor="fleur")

    def _pan_move(self, e):
        if not self._panning:
            return
        dx = e.x - self._pan_from[0]
        dy = e.y - self._pan_from[1]
        self._pan_from = (e.x, e.y)
        self._pan_x += dx
        self._pan_y += dy
        self._clamp_pan()
        self._crop_key = None
        self.redraw()

    def _pan_release(self, _e=None):
        self._panning = False
        self.configure(cursor="sb_h_double_arrow")

    def _zoom_click(self, tag: str) -> None:
        if tag == "zin":
            self.zoom_by(1.25)
        elif tag == "zout":
            self.zoom_by(1 / 1.25)
        elif tag == "zfit":
            self.reset_zoom()

    # --- data ---
    def set_images(self, before: Image.Image, after: Image.Image) -> None:
        self._img_b, self._img_a = before, after
        self._zoom = 1.0
        self._pan_x = self._pan_y = 0.0
        self._keep.clear()
        # Paksa bangun ulang: redraw() hanya membangun ulang kalau PhotoImage
        # dianggap mati, sehingga _fit_scale bisa tertinggal dari gambar lama
        # (gambar baru jadi salah skala/tak di-fit).
        self._ph_a = self._ph_b = None
        self._fit_scale = 1.0
        self._build_photos()
        self.redraw()

    def clear(self) -> None:
        self._img_b = self._img_a = None
        self._ph_b = self._ph_a = None
        self.redraw()

    @property
    def split(self) -> float:
        return self._split

    # --- ukuran ---
    def _fit(self) -> None:
        self._build_photos()
        self.redraw()

    def _build_photos(self) -> None:
        w = max(80, self.winfo_width() - 4)
        h = max(80, self.winfo_height() - 4)
        try:
            if self._img_b is not None:
                ib = self._img_b.copy()
                ib.thumbnail((w, h), Image.LANCZOS)
                self._ph_b = ImageTk.PhotoImage(ib)
                self._fit_b = ib.size
                self._keep["b"] = self._ph_b
            if self._img_a is not None:
                ia = self._img_a.copy()
                ia.thumbnail((w, h), Image.LANCZOS)
                self._ph_a = ImageTk.PhotoImage(ia)
                self._fit_a = ia.size
                self._keep["a"] = self._ph_a
                # skala fit murni (tanpa zoom): dipakai untuk hitung zoom nyata
                src = self._img_a
                base = min(w / src.width, h / src.height)
                self._fit_scale = max(1e-6, base)
        except Exception:
            self._ph_a = self._ph_b = None
        self._crop_key = None

    # --- interaksi ---
    def _enter(self, _e=None):
        self._hover = True
        self.redraw()

    def _leave(self, _e=None):
        self._hover = False
        self.redraw()

    def _press(self, e):
        if self._ph_a is None:
            return
        # Klik di luar gambar (area letterbox) tidak boleh menggeser pembatas.
        if not self._inside_image(e.x, e.y):
            return
        self._drag = True
        self._set_split(e.x)

    def _move(self, e):
        if self._drag:
            self._set_split(e.x)

    def _release(self, _e=None):
        self._drag = False
        self.configure(cursor="sb_h_double_arrow")
        self.redraw()

    def _inside_image(self, x: float, y: float) -> bool:
        left, top, gw, gh = self._geom()
        return left <= x <= left + gw and top <= y <= top + gh

    def _geom(self):
        """(left, top, gw, gh) gambar di layar, sesuai redraw()."""
        sc = max(1e-6, getattr(self, "_fit_scale", 1.0) or 1.0)
        iw = getattr(self._img_a, "width", self.winfo_width()) or self.winfo_width()
        ih = getattr(self._img_a, "height", self.winfo_height()) or self.winfo_height()
        gw = iw * sc * self._zoom
        gh = ih * sc * self._zoom
        gx = self.winfo_width() / 2 + self._pan_x
        gy = self.winfo_height() / 2 + self._pan_y
        return gx - gw / 2, gy - gh / 2, gw, gh

    def _set_split(self, x: float):
        """Ubah pembatas dari posisi x di kanvas -> rasio 0..1 terhadap GAMBAR."""
        left, _, gw, _ = self._geom()
        if gw <= 0:
            return
        self._split = min(1.0, max(0.0, (x - left) / gw))
        self.redraw()

    # --- gambar ---
    def redraw(self) -> None:
        self.delete("all")
        p = ui.theme()
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        self.configure(bg=p["chip"])

        # PhotoImage bisa mati (GC/ganti ukuran) -> bangun ulang sebelum dipakai
        if self._img_a is not None and not self._alive(self._ph_a):
            self._build_photos()
        if self._ph_a is None:
            self.create_text(w / 2, h / 2 - 10, text=self._empty_text, fill=p["text_dim"],
                             justify="center", font=ui.font(10))
            return

        cx, cy = w / 2, h / 2

        # --- ukuran gambar di layar: fit x zoom, digeser pan ---
        sc = max(1e-6, getattr(self, "_fit_scale", 1.0) or 1.0)
        gw = (getattr(self._img_a, "width", w)) * sc * self._zoom
        gh = (getattr(self._img_a, "height", h)) * sc * self._zoom
        gx = cx + self._pan_x
        gy = cy + self._pan_y
        left = gx - gw / 2
        top = gy - gh / 2

        box = (left, top, gx + gw / 2, gy + gh / 2)
        if box[2] < 0 or box[0] > w or box[3] < 0 or box[1] > h:
            # tergeser keluar kanvas sepenuhnya — biar tidak bingung, reset
            self.reset_zoom()
            return

        # 'sesudah' = alas penuh
        self.create_image(gx, gy, image=self._fit_photo("a", gw, gh), anchor="center")

        # ---- 'sebelum' digambar menimpa bagian KIRI gambar ----
        # Slider disimpan sebagai rasio 0..1 terhadap GAMBAR (bukan kanvas),
        # supaya garis pembatas selalu tepat di batas potongan walau gambar
        # tidak selebar kanvas (letterbox) atau sedang di-zoom/digeser.
        gx_split = left + gw * self._split          # x garis, koordinat kanvas
        gx_split = max(0.0, min(float(w), gx_split))  # garis selalu di kanvas

        if self._split > 0 and self._img_b is not None:
            crop = self._crop_before_scaled(self._split, gw, gh)
            if crop is not None:
                # crop = lebar `_split * gw`. Anker di 'w' (kiri) lalu taruh
                # tepat di tepi kiri gambar -> tidak ada pergeseran.
                self.create_image(left, top, image=crop, anchor="nw")

        # bingkai tipis supaya tepi gambar jelas di atas latar canvas
        self._frame_box(w, h, box, p)

        # garis pembanding + handle (persis di batas potongan)
        sx = gx_split
        line_col = p["accent_text"]
        self.create_line(sx, 0, sx, h, fill=line_col, width=2)
        r = 13
        hcol = p["accent"] if (self._hover or self._drag) else p["panel2"]
        self.create_oval(sx - r, cy - r, sx + r, cy + r, fill=hcol,
                         outline=line_col, width=2)
        # ikon panah kiri-kanan di handle
        for dx in (-6, 6):
            s = 4
            x0 = sx + dx
            self.create_polygon(
                x0 - s if dx < 0 else x0 + s, cy,
                x0, cy - s + 1,
                x0, cy + s - 1,
                fill=line_col, outline=line_col,
            )

        # label chip: kiri nempel kiri, kanan nempel kanan (tidak pernah terpotong)
        self._chip_right(8, 8, "Sebelum", p)
        self._chip_left(w - 8, 8, "Sesudah", p)

        # keterangan arah: geser ke kiri = lebih banyak 'sebelum' terlihat
        if self._ph_a is not None and self._img_b is not None:
            self.create_text(w / 2, h - 34,
                             text=f"{self._split * 100:.0f}% sebelum · "
                                  f"{(1 - self._split) * 100:.0f}% sesudah",
                             fill=p["text_dim"], font=ui.font(8))

        # ---- indikator zoom + tombol − / + / Fit (kanan bawah) ----
        ztxt = f"{self._zoom * 100:.0f}%"
        bh_ = 24
        bx1 = w - 8
        tw = self._tw(ztxt) + 20
        x_fit = bx1 - 46
        x_plus = x_fit - 34
        x_minus = x_plus - 34
        x_val = x_minus - tw
        y0 = h - bh_ - 8
        for x0, x1, label, tag in (
            (x_val, x_minus, ztxt, "zv"),
            (x_minus, x_plus, "−", "zout"),
            (x_plus, x_fit, "+", "zin"),
            (x_fit, bx1, "Fit", "zfit"),
        ):
            self.create_polygon(ui.rounded_points(x0, y0, x1, y0 + bh_, 6),
                                fill=p["chip"], outline=p["border"], width=1,
                                tags=(tag,))
            self.tag_bind(tag, "<Button-1>", lambda _e, t=tag: self._zoom_click(t))
            self.create_text((x0 + x1) / 2, y0 + bh_ / 2, text=label,
                             fill=p["text"], font=ui.font(9, True), tags=(tag,))
            self.tag_bind(tag, "<Enter>", lambda _e: self.configure(cursor="hand2"))
            self.tag_bind(tag, "<Leave>", lambda _e: self.configure(
                cursor="sb_h_double_arrow"))

    def _alive(self, ph) -> bool:
        if ph is None:
            return False
        try:
            return str(ph) in self.tk.call("image", "names")
        except Exception:
            return False

    def _fit_photo(self, key: str, gw: float, gh: float):
        """PhotoImage yang sudah diskalakan ke gw x gh, di-cache per ukuran.

        Dipakai supaya zoom benar-benar mengubah resolusi tampilan (bukan
        sekadar memperbesar bitmap hasil fit).
        """
        key = (key, int(gw), int(gh))
        ph = self._keep.get(key)
        if ph is not None:
            return ph
        src = self._img_a if key[0] == "a" else self._img_b
        if src is None:
            return None
        try:
            im = src.copy()
            im = im.resize((max(1, int(gw)), max(1, int(gh))), Image.LANCZOS)
            ph = ImageTk.PhotoImage(im)
            self._keep[key] = ph
            # batasi cache supaya memori tidak meledak saat zoom bolak-balik
            if len(self._keep) > 24:
                for k in list(self._keep.keys()):
                    if k in ("a", "b"):
                        continue
                    self._keep.pop(k, None)
                    if len(self._keep) <= 16:
                        break
            return ph
        except Exception:
            return None

    def _frame_box(self, w: float, h: float, box, p: dict) -> None:
        """Beri sedikit bayangan/tepi supaya batas gambar jelas kalau lebih kecil."""
        x0, y0, x1, y1 = box
        if x0 > 0 or y0 > 0 or x1 < w or y1 < h:
            self.create_rectangle(max(0, x0), max(0, y0), min(w, x1), min(h, y1),
                                  outline=p["border"], width=1)

    def _crop_before_scaled(self, split: float, gw: float, gh: float):
        """Irisan kiri gambar 'sebelum' selebar `split` (rasio 0..1) dari gambar.

        Dipotong di ruang gambar (bukan ditutup kotak warna) supaya tidak ada
        artefak, dan tetap benar walau gambar sedang di-zoom / digeser.
        Lebar hasil SELALU `split * gw` sehingga bisa ditempel persis di tepi
        kiri gambar tanpa pergeseran.
        """
        src = self._img_b
        if src is None or gw <= 0:
            return None
        split = max(0.0, min(1.0, float(split)))
        if split <= 0:
            return None
        full_w = max(1, int(round(gw)))
        full_h = max(1, int(round(gh)))
        wpx = max(1, int(round(full_w * split)))
        key = ("bcut", split, full_w, full_h)
        ph = self._keep.get(key)
        if ph is not None:
            return ph
        try:
            im = src.copy()
            # skala ke ukuran layar penuh dulu, baru potong -> tidak ada rounding
            if split < 1.0:
                full = im.resize((full_w, full_h), Image.LANCZOS)
                part = full.crop((0, 0, wpx, full_h))
            else:
                part = im.resize((full_w, full_h), Image.LANCZOS)
            ph = ImageTk.PhotoImage(part)
            self._keep[key] = ph
            self._crop_key = key
            return ph
        except Exception:
            return None

    def _crop_before(self, cut: int, bw: float, bh: float):
        """Ambil irisan kiri gambar 'sebelum' selebar `cut` px, cache per (cut,size)."""
        if self._img_b is None or bw <= 0:
            return None
        key = (cut, int(bw), int(bh))
        if getattr(self, "_crop_key", None) == key and self._keep.get(key):
            return self._keep[key]
        try:
            src = self._img_b.copy()
            src.thumbnail((max(1, int(self.winfo_width())), max(1, int(self.winfo_height()))),
                          Image.LANCZOS)
            frac = min(1.0, cut / max(1.0, bw))
            wpx = max(1, int(round(src.width * frac)))
            part = src.crop((0, 0, wpx, src.height))
            ph = ImageTk.PhotoImage(part)
            self._keep[key] = ph      # simpan; jangan biarkan di-GC
            self._crop_key = key
            self._crop_ph = ph
            return ph
        except Exception:
            return None

    def _tw(self, text: str) -> int:
        import tkinter.font as tkfont

        f = tkfont.Font(family=ui.FONT_UI, size=9)
        return f.measure(text)

    def _chip_right(self, x: float, y: float, text: str, p: dict) -> None:
        """Chip dengan sudut kiri di x."""
        w = self._tw(text) + 24
        h = 26
        self.create_polygon(ui.rounded_points(x, y, x + w, y + h, h / 2),
                            fill=p["chip"], outline=p["border"], width=1)
        self.create_text(x + w / 2, y + h / 2, text=text, fill=p["text"],
                         font=ui.font(9, True))

    def _chip_left(self, x: float, y: float, text: str, p: dict) -> None:
        """Chip dengan sudut KANAN di x (anchor kanan)."""
        w = self._tw(text) + 24
        h = 26
        x0 = x - w
        self.create_polygon(ui.rounded_points(x0, y, x, y + h, h / 2),
                            fill=p["chip"], outline=p["border"], width=1)
        self.create_text(x0 + w / 2, y + h / 2, text=text, fill=p["text"],
                         font=ui.font(9, True))


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #


class GUI:
    """Rakit UI v1.2.0 di atas mesin kompresi yang sudah ada.

    Semua akses ke state mesin lewat `self.core` (instance App lama) supaya
    logika kompresi/pratinjau tidak diduplikasi di sini.
    """

    def __init__(self, root: tk.Tk, core):
        self.root = root
        self.core = core
        ui.init(root)
        ui.dark_titlebar(root)
        root.title(f"{APP_NAME} v{core.APP_VER}")
        ic = _ico_path()
        if ic:
            try:
                root.iconbitmap(ic)
            except tk.TclError:
                pass
        root.minsize(1120, 780)
        root.configure(bg=ui.theme()["bg"])
        self._build()
        self._wire()
        self.refresh_live()

    # ---------- susun ----------
    def _build(self):
        p = ui.theme()
        root = self.root
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        self._header()
        self._left()
        self._right()
        self._footer()

    def _header(self):
        p = ui.theme()
        hdr = tk.Frame(self.root, bg=p["bg"])
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(14, 6))
        hdr.columnconfigure(1, weight=1)

        box = tk.Frame(hdr, bg=p["bg"])
        box.grid(row=0, column=0, sticky="w")
        title = tk.Frame(box, bg=p["bg"])
        title.pack(side="left")
        ui.Label(title, APP_NAME, size=13, bold=True, bg=p["bg"]).pack(anchor="w")

        right = tk.Frame(hdr, bg=p["bg"])
        right.grid(row=0, column=2, sticky="e")
        self.badge_heic = ui.Badge(right, "HEIC siap" if self.core.HEIC_SUPPORT else "HEIC off")
        self.badge_heic.pack(side="left", padx=(0, 10))

        ui.Divider(self.root).grid(row=0, column=0, columnspan=2, sticky="sew",
                                   padx=18, pady=(0, 0))

    def _left(self):
        """Panel kiri: pratinjau interaktif + tombol aksi + status + log."""
        p = ui.theme()
        col = tk.Frame(self.root, bg=p["bg"])
        col.grid(row=1, column=0, sticky="nsew", padx=(18, 9), pady=(10, 14))
        col.columnconfigure(0, weight=1)
        col.rowconfigure(1, weight=1)

        # --- kartu pratinjau ---
        card = ui.Card(col)
        card.grid(row=0, column=0, sticky="nsew")
        card.body.columnconfigure(0, weight=1)
        card.body.rowconfigure(1, weight=1)

        head = tk.Frame(card.body, bg=p["panel"])
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8))
        head.columnconfigure(0, weight=1)
        ui.Label(head, "Pratinjau Interaktif", size=11, bold=True,
                 bg=p["panel"]).grid(row=0, column=0, sticky="w")
        self.lbl_prev = ui.Label(head, "Belum ada contoh", size=9,
                                 color=p["text_dim"], bg=p["panel"])
        self.lbl_prev.grid(row=1, column=0, sticky="w", pady=(2, 0))


        self.compare = ComparePanel(card.body, PREVIEW_PX, PREVIEW_PY)
        self.compare.grid(row=1, column=0, sticky="nsew", padx=14)

        # chip ukuran di bawah kanvas
        chips = tk.Frame(card.body, bg=p["panel"])
        chips.grid(row=2, column=0, sticky="ew", padx=14, pady=(10, 12))
        chips.columnconfigure(2, weight=1)
        self.chip_b = ui.Badge(chips, "Sebelum —", color_key="text_dim")
        self.chip_b.grid(row=0, column=0, sticky="w")
        self.chip_a = ui.Badge(chips, "Sesudah —", color_key="ok")
        self.chip_a.grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.chip_dims = ui.Label(chips, "", size=9, color=p["text_dim"], bg=p["panel"])
        self.chip_dims.grid(row=0, column=2, sticky="e")

        # --- bar tombol aksi ---
        act = tk.Frame(col, bg=p["bg"])
        act.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        act.columnconfigure(2, weight=1)
        self.btn_go = ui.Btn(act, "Mulai Kompres", variant="primary",
                             icon="play", height=38, fontsize=10, command=self.start)
        self.btn_go.grid(row=0, column=0, sticky="w")
        self.btn_stop = ui.Btn(act, "Stop", variant="secondary", icon="stop",
                              height=38, command=self.stop)
        self.btn_stop.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.btn_stop.set_disabled(True)
        self.btn_open = ui.Btn(act, "Buka hasil", variant="ghost", icon="folder",
                              height=38, command=self.open_result)
        self.btn_open.grid(row=0, column=3, sticky="e")

        # --- progress + status ---
        prog = tk.Frame(col, bg=p["bg"])
        prog.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        prog.columnconfigure(0, weight=1)
        self.bar = ui.Progress(prog, 16)
        self.bar.grid(row=0, column=0, sticky="ew")
        self.lbl_count = ui.Label(prog, "0 / 0", size=9, color=p["text_dim"], bg=p["bg"])
        self.lbl_count.grid(row=0, column=1, sticky="e", padx=(10, 0))
        self.lbl_status = ui.Label(prog, "Siap.", size=9, color=p["text_dim"], bg=p["bg"])
        self.lbl_status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # --- log ---
        logcard = ui.Card(col)
        logcard.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        logcard.configure(height=210)
        col.rowconfigure(1, weight=3)
        col.rowconfigure(4, weight=1)
        logcard.body.columnconfigure(0, weight=1)
        logcard.body.rowconfigure(1, weight=1)
        row = tk.Frame(logcard.body, bg=p["panel"])
        row.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        row.columnconfigure(0, weight=1)
        ui.Label(row, "Log", size=10, bold=True, bg=p["panel"]).grid(row=0, column=0, sticky="w")
        ui.Btn(row, "Bersihkan", variant="ghost", height=26, fontsize=9,
               command=self.clear_log).grid(row=0, column=1, sticky="e")

        wrap = tk.Frame(logcard.body, bg=p["panel"])
        wrap.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)
        self.txt = tk.Text(wrap, height=8, wrap="none", bd=0, relief="flat",
                           font=(ui.FONT_MONO, 9), bg=p["chip"], fg=p["text"],
                           insertbackground=p["text"], padx=10, pady=8,
                           highlightthickness=1, highlightbackground=p["border"],
                           highlightcolor=p["border"])
        self.txt.grid(row=0, column=0, sticky="nsew")
        # Scrollbar native Windows selalu terang & tak bisa diwarnai;
        # pakai milik kita sendiri (Canvas tipis) supaya menyatu dengan tema.
        self.txt.grid_configure(padx=(0, 8))
        self.txt.configure(state="disabled")
        self.txt.bind("<MouseWheel>", self._on_wheel)
        self.txt.bind("<Key>", lambda _e: "break")
        self.txt.tag_configure("err", foreground=p["err"])
        self.txt.tag_configure("ok", foreground=p["ok"])
        self.txt.tag_configure("skip", foreground=p["warn"])
        self.txt.tag_configure("dim", foreground=p["text_dim"])

    def _right(self):
        """Sidebar kanan: 3 seksi bernomor, bisa di-scroll kalau jendela pendek."""
        p = ui.theme()
        side = tk.Frame(self.root, bg=p["bg"], width=440)
        side.grid(row=1, column=1, sticky="nsew", padx=(9, 18), pady=(10, 14))
        side.grid_propagate(False)
        self.root.columnconfigure(1, weight=0, minsize=440)

        # Canvas + scrollbar: tanpa ini, saat jendela tidak maximize isi panel
        # kanan tumpah ke bawah dan menabrak baris tombol di kolom kiri.
        cv = tk.Canvas(side, bg=p["bg"], highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(side, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=vsb.set)
        cv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        side.rowconfigure(0, weight=1)
        side.columnconfigure(0, weight=1)
        self.side_canvas = cv

        holder = tk.Frame(cv, bg=p["bg"])
        win = cv.create_window((0, 0), window=holder, anchor="nw")

        def _on_conf(_e=None):
            cv.itemconfigure(win, width=cv.winfo_width())
            cv.configure(scrollregion=cv.bbox("all"))
            # sembunyikan scrollbar kalau isi muat
            need = holder.winfo_reqheight() > cv.winfo_height()
            if need:
                vsb.grid()
            else:
                vsb.grid_remove()

        holder.bind("<Configure>", _on_conf)
        cv.bind("<Configure>", _on_conf)

        def _wheel_side(e):
            if holder.winfo_reqheight() > cv.winfo_height():
                cv.yview_scroll(-1 if e.delta > 0 else 1, "units")

        for w in (cv, holder):
            w.bind("<MouseWheel>", _wheel_side)

        card = ui.Card(holder)
        card.grid(row=0, column=0, sticky="nsew")
        holder.columnconfigure(0, weight=1)
        card.body.columnconfigure(0, weight=1)   # isi card melar mengikuti lebar
        self.side_holder = holder

        # ---- 1 · Sumber & tujuan ----
        ui.Section(card.body, "1", "Folder").grid(row=0, column=0, sticky="ew",
                                                  padx=14, pady=(14, 6))
        ui.Label(card.body, "Sumber", size=9, color=p["text_dim"],
                 bg=p["panel"]).grid(row=1, column=0, sticky="w", padx=14)
        s_in = tk.Frame(card.body, bg=p["panel"])
        s_in.grid(row=2, column=0, sticky="ew", padx=14, pady=(4, 0))
        s_in.columnconfigure(0, weight=1)
        self.e_in = ui.Entry(s_in, self.core.var_in, height=34)
        self.e_in.grid(row=0, column=0, sticky="ew")
        ui.IconBtn(s_in, "folder", command=self.pick_in).grid(row=0, column=1, padx=(6, 0))
        self.sw_recursive = ui.Switch(card.body, self.core.var_recursive,
                                      "Sertakan subfolder", height=26)
        self.sw_recursive.grid(row=3, column=0, sticky="w", padx=14, pady=(8, 0))

        # --- baris file terpilih: tombol Pilih File + info + bersihkan ---
        frow = tk.Frame(card.body, bg=p["panel"])
        frow.grid(row=4, column=0, sticky="ew", padx=14, pady=(10, 0))
        frow.columnconfigure(1, weight=1)
        ui.Btn(frow, "Pilih File", variant="secondary", icon="image",
               height=34, fontsize=9, command=self.pick_files).grid(row=0, column=0, sticky="w")
        self.lbl_files = ui.Label(frow, "", size=9, color=p["text_dim"], bg=p["panel"])
        self.lbl_files.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.btn_clear_files = ui.Btn(frow, "Bersihkan", variant="ghost",
                                      height=30, fontsize=9, command=self.clear_files)
        self.btn_clear_files.grid(row=0, column=2, sticky="e")
        self.btn_clear_files.set_disabled(True)
        ui.Label(card.body, "Pilih file tertentu (bisa banyak), atau tarik file ke jendela.",
                 size=8, color=p["text_dim"], bg=p["panel"]).grid(
            row=5, column=0, sticky="w", padx=14, pady=(2, 0))

        ui.Label(card.body, "Tujuan", size=9, color=p["text_dim"],
                 bg=p["panel"]).grid(row=6, column=0, sticky="w", padx=14, pady=(14, 0))
        # Radio ditumpuk VERTIKAL: 'Folder lain' di bawah 'Timpa di tempat'
        # supaya keduanya selalu terlihat, termasuk saat jendela sempit.
        mrow = tk.Frame(card.body, bg=p["panel"])
        mrow.grid(row=7, column=0, sticky="ew", padx=14, pady=(4, 0))
        self.rb_inplace = ui.Radio(mrow, "Timpa di tempat", self.core.var_mode,
                                   "inplace", command=self.on_mode)
        self.rb_inplace.grid(row=0, column=0, sticky="w")
        self.rb_own = ui.Radio(mrow, "Folder lain (pilih folder tujuan)",
                               self.core.var_mode, "own", command=self.on_mode)
        self.rb_own.grid(row=1, column=0, sticky="w", pady=(6, 0))

        s_out = tk.Frame(card.body, bg=p["panel"])
        s_out.grid(row=8, column=0, sticky="ew", padx=14, pady=(6, 0))
        s_out.columnconfigure(0, weight=1, minsize=60)
        self.e_out = ui.Entry(s_out, self.core.var_out, height=34)
        self.e_out.grid(row=0, column=0, sticky="ew")
        # Tombol folder tujuan harus SELALU terlihat: kolom 1 tidak boleh
        # melar, dan entry dibatasi supaya path panjang tidak mendorongnya keluar.
        s_out.columnconfigure(1, weight=0)
        self.btn_out = ui.IconBtn(s_out, "folder", command=self.pick_out)
        self.btn_out.grid(row=0, column=1, padx=(6, 0), sticky="e")

        ui.Divider(card.body).grid(row=9, column=0, sticky="ew", padx=14, pady=(14, 0))

        # ---- 2 · Kualitas ----
        ui.Section(card.body, "2", "Kualitas").grid(row=10, column=0, sticky="ew",
                                                    padx=14, pady=(12, 6))
        qrow = tk.Frame(card.body, bg=p["panel"])
        qrow.grid(row=11, column=0, sticky="ew", padx=14)
        qrow.columnconfigure(0, weight=1)
        ui.Label(qrow, "Lebar maksimal", size=9, color=p["text_dim"],
                 bg=p["panel"]).grid(row=0, column=0, sticky="w")
        self.lbl_w = ui.Label(qrow, "1920 px", size=9, bg=p["panel"])
        self.lbl_w.grid(row=0, column=1, sticky="e")
        self.slider_w = ui.Slider(card.body, self.core.var_width, 0, 4000,
                                  height=30, command=lambda _v: self._on_w())
        self.slider_w.grid(row=12, column=0, sticky="ew", padx=14, pady=(2, 0))

        qrow2 = tk.Frame(card.body, bg=p["panel"])
        qrow2.grid(row=13, column=0, sticky="ew", padx=14, pady=(8, 0))
        qrow2.columnconfigure(0, weight=1)
        ui.Label(qrow2, "Kualitas", size=9, color=p["text_dim"],
                 bg=p["panel"]).grid(row=0, column=0, sticky="w")
        self.lbl_q = ui.Label(qrow2, "", size=9, bg=p["panel"])
        self.lbl_q.grid(row=0, column=1, sticky="e")
        self.slider_q = ui.Slider(card.body, self.core.var_quality, 30, 100,
                                  height=30, command=lambda _v: self._on_q())
        self.slider_q.grid(row=14, column=0, sticky="ew", padx=14, pady=(2, 0))

        ui.Label(card.body, "Format keluaran", size=9, color=p["text_dim"],
                 bg=p["panel"]).grid(row=15, column=0, sticky="w", padx=14, pady=(10, 3))
        self.combo_fmt = ttk.Combobox(card.body, textvariable=self.core.var_fmt,
                                      state="readonly", values=list(self.core.FMT_LABEL.values()))
        self.combo_fmt.grid(row=16, column=0, sticky="ew", padx=14)
        self.combo_fmt.bind("<<ComboboxSelected>>", lambda _e: self.refresh_live())

        jrow = tk.Frame(card.body, bg=p["panel"])
        jrow.grid(row=17, column=0, sticky="ew", padx=14, pady=(10, 0))
        jrow.columnconfigure(0, weight=1)
        ui.Label(jrow, "Worker paralel", size=9, color=p["text_dim"],
                 bg=p["panel"]).grid(row=0, column=0, sticky="w")
        self.lbl_jobs = ui.Label(jrow, "", size=9, color=p["text_dim"], bg=p["panel"])
        self.lbl_jobs.grid(row=0, column=1, sticky="e")
        self.slider_j = ui.Slider(card.body, self.core.var_jobs, 0, 32,
                                  height=30, command=lambda _v: self._on_jobs())
        self.slider_j.grid(row=18, column=0, sticky="ew", padx=14, pady=(2, 0))

        ui.Divider(card.body).grid(row=19, column=0, sticky="ew", padx=14, pady=(14, 0))

        # ---- 3 · Opsi ----
        ui.Section(card.body, "3", "Opsi").grid(row=20, column=0, sticky="ew",
                                                padx=14, pady=(12, 4))
        self.sw_skip = ui.Switch(card.body, self.core.var_skip_bigger,
                                 "Lewati jika hasil tidak lebih kecil", height=26)
        self.sw_skip.grid(row=21, column=0, sticky="w", padx=14, pady=(6, 0))
        self.sw_delete = ui.Switch(card.body, self.core.var_delete_orig,
                                   "Hapus asli setelah konversi", height=26)
        self.sw_delete.grid(row=22, column=0, sticky="w", padx=14, pady=(6, 0))
        self.sw_open = ui.Switch(card.body, self.core.var_open_after,
                                 "Buka folder setelah selesai", height=26)
        self.sw_open.grid(row=23, column=0, sticky="w", padx=14, pady=(6, 14))

    def _footer(self):
        p = ui.theme()
        foot = tk.Frame(self.root, bg=p["bg"])
        foot.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 10))
        foot.columnconfigure(1, weight=1)
        self.lbl_foot = ui.Label(foot, f"v{self.core.APP_VER}", size=8,
                                 color=p["text_dim"], bg=p["bg"])
        self.lbl_foot.grid(row=0, column=0, sticky="w")
        self.lbl_hint = ui.Label(foot, "Tarik gambar/folder ke jendela ini",
                                 size=8, color=p["text_dim"], bg=p["bg"])
        self.lbl_hint.grid(row=0, column=2, sticky="e")

    # ---------- perilaku ----------
    def _wire(self):
        """Sambungkan widget baru ke state mesin + pasang drag & drop."""
        c = self.core
        # geser-geser yang memicu pratinjau ulang
        c.var_width.trace_add("write", lambda *_: self._on_w())
        c.var_quality.trace_add("write", lambda *_: self._on_q())
        c.var_fmt.trace_add("write", lambda *_: self.refresh_live())
        c.var_jobs.trace_add("write", lambda *_: self._on_jobs())
        c.var_mode.trace_add("write", lambda *_: self.on_mode())

        # Drag & drop: pasang ke root. Kalau gagal, coba widget anak (canvas
        # pratinjau) — di beberapa build Tk/Nuitka root di-subclass ulang oleh
        # Tk sendiri sehingga hook-nya hilang. Kegagalan TIDAK boleh senyap.
        ok = enable_drop(self.root, self.on_drop)
        if not ok:
            for w in (self.compare, self.txt):
                try:
                    if enable_drop(w, self.on_drop):
                        ok = True
                        break
                except Exception:
                    pass
        self.drop_ok = ok
        if not ok:
            try:
                self.set_status(
                    "Catatan: drag & drop tidak aktif di build ini — "
                    "pakai tombol 'Pilih Folder'."
                )
            except Exception:
                pass
        return ok

    # --- handler slider ---
    def _on_w(self):
        v = int(float(self.core.var_width.get() or 0))
        self.lbl_w.configure(text="tanpa resize" if v <= 0 else f"{v} px")
        self.compare.redraw()

    def _on_q(self):
        f = self.core.LABEL_FMT.get(self.core.var_fmt.get(), "JPEG")
        q = int(float(self.core.var_quality.get()))
        note = "" if f in ("JPEG", "WEBP") else " (PNG lossless)"
        self.lbl_q.configure(text=f"{q}{note}")
        # kualitas berubah -> pratinjau harus dihitung ulang dengan nilai baru
        try:
            self.core.schedule_preview(120)
        except Exception:
            self.compare.redraw()

    def _on_jobs(self):
        n = int(float(self.core.var_jobs.get() or 0))
        if n == 0:
            self.lbl_jobs.configure(text=f"otomatis · {self.core.cpu_default()}")
        elif n == 1:
            self.lbl_jobs.configure(text="berurutan")
        else:
            self.lbl_jobs.configure(text=f"{n} worker")

    def refresh_live(self):
        self._on_w()
        self._on_q()
        self._on_jobs()
        self.core.schedule_preview(300)

    def on_mode(self):
        own = self.core.var_mode.get() == "own"
        # Entry tujuan: abu-abu saat mode "Timpa di tempat" — tapi tombol folder
        # tetap AKTIF supaya user bisa pakai jalur pintas memilih folder lain
        # (pick_out otomatis memindahkan mode).
        self.e_out.configure(state="normal" if own else "disabled")
        self.core.sync_mode()

    def pick_in(self):
        d = filedialog.askdirectory(title="Pilih folder sumber",
                                    initialdir=self.core.var_in.get() or None)
        if d:
            self.core.var_files = []          # pindah ke mode folder
            self.core.refresh_files()
            self.core.var_in.set(os.path.normpath(d))
            if not self.core.var_out.get():
                self.core.var_out.set(os.path.normpath(d))
            self.core.save_config()

    # --- mode file terpilih ---
    def pick_files(self):
        self.core.pick_files()

    def clear_files(self):
        self.core.clear_files()

    def show_file_selection(self, files: list[str]) -> None:
        """Perbarui label jumlah file terpilih + tombol bersihkan."""
        n = len(files)
        if not n:
            self.lbl_files.configure(text="")
            self.btn_clear_files.set_disabled(True)
            return
        total = 0
        for f in files:
            try:
                total += os.path.getsize(f)
            except Exception:
                pass
        self.lbl_files.configure(text=f"{n} file · {self.core.human(total)}")
        self.btn_clear_files.set_disabled(False)

    def pick_out(self):
        # Klik tombol folder tujuan = user memang mau ke folder lain.
        # Jangan biarkan tombolnya mati karena mode masih "Timpa di tempat":
        # pindahkan mode otomatis, baru buka dialog.
        if self.core.var_mode.get() != "own":
            self.core.var_mode.set("own")     # memicu on_mode() lewat trace
            self.on_mode()
        d = filedialog.askdirectory(title="Pilih folder tujuan",
                                    initialdir=self.core.var_out.get() or None)
        if d:
            self.core.var_out.set(os.path.normpath(d))
            self.core.save_config()

    def on_drop(self, paths: list[str]) -> None:
        """File/folder ditarik ke jendela.

        Sebelumnya fungsi ini cuma mengisi kolom folder sumber, sehingga
        pratinjau tidak pernah dihitung dan user tidak melihat hasil apa pun.
        Sekarang: isi field -> hitung isi folder -> paksa pratinjau jalan.
        """
        paths = [os.path.abspath(p) for p in paths if p]
        folders = [p for p in paths if os.path.isdir(p)]
        images = [p for p in paths if os.path.isfile(p)
                  and p.lower().endswith(self.core.EXTS)]
        bad = [p for p in paths if p not in folders and p not in images]

        if folders:
            self.core.var_files = []          # drop folder = mode folder
            self.core.refresh_files()
            self.core.var_in.set(os.path.normpath(folders[0]))
            if not self.core.var_out.get():
                self.core.var_out.set(os.path.normpath(folders[0]))
        elif images:
            # drop gambar saja -> jadikan daftar file terpilih (bisa banyak),
            # dan folder induknya dipakai sebagai konteks
            self.core.var_files = list(images)
            self.core.refresh_files()
            self.core.var_in.set(os.path.dirname(images[0]))

        self.core.save_config()

        # Hitung isi folder sumber supaya user benar-benar melihat hasil drop.
        d = self.core.var_in.get().strip()
        n_files = 0
        if d and os.path.isdir(d):
            try:
                n_files = len(iter_sources(d, self.core.var_recursive.get()))
            except Exception:
                n_files = 0

        if images:
            self.core.preview_source(images[0])
        elif folders and n_files:
            # folder berisi gambar: pakai yang terbesar sebagai contoh pratinjau
            try:
                found = iter_sources(d, self.core.var_recursive.get())
                self.core.preview_source(max(found, key=os.path.getsize))
            except Exception:
                self.core.schedule_preview(50)
        self.core.schedule_preview(50)

        parts = []
        if folders:
            parts.append(f"{len(folders)} folder")
        if images:
            parts.append(f"{len(images)} gambar")
        if bad:
            parts.append(f"{len(bad)} dilewati")
        pesan = ", ".join(parts) if parts else "tidak ada yang bisa dipakai"
        if n_files:
            self.set_status(f"Dilepas: {pesan} · {n_files} gambar siap dikompres.")
        elif folders:
            self.set_status(f"Dilepas: {pesan} · folder sumber belum ada gambarnya.")
        else:
            self.set_status(f"Dilepas: {pesan}.")

    # --- aksi ---
    def start(self):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")
        self.bar.set(0)
        self.btn_go.set_disabled(True)
        self.btn_stop.set_disabled(False)
        self.core.start()

    def stop(self):
        self.core.stop()
        self.btn_stop.set_disabled(True)

    def open_result(self):
        d = self.core.last_out_dir
        if d and os.path.isdir(d):
            try:
                os.startfile(d)  # noqa: S606
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Gagal membuka folder:\n{exc}")
        else:
            messagebox.showinfo(APP_NAME, "Belum ada folder hasil. Jalankan kompresi dulu.")

    def clear_log(self):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")

    def about(self):
        messagebox.showinfo(
            APP_NAME,
            f"{APP_NAME} v{self.core.APP_VER}\n\n"
            "Paralel multi-thread, pratinjau sebelum-sesudah,\n"
            "drag & drop file/folder ke jendela.\n\n"
            f"HEIC: {'didukung' if self.core.HEIC_SUPPORT else 'tidak didukung'}",
        )

    def _repaint(self):
        p = ui.theme()
        self.root.configure(bg=p["bg"])
        self.txt.configure(bg=p["chip"], fg=p["text"], insertbackground=p["text"],
                           highlightbackground=p["border"], highlightcolor=p["border"])
        self.txt.tag_configure("err", foreground=p["err"])
        self.txt.tag_configure("ok", foreground=p["ok"])
        self.txt.tag_configure("skip", foreground=p["warn"])
        self.txt.tag_configure("dim", foreground=p["text_dim"])
        self.compare.redraw()

    # --- status ---
    def set_status(self, text: str) -> None:
        self.lbl_status.configure(text=text)

    def set_progress(self, done: int, total: int) -> None:
        self.bar.set(0 if not total else done / total)
        self.lbl_count.configure(text=f"{done} / {total}")

    # --- pratinjau ---
    def show_preview(self, p: dict) -> None:
        self.core.prev_busy = False
        self.compare.set_images(p["before"], p["after"])
        self.lbl_prev.configure(text=f"Contoh: {p['name']}")
        self.chip_b.set(f"Sebelum  {self.core.human(p['orig'])}", "text_dim")
        self.chip_a.set(f"Sesudah  {self.core.human(p['new'])}  "
                        f"({self.core.pct_text(p['orig'], p['new'])})", "ok")
        self.chip_dims.configure(
            text=f"{p['bdim'][0]}×{p['bdim'][1]}  →  {p['adim'][0]}×{p['adim'][1]}"
        )

    def preview_failed(self, msg: str) -> None:
        self.core.prev_busy = False
        self.lbl_prev.configure(text=f"Pratinjau gagal: {msg}")

    # --- log ---
    def append_log(self, line: str) -> None:
        tag = ""
        if line.startswith("[ERR]"):
            tag = "err"
        elif line.startswith("[OK]"):
            tag = "ok"
        elif line.startswith("[SKIP]"):
            tag = "skip"
        elif line.startswith(("-", "[i]")):
            tag = "dim"
        self.txt.configure(state="normal")
        self.txt.insert("end", line + "\n", (tag,) if tag else ())
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _on_wheel(self, event):
        self.txt.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ---------- loop event ----------
    def run(self, interval: int = 90):
        """Ganti core.pump(): antrean mesin dibaca di sini, diteruskan ke widget baru."""
        import queue as _q

        try:
            while True:
                kind, payload = self.core.q.get_nowait()
                if kind == "log":
                    self.append_log(payload)
                elif kind == "progress":
                    done, total, name = payload
                    self.set_progress(done, total)
                    if name:
                        pct = 0 if not total else done * 100.0 / total
                        self.set_status(f"{pct:.0f}%  ·  {name}")
                elif kind == "status":
                    self.set_status(payload)
                elif kind == "prev":
                    self.show_preview(payload)
                elif kind == "prev_err":
                    self.preview_failed(payload)
                elif kind == "done":
                    self.finish()
        except _q.Empty:
            pass
        self.root.after(interval, self.run)

    def finish(self):
        self.btn_go.set_disabled(False)
        self.btn_stop.set_disabled(True)
        self.core.finish_ui()
        self.core.save_config()
        st = self.core.var_status.get()
        self.set_status(st)
        self.chip_dims.configure(text=self.chip_dims.cget("text"))



