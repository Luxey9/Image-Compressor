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

GUI cukup untuk kerja manual. Untuk banyak folder, otomatisasi, atau tugas terjadwal,
pakai mode headless.

```bat
ImageCompressor.exe --cli "D:\foto"
```

Tanpa `--cli`, exe hanya membuka GUI:

```bat
ImageCompressor.exe                       :: buka GUI kosong
ImageCompressor.exe "D:\foto"             :: GUI dengan folder sumber terisi
```

### Perintah yang paling sering dipakai

```bat
:: kompres satu folder, hasil di "foto_compressed" sebelah folder asalnya
ImageCompressor.exe --cli "D:\foto"

:: banyak folder sekaligus, tiap folder dapat folder hasilnya sendiri
ImageCompressor.exe --cli "D:\foto-a" "D:\foto-b" "D:\foto-c"

:: banyak folder, semuanya dikumpulkan ke satu folder tujuan
ImageCompressor.exe --cli "D:\foto-a" "D:\foto-b" --out "D:\hasil"

:: file tertentu saja, boleh dari folder berbeda
ImageCompressor.exe --cli "D:\a\1.jpg" "D:\b\2.png" --out "D:\pilih"

:: konversi ke WebP dan timpa di tempat
ImageCompressor.exe --cli "D:\foto" --format WEBP --in-place
```

### Semua opsi

| Opsi | Default | Keterangan |
|---|---|---|
| `--cli` | wajib | Mode headless, tanpa jendela GUI |
| `--out DIR`, `-o DIR` | `<folder>_compressed` | Folder tujuan |
| `--in-place` | nonaktif | Timpa di tempat, nama file ikut format keluaran |
| `--width N`, `-w N` | `1920` | Lebar maksimal px. `0` berarti tanpa resize |
| `--quality N`, `-q N` | `85` | Kualitas JPEG/WebP, 1 sampai 100 |
| `--format FMT` | `JPEG` | `JPEG`, `WEBP`, atau `PNG` |
| `--jobs N`, `-j N` | otomatis | Jumlah worker paralel. `1` berarti berurutan |
| `--no-recursive` | nonaktif | Jangan telusuri subfolder |
| `--keep-bigger` | nonaktif | Tetap tulis hasil walau ukurannya tidak lebih kecil |
| `--delete-orig` | nonaktif | Hapus file asli setelah konversi format |
| `-h`, `--help` | | Tampilkan bantuan |

### Nama folder hasil

Kalau `--out` tidak diberikan, tiap folder sumber menghasilkan folder baru bernama
`<nama folder>_compressed`, ditaruh **di sebelah** folder asalnya, bukan di dalamnya.

| Folder sumber | Folder hasil |
|---|---|
| `D:\Foto Liburan` | `D:\Foto Liburan_compressed` |
| `D:\foto-kecil` | `D:\foto-kecil_compressed` |
| `D:\proyek\2026\raw` | `D:\proyek\2026\raw_compressed` |

Struktur subfolder di dalamnya tetap dipelihara:

```
foto-b\b1.jpg            -> foto-b_compressed\b1.webp
foto-b\sub\b2-sub.jpg    -> foto-b_compressed\sub\b2-sub.webp
```

Kalau `--out` diberikan, nama folder sumber diabaikan dan semua isinya dikumpulkan ke
folder itu. Karena semuanya dituang ke satu tempat, file dengan nama sama dari folder
berbeda akan saling menimpa. Pakai mode tanpa `--out` kalau nama file di folder-folder
tersebut mirip.

### Banyak folder sekaligus

Jumlah folder tidak dibatasi, dan folder boleh dicampur dengan file dalam satu perintah:

```bat
ImageCompressor.exe --cli "D:\a" "D:\b" "D:\c" --out "D:\hasil" --format WEBP --width 1280
```

Kalau foldernya berpola, biarkan shell yang mengumpulkan:

```bat
:: CMD, setiap subfolder di D:\proyek jadi satu pekerjaan terpisah
for /D %d in ("D:\proyek\*") do ImageCompressor.exe --cli "%~fd" --format WEBP
```

```powershell
# PowerShell, folder dijalankan paralel sehingga jauh lebih cepat
Get-ChildItem "D:\proyek" -Directory | ForEach-Object {
  Start-Process -NoNewWindow -Wait "ImageCompressor.exe" -ArgumentList @(
    "--cli", "`"$($_.FullName)`"",
    "--out", "`"$($_.FullName)-web`"",
    "--format", "WEBP", "--width", "1280"
  )
}
```

### Format HEIC dari iPhone

HEIC dibaca langsung, tidak perlu dikonversi dulu:

```bat
ImageCompressor.exe --cli "D:\iPhone" --format JPEG --quality 90
```

### Contoh hasil nyata

```
7 gambar di 3 folder
Selesai dalam 1.6s  |  OK 7  |  dilewati 0  |  gagal 0
Kecepatan     : 17.6 MB/s
Total ukuran  : 27.8 MB -> 480.7 KB
Ruang dihemat : 98.3%
```

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

### Dipanggil dari aplikasi lain

Exit code `0` berarti semua file berhasil, selain itu ada yang gagal. Cocok untuk
dipanggil dari skrip, Task Scheduler, atau build pipeline:

```bat
ImageCompressor.exe --cli "D:\hasil-export" --format WEBP --jobs 8
if errorlevel 1 echo ada yang gagal
```

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
