@echo off
chcp 65001 >nul
title Conciliador ERP - Instalacao
cd /d "%~dp0"
echo.
echo  === Conciliador ERP - instalacao ===
echo.
where python >nul 2>nul
if errorlevel 1 (
  echo  Python nao encontrado. Instale pela Microsoft Store ^(Python 3.12 ou mais novo^)
  echo  ou em https://www.python.org/downloads/  e rode este arquivo de novo.
  echo  Alternativa sem Python: o CONCILIAR.bat da pasta principal ja usa programa\Conciliador.exe.
  pause & exit /b 1
)
python -m pip install --user -r requirements.txt
if errorlevel 1 ( echo  Falha ao instalar dependencias. & pause & exit /b 1 )
if not exist "%USERPROFILE%\Documents\ConciliadorERP" mkdir "%USERPROFILE%\Documents\ConciliadorERP"
if not exist "%USERPROFILE%\Documents\ConciliadorERP\config.json" (
  copy "config.json" "%USERPROFILE%\Documents\ConciliadorERP\config.json" >nul
  echo  Config pessoal criada em Documentos\ConciliadorERP\config.json  ^(edite empresas/planilhas^)
)
echo.
python -m conciliador diagnostico
echo.
echo  Instalacao concluida. Use o CONCILIAR.bat da pasta principal.
pause
