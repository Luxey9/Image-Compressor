@echo off
cd /d "%~dp0"
echo BUILD_START %DATE% %TIME% > build_log.txt
".venv\Scripts\python.exe" -m nuitka ^
  --standalone --onefile ^
  --enable-plugin=tk-inter ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=app.ico ^
  --assume-yes-for-downloads ^
  --disable-cache=ccache ^
  --output-dir=build ^
  --output-filename=ImageCompressor.exe ^
  --company-name="Lab AP" ^
  --product-name="Image Compressor" ^
  --file-version=1.1.0.0 ^
  --product-version=1.1.0.0 ^
  --file-description="Kompres dan resize massal aset gambar untuk web" ^
  --include-package=pillow_heif ^
  --include-package-data=pillow_heif ^
  --nofollow-import-to=test_core ^
  --nofollow-import-to=make_icon ^
  image_compressor.py >> build_log.txt 2>&1
echo BUILD_EXIT=%ERRORLEVEL% >> build_log.txt
