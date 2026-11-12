# Image Compressor

Kompres & resize massal gambar untuk web. Windows, **satu file `.exe`, tanpa Python**.
Ada GUI, bisa drag & drop folder, bisa juga lewat command line.

- Masuk: `.jpg .jpeg .png .webp .gif .bmp .tif .tiff` + `.heic .heif` (iPhone)
- Keluar: **JPEG / WebP / PNG**

---

## 1. Cuma mau pakai (paling gampang)

Download **[ImageCompressor.exe](https://github.com/Luxey9/Image-Compressor/releases/latest/download/ImageCompressor.exe)** (±16 MB) → double-click.

1. **Folder sumber** → pilih folder gambar
2. **Folder tujuan** → *timpa di tempat* atau *folder lain*
3. Atur lebar maks / kualitas / format → **Mulai Kompres**

**Drag & drop:** tarik sebuah folder ke atas `ImageCompressor.exe` → langsung
diproses (rekursif, JPEG 1920 px q85), hasil ke `<folder>_compressed`.

> **SmartScreen protes?** Wajar, exe-nya belum ditandatangani. *More info* → *Run anyway*.
> Pengaturan GUI tersimpan otomatis di `%USERPROFILE%\.image_compressor.json`.

---

## 2. Clone & jalanin dari source

Butuh Python 3.10+.

```bash
git clone https://github.com/Luxey9/Image-Compressor.git
cd Image-Compressor
pip install -r requirements.txt
python image_compressor.py
```

---

## 3. Clone & build exe sendiri

Butuh compiler C — MSVC Build Tools atau MinGW. Nuitka mendeteksi otomatis.

```bash
git clone https://github.com/Luxey9/Image-Compressor.git
cd Image-Compressor

uv venv .venv --python 3.11
uv pip install -r requirements-build.txt --python .venv/Scripts/python.exe

.venv/Scripts/python.exe test_core.py    # smoke test core
build.cmd                                # hasil: build\ImageCompressor.exe
```

Build pertama 5–9 menit. Log lengkap ada di `build_log.txt`.

---

## Command line (tanpa GUI)

```bat
ImageCompressor.exe --cli "D:\foto"
ImageCompressor.exe --cli "D:\foto" --format WEBP --width 800 --quality 70 --out "D:\foto-web"
ImageCompressor.exe --help
```

| Opsi | Default | Keterangan |
|---|---|---|
| `--out DIR` | `<folder>_compressed` | Folder tujuan |
| `--in-place` | off | Timpa di tempat, nama file ikut format keluaran |
| `--width N` | 1920 | Lebar maksimal px, `0` = tanpa resize |
| `--quality N` | 85 | Kualitas JPEG/WebP |
| `--format FMT` | JPEG | `JPEG` / `WEBP` / `PNG` |
| `--no-recursive` | off | Jangan telusuri subfolder |
| `--keep-bigger` | off | Tetap tulis hasil walau tidak lebih kecil |
| `--delete-orig` | off | Hapus file asli setelah konversi format |

Tanpa `--cli`, `ImageCompressor.exe "D:\foto"` hanya membuka GUI dengan folder sumber terisi.

---

## File di repo

```
image_compressor.py   source — core + GUI + mode headless
test_core.py          smoke test core, tanpa GUI
build.cmd             script build Nuitka → build\ImageCompressor.exe
make_icon.py          generator app.ico
app.ico               ikon aplikasi
requirements.txt      dependency runtime (Pillow, pillow-heif)
requirements-build.txt  + Nuitka, buat bikin exe
```

Catatan kecil: JPEG mem-flatten transparansi ke latar putih, orientasi EXIF
dibetulkan (foto HP tidak miring), dan *"lewati jika hasil tidak lebih kecil"*
aktif secara default.

---

MIT — lihat [LICENSE](LICENSE).
