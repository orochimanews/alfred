@echo off
title Alfred - Compilation Build Windows
echo ===================================================
echo        Compilation d'un .exe autonome d'Alfred
echo ===================================================

echo [1/3] Verification de l'environnement uv...
uv run python --version

echo [2/3] Compilation avec PyInstaller (sans UPX)...
uv run pyinstaller --noconfirm --onedir --windowed ^
    --name "Alfred" ^
    --icon "assets\icon.ico" ^
    --noupx ^
    --distpath "dist_new" ^
    --collect-all customtkinter ^
    --collect-all pystray ^
    --collect-all PIL ^
    --collect-all keyboard ^
    --hidden-import "src.alfred.core" ^
    --hidden-import "src.alfred.ui" ^
    main.py

if errorlevel 1 (
    echo [ERREUR] La compilation a echoue.
    exit /b %errorlevel%
)

echo [3/3] Copie des dossiers settings et assets dans dist_new/Alfred/...
if not exist "dist_new\Alfred\settings" mkdir "dist_new\Alfred\settings"
xcopy /E /I /Y "settings" "dist_new\Alfred\settings"
if not exist "dist_new\Alfred\assets" mkdir "dist_new\Alfred\assets"
xcopy /E /I /Y "assets" "dist_new\Alfred\assets"

echo ===================================================
echo [SUCCES] L'executable autonome est pret dans dist_new\Alfred\Alfred.exe
echo ===================================================
