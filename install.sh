#!/bin/bash
# Installation de l'agent Dolibarr Sysinfo pour Linux.
# Compatible Debian/Ubuntu en priorite, ainsi que RHEL/Fedora/CentOS,
# openSUSE et Arch (systemd requis).
set -euo pipefail

INSTALL_DIR="/opt/dolibarr-agent"
SERVICE_NAME="dolibarr-agent"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "Erreur : executez ce script en root (sudo ./install.sh)." >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Erreur : python3 est requis." >&2
    exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
    echo "Erreur : systemd est requis (non disponible sur ce systeme)." >&2
    exit 1
fi

mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR/agent" "$SCRIPT_DIR/run.py" "$INSTALL_DIR/"

if [ ! -f "$INSTALL_DIR/config.json" ]; then
    if [ -f "$SCRIPT_DIR/config.json" ]; then
        cp "$SCRIPT_DIR/config.json" "$INSTALL_DIR/"
    else
        cp "$SCRIPT_DIR/config.example.json" "$INSTALL_DIR/config.json"
    fi
    chmod 600 "$INSTALL_DIR/config.json"
    echo "Configuration creee : $INSTALL_DIR/config.json (a adapter)."
fi

if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    python3 -m pip install -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null \
        || python3 -m pip install --break-system-packages -r "$SCRIPT_DIR/requirements.txt" \
        || echo "Attention : installation des dependances pip echouee (installez requests et psutil via votre gestionnaire de paquets)."
fi

cp "$SCRIPT_DIR/dolibarr-agent.service" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"

echo ""
echo "Installation terminee dans $INSTALL_DIR."
echo "Prochaines etapes :"
echo "  1. Editez $INSTALL_DIR/config.json (api_url, eventuellement --enroll)"
echo "  2. Enrolement : python3 $INSTALL_DIR/run.py --config $INSTALL_DIR/config.json --enroll CODE"
echo "  3. Demarrez   : systemctl start $SERVICE_NAME"
