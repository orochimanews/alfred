@echo off
title Alfred - Compilation Build Windows
echo ===================================================
echo        Compilation d'un .exe autonome d'Alfred
echo ===================================================

echo [1/3] Verification de l'environnement uv...
uv run python --version

echo [2/3] Compilation avec PyInstaller...
uv run pyinstaller --noconfirm --onedir --windowed --uac-admin ^
    --name "Alfred" ^
    --icon "assets\icon.ico" ^
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

echo [3/3] Nettoyage et copie des dossiers settings et assets dans dist/Alfred/...
if exist "dist\Alfred\_internal\settings" rmdir /s /q "dist\Alfred\_internal\settings"
if not exist "dist\Alfred\settings" mkdir "dist\Alfred\settings"
xcopy /E /I /Y "settings" "dist\Alfred\settings"
if not exist "dist\Alfred\assets" mkdir "dist\Alfred\assets"
xcopy /E /I /Y "assets" "dist\Alfred\assets"

echo ===================================================
echo [SUCCES] L'executable autonome est pret dans dist\Alfred\Alfred.exe
echo ===================================================
