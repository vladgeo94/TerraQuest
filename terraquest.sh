#!/usr/bin/env bash
# TerraQuest launcher for Linux/macOS. All options are handled by terraquest.py (see --help);
# this wrapper only adds the Linux application-menu entry.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-}" in
  --install-desktop)
    mkdir -p "$HOME/.local/share/applications"
    cat > "$HOME/.local/share/applications/terraquest.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TerraQuest
Comment=Learn Terraform Associate (004) as a game
Exec=$DIR/terraquest.sh
Icon=applications-games
Terminal=true
Categories=Education;Development;
EOF
    echo "Installed: ~/.local/share/applications/terraquest.desktop (look for TerraQuest in your app menu)"
    exit 0 ;;
  --uninstall-desktop)
    rm -f "$HOME/.local/share/applications/terraquest.desktop"
    echo "Removed."
    exit 0 ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 not found. Install Python 3.11+ (Arch/CachyOS: sudo pacman -S python, macOS: brew install python)."
  exit 1
fi

exec python3 "$DIR/terraquest.py" "$@"
