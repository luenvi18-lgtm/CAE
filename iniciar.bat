@echo off
REM Inicia CAE en Windows. Requiere Python 3.10 o superior (python.org).
cd /d "%~dp0"
if not exist .venv (
    echo Creando entorno virtual...
    python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat
echo Instalando dependencias...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt || goto :error
python wsgi.py
pause
exit /b 0

:error
echo.
echo No se pudo iniciar. Verifique que Python este instalado y en el PATH.
pause
exit /b 1
