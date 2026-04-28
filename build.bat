@echo off
echo ============================================
echo  Local Dimming Validator - Build Executable
echo ============================================

pyinstaller local_dimming_align.spec --noconfirm

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo [OK] Build complete.
echo Output folder: dist\local_dimming_validator\
echo.
echo Copy the following files alongside the .exe before running:
echo   zone.txt
pause
