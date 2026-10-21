#!/bin/sh
# Run the Wysun shell with its own, coherent Qt runtime (see installer/runtime_build.py).
set -eu
runtime="${WYSUN_RUNTIME:-${XDG_DATA_HOME:-$HOME/.local/share}/wysun/runtime}"
qs="$runtime/quickshell/bin/quickshell"
if [ ! -x "$qs" ]; then
    echo 'Wysun: falta el runtime del shell. Ejecuta: python3 installer/runtime_build.py (o ./instalar.sh --orbit-only).' >&2
    exit 1
fi
export QML_IMPORT_PATH="$runtime/shell/lib/qt6/qml:$runtime/deps/lib/qt6/qml"
export WYSUN_LIB_DIR="$runtime/shell/lib/wysun"
config="${WYSUN_SHELL_CONFIG:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
# Executable and plugin RPATHs select Qt; no LD_LIBRARY_PATH is exported.
exec "$qs" -p "$config" "$@"
