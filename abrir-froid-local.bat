@echo off
setlocal
cd /d "%~dp0froid-dashboard\dist"
echo.
echo FROID local aberto em:
echo http://127.0.0.1:5181/#/session/froid-preview-layout
echo.
echo Mantenha esta janela aberta enquanto estiver usando o FROID local.
echo Para encerrar, pressione Ctrl+C.
echo.
python -m http.server 5181 --bind 127.0.0.1
pause
