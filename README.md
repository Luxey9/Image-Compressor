# Image Compressor

Kompres dan resize massal gambar untuk web. Windows, satu file `.exe`, tanpa Python.
Ada GUI lengkap dengan drag and drop, ada juga mode command line.

- Masuk: `.jpg .jpeg .png .webp .gif .bmp .tif .tiff` serta `.heic .heif` (iPhone)
- Keluar: JPEG / WebP / PNG
- HEIC didukung langsung. `pillow-heif` dan `libheif` sudah dibundel di dalam exe,
  jadi pengguna tidak perlu install apa pun.

---

## 1. Pakai langsung

Download **[ImageCompressor.exe](https://github.com/Luxey9/Image-Compressor/releases/latest/download/ImageCompressor.exe)**
(sekitar 17 MB), lalu double-click. Tidak perlu Python, tidak perlu `pip install`.

> SmartScreen protes? Wajar, exe-nya belum ditandatangani. Pilih **More info**,
> lalu **Run anyway**.

### Alur GUI

1. **Sumber**, pilih salah satu cara:
   - tombol folder untuk satu folder penuh (rekursif ke subfolder)
   - tombol **Pilih File** untuk 1 atau beberapa file tertentu, boleh dari folder berbeda
   - tarik folder atau file ke jendela aplikasi (drag and drop)
2. **Tujuan**: *Timpa di tempat*, atau *Folder lain (pilih folder tujuan)*
3. **Opsi**: lebar maks, kualitas, format, worker paralel, dan lain-lain
4. Klik **Mulai Kompres**, lalu lihat progres dan log di bawah

Folder sumber dan tujuan **selalu kosong saat aplikasi dibuka**. Kamu pilih sendiri
tiap sesi, jadi tidak ada risiko salah timpa folder. Pengaturan lain (lebar, kualitas,
format, opsi) tetap diingat.

### Mode "Pilih File"

Kompres hanya file yang kamu mau, bukan seluruh folder:

- klik **Pilih File**, lalu pilih beberapa file (Ctrl klik atau Shift klik)
- atau tarik file gambarnya langsung ke jendela aplikasi
- label akan menampilkan `3 file, 59.1 KB` dan tombol **Bersihkan** menjadi aktif
- file dari folder berbeda boleh dicampur. Hasilnya dikumpulkan ke satu folder
  tujuan, nama file dipertahankan
- kalau memakai *timpa di tempat*, tiap hasil ditulis di samping file asalnya

### Drag and drop

- Tarik **folder** ke jendela: folder itu jadi folder sumber, pratinjau muncul
- Tarik **file gambar** ke jendela: masuk mode "Pilih File", pratinjau muncul
- Bisa banyak file sekaligus
- Tarik folder ke atas **`ImageCompressor.exe`** dari luar aplikasi: langsung
  diproses tanpa membuka GUI, hasil ke `<folder>_compressed`

### Pratinjau sebelum dan sesudah

Satu kanvas, satu gambar hasil, dan sebuah slider pembatas:

- geser garis ke kiri atau ke kanan untuk membandingkan **Sebelum** dan **Sesudah**
- label di bawah menunjukkan `50% sebelum, 50% sesudah`
- **roda mouse** untuk zoom, **Ctrl + drag** untuk geser (pan), **klik tengah** untuk reset
- tombol `-`, `+`, dan `Fit` di kanan bawah kanvas
- pembatas tetap presisi walau gambar di-zoom atau digeser

---

## 2. Clone dan jalankan dari source

Butuh Python 3.10 atau lebih baru.

```bash
git clone https://github.com/Luxey9/Image-Compressor.git
cd Image-Compressor
pip install -r requirements.txt
python image_compressor.py          # GUI
python image_compressor.py --help   # bantuan CLI
```

---

## 3. Clone dan build exe sendiri

Butuh compiler C, misalnya MSVC Build Tools atau MinGW. Nuitka mendeteksi otomatis.

```bash
git clone https://github.com/Luxey9/Image-Compressor.git
cd Image-Compressor

uv venv .venv --python 3.11
uv pip install -r requirements-build.txt --python .venv/Scripts/python.exe

build.cmd                                # hasil: build\ImageCompressor.exe
```

Build pertama 5 sampai 9 menit. Log lengkap ada di `build_log.txt`.

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
| `--cli` | wajib | Mode tanpa GUI, dipakai untuk otomatisasi |
| `--out DIR` | `<folder>_compressed` | Folder tujuan |
| `--in-place` | nonaktif | Timpa di tempat, nama file ikut format keluaran |
| `--width N` | 1920 | Lebar maksimal px. `0` berarti tanpa resize |
| `--quality N` | 85 | Kualitas JPEG/WebP |
| `--format FMT` | JPEG | `JPEG` / `WEBP` / `PNG` |
| `--jobs N` | otomatis | Jumlah worker paralel. `1` berarti berurutan |
| `--no-recursive` | nonaktif | Jangan telusuri subfolder |
| `--keep-bigger` | nonaktif | Tetap tulis hasil walau tidak lebih kecil |
| `--delete-orig` | nonaktif | Hapus file asli setelah konversi format |

Folder tujuan yang sama dipakai untuk file maupun folder. Beberapa file dari folder
berbeda akan dikumpulkan datar ke `--out`, sementara nama file dipertahankan.

Tanpa `--cli`, `ImageCompressor.exe "D:\foto"` hanya membuka GUI dengan folder
sumber terisi.

### Contoh hasil nyata

```
60 gambar (648 MB) menjadi 12.3 MB dalam 14.5 s, 44.8 MB/s, hemat 98.1%
```

### Paralel dan cepat

Semua file dikerjakan bersamaan, bukan satu per satu. Pillow melepas GIL saat
decode dan encode, jadi thread benar-benar paralel. Semuanya berjalan di **CPU**,
tidak ada akselerasi GPU:

| Mode | 16 file / 91 MB | Speedup |
|---|---|---|
| berurutan | 11,4 s | 1,0x |
| thread 4 | 4,8 s | 2,4x |
| thread 8 | 3,5 s | 3,3x |
| **thread 16** | **2,5 s** | **4,6x** |

Jumlah worker default sama dengan jumlah core, dibatasi RAM yang tersedia (sekitar
300 MB per worker). Atur manual dengan `--jobs`, atau kolom *Worker paralel* di GUI.

---

## File di repo

```
image_compressor.py     core, GUI, dan mode headless
gui_v12.py              seluruh widget GUI (tkinter)
ui_kit.py               komponen UI kustom (tombol, switch, radio, entry)
build.cmd               script build Nuitka, hasil ke build\ImageCompressor.exe
make_icon.py            generator app.ico
app.ico                 ikon aplikasi
requirements.txt        dependency runtime (Pillow, pillow-heif)
requirements-build.txt  tambahan Nuitka untuk membangun exe
```

Catatan kecil:

- JPEG mem-flatten transparansi ke latar putih
- orientasi EXIF dibetulkan, jadi foto HP tidak miring
- "lewati jika hasil tidak lebih kecil" aktif secara default
- pengaturan GUI disimpan di `%USERPROFILE%\.image_compressor.json`, folder sumber
  dan tujuan sengaja tidak disimpan

---

MIT, lihat [LICENSE](LICENSE).
