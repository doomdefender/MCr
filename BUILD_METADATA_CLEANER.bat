@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title MetaDataCleaner - Build
echo ==========================================
echo        MetaDataCleaner - BUILD
echo ==========================================
echo.
where py >nul 2>nul
if not errorlevel 1 (
    set "PY=py"
) else (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PY=python"
    ) else (
        echo ERROR: Python no esta instalado o no esta en PATH.
        echo Instala Python 3.11+ y vuelve a ejecutar este archivo.
        echo.
        pause
        exit /b 1
    )
)
echo Python detectado: %PY%
echo.
echo [1/3] Instalando/actualizando dependencias de compilacion...
%PY% -m pip install --upgrade pillow pyinstaller
if errorlevel 1 goto :error
echo.
echo [2/3] Limpiando compilaciones anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist MetaDataCleaner.spec del /q MetaDataCleaner.spec
if not exist "metadata_cleaner.py" (
    echo ERROR: No se encontro metadata_cleaner.py
    goto :error
)
if not exist "MCr.ico" (
    echo ERROR: No se encontro MCr.ico
    goto :error
)
if not exist "MCr_logo.png" (
    echo ERROR: No se encontro MCr_logo.png
    goto :error
)
echo.
echo [3/3] Compilando MetaDataCleaner.exe...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name MetaDataCleaner ^
  --icon "%CD%MCr.ico" ^
  --add-data "%CD%MCr.ico;." ^
  --add-data "%CD%MCr_logo.png;." ^
  metadata_cleaner.py
if errorlevel 1 goto :error
if not exist "distMetaDataCleaner.exe" (
    echo ERROR: PyInstaller termino pero no se encontro el EXE.
    goto :error
)
echo.
echo ==========================================
echo        COMPILACION TERMINADA
echo ==========================================
echo.
echo EXE creado en:
echo %CD%distMetaDataCleaner.exe
echo.
echo El EXE compilado puede ejecutarse sin Python ni Internet.
echo Los archivos originales no se modifican al usar la aplicacion.
echo.
pause
exit /b 0
:error
echo.
echo ==========================================
echo        ERROR DE COMPILACION
echo ==========================================
echo Revisa el mensaje anterior.
echo.
pause
exit /b 1
