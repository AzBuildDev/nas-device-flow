#!/bin/sh
# Read-only guest prerequisites. Does NOT prove bridge/DHCP/IPv6 readiness.
set -eu
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] || { echo 'Requires x86_64 Linux VM' >&2; exit 1; }
command -v docker >/dev/null
docker info >/dev/null
docker compose version
endpoint=${DOCKER_HOST:-$(docker context inspect --format '{{.Endpoints.docker.Host}}')}
case "$endpoint" in unix://*) ;; *) echo 'Local guest Docker socket required' >&2; exit 1 ;; esac
case "$(docker info --format '{{json .SecurityOptions}}')" in *rootless*) echo 'Rootful Docker required for macvlan/TUN' >&2; exit 1 ;; esac
[ -c /dev/net/tun ] || { echo 'Missing /dev/net/tun' >&2; exit 1; }
for tool in ip arping python3; do command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 1; }; done
ip -brief link
ip -brief address
ip route show default
printf '%s\n' 'Prerequisites only. Verify wired external switch, MAC spoofing/multi-MAC, unused addresses outside DHCP pool, unique DHCP authority and IPv6 path separately. No readiness claim.'
