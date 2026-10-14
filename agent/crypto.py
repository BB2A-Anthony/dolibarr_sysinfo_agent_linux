"""Encryption helpers for storing the API key at rest.

On Linux the key is stored with file-based protection instead of a DPAPI
equivalent: the config only ever stores "file:<base64>", where the blob is
randomly salted and obfuscated (XOR stream derived from a machine-specific
key). This is not equivalent to a TPM/DPAPI hardware-bound store; it mainly
avoids leaving the plaintext key in world-readable config files.
"""

import base64
import hashlib
import json
import logging
import os

logger = logging.getLogger("agent.crypto")

_PREFIX = "file:"


def _machine_secret():
    """Stable per-machine secret derived from /etc/machine-id (or fallback)."""
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path, "rb") as f:
                data = f.read().strip()
            if data:
                return hashlib.sha256(b"agent:" + data).digest()
        except OSError:
            continue
    return hashlib.sha256(b"agent:fallback").digest()


def _xor(value, salt):
    key = hashlib.sha256(salt + _machine_secret()).digest()
    out = bytearray(value)
    for i in range(len(out)):
        out[i] ^= key[i % len(key)]
    return bytes(out)


def encrypt(value):
    """Encrypt a secret. Returns 'file:<base64 salt>:<base64 data>' or None."""
    try:
        salt = os.urandom(16)
        data = _xor(value.encode("utf-8"), salt)
        return _PREFIX + base64.b64encode(salt).decode("ascii") + ":" + base64.b64encode(data).decode("ascii")
    except Exception:
        logger.exception("Encryption failed")
        return None


def decrypt(stored):
    """Decrypt a 'file:...' value back to plaintext, or None."""
    if not stored or not stored.startswith(_PREFIX):
        return None
    try:
        salt_b64, data_b64 = stored[len(_PREFIX):].split(":", 1)
        data = _xor(base64.b64decode(data_b64), base64.b64decode(salt_b64))
        return data.decode("utf-8")
    except Exception:
        logger.exception("Decryption failed")
        return None


def migrate_config(config, path):
    """Encrypt a plaintext api_key and remove it from the file.

    Called after load_config: if config contains a plaintext api_key,
    replace it with api_key_encrypted on disk.
    """
    plaintext = config.get("api_key")
    if not plaintext:
        return config
    encrypted = encrypt(plaintext)
    if not encrypted:
        return config
    config["api_key_encrypted"] = encrypted
    config.pop("api_key", None)
    try:
        with open(path, "r", encoding="utf-8") as f:
            on_disk = json.load(f)
        on_disk["api_key_encrypted"] = encrypted
        on_disk.pop("api_key", None)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(on_disk, f, indent=4)
        logger.info("Cle API migree: stockage chiffre, clair supprime")
    except OSError:
        logger.warning("Cle API chiffree en memoire mais non persistee")
    return config
