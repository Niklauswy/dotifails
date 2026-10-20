#!/bin/sh
# Run only this Caelestia adaptation with its coherent, parallel Qt runtime.
set -eu
runtime="${WYSUN_CAEL_RUNTIME:-$HOME/.local/opt/wysun-caelestia-runtime}"
qs="$runtime/quickshell/bin/quickshell"
if [ ! -x "$qs" ]; then
    echo 'Wysun: falta compilar el runtime Caelestia. Consulta apps/shell/WYSUN.md.' >&2
    exit 1
fi
config="${WYSUN_SHELL_CONFIG:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
# qt.conf and executable/plugin RPATHs select Qt. No LD_LIBRARY_PATH or Qt
# import/plugin environment is exported into applications launched by the shell.
exec "$qs" -p "$config" "$@"
