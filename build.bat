@echo off
title Alfred - Compilation Build Windows
echo ===================================================
echo        Compilation d'un .exe autonome d'Alfred
echo ===================================================

echo [1/3] Verification de l'environnement uv...
uv run python --version

echo [2/3] Compilation avec PyInstaller...
uv run pyinstaller --noconfirm --onedir --windowed ^
    --name "Alfred" ^
    --collect-all customtkinter ^
    --hidden-import "src.alfred.core" ^
    --hidden-import "src.alfred.ui" ^
    main.py

if errorlevel 1 (
    echo [ERREUR] La compilation a echoue.
    exit /b %errorlevel%
)

echo [3/3] Copie du dossier settings dans dist/Alfred/...
if not exist "dist\Alfred\settings" mkdir "dist\Alfred\settings"
xcopy /E /I /Y "settings" "dist\Alfred\settings"

echo ===================================================
echo [SUCCES] L'executable autonome est pret dans dist\Alfred\Alfred.exe
echo ===================================================
