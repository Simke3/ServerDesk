#!/usr/bin/env bash
# Removes ServerDesk installed by install.sh (per-user): app dir, launcher and menu entry.
# User data (config, audit log, cache) is kept unless you pass --purge or answer "y" when asked.
#
# Usage: ./uninstall.sh [--purge | --keep-data] [-y]
#   --purge      also delete config, audit log and cache
#   --keep-data  never delete config, audit log and cache (no question asked)
#   -y           do not ask for confirmation
set -euo pipefail

PURGE=ask
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=yes ;;
    --keep-data) PURGE=no ;;
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

DEST="$HOME/.local/share/serverdesk-app"
LAUNCHER="$HOME/.local/bin/serverdesk"
DESKTOP="$HOME/.local/share/applications/serverdesk.desktop"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/serverdesk"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/serverdesk"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/serverdesk"

ask() {  # ask "question" -> returns 0 on yes
  local reply
  read -r -p "$1 [y/N] " reply || return 1
  [[ "$reply" =~ ^[Yy]$ ]]
}

if [ "$ASSUME_YES" -eq 0 ]; then
  ask "Remove ServerDesk (app, launcher, menu entry)?" || { echo "Cancelled."; exit 0; }
fi

# Stop a running instance and close SSH multiplexed connections.
pkill -f "$DEST/venv/bin/python -m serverdesk" 2>/dev/null || true
if [ -d "$CACHE_DIR" ]; then
  for sock in "$CACHE_DIR"/cm-*; do
    [ -S "$sock" ] && ssh -O exit -o "ControlPath=$sock" dummy >/dev/null 2>&1 || true
  done
fi

rm -rf "$DEST"
rm -f "$LAUNCHER" "$DESKTOP"
command -v update-desktop-database >/dev/null 2>&1 \
  && update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
echo "Removed application, launcher and menu entry."

if [ "$PURGE" = ask ]; then
  if [ "$ASSUME_YES" -eq 1 ]; then PURGE=no
  elif ask "Also delete config, audit log and cache ($CONFIG_DIR, $DATA_DIR, $CACHE_DIR)?"; then PURGE=yes
  else PURGE=no; fi
fi

if [ "$PURGE" = yes ]; then
  rm -rf "$CONFIG_DIR" "$DATA_DIR" "$CACHE_DIR"
  echo "Removed config, audit log and cache."
else
  echo "Kept user data: $CONFIG_DIR, $DATA_DIR"
  rm -rf "$CACHE_DIR"
fi

echo "ServerDesk uninstalled."
