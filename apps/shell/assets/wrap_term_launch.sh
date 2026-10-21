#!/usr/bin/env sh

cat ~/.local/state/wysun/sequences.txt 2>/dev/null

exec "$@"
