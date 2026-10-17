"""Auto-update for the Linux agent.

Queries the Dolibarr module 'sysinfo' config endpoint
(GET /api/index.php/sysinfo/config), which exposes the latest agent
version and its GitHub release update folder. If the remote version is
newer, downloads the package zip, replaces the installed files
(config.json preserved) and restarts the agent process.
"""

import logging
import os
import shutil
import sys
import tempfile
import zipfile

import requests

from agent import sender

logger = logging.getLogger("agent.updater")

AGENT_VERSION = "1.0.0"
OS_KEY = "linux"
PACKAGE_FILENAME = "dolibarr_agent_linux.zip"
CONFIG_ENDPOINT = "/sysinfo/config"


def _version_tuple(version):
    parts = []
    for chunk in str(version).split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_for_update(config):
    """Return the remote update info if a newer version is available."""
    if not config.get("auto_update", True):
        return None
    try:
        resp = requests.get(
            sender.dolibarr_url(config, CONFIG_ENDPOINT),
            headers=sender.auth_headers(config),
            timeout=config.get("timeout_seconds", 30),
            verify=config.get("verify_ssl", True),
        )
        resp.raise_for_status()
        info = (resp.json() or {}).get(OS_KEY) or {}
    except Exception as exc:
        logger.warning("Verification de mise a jour echouee : %s", exc)
        return None
    remote_version = info.get("version")
    update_url = info.get("update_url")
    if not remote_version or not update_url:
        return None
    if _version_tuple(remote_version) <= _version_tuple(AGENT_VERSION):
        return None
    logger.info("Nouvelle version disponible : %s (actuelle %s)", remote_version, AGENT_VERSION)
    return info


def apply_update(config, info):
    """Download and install the new version, then restart the process."""
    package_url = info["update_url"].rstrip("/") + "/" + PACKAGE_FILENAME
    install_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmp = tempfile.mkdtemp(prefix="dolibarr-agent-update-")
    try:
        logger.info("Telechargement de %s", package_url)
        resp = requests.get(
            package_url,
            timeout=config.get("timeout_seconds", 30),
            verify=config.get("verify_ssl", True),
        )
        resp.raise_for_status()
        zip_path = os.path.join(tmp, PACKAGE_FILENAME)
        with open(zip_path, "wb") as f:
            f.write(resp.content)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        for name in os.listdir(tmp):
            if name == PACKAGE_FILENAME:
                continue
            if name in ("config.json", "config.example.json"):
                continue
            src = os.path.join(tmp, name)
            dst = os.path.join(install_dir, name)
            if os.path.isdir(src):
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    logger.info("Mise a jour vers %s appliquee, redemarrage", info.get("version"))
    os.execv(sys.executable, [sys.executable] + sys.argv)
