@echo off
REM Compila el visor en un paquete autonomo y arma el instalador.
REM No hace falta Python en la maquina de destino: va todo dentro.
setlocal
cd /d "%~dp0"

echo [1/2] empaquetando...
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build dcmviewer.spec || exit /b 1

echo [2/2] instalador...
set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
  echo   Falta Inno Setup:  winget install -e --id JRSoftware.InnoSetup
  exit /b 1
)
%ISCC% instalador.iss || exit /b 1
echo.
echo Listo. El instalador esta en packaging\salida
