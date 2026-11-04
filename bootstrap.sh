#!/bin/sh
# Equipo nuevo: clona Wysun (rama main) en ~/.local/share/wysun/source e instala todo. Las actualizaciones: wysun update.
set -eu
if ! command -v git >/dev/null || ! command -v python3 >/dev/null; then
    sudo apt-get update
    sudo apt-get install --yes git python3 ca-certificates
fi
destination="${WYSUN_DIR:-$HOME/.local/share/wysun/source}"
if [ -e "$destination" ]; then
    echo "Ya existe $destination. Ejecuta $destination/instalar.sh o, si ya está instalado, wysun update."
    exit 1
fi
git clone --branch main https://github.com/Niklauswy/dotifails.git "$destination"
exec "$destination/instalar.sh" "$@"
