# Image Compressor

Kompres dan resize massal gambar untuk web. Windows, **satu file `.exe`, tanpa Python**.
Ada GUI lengkap dengan drag & drop, ada juga mode command line.

- Masuk: `.jpg .jpeg .png .webp .gif .bmp .tif .tiff` + `.heic .heif` (iPhone)
- Keluar: **JPEG / WebP / PNG**
- HEIC didukung langsung — `pillow-heif` + `libheif` sudah dibundel di dalam exe,
  tidak perlu install apa pun.

---

## 1. Pakai langsung (paling gampang)

Download **[ImageCompressor.exe](https://github.com/Luxey9/Image-Compressor/releases/latest/download/ImageCompressor.exe)**
(±17 MB) → double-click. Tidak perlu Python, tidak perlu `pip install`.

> **SmartScreen protes?** Wajar, exe-nya belum ditandatangani. *More info* → *Run anyway*.

### Alur GUI

1. **1 · Sumber** — pilih salah satu:
   - tombol **folder** → satu folder penuh (rekursif ke subfolder)
   - tombol **Pilih File** → 1 atau beberapa file tertentu, boleh dari folder berbeda
   - **tarik folder/file ke jendela aplikasi** (drag & drop)
2. **2 · Tujuan** — *Timpa di tempat*, atau *Folder lain (pilih folder tujuan)*
3. **3 · Opsi** — lebar maks, kualitas, format, worker paralel, dst.
4. **Mulai Kompres** → lihat progres + log.

Folder sumber dan tujuan **selalu kosong saat aplikasi dibuka** — kamu pilih
sendiri tiap sesi, jadi tidak ada risiko salah timpa folder secara tidak sengaja.
Pengaturan lain (lebar, kualitas, format, opsi) tetap diingat.

### Mode "Pilih File"

Kompres hanya file yang kamu mau, bukan seluruh folder:

- klik **Pilih File** → pilih beberapa file (Ctrl / Shift klik)
- atau tarik file gambarnya langsung ke jendela aplikasi
- label akan menampilkan `3 file · 59.1 KB` dan tombol **Bersihkan** aktif
- file dari folder berbeda-beda boleh dicampur; hasilnya dikumpulkan ke satu
  folder tujuan, nama file dipertahankan
- mode *timpa di tempat* → tiap hasil ditulis di samping file asalnya

### Drag & drop

- Tarik **folder** ke jendela → folder itu jadi folder sumber, pratinjau muncul
- Tarik **file gambar** ke jendela → masuk mode "Pilih File", pratinjau muncul
- Bisa banyak file sekaligus
- Tarik folder ke atas **`ImageCompressor.exe`** (di luar aplikasi) → langsung
  diproses tanpa buka GUI, hasil ke `<folder>_compressed`

### Pratinjau sebelum–sesudah

Satu kanvas, satu gambar hasil, dan sebuah **slider pembatas**:

- geser garis ke kiri/kanan → bandingkan **Sebelum** vs **Sesudah**
- label di bawah menunjukkan `50% sebelum · 50% sesudah`
- **roda mouse** = zoom · **Ctrl + drag** = geser (pan) · **klik tengah** = reset
- tombol `−` `+` `Fit` di kanan bawah kanvas
- pembatas tetap presisi walau di-zoom atau digeser

---

## 2. Clone dan jalankan dari source

Butuh Python 3.10+.

```bash
git clone https://github.com/Luxey9/Image-Compressor.git
cd Image-Compressor
pip install -r requirements.txt
python image_compressor.py          # GUI
python image_compressor.py --help   # bantuan CLI
```

---

## 3. Clone dan build exe sendiri

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
ImageCompressor.exe --cli "D:\foto\IMG_0001.jpg" "D:\foto\IMG_0002.jpg" --out "D:\pilih"
ImageCompressor.exe --cli "D:\foto" --in-place --format WEBP
ImageCompressor.exe --help
```

| Opsi | Default | Keterangan |
|---|---|---|
| `--cli` | — | Mode tanpa GUI (wajib untuk otomatisasi) |
| `--out DIR` | `<folder>_compressed` | Folder tujuan |
| `--in-place` | off | Timpa di tempat, nama file ikut format keluaran |
| `--width N` | 1920 | Lebar maksimal px, `0` = tanpa resize |
| `--quality N` | 85 | Kualitas JPEG/WebP |
| `--format FMT` | JPEG | `JPEG` / `WEBP` / `PNG` |
| `--jobs N` | otomatis | Jumlah worker paralel; `1` = berurutan |
| `--no-recursive` | off | Jangan telusuri subfolder |
| `--keep-bigger` | off | Tetap tulis hasil walau tidak lebih kecil |
| `--delete-orig` | off | Hapus file asli setelah konversi format |

Tujuan yang sama dipakai untuk file maupun folder — beberapa file dari folder
berbeda akan dikumpulkan datar ke `--out`, sementara nama file dipertahankan.

Tanpa `--cli`, `ImageCompressor.exe "D:\foto"` hanya membuka GUI dengan folder
sumber terisi.

### Contoh hasil nyata

```
60 gambar (648 MB) -> 12.3 MB   dalam 14.5 s   (44.8 MB/s, hemat 98.1%)
```

### Paralel · cepat

Semua file dikerjakan bersamaan, bukan satu-satu. Pillow melepas GIL saat
decode/encode, jadi thread benar-benar paralel. Semuanya di **CPU** — tidak ada
akselerasi GPU:

| Mode | 16 file / 91 MB | Speedup |
|---|---|---|
| berurutan | 11,4 s | 1,0× |
| thread 4 | 4,8 s | 2,4× |
| thread 8 | 3,5 s | 3,3× |
| **thread 16** | **2,5 s** | **4,6×** |

Jumlah worker default = jumlah core, dibatasi RAM yang tersedia (~300 MB per
worker). Atur manual dengan `--jobs`, atau kolom *Worker paralel* di GUI.

---

## Tes

```bash
.venv/Scripts/python.exe test_core.py     # core + CLI, tanpa GUI
.venv/Scripts/python.exe test_v132.py     # sumber/tujuan kosong, HEIC
.venv/Scripts/python.exe test_v133.py     # zoom, pan, tombol kanvas
.venv/Scripts/python.exe test_v134.py     # mode "Pilih File"
.venv/Scripts/python.exe test_v135.py     # layout panel kanan
.venv/Scripts/python.exe test_v136.py     # logika slider sebelum/sesudah
.venv/Scripts/python.exe test_v136b.py    # radio "Folder lain"
```

---

## File di repo

```
image_compressor.py   core + GUI + mode headless
gui_v12.py            seluruh widget GUI (tkinter)
ui_kit.py             komponen UI kustom (tombol, switch, radio, entry)
build.cmd             script build Nuitka -> build\ImageCompressor.exe
make_icon.py          generator app.ico
app.ico               ikon aplikasi

test_core.py          smoke test core + CLI
test_v132.py          folder kosong saat start, drag & drop, HEIC
test_v133.py          zoom / pan / tombol kanvas
test_v134.py          mode "Pilih File"
test_v135.py          layout panel kanan
test_v136.py          slider sebelum-sesudah (presisi koordinat)
test_v136b.py         radio "Folder lain" bertumpuk vertikal

requirements.txt      dependency runtime (Pillow, pillow-heif)
requirements-build.txt  + Nuitka, buat bikin exe
```

Catatan kecil:

- JPEG mem-flatten transparansi ke latar putih
- orientasi EXIF dibetulkan (foto HP tidak miring)
- *"lewati jika hasil tidak lebih kecil"* aktif secara default
- pengaturan GUI disimpan di `%USERPROFILE%\.image_compressor.json`
  (folder sumber & tujuan sengaja **tidak** disimpan)

---

MIT — lihat [LICENSE](LICENSE).
