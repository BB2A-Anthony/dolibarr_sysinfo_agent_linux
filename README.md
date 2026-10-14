# Dolibarr Sysinfo Agent Linux

Agent Linux qui collecte les informations systemes de la machine et les envoie periodiquement a une API Dolibarr (module `systeminfo`) via HTTP POST (JSON). Chaque machine est identifiee par un `guid` (derive de `/etc/machine-id`), ce qui permet de rattacher les informations au bon tiers.

C'est l'equivalent Linux de l'agent Windows ([dolibarr_sysinfo_agent_windows](https://github.com/BB2A-Anthony/dolibarr_sysinfo_agent_windows)) : meme format de payload, meme protocol d'enrolement, meme module serveur Dolibarr.

## Compatibilite

| Composant | Minimum | Maximum (teste) |
|---|---|---|
| Python | 3.6 | 3.13 |
| psutil | 5.9.0 | 7.x |
| requests | 2.31.0 | 2.32.x |
| systemd | 219 | 256 |
| noyau Linux | 3.10 | 6.12 |
| Dolibarr (module systeminfo) | 11.0 | 20.0 |
| API PHP (cote serveur) | 7.3 | 8.3 |

### Distributions supportees

Priorite : **Ubuntu** et **Debian**. La plupart des distributions avec systemd et Python 3 fonctionnent.

| Distribution | Version min | Version max (teste) | Gestionnaire de paquets |
|---|---|---|---|
| **Ubuntu** | 20.04 LTS | 24.04 LTS (24.10) | apt / dpkg |
| **Debian** | 10 (Buster) | 13 (Trixie) | apt / dpkg |
| **Raspbian / Raspberry Pi OS** | 10 | 13 | apt / dpkg |
| Linux Mint | 20 | 22 | apt / dpkg |
| RHEL / AlmaLinux / Rocky Linux | 8 | 9 | dnf / rpm |
| CentOS Stream | 8 | 9 | dnf / rpm |
| Fedora | 36 | 41 | dnf / rpm |
| openSUSE Leap / Tumbleweed | 15.4 | 15.6 / 2024 | zypper / rpm |
| Arch Linux | — (rolling) | — (rolling) | pacman |

Remarques :
- Les collecteurs optionnels (pare-feu, mises a jour en attente, paquets installes) s'adaptent au gestionnaire de paquets present (`apt`/`dpkg`, `dnf`/`yum`, `zypper`, `pacman`) et se desactivent proprement si l'outil est absent.
- Le support des versions max correspond a la derniere version testee ; les versions ulterieures devraient generalement fonctionner mais ne sont pas garanties.

## Informations collectees

- Hostname, FQDN, nom et version de la distribution (`/etc/os-release`), architecture, processeur (`/proc/cpuinfo`)
- CPU (coeurs logiques/physiques, utilisation)
- Memoire (totale, disponible, utilisee, %)
- Disques (par point de montage : total, utilise, libre, %)
- Interfaces reseau (adresses IPv4/IPv6), adresses MAC, IP publique, FAI (ISP)
- Temps de demarrage et uptime
- Pare-feu (ufw, firewalld, nftables — best effort)
- Mises a jour en attente (apt, dnf, yum, zypper, pacman — best effort)
- Paquets installes (dpkg, rpm, pacman)
- Outils d'acces a distance : TeamViewer, RustDesk, AnyDesk (best effort)

## Configuration (`config.json`)

```json
{
    "api_url": "https://dolibarr.example.com",
    "initial_delay_seconds": 30,
    "poll_interval_seconds": 14400,
    "timeout_seconds": 30,
    "verify_ssl": true
}
```

| Cle | Role |
|---|---|
| `api_url` | URL de base de votre Dolibarr (l'agent construit les URLs `/api/index.php/...`) |
| `guid` | Identifiant de la machine, genere automatiquement (`/etc/machine-id`) — ne se configure normalement pas |
| `api_key` / `api_key_encrypted` | Cle API Dolibarr, envoyee en en-tete `DOLIBARR_API_KEY` ; stockee chiffree apres enrôlement ou `--set-api-key` |
| `initial_delay_seconds` | Delai avant le premier envoi apres demarrage (par defaut 30 s) |
| `poll_interval_seconds` | Intervalle entre deux envois (par defaut 14400 s = 4 h) |
| `timeout_seconds` | Timeout HTTP (par defaut 30 s) |
| `verify_ssl` | Verification du certificat TLS (par defaut true) |

Pas de tiers a renseigner : la machine remonte sans affectation et est rattachee a un tiers **depuis Dolibarr** (`PUT /systeminfo/machine/{guid}/soc` avec `fk_soc`).

## Utilisation en ligne de commande

```bash
# Envoi unique
python3 run.py --config config.json

# Envoi en boucle (toutes les poll_interval_seconds)
python3 run.py --config config.json --loop

# Enrolement avec un code a usage unique genere sur la fiche tiers
python3 run.py --config config.json --enroll CODE

# Stocker la cle API chiffree manuellement
python3 run.py --config config.json --set-api-key CLE_API

# Tester la connexion a l'API Dolibarr
python3 run.py --config config.json --test-connection
```

## Installation en tant que service systemd

```bash
sudo ./install.sh
```

Le script :
1. Copie l'agent dans `/opt/dolibarr-agent`
2. Cree `config.json` (droits 600) s'il n'existe pas
3. Installe les dependances Python (`requests`, `psutil`)
4. Installe et active l'unite systemd `dolibarr-agent`

Ensuite :

```bash
sudo systemctl start dolibarr-agent
sudo systemctl status dolibarr-agent
journalctl -u dolibarr-agent -f
```

Desinstallation :

```bash
sudo systemctl disable --now dolibarr-agent
sudo rm /etc/systemd/system/dolibarr-agent.service
sudo rm -rf /opt/dolibarr-agent
sudo systemctl daemon-reload
```

## Connexion a une instance Dolibarr

1. **Cote Dolibarr** : activer l'API (Configuration > API, module REST), installer le module `systeminfo` (voir le depot de l'agent Windows, dossier `server_module/systeminfo`).
2. **Cote agent** : renseigner `api_url` dans `config.json`, puis soit utiliser l'enrolement (`--enroll CODE` depuis la fiche tiers), soit definir une cle API (`--set-api-key`).
3. L'authentification Dolibarr utilise l'en-tete `DOLIBARR_API_KEY` (pas de Bearer).

## Stockage chiffre de la cle API

La cle API est stockee chiffree dans `config.json` (`api_key_encrypted`), derivee de `/etc/machine-id` : le fichier de config reste protege (chmod 600) mais la cle n'y apparait jamais en clair. Si la machine est reinstanciee ou `/etc/machine-id` regenere, relancez l'enrolement.

## Differences avec l'agent Windows

- Service **systemd** au lieu du service Windows ; pas d'icône de barre des taches (CLI uniquement).
- Identifiant machine : `/etc/machine-id` au lieu du `MachineGuid` du registre.
- Chiffrement de la cle : derive de `/etc/machine-id` au lieu de DPAPI.
- OS, pare-feu, mises a jour et logiciels installes sont collectes via les outils Linux (`/etc/os-release`, `ufw`/`firewalld`/`nft`, `apt`/`dnf`/`zypper`/`pacman`) au lieu du registre/COM Windows.
