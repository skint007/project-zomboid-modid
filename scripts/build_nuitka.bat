@echo off
setlocal

set PROJECT_DIR=%~dp0..
cd /d "%PROJECT_DIR%"

python -m nuitka ^
    --onefile ^
    --enable-plugin=pyside6 ^
    --windows-console-mode=disable ^
    --include-package=pz_mod_manager ^
    --output-filename=PZ-Mod-Manager.exe ^
    --output-dir=dist ^
    --remove-output ^
    src\pz_mod_manager\__main__.py

echo Build complete: dist\PZ-Mod-Manager.exe
