#!/bin/sh
set -eu
if ! command -v git >/dev/null || ! command -v python3 >/dev/null; then
    sudo apt-get update
    sudo apt-get install --yes git python3 ca-certificates
fi
destination="${WYSUN_DIR:-$HOME/.local/share/wysun/source}"
if [ -e "$destination" ]; then
    echo "Ya existe $destination. Ejecuta su instalar.sh o wysun-install update."
    exit 1
fi
git clone --depth 1 --branch "${WYSUN_REF:-master}" https://github.com/Niklauswy/dotifails.git "$destination"
exec "$destination/instalar.sh" "$@"
