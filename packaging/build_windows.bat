@echo off
REM Build SUpload.exe tren Windows. Ket qua: dist\SUpload\SUpload.exe va dist\SUpload-windows.zip
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :err
REM Giao dien da duoc build san trong web\. Neu sua frontend\ thi chay truoc: cd frontend ^&^& npm ci ^&^& npm run build
pyinstaller packaging\supload.spec --noconfirm
if errorlevel 1 goto :err
powershell -NoProfile -Command "Compress-Archive -Path dist\SUpload -DestinationPath dist\SUpload-windows.zip -Force"
echo.
echo Xong: dist\SUpload\SUpload.exe  (ban zip: dist\SUpload-windows.zip)
pause
exit /b 0
:err
echo Build that bai, xem loi o tren.
pause
exit /b 1
