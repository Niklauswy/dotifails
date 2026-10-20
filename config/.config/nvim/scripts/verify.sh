#!/bin/sh
set -eu
config_path=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
NVIM_CHECK_ROOT=$(mktemp -d /tmp/nvim-workbench-test.XXXXXX)
export NVIM_CHECK_ROOT
cp "$config_path"/tests/fixtures/* "$NVIM_CHECK_ROOT/"
g++ -g -O0 -std=c++20 "$NVIM_CHECK_ROOT/debug.cpp" -o "$NVIM_CHECK_ROOT/debug-bin"
result=0
timeout 120s nvim -n -i NONE --headless -c "luafile $config_path/scripts/check.lua" > "$NVIM_CHECK_ROOT/core.log" 2>&1 || result=1
for lang in python javascript cpp; do
  NVIM_CHECK_LANG="$lang" timeout 50s nvim -n -i NONE --headless -c "luafile $config_path/scripts/check-debug.lua" > "$NVIM_CHECK_ROOT/dap-$lang.log" 2>&1 || result=1
done
printf 'Resultados: %s\n' "$NVIM_CHECK_ROOT"
cat "$NVIM_CHECK_ROOT/results.json" "$NVIM_CHECK_ROOT"/dap-*.json
exit "$result"
