Name:           dolibarr-agent
Version:        1.0.0
Release:        1%{?dist}
Summary:        Dolibarr Sysinfo Agent (Linux)
License:        GPL-3.0-or-later
URL:            https://github.com/BB2A-Anthony/dolibarr_sysinfo_agent_linux
BuildArch:      noarch
Requires:       python3 >= 3.6
Requires:       python3-psutil
Requires:       python3-requests
%if 0%{?suse_version}
BuildRequires:  systemd-rpm-macros
%{?systemd_requires}
%else
Requires(post):  systemd
Requires(preun): systemd
Requires(postun): systemd
%endif

%description
Agent Linux qui collecte les informations systemes de la machine
et les envoie periodiquement a l'API Dolibarr (module systeminfo)
via HTTP POST (JSON).

%prep
# Les sources sont fournies directement par build-packages.sh via un repertoire.

%build
# Script Python pur, rien a compiler.

%install
mkdir -p %{buildroot}/opt/dolibarr-agent
cp -r agent run.py config.example.json %{buildroot}/opt/dolibarr-agent/
mkdir -p %{buildroot}%{_unitdir}
cp dolibarr-agent.service %{buildroot}%{_unitdir}/dolibarr-agent.service

%files
/opt/dolibarr-agent
%{_unitdir}/dolibarr-agent.service

%post
if [ ! -f /opt/dolibarr-agent/config.json ]; then
    cp /opt/dolibarr-agent/config.example.json /opt/dolibarr-agent/config.json
    chmod 600 /opt/dolibarr-agent/config.json
fi
%if 0%{?suse_version}
%service_add_post dolibarr-agent.service
%else
systemctl daemon-reload || true
systemctl enable dolibarr-agent.service || true
%endif

%preun
%if 0%{?suse_version}
%service_del_preun dolibarr-agent.service
%else
systemctl stop dolibarr-agent.service >/dev/null 2>&1 || true
%endif

%postun
%if 0%{?suse_version}
%service_del_postun dolibarr-agent.service
%else
systemctl daemon-reload || true
%endif

%changelog
* Wed Feb  5 2025 BB2A-Anthony 1.0.0-1
- Version initiale : agent Linux Dolibarr Sysinfo.
