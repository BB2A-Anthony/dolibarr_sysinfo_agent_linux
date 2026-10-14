import logging
import platform
import socket
import subprocess

import psutil
import requests

logger = logging.getLogger("agent.collector")

PUBLIC_IP_SERVICES = (
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://icanhazip.com",
)

ISP_INFO_SERVICE = "https://ipinfo.io/json"

OS_RELEASE_FILES = ("/etc/os-release", "/usr/lib/os-release")


def collect_system_info(config):
    """Collect Linux system information to report to the API."""
    info = {
        "guid": config["guid"],
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": _processor(),
        "python_version": platform.python_version(),
    }

    os_release = _os_release()
    if os_release:
        info["os_details"] = os_release
        info["linux_distribution"] = " ".join(
            p
            for p in (os_release.get("NAME"), os_release.get("VERSION_ID"))
            if p
        )

    mem = psutil.virtual_memory()
    info["memory"] = {
        "total_bytes": mem.total,
        "available_bytes": mem.available,
        "used_bytes": mem.used,
        "percent_used": mem.percent,
    }

    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        disks.append(
            {
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "percent_used": usage.percent,
            }
        )
    info["disks"] = disks

    nics = []
    for name, addrs in psutil.net_if_addrs().items():
        addresses = [
            {"family": str(a.family), "address": a.address, "netmask": a.netmask}
            for a in addrs
            if a.family in (socket.AF_INET, socket.AF_INET6)
        ]
        if addresses:
            nics.append({"name": name, "addresses": addresses})
    info["network_interfaces"] = nics

    boot_time = psutil.boot_time()
    info["boot_time"] = boot_time
    info["uptime_seconds"] = psutil.time.time() - boot_time

    info["cpu"] = {
        "count_logical": psutil.cpu_count(logical=True),
        "count_physical": psutil.cpu_count(logical=False),
        "percent_used": psutil.cpu_percent(interval=1),
    }

    info["mac_addresses"] = _mac_addresses()
    info["public_ip"] = _public_ip()
    info["isp"] = _isp()

    info["firewall"] = _firewall_status()
    info["updates"] = _update_status()
    info["installed_softwares"] = _installed_packages()
    info["teamviewer"] = _remote_access_id("teamviewer")
    info["rustdesk"] = _remote_access_id("rustdesk")
    info["anydesk"] = _remote_access_id("anydesk")

    return info


def _processor():
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or ""


def _os_release():
    for path in OS_RELEASE_FILES:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = {}
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    data[key] = value.strip('"').strip("'")
                if data:
                    return data
        except OSError:
            continue
    return {}


def _firewall_status():
    """Best-effort firewall detection: firewalld, ufw, nftables, iptables."""
    status = {"available": False}
    try:
        if subprocess.run(
            ["systemctl", "is-active", "firewalld"],
            capture_output=True,
            timeout=5,
        ).returncode == 0:
            status["available"] = True
            status["backend"] = "firewalld"
            status["enabled"] = True
            return status
    except (OSError, subprocess.SubprocessError):
        pass

    for backend, cmd in (("ufw", ["ufw", "status"]), ("nftables", ["nft", "list", "ruleset"])):
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            if result.returncode != 0 and backend != "nftables":
                continue
            output = (result.stdout or b"").decode("utf-8", errors="ignore")
            if backend == "ufw":
                status["available"] = True
                status["backend"] = "ufw"
                status["enabled"] = "Status: active" in output
            else:
                status["available"] = True
                status["backend"] = "nftables"
                status["enabled"] = bool(output.strip())
            if status["available"]:
                return status
        except (OSError, subprocess.SubprocessError):
            continue
    return status


def _update_status():
    """Best-effort pending updates count (apt, dnf, yum, zypper, pacman)."""
    status = {"available": False}
    checks = (
        ("apt", ["apt-get", "-s", "upgrade"], "Inst "),
        ("dnf", ["dnf", "-q", "check-update"], None),
        ("yum", ["yum", "-q", "check-update"], None),
        ("zypper", ["zypper", "--non-interactive", "lu"], None),
        ("pacman", ["pacman", "-Qu"], None),
    )
    for backend, cmd, marker in checks:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode not in (0, 100):
            continue
        output = (result.stdout or b"").decode("utf-8", errors="ignore")
        if marker:
            pending = sum(1 for line in output.splitlines() if line.startswith(marker))
        else:
            pending = sum(
                1
                for line in output.splitlines()
                if line.strip() and not line.startswith(("Loaded", "Checking", "Last metadata"))
            )
        status["available"] = True
        status["backend"] = backend
        status["pending_count"] = pending
        return status
    return status


def _installed_packages():
    """List installed package names (dpkg, rpm, pacman)."""
    for cmd, prefix in (
        (["dpkg-query", "-W", "-f=${Package}\\n"], None),
        (["rpm", "-qa", "--qf", "%{NAME}\\n"], None),
        (["pacman", "-Qq"], None),
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0:
            continue
        names = sorted(
            set(
                line.strip()
                for line in (result.stdout or b"").decode("utf-8", errors="ignore").splitlines()
                if line.strip()
            )
        )
        return names
    return []


def _remote_access_id(name):
    """Best-effort read of a remote-access tool ID from its config file."""
    result = {"installed": False, "id": None}
    candidates = {
        "teamviewer": (
            ("/opt/teamviewer/config/global.conf", "XGuard -"),
            ("/var/lib/teamprefs/teamviewer/global.conf", "XGuard -"),
        ),
        "rustdesk": (
            ("/root/.config/rustdesk/RustDesk.toml", "id ="),
            ("~/.config/rustdesk/RustDesk.toml", "id ="),
        ),
        "anydesk": (
            ("/etc/anydesk/system.conf", "ad.anynet.id ="),
            ("~/.config/anydesk/system.conf", "ad.anynet.id ="),
        ),
    }
    import os

    for path, marker in candidates.get(name, ()):
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            continue
        result["installed"] = True
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith(marker):
                        continue
                    value = line.split("=", 1)[1].strip().strip("'\"")
                    digits = "".join(c for c in value if c.isdigit())
                    if digits:
                        result["id"] = digits
                        return result
        except OSError:
            continue
    return result


def _public_ip():
    """Fetch the public IP from an external service (best effort, short timeout)."""
    for service in PUBLIC_IP_SERVICES:
        try:
            resp = requests.get(service, timeout=5)
            if resp.status_code == 200:
                ip = resp.text.strip()
                if ip:
                    return ip
        except requests.RequestException:
            continue
    return None


def _isp():
    """Fetch the ISP name from ipinfo.io (best effort, short timeout)."""
    try:
        resp = requests.get(ISP_INFO_SERVICE, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("org") or None
    except (requests.RequestException, ValueError):
        pass
    return None


def _mac_addresses():
    macs = []
    for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == getattr(psutil, "AF_LINK", None):
                if addr.address and addr.address not in macs:
                    macs.append(addr.address)
    return macs
