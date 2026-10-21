#!/bin/sh
# Run only this Wysun adaptation with its coherent, parallel Qt runtime.
set -eu
optdir="$HOME/.local/opt"
runtime="${WYSUN_CAEL_RUNTIME:-$optdir/wysun-wysun-runtime}"
qs="$runtime/quickshell/bin/quickshell"
if [ ! -x "$qs" ]; then
    echo 'Wysun: falta compilar el runtime Wysun. Consulta apps/shell/WYSUN.md.' >&2
    exit 1
fi
export QML_IMPORT_PATH="$runtime/wysun/lib/qt6/qml:$runtime/deps/lib/qt6/qml"
export WYSUN_LIB_DIR="$runtime/wysun/lib/wysun"
config="${WYSUN_SHELL_CONFIG:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
# qt.conf and executable/plugin RPATHs select Qt; no LD_LIBRARY_PATH is exported.
# Only the Wysun QML import path is set (applications launched by the shell
# should ignore it; backend.py also strips it for its own subprocesses).
exec "$qs" -p "$config" "$@"
