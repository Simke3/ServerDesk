#!/usr/bin/env bash
# Installs ServerDesk for the current user: ~/.local/share/serverdesk-app + launcher + menu entry.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/serverdesk-app"
mkdir -p "$DEST" "$HOME/.local/bin" "$HOME/.local/share/applications"
rm -rf "$DEST/serverdesk"
cp -r "$SRC/serverdesk" "$SRC/requirements.txt" "$DEST/"
python3 -m venv "$DEST/venv"
"$DEST/venv/bin/pip" install --upgrade pip >/dev/null
"$DEST/venv/bin/pip" install -r "$DEST/requirements.txt"
cat > "$HOME/.local/bin/serverdesk" <<LAUNCH
#!/usr/bin/env bash
cd "$DEST"
exec "$DEST/venv/bin/python" -m serverdesk "\$@"
LAUNCH
chmod +x "$HOME/.local/bin/serverdesk"
cat > "$HOME/.local/share/applications/serverdesk.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=ServerDesk
Comment=Linux server administration console
Exec=$HOME/.local/bin/serverdesk
Terminal=false
Categories=System;Monitor;Network;
DESK
echo "Installed. Run 'serverdesk' or open it from your application menu."
