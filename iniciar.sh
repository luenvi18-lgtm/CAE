#!/usr/bin/env sh
# Inicia CAE en Linux o macOS. Requiere Python 3.10 o superior.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
    echo "Creando entorno virtual..."
    python3 -m venv .venv
fi
. .venv/bin/activate
echo "Instalando dependencias..."
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
exec python wsgi.py
