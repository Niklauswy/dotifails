#!/bin/sh
# Instala el escritorio Wysun completo desde esta copia del repositorio, que queda como fuente de `wysun update`.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec /usr/bin/python3 "$repo/installer/main.py" install --source "$repo" "$@"
