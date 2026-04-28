@echo off
echo ============================================
echo  Local Dimming Validator - Build Executable
echo ============================================

pyinstaller local_dimming_align.spec --noconfirm --distpath .

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo [OK] Build complete.
echo Output: local_dimming_validator.exe (same folder as this script)
pause
