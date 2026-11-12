"""Toolkit UI kecil untuk Image Compressor — tema gelap/terang ala Fluent.

Semua widget digambar sendiri di Canvas karena Tk tidak punya border-radius.
Setiap widget mendaftar ke registry supaya ganti tema cukup memanggil set_theme().
"""

from __future__ import annotations

import tkinter as tk
import weakref
from tkinter import ttk

# --------------------------------------------------------------------------- #
# Palet
# --------------------------------------------------------------------------- #

THEMES = {
    "dark": {
        "bg": "#1e1e1e",
        "panel": "#252526",
        "panel2": "#2d2d30",
        "input": "#2a2a2c",
        "border": "#3e3e42",
        "border_soft": "#333336",
        "text": "#f2f2f2",
        "text_dim": "#a8a8b0",
        "accent": "#0a84ff",
        "accent_hover": "#3d9bff",
        "accent_press": "#0068d6",
        "accent_text": "#ffffff",
        "ok": "#3fb950",
        "warn": "#d29922",
        "err": "#f85149",
        "chip": "#101014",
        "track": "#3a3a3e",
        "hover": "#333336",
        "select": "#094771",
    },
    "light": {
        "bg": "#f3f3f3",
        "panel": "#ffffff",
        "panel2": "#f7f7f7",
        "input": "#ffffff",
        "border": "#d6d6d6",
        "border_soft": "#e4e4e4",
        "text": "#1b1b1b",
        "text_dim": "#5f5f66",
        "accent": "#0067c0",
        "accent_hover": "#0a7ad6",
        "accent_press": "#00529a",
        "accent_text": "#ffffff",
        "ok": "#1a7f37",
        "warn": "#9a6700",
        "err": "#cf222e",
        "chip": "#ffffff",
        "track": "#d9d9de",
        "hover": "#ececec",
        "select": "#cfe4fb",
    },
}

_current = {"name": "light"}
_registry: "weakref.WeakSet" = weakref.WeakSet()


def theme() -> dict:
    return THEMES[_current["name"]]


def theme_name() -> str:
    return _current["name"]


def register(widget) -> None:
    """Widget mendaftar supaya ikut di-restyle saat tema berganti."""
    _registry.add(widget)


def set_theme(name: str, root: tk.Misc | None = None) -> None:
    if name not in THEMES:
        return
    _current["name"] = name
    apply_ttk(root)
    for w in list(_registry):
        try:
            w.restyle()
        except tk.TclError:
            pass


FONT_UI = "Segoe UI"
FONT_SEMI = "Segoe UI Semibold"
FONT_MONO = "Consolas"


def font(size: int = 10, bold: bool = False) -> tuple:
    return (FONT_SEMI if bold else FONT_UI, size)


class Label(tk.Label):
    """Label biasa yang ikut berganti tema lewat cget/set manual."""

    def __init__(self, master, text: str = "", size: int = 10, bold: bool = False,
                 color: str | None = None, bg: str | None = None, **kw):
        self._color = color
        self._bg = bg
        self._size = size
        self._bold = bold
        super().__init__(master, text=text, font=font(size, bold),
                         bg=bg or theme()["bg"],
                         fg=color or theme()["text"], **kw)
        register(self)

    def restyle(self) -> None:
        mine_bg = theme()["bg"] if self._bg is None else None
        if mine_bg is not None:
            self.configure(bg=mine_bg)
        elif self._bg is not None:
            self.configure(bg=self._bg)
        if self._color is None:
            self.configure(fg=theme()["text"])

    def set_color(self, key: str) -> None:
        self._color = theme()[key]
        self.configure(fg=self._color)


class Card(tk.Frame):
    """Kartu panel: latar `panel`, border 1px, sudut membulat.

    Tk Frame tidak bisa radius, jadi kartu = Frame `panel` yang menampung
    Frame isi; radius hanya terlihat lewat `Card.body` yang diberi padding.
    """

    def __init__(self, master, radius: int = 10, **kw):
        super().__init__(master, bg=theme()["panel"],
                         highlightthickness=1,
                         highlightbackground=theme()["border"],
                         highlightcolor=theme()["border"], **kw)
        self.body = tk.Frame(self, bg=theme()["panel"])
        self.body.pack(fill="both", expand=True, padx=1, pady=1)
        register(self)

    def restyle(self) -> None:
        p = theme()
        self.configure(bg=p["panel"], highlightbackground=p["border"],
                       highlightcolor=p["border"])
        self.body.configure(bg=p["panel"])


class Card2(Card):
    """Kartu bernuansa lebih terang (panel2) untuk area yang ditonjolkan."""


class Divider(tk.Frame):
    """Garis pemisah tipis, tinggi 1px."""

    def __init__(self, master, **kw):
        super().__init__(master, height=1, **kw)
        self.configure(bg=theme()["border_soft"])
        register(self)

    def restyle(self) -> None:
        self.configure(bg=theme()["border_soft"])



# --------------------------------------------------------------------------- #
# bantu gambar
# --------------------------------------------------------------------------- #


def rounded_points(x0: float, y0: float, x1: float, y1: float, r: float, steps: int = 8):
    """Titik polygon untuk persegi bersudut bulat (satu item, mudah diwarnai)."""
    r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts: list[float] = []
    import math

    corners = (
        (x1 - r, y0 + r, -90, 0),
        (x1 - r, y1 - r, 0, 90),
        (x0 + r, y1 - r, 90, 180),
        (x0 + r, y0 + r, 180, 270),
    )
    for cx, cy, a0, a1 in corners:
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / steps)
            pts.extend((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def mix(c1: str, c2: str, t: float) -> str:
    """Campur dua warna hex."""
    a = tuple(int(c1[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i : i + 2], 16) for i in (1, 3, 5))
    return "#{:02x}{:02x}{:02x}".format(
        *(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    )


# --------------------------------------------------------------------------- #
# ttk styling
# --------------------------------------------------------------------------- #


def apply_ttk(root: tk.Misc | None = None) -> None:
    p = theme()
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass

    st.configure(".", background=p["bg"], foreground=p["text"], font=font(10))
    st.configure("TFrame", background=p["bg"])
    st.configure("Panel.TFrame", background=p["panel"])
    st.configure("TLabel", background=p["bg"], foreground=p["text"], font=font(10))
    st.configure("Dim.TLabel", background=p["bg"], foreground=p["text_dim"], font=font(9))

    st.configure(
        "TCombobox",
        fieldbackground=p["input"],
        background=p["panel2"],
        foreground=p["text"],
        arrowcolor=p["text_dim"],
        bordercolor=p["border"],
        lightcolor=p["input"],
        darkcolor=p["input"],
        selectbackground=p["select"],
        selectforeground=p["text"],
        padding=6,
        relief="flat",
    )
    st.map(
        "TCombobox",
        fieldbackground=[("readonly", p["input"])],
        foreground=[("readonly", p["text"])],
        bordercolor=[("focus", p["accent"]), ("hover", p["accent_hover"])],
    )
    st.configure(
        "Horizontal.TProgressbar",
        background=p["accent"],
        troughcolor=p["track"],
        bordercolor=p["track"],
        lightcolor=p["accent"],
        darkcolor=p["accent"],
        thickness=6,
    )
    st.configure(
        "Vertical.TScrollbar",
        background=p["panel2"],
        troughcolor=p["panel"],
        bordercolor=p["panel"],
        arrowcolor=p["text_dim"],
    )


def init(root: tk.Tk) -> None:
    apply_ttk(root)
    root.option_add("*TCombobox*Listbox.background", theme()["panel2"])
    root.option_add("*TCombobox*Listbox.foreground", theme()["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", theme()["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", theme()["accent_text"])


def dark_titlebar(root: tk.Tk) -> None:
    """Judul window ikut gelap di Windows 10/11."""
    try:
        import ctypes

        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1 if _current["name"] == "dark" else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE, fallback lama
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
            )
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# widget dasar
# --------------------------------------------------------------------------- #


class _Base(tk.Canvas):
    def __init__(self, master, height: int = 36, **kw):
        super().__init__(
            master,
            height=height,
            highlightthickness=0,
            bd=0,
            bg=theme()["bg"],
            **kw,
        )
        register(self)

    def restyle(self) -> None:
        self.configure(bg=self._bg())
        self.redraw()

    def _bg(self) -> str:
        try:
            return self.master.cget("bg") or theme()["bg"]
        except tk.TclError:
            return theme()["bg"]

    def redraw(self) -> None:  # pragma: no cover - ditimpa subclass
        pass


class Btn(_Base):
    """Tombol rounded: variant primary / secondary / ghost."""

    def __init__(self, master, text: str, command=None, variant: str = "secondary",
                 icon: str | None = None, width: int | None = None, height: int = 34,
                 radius: int = 8, fontsize: int = 10, bold: bool = True):
        self._label = text
        self._cmd = command
        self._variant = variant
        self._icon = icon
        self._radius = radius
        self._fontsize = fontsize
        self._bold = bold
        self._hover = False
        self._press = False
        self._disabled = False
        self._fixed_w = width
        self._pad = 14
        self._bgid = self._t1 = self._t2 = self._i1 = None

        tw = font(fontsize, bold).__class__  # noqa: F841  (placeholder)
        super().__init__(master, height=height)

        self._draw_text_metrics()
        if width:
            self.configure(width=width)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda _e: self.redraw())

    # --- ukuran teks ---
    def _draw_text_metrics(self) -> None:
        f = tk.font.Font(family=FONT_SEMI if self._bold else FONT_UI,
                         size=self._fontsize) if getattr(tk, "font", None) else None
        if f is None:
            import tkinter.font as tkfont

            f = tkfont.Font(family=FONT_SEMI if self._bold else FONT_UI, size=self._fontsize)
        tw = f.measure(self._label)
        th = f.metrics("linespace")
        icon_w = 16 if self._icon else 0
        gap = 8 if self._icon else 0
        need = tw + icon_w + gap + self._pad * 2
        if not self._fixed_w:
            self.configure(width=max(need, 72))
        self._text_h = th

    # --- interaksi ---
    def _on_enter(self, _e=None):
        if self._disabled:
            return
        self._hover = True
        self.configure(cursor="hand2")
        self.redraw()

    def _on_leave(self, _e=None):
        self._hover = False
        self._press = False
        self.configure(cursor="")
        self.redraw()

    def _on_press(self, _e=None):
        if self._disabled:
            return
        self._press = True
        self.redraw()

    def _on_release(self, e=None):
        was = self._press
        self._press = False
        self.redraw()
        if was and not self._disabled and self._cmd:
            if e is None or (0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()):
                self._cmd()

    def invoke(self):
        if not self._disabled and self._cmd:
            self._cmd()

    def set_disabled(self, flag: bool) -> None:
        self._disabled = bool(flag)
        self.configure(cursor="" if flag else "hand2")
        self.redraw()

    def set_text(self, text: str) -> None:
        self._label = text
        self._draw_text_metrics()
        self.redraw()

    def _colors(self):
        p = theme()
        if self._variant == "primary":
            base = p["accent_press"] if self._press else (
                p["accent_hover"] if self._hover else p["accent"]
            )
            fg = p["accent_text"]
            border = base
        elif self._variant == "ghost":
            base = p["hover"] if (self._hover or self._press) else self._bg()
            fg = p["text_dim"] if not self._hover else p["text"]
            border = self._bg()
        else:
            base = p["panel2"] if not self._hover else mix(p["panel2"], p["text"], 0.10)
            if self._press:
                base = mix(p["panel2"], p["text"], 0.16)
            fg = p["text"]
            border = p["border"]
        if self._disabled:
            base = mix(self._bg(), p["panel"], 0.6)
            fg = p["text_dim"]
            border = p["border_soft"]
        return base, fg, border

    def redraw(self) -> None:
        self.delete("all")
        w = self.winfo_width() or int(self.cget("width"))
        h = self.winfo_height() or int(self.cget("height"))
        if w <= 1:
            w = 120
        base, fg, border = self._colors()
        pts = rounded_points(1, 1, w - 1, h - 1, self._radius)
        self.create_polygon(pts, fill=base, outline=border, width=1)

        cx = w / 2
        if self._icon:
            icon_w, gap = 14, 8
            total = icon_w + gap + self._measure(self._label)
            x0 = cx - total / 2
            self._draw_icon(x0, h / 2, fg, self._icon)
            self.create_text(x0 + icon_w + gap, h / 2, text=self._label, fill=fg,
                             anchor="w", font=font(self._fontsize, self._bold))
        else:
            self.create_text(cx, h / 2, text=self._label, fill=fg,
                             font=font(self._fontsize, self._bold))

    def _measure(self, text: str) -> int:
        import tkinter.font as tkfont

        f = tkfont.Font(family=FONT_SEMI if self._bold else FONT_UI, size=self._fontsize)
        return f.measure(text)

    def _draw_icon(self, x: float, cy: float, color: str, kind: str) -> None:
        s = 7
        if kind == "play":
            self.create_polygon(x, cy - s + 1, x + s * 1.5, cy, x, cy + s - 1,
                                fill=color, outline=color)
        elif kind == "stop":
            self.create_rectangle(x, cy - s + 2, x + s * 1.4, cy + s - 2,
                                  fill=color, outline=color)
        elif kind == "folder":
            self.create_line(x, cy - 4, x + 5, cy - 4, x + 7, cy - 2, x + 13, cy - 2,
                             fill=color, width=1.4)
            self.create_rectangle(x, cy - 2, x + 13, cy + 5, outline=color, width=1.4)
        elif kind == "check":
            self.create_line(x + 1, cy, x + 5, cy + 4, x + 13, cy - 5, fill=color, width=2)
        elif kind == "x":
            self.create_line(x + 2, cy - 5, x + 12, cy + 5, fill=color, width=1.8)
            self.create_line(x + 12, cy - 5, x + 2, cy + 5, fill=color, width=1.8)
        elif kind in ("theme", "moon", "sun"):
            # bulan sabit: lingkaran penuh + potongan dari kanan-atas
            self.create_oval(x + 1, cy - 6, x + 13, cy + 6, outline=color, width=1.6)
            self.create_oval(x + 5, cy - 7, x + 17, cy + 5,
                             fill=self._bg(), outline=self._bg())


class IconBtn(_Base):
    """Tombol ikon kecil (mis. pilih folder)."""

    def __init__(self, master, icon: str, command=None, size: int = 34):
        self._icon = icon
        self._cmd = command
        self._hover = False
        self._disabled = False
        self._size = size
        super().__init__(master, width=size, height=size)
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._click)
        self.bind("<Configure>", lambda _e: self.redraw())

    def _click(self, _e=None):
        if not self._disabled and self._cmd:
            self._cmd()

    def set_disabled(self, flag: bool) -> None:
        self._disabled = bool(flag)
        self.configure(cursor="" if flag else "hand2")
        self.redraw()

    def _set_hover(self, flag: bool):
        if self._disabled:
            return
        self._hover = flag
        self.configure(cursor="hand2" if flag else "")
        self.redraw()

    def redraw(self):
        self.delete("all")
        p = theme()
        w = self.winfo_width() or self._size
        h = self.winfo_height() or self._size
        fill = p["hover"] if self._hover else p["panel2"]
        self.create_polygon(rounded_points(1, 1, w - 1, h - 1, 8), fill=fill,
                            outline=p["border"], width=1)
        col = p["text_dim"] if self._disabled else p["text"]
        Btn._draw_icon(self, w / 2 - 7, h / 2, col, self._icon)


class Entry(_Base):
    """Input teks gelap dengan placeholder dan ring fokus."""

    def __init__(self, master, textvariable: tk.StringVar, placeholder: str = "",
                 height: int = 34, fontsize: int = 9):
        self.var = textvariable
        self._ph = placeholder
        self._focus = False
        super().__init__(master, height=height)
        self._font = font(fontsize)
        self._entry = tk.Entry(
            self,
            textvariable=textvariable,
            bd=0,
            relief="flat",
            highlightthickness=0,
            insertbackground=theme()["text"],
            font=self._font,
        )
        register(self._entry)
        self._entry.bind("<FocusIn>", lambda _e: self._set_focus(True))
        self._entry.bind("<FocusOut>", lambda _e: self._set_focus(False))
        self._win = self.create_window(12, height // 2, anchor="w", window=self._entry,
                                       height=height - 12)
        self.bind("<Configure>", lambda _e: self.redraw())

    def _set_focus(self, flag: bool):
        self._focus = flag
        self.redraw()

    def restyle(self):
        self.configure(bg=self._bg())
        self._entry.configure(bg=theme()["input"], fg=theme()["text"],
                              insertbackground=theme()["text"])
        self.redraw()

    def redraw(self):
        self.delete("bgrect")
        p = theme()
        w = self.winfo_width() or 200
        h = self.winfo_height() or 34
        self.create_polygon(
            rounded_points(1, 1, w - 1, h - 1, 8),
            fill=p["input"],
            outline=p["accent"] if self._focus else p["border"],
            width=2 if self._focus else 1,
            tags="bgrect",
        )
        self.tag_lower("bgrect")
        self.configure(bg=self._bg())
        try:
            self.itemconfigure(self._win, width=max(10, w - 24))
        except tk.TclError:
            pass
        self._entry.configure(bg=p["input"], fg=p["text"])


class Slider(_Base):
    """Slider horizontal: track tipis + thumb bulat + nilai."""

    def __init__(self, master, var: tk.IntVar, lo: int = 1, hi: int = 100,
                 height: int = 34, command=None, suffix: str = "",
                 width: int | None = None):
        self.var = var
        self.lo, self.hi = lo, hi
        self._cmd = command
        self._suffix = suffix
        self._drag = False
        super().__init__(master, height=height)
        if width:
            self.configure(width=width)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Configure>", lambda _e: self.redraw())
        self.var.trace_add("write", lambda *_: self.redraw())
        self.configure(cursor="hand2")

    def _value_at(self, x: float) -> int:
        w = self.winfo_width() or 200
        pad = 12
        t = (x - pad) / max(1, (w - pad * 2))
        t = min(1.0, max(0.0, t))
        return int(round(self.lo + t * (self.hi - self.lo)))

    def _press(self, e):
        self._drag = True
        self._apply(self._value_at(e.x))

    def _move(self, e):
        if self._drag:
            self._apply(self._value_at(e.x))

    def _release(self, _e):
        self._drag = False

    def _apply(self, v: int):
        v = min(self.hi, max(self.lo, v))
        if int(self.var.get()) != v:
            self.var.set(v)
            if self._cmd:
                self._cmd(v)
        self.redraw()

    def redraw(self):
        self.delete("all")
        p = theme()
        w = self.winfo_width() or 200
        h = self.winfo_height() or 34
        pad = 12
        cy = h / 2
        t = (int(self.var.get()) - self.lo) / max(1, (self.hi - self.lo))
        x = pad + t * (w - pad * 2)

        self.create_line(pad, cy, w - pad, cy, fill=p["track"], width=4,
                         capstyle="round")
        if x > pad:
            self.create_line(pad, cy, x, cy, fill=p["accent"], width=4,
                             capstyle="round")
        r = 8
        self.create_oval(x - r, cy - r, x + r, cy + r, fill=p["accent"],
                         outline=mix(p["accent"], "#ffffff", 0.35), width=1)
        if self._suffix:
            self.create_text(w - 2, cy, text=f"{int(self.var.get())}{self._suffix}",
                             fill=p["text"], anchor="e", font=font(9, True))


class Switch(_Base):
    """Toggle pill dengan animasi kecil."""

    def __init__(self, master, var: tk.BooleanVar, label: str = "",
                 command=None, height: int = 26, width: int = 46):
        self.var = var
        self._cmd = command
        self._label = label
        self._pos = 1.0 if var.get() else 0.0
        self._pill_w = width
        import tkinter.font as tkfont

        _f = tkfont.Font(family=FONT_UI, size=10)
        _need = width + 10 + _f.measure(label) + 8
        super().__init__(master, height=height, width=max(width + 90, _need))
        self.bind("<ButtonRelease-1>", self._click)
        self.bind("<Configure>", lambda _e: self.redraw())
        self.configure(cursor="hand2")
        self.redraw()

    def _click(self, _e=None):
        self.var.set(not self.var.get())
        self._animate(1.0 if self.var.get() else 0.0)
        if self._cmd:
            self._cmd(self.var.get())

    def _animate(self, target: float):
        step = 0.18 if target > self._pos else -0.18
        self._pos = max(0.0, min(1.0, self._pos + step))
        self.redraw()
        if abs(self._pos - target) > 0.01:
            self.after(12, lambda: self._animate(target))

    def redraw(self):
        self.delete("all")
        p = theme()
        h = self.winfo_height() or 26
        bh = 22
        by = (h - bh) / 2
        fill = mix(p["track"], p["accent"], self._pos)
        self.create_polygon(rounded_points(1, by, self._pill_w - 1, by + bh, bh / 2),
                            fill=fill, outline="")
        cx = 1 + bh / 2 + self._pos * (self._pill_w - 2 - bh)
        r = bh / 2 - 3
        self.create_oval(cx - r, h / 2 - r, cx + r, h / 2 + r, fill="#ffffff", outline="")
        if self._label:
            self.create_text(self._pill_w + 10, h / 2, text=self._label, anchor="w",
                             fill=p["text"], font=font(10))


class Radio(_Base):
    """Radio bulat dengan label, satu grup = list objek Radio."""

    def __init__(self, master, text: str, variable: tk.StringVar, value: str,
                 command=None, height: int = 26):
        self.var = variable
        self.value = value
        self._text = text
        self._cmd = command
        self._hover = False
        super().__init__(master, height=height)
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._click)
        self.configure(cursor="hand2")
        self.var.trace_add("write", lambda *_: self.redraw())
        self.bind("<Configure>", lambda _e: self.redraw())

    def _set_hover(self, flag):
        self._hover = flag
        self.redraw()

    def _click(self, _e=None):
        self.var.set(self.value)
        if self._cmd:
            self._cmd()

    def redraw(self):
        self.delete("all")
        p = theme()
        h = self.winfo_height() or 26
        cy = h / 2
        on = self.var.get() == self.value
        r = 7
        col = p["accent"] if on else (p["text_dim"] if self._hover else p["border"])
        self.create_oval(2, cy - r, 2 + 2 * r, cy + r, outline=col, width=1.6,
                         fill=p["bg"])
        if on:
            self.create_oval(2 + 3, cy - r + 3, 2 + 2 * r - 3, cy + r - 3,
                             fill=p["accent"], outline="")
        self.create_text(2 + 2 * r + 10, cy, text=self._text, anchor="w",
                         fill=p["text"] if on else p["text_dim"], font=font(9))


class Section(_Base):
    """Header seksi bernomor: badge bulat + judul kapital."""

    def __init__(self, master, number: str, title: str, height: int = 24):
        self._num = number
        self._title = title
        super().__init__(master, height=height)
        self.bind("<Configure>", lambda _e: self.redraw())

    def redraw(self):
        self.delete("all")
        p = theme()
        h = self.winfo_height() or 24
        cy = h / 2
        self.create_oval(1, cy - 8, 17, cy + 8, fill=p["panel2"], outline=p["border"])
        self.create_text(9, cy, text=self._num, fill=p["text_dim"], font=font(8, True))
        self.create_text(25, cy, text=self._title.upper(), fill=p["text_dim"],
                         anchor="w", font=font(9, True))


class Progress(_Base):
    def __init__(self, master, height: int = 18):
        self._frac = 0.0
        super().__init__(master, height=height)
        self.bind("<Configure>", lambda _e: self.redraw())

    def set(self, frac: float):
        self._frac = min(1.0, max(0.0, frac))
        self.redraw()

    def redraw(self):
        self.delete("all")
        p = theme()
        w = self.winfo_width() or 200
        h = self.winfo_height() or 18
        cy = h / 2
        self.create_line(0, cy, w, cy, fill=p["track"], width=5, capstyle="round")
        if self._frac > 0:
            self.create_line(0, cy, max(6, w * self._frac), cy, fill=p["accent"],
                             width=5, capstyle="round")


class Badge(_Base):
    """Chip kecil untuk label status."""

    def __init__(self, master, text: str = "", height: int = 22, color_key: str = "text_dim"):
        self._text = text
        self._ck = color_key
        super().__init__(master, height=height)
        self.bind("<Configure>", lambda _e: self.redraw())

    def set(self, text: str, color_key: str | None = None):
        self._text = text
        if color_key:
            self._ck = color_key
        self.redraw()

    def redraw(self):
        self.delete("all")
        p = theme()
        import tkinter.font as tkfont

        f = tkfont.Font(family=FONT_UI, size=9)
        tw = f.measure(self._text)
        w = tw + 20
        h = self.winfo_height() or 22
        self.create_polygon(rounded_points(0, 1, w, h - 1, (h - 2) / 2),
                            fill=p["chip"], outline=p["border"], width=1)
        self.create_text(w / 2, h / 2, text=self._text, fill=p[self._ck], font=font(9))
        self.configure(width=w)
