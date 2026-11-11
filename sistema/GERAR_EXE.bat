@echo off
rem Gera dist\Conciliador.exe (para colegas sem Python). Rodar numa maquina COM Python.
cd /d "%~dp0"
python -m pip install --user -r requirements.txt pyinstaller || goto :erro
python -m PyInstaller --noconfirm --onefile --name Conciliador ^
  --distpath "%~dp0..\programa" --workpath "%TEMP%\conciliador_build" --specpath "%TEMP%\conciliador_build" ^
  --add-data "%~dp0conciliador\ocr_windows.ps1;conciliador" ^
  --add-data "%~dp0config.json;." ^
  --hidden-import win32timezone --collect-submodules pywinauto --collect-submodules comtypes ^
  "%~dp0conciliador_cli.py" || goto :erro
echo Gerado: programa\Conciliador.exe
pause & exit /b 0
:erro
echo Falha ao gerar o executavel.
pause & exit /b 1
