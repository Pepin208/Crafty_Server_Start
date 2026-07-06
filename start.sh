#!/bin/bash
# Corre el gateway. Ctrl+C para frenar.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/config.sh"
"$CRAFTY_DIR/venv/bin/python3" "$DIR/gateway.py"
