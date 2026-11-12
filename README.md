# Image Compressor v1.0.0

Kompres & resize massal aset gambar untuk web. Aplikasi Windows standalone
(`ImageCompressor.exe`) — target **tidak butuh Python terinstal**.

Dua mode dalam satu binary:

- **GUI** — pilih folder, atur lebar/kualitas/format, progress bar + log per file.
- **Headless** — tarik folder ke atas `ImageCompressor.exe`, langsung diproses
  dengan preset aman, muncul ringkasan, folder hasil dibuka otomatis.

Logika kompresi diadaptasi dari `Praktikum AP/compress_gallery.py` (EXIF
transpose, resize LANCZOS, flatten transparansi, save `optimize=True`),
ditambah GUI, mode headless, dan opsi.

---

## Cara pakai cepat

1. Double-click `ImageCompressor.exe`
2. **Folder sumber** → pilih folder berisi gambar
3. **Folder tujuan** → pilih:
   - *Timpa di tempat* → hasil menimpa folder sumber (aman: file ditulis ke temp dulu, baru `os.replace`)
   - *Folder lain* → sumber tidak disentuh
4. Atur lebar maksimal + kualitas + format
5. **Mulai Kompres**

**Drag & drop:** tarik sebuah folder ke atas `ImageCompressor.exe` → langsung
diproses headless (rekursif, JPEG 1920 px q85), hasil ke `<folder>_compressed`,
lalu muncul ringkasan + folder hasil dibuka.

Pengaturan terakhir disimpan otomatis di `%USERPROFILE%\.image_compressor.json`.

---

## Mode headless (CLI)

```bat
ImageCompressor.exe --cli "D:\foto"
ImageCompressor.exe --cli "D:\foto" --format WEBP --width 800 --quality 70 --out "D:\foto-web"
ImageCompressor.exe --cli "D:\foto" --in-place
ImageCompressor.exe --help
```

| Opsi | Default | Keterangan |
|---|---|---|
| `--out DIR` | `<folder>_compressed` | Folder tujuan |
| `--in-place` | off | Timpa di tempat, nama file mengikuti format keluaran |
| `--width N` | 1920 | Lebar maksimal px, `0` = tanpa resize |
| `--quality N` | 85 | Kualitas JPEG/WebP |
| `--format FMT` | JPEG | `JPEG` / `WEBP` / `PNG` |
| `--no-recursive` | off | Jangan telusuri subfolder |
| `--keep-bigger` | off | Tetap tulis hasil walau tidak lebih kecil |
| `--delete-orig` | off | Hapus file asli setelah konversi format |

Tanpa `--cli`, `ImageCompressor.exe "D:\foto"` membuka GUI dengan folder sumber
sudah terisi.

---

## Pengaturan (GUI)

| Setting | Default | Keterangan |
|---|---|---|
| Lebar maksimal | 1920 px | Gambar lebih lebar dikecilkan (rasio dijaga). `0` = tanpa resize |
| Format keluaran | JPEG | JPEG / WebP / PNG |
| Kualitas | 85 | Berlaku untuk JPEG & WebP. PNG selalu lossless |
| Sertakan subfolder | ✅ | Struktur folder dipertahankan di output |
| Lewati jika hasil tidak lebih kecil | ✅ | Kalau hasil ≥ aslinya, file asli dipertahankan |
| Hapus file asli setelah konversi format | ❌ | Mis. `foto.png` → `foto.jpg`, file `.png` dihapus |
| Buka folder hasil setelah selesai | ❌ | |

**Format yang didukung masuk:** `.jpg .jpeg .png .webp .gif .bmp .tif .tiff` + `.heic .heif` (iPhone).

---

## Catatan format

- **JPEG** — paling kompatibel, paling kecil. Transparansi (PNG/GIF) di-flatten ke latar putih. Progressive + optimize.
- **WebP** — paling kecil, tetap dukung transparansi. Rekomendasi untuk web modern.
- **PNG** — lossless, `compress_level=9`. Untuk grafik/ikon/butuh alpha. Tidak mengecil drastis seperti JPEG.

Setelah selesai, log menampilkan ringkasan: OK / dilewati / gagal, total ukuran
sebelum → sesudah, dan persentase ruang yang dihemat.

---

## Troubleshooting

**HEIC gagal / tidak terdeteksi**
Build ini sudah bundel `pillow-heif`. Kalau ada `.heic` yang error, cek log — namanya dicetak lengkap dengan pesan errornya.

**Hasil kompresi malah membesar**
Aktifkan "Lewati jika hasil tidak lebih kecil". Biasanya terjadi pada konversi PNG → PNG, atau JPEG yang sudah dikompres ulang di kualitas lebih tinggi.

**Windows Defender / SmartScreen nge-block**
Normal untuk `.exe` yang belum ditandatangani. Klik *More info* → *Run anyway*. File-nya di-compile lokal dari `image_compressor.py` di repo ini — source-nya bisa dibaca sendiri.

**Drag folder tapi tidak terjadi apa-apa**
Pastikan yang ditarik benar-benar **folder**, bukan file. Mode headless hanya jalan kalau argumennya folder.

---

## Struktur repo

```
Image-Compressor/
├─ image_compressor.py    ← source aplikasi (core + GUI + headless)
├─ test_core.py           ← smoke test core tanpa GUI
├─ make_icon.py           ← generate app.ico
├─ app.ico                ← ikon aplikasi
├─ build.cmd              ← script build Nuitka (Windows)
├─ requirements.txt       ← dependency build
└─ README.md
```

Hasil build (`build/`, `ImageCompressor.exe`) dan `.venv/` tidak ikut di-commit.

---

## Rebuild dari source

```bat
cd "Image Compressor"

:: 1. venv + dependency
uv venv .venv --python 3.11
uv pip install --python .venv/Scripts/python.exe -r requirements.txt

:: 2. ikon (sekali saja)
.venv\Scripts\python.exe make_icon.py

:: 3. test core
.venv\Scripts\python.exe test_core.py

:: 4. build exe
build.cmd
```

`build.cmd` menjalankan Nuitka `--standalone --onefile --enable-plugin=tk-inter
--windows-console-mode=disable --windows-icon-from-ico=app.ico`, output
`build\ImageCompressor.exe` (±16 MB), dan menulis seluruh output ke `build_log.txt`.

Butuh compiler C: MSVC (Visual Studio Build Tools) atau MinGW. Nuitka mendeteksi
otomatis lewat `vswhere`.

Jalan langsung tanpa build (butuh Python + Pillow):

```bash
.venv/Scripts/python.exe image_compressor.py              # GUI
.venv/Scripts/python.exe image_compressor.py --cli "D:\folder\gambar"
```

---

## Lisensi

MIT — lihat [LICENSE](LICENSE).

Dibuat untuk Lab Algoritma & Pemrograman.
