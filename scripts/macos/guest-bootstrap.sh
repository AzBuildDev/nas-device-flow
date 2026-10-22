#!/bin/bash
# Prepare a private source copy and controller image inside the bridged Linux VM.
# Never starts a container, DHCP service, or changes host/router networking.
set -euo pipefail

usage() { echo 'Usage: sudo bash guest-bootstrap.sh --source /mnt/ndf-source --destination /home/USER/nas-device-flow [--interface ndflan] [--check-only]'; }
SOURCE=/mnt/ndf-source
DESTINATION=
LAN_INTERFACE=ndflan
CHECK_ONLY=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --source|--destination|--interface)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      case "$1" in --source) SOURCE=$2 ;; --destination) DESTINATION=$2 ;; --interface) LAN_INTERFACE=$2 ;; esac
      shift 2 ;;
    --check-only) CHECK_ONLY=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done
fail() { printf 'Preparation stopped: %s\n' "$1" >&2; exit 1; }
[[ $(uname -s) == Linux ]] || fail 'Run this inside the Linux VM, not on macOS.'
[[ $EUID -eq 0 ]] || fail 'Run explicitly with sudo inside the Linux VM.'
case "$(uname -m)" in x86_64|aarch64|arm64) ;; *) fail 'Only x86-64 and ARM64 guest architectures are accepted.' ;; esac
[[ "$SOURCE" == /* && "$DESTINATION" == /* && "$DESTINATION" != / ]] || fail 'Source and destination must be absolute paths; destination must not be /.'
[[ "$LAN_INTERFACE" =~ ^[a-zA-Z0-9_.:-]+$ ]] || fail 'Invalid LAN interface name.'
for tool in python3 ip docker tar; do
  command -v "$tool" >/dev/null || fail 'Missing guest dependencies. Install python3, python3-venv, iproute2, tar, rootful Docker and Docker Compose v2 using your distribution instructions. On Debian/Ubuntu the base packages are: sudo apt-get install python3 python3-venv iproute2 tar. Docker installation is separate.'
done
docker compose version >/dev/null 2>&1 || fail 'Docker Compose v2 is unavailable.'
docker info >/dev/null 2>&1 || fail 'Rootful Docker daemon is unavailable.'
docker_endpoint=${DOCKER_HOST:-$(docker context inspect --format '{{.Endpoints.docker.Host}}')}
[[ "$docker_endpoint" == unix://* ]] || fail 'Use the local guest Docker daemon, not a remote Docker context.'
[[ $(docker info --format '{{.OSType}}') == linux ]] || fail 'The local Docker daemon must run Linux containers.' 
security_options=$(docker info --format '{{json .SecurityOptions}}')
[[ "$security_options" != *rootless* ]] || fail 'Rootless Docker cannot provide this macvlan gateway.'
[[ -c /dev/net/tun ]] || fail 'The guest is missing /dev/net/tun.'
[[ ! -d "/sys/class/net/$LAN_INTERFACE/wireless" ]] || fail 'Use the bridged wired LAN interface.'
# Only print validation errors, not interface addresses or network inventories.
python3 - "$LAN_INTERFACE" <<'PY'
import ipaddress,json,subprocess,sys
interface=sys.argv[1]
def fail(message):
 print('Preparation stopped: '+message,file=sys.stderr);sys.exit(1)
def ip(*args):
 try:return json.loads(subprocess.check_output(['ip','-j',*args],stderr=subprocess.DEVNULL))
 except (subprocess.SubprocessError,ValueError):fail('Cannot inspect the bridged guest interface.')
entries=ip('address','show','dev',interface)
if len(entries)!=1 or entries[0].get('link_type')!='ether' or 'UP' not in entries[0].get('flags',[]):fail('Bridged Ethernet interface must exist and be UP.')
private=[ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')]
addresses=[ipaddress.ip_interface(str(a['local'])+'/'+str(a['prefixlen'])) for a in entries[0].get('addr_info',[]) if a.get('family')=='inet' and a.get('scope')=='global']
if not any(any(a.ip in network for network in private) for a in addresses):fail('Bridged interface needs a private LAN IPv4 address.')
routes=ip('route','show','default')
if not routes or any(r.get('dev')!=interface for r in routes):fail('Default IPv4 route must use the bridged LAN interface; a NAT default is not accepted.')
if not any(r.get('gateway') and any(ipaddress.ip_address(r['gateway']) in a.network for a in addresses) for r in routes):fail('LAN default gateway must be on the bridged subnet.')
PY
for entry in app scripts examples docs Dockerfile requirements.txt compose.yaml setup.compose.yaml LICENSE; do
  [[ -e "$SOURCE/$entry" ]] || fail 'Source checkout is incomplete.'
  [[ -z $(find "$SOURCE/$entry" -type l -print -quit) ]] || fail 'Source allowlist contains a symlink; inspect it before copying.'
done
[[ ! -e "$DESTINATION" && ! -L "$DESTINATION" ]] || fail 'Destination already exists; choose a new private directory. Existing configurations are never overwritten.'
if $CHECK_ONLY; then
  echo 'Guest preflight passed. No files copied, image built, services started or network settings changed.'
  exit 0
fi
umask 077
mkdir -p "$DESTINATION"
# Copy only public source paths. Never copy .env, runtime, .git or local credentials.
tar -C "$SOURCE" --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' -cf - app scripts examples docs Dockerfile requirements.txt compose.yaml setup.compose.yaml LICENSE | tar -C "$DESTINATION" -xf -
# No compose initialization exists yet. Build the Dockerfile directly instead of
# inventing required production LAN values just to run compose build.
docker build --tag ndfcontroller:0.3.0-rc.1 "$DESTINATION"
if [[ -n ${SUDO_UID:-} && -n ${SUDO_GID:-} && ${SUDO_UID} != 0 ]]; then
  chown -R "$SUDO_UID:$SUDO_GID" "$DESTINATION"
fi
cat <<'MESSAGE'
Private source copy and local controller image are ready.
No containers or DHCP services were started. No router settings were changed.
Next: in the private destination, create and review config.local.json, use
scripts/initialize.py with the actual bridged LAN interface, then set
CONTROLLER_IMAGE=ndfcontroller:0.3.0-rc.1 in the private .env before starting
Compose. Verify the configuration and image architecture first. Keep DHCP OFF
until a separate LAN client passes direct/proxy/DNS and recovery tests.
MESSAGE
