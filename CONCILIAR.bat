@echo off
chcp 65001 >nul
title Conciliador ERP
cd /d "%~dp0"
if exist "programa\Conciliador.exe" (
  set RUN="%~dp0programa\Conciliador.exe"
) else (
  cd /d "%~dp0sistema"
  set RUN=python -m conciliador
)
echo.
echo  === Conciliador ERP (metodo automatico, sem Claude) ===
echo.
echo  Antes de continuar:
echo   1. Minerion SGA aberto SO na empresa que vai conciliar
echo   2. Planilha da empresa ABERTA no Excel (do jeito que voce sempre abre)
echo   3. Nao mexa no mouse/teclado durante a leitura do ERP
echo.
%RUN% diagnostico | findstr /B /C:"Empresas"
set /p EMP= Empresa (uma das listadas acima): 
set /p DE= Data inicial DD/MM/AAAA (Enter = dia 1 do mes):
set /p ATE= Data final DD/MM/AAAA (Enter = hoje):
set "OPC=--empresa %EMP%"
if not "%DE%"=="" set "OPC=%OPC% --de %DE%"
if not "%ATE%"=="" set "OPC=%OPC% --ate %ATE%"
echo.
echo  1 = Simular (le o ERP e mostra o que lancaria, sem gravar)
echo  2 = Conciliar de verdade (le o ERP e acrescenta na planilha)
set /p MODO= Opcao:
if "%MODO%"=="1" (
  %RUN% coletar %OPC% && %RUN% extrair --empresa %EMP% && %RUN% lancar --empresa %EMP% --simular
) else (
  %RUN% tudo %OPC%
)
echo.
echo  Relatorio e capturas: %USERPROFILE%\Documents\ConciliadorERP\%EMP%\
pause
