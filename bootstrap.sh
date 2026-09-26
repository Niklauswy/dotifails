#!/bin/sh
set -eu
if ! command -v git >/dev/null || ! command -v python3 >/dev/null; then
    sudo apt-get update
    sudo apt-get install --yes git python3 ca-certificates
fi
destination="${DOTIFAILS_DIR:-$HOME/.local/share/dotifails/source}"
if [ -e "$destination" ]; then
    echo "Ya existe $destination. Ejecuta su instalar.sh o dotifails update."
    exit 1
fi
git clone --depth 1 --branch "${DOTIFAILS_REF:-master}" https://github.com/Niklauswy/dotifails.git "$destination"
exec "$destination/instalar.sh" "$@"
