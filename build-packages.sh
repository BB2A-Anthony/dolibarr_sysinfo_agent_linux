#!/bin/bash
# Genere les paquets natifs de l'agent Dolibarr Sysinfo :
#   - .deb  (Debian, Ubuntu, Raspbian/Raspberry Pi OS, Mint) : build natif via dpkg-deb
#   - .rpm  (RHEL/Alma/Rocky, CentOS, Fedora, openSUSE)      : via rpmbuild ou fpm si disponible
#   - Arch  (pacman)                                        : sources preparees pour makepkg
set -euo pipefail

VERSION="${1:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGE="$SCRIPT_DIR/dist"
PKG="dolibarr-agent"

rm -rf "$STAGE"
mkdir -p "$STAGE"

echo "=== [1/3] Construction du paquet .deb (Debian/Ubuntu/Raspbian) ==="
DEB_ROOT="$STAGE/debroot"
mkdir -p "$DEB_ROOT/opt/dolibarr-agent" "$DEB_ROOT/etc/systemd/system"
cp -r "$SCRIPT_DIR/agent" "$SCRIPT_DIR/run.py" \
      "$SCRIPT_DIR/config.example.json" "$DEB_ROOT/opt/dolibarr-agent/"
cp "$SCRIPT_DIR/dolibarr-agent.service" "$DEB_ROOT/etc/systemd/system/${PKG}.service"
find "$DEB_ROOT" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

mkdir -p "$DEB_ROOT/DEBIAN"
cp "$SCRIPT_DIR/packaging/debian/control" "$DEB_ROOT/DEBIAN/control"
sed -i "s/^Version: .*/Version: $VERSION/" "$DEB_ROOT/DEBIAN/control"
cp "$SCRIPT_DIR/packaging/debian/postinst" "$DEB_ROOT/DEBIAN/postinst"
cp "$SCRIPT_DIR/packaging/debian/prerm" "$DEB_ROOT/DEBIAN/prerm"
chmod 755 "$DEB_ROOT/DEBIAN/postinst" "$DEB_ROOT/DEBIAN/prerm"
chmod 644 "$DEB_ROOT/DEBIAN/control"

dpkg-deb --root-owner-group --build "$DEB_ROOT" "$STAGE/${PKG}_${VERSION}_all.deb"
echo "OK : $STAGE/${PKG}_${VERSION}_all.deb"

echo "=== [2/3] Construction du paquet .rpm (RHEL/Fedora/openSUSE) ==="
RPM_BUILT=""
if command -v rpmbuild >/dev/null 2>&1; then
    RPM_TOP="$STAGE/rpmbuild"
    for d in BUILD BUILDROOT RPMS SRPMS SOURCES SPECS; do mkdir -p "$RPM_TOP/$d"; done
    tar -czf "$RPM_TOP/SOURCES/${PKG}-${VERSION}.tar.gz" \
        -C "$DEB_ROOT/opt" dolibarr-agent \
        -C "$SCRIPT_DIR" dolibarr-agent.service
    cp "$SCRIPT_DIR/packaging/rpm/dolibarr-agent.spec" "$RPM_TOP/SPECS/"
    sed -i "s/^Version: .*/Version: $VERSION/" "$RPM_TOP/SPECS/dolibarr-agent.spec"
    sed -i "s|^cp -r agent run.py config.example.json.*|cp -r /opt/dolibarr-agent/agent /opt/dolibarr-agent/run.py /opt/dolibarr-agent/config.example.json %{buildroot}/opt/dolibarr-agent/|" \
        "$RPM_TOP/SPECS/dolibarr-agent.spec"
    rpmbuild --define "_topdir $RPM_TOP" -bb "$RPM_TOP/SPECS/dolibarr-agent.spec" \
        && RPM_BUILT="yes"
fi
if [ -z "$RPM_BUILT" ] && [ -f "$STAGE/rpmbuild" ] || ! command -v rpmbuild >/dev/null 2>&1; then
    echo "AVERTISSEMENT : rpmbuild indisponible ici (fpm pip est un faux paquet, ignore)."
    echo "Le spec est pret : packaging/rpm/dolibarr-agent.spec"
    echo "Sur une machine cible (RHEL/Fedora/openSUSE) :"
    echo "  sudo dnf/zypper install rpm-build && rpmbuild -bb packaging/rpm/dolibarr-agent.spec"
fi

echo "=== [3/3] Preparation des sources Arch (pacman) ==="
ARCH_DIR="$STAGE/arch"
mkdir -p "$ARCH_DIR"
tar -czf "$ARCH_DIR/agent.tar.gz" \
    -C "$SCRIPT_DIR" agent run.py config.example.json dolibarr-agent.service \
    --transform 's|^dolibarr-agent.service$|dolibarr-agent.service|'
cp "$SCRIPT_DIR/packaging/arch/PKGBUILD" "$ARCH_DIR/"
cp "$SCRIPT_DIR/packaging/arch/dolibarr-agent.install" "$ARCH_DIR/"
echo "OK : $ARCH_DIR/ (lancer 'makepkg -sf' sur une machine Arch)"

echo ""
echo "=== Paquets generes dans $STAGE/ ==="
ls -la "$STAGE"/*.deb 2>/dev/null || true
ls -la "$STAGE"/*.rpm 2>/dev/null || true
