#!/usr/bin/env bash
# Offline Linux test: only an isolated veth pair, no production LAN or host DHCP.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $(id -u) == 0 ]] || { echo 'Run as root on a disposable Linux test host'; exit 1; }
[[ $(uname -s) == Linux ]] || exit 1
image=${NDF_TEST_IMAGE:-nas-device-flow-controller:0.1.0-rc.4}
settings=${1:-examples/settings.json}
tmp=$(mktemp -d)
ns="ndf-client-$$"
container="ndf-dhcp-test-$$"
cleanup(){
 docker exec "$container" cat /tmp/dhcp-start.log 2>/dev/null || true
 ip netns del "$ns" 2>/dev/null || true
 docker stop -t 5 "$container" >/dev/null 2>&1 || true
 docker rm "$container" >/dev/null 2>&1 || true
 rm -rf "$tmp"
}
trap cleanup EXIT
mapfile -t cfg < <(PYTHONPATH=app python3 - "$settings" "$tmp" <<'PYCONFIG'
import json,sys,ipaddress
from pathlib import Path
from settings import Settings
s=Settings(**json.loads(Path(sys.argv[1]).read_text()));s.dhcp_authoritative=True
outside=[ip for ip in s.scan_hosts() if not int(ipaddress.ip_address(s.dhcp_start))<=int(ipaddress.ip_address(ip))<=int(ipaddress.ip_address(s.dhcp_end))]
if len(outside)<2:raise SystemExit('Test needs two available addresses outside DHCP pool')
Path(sys.argv[2]+'/dnsmasq.conf').write_text(s.dnsmasq('/tmp'))
print(s.panel_ip);print(s.core_ip);print(s.network.prefixlen);print(outside[0]);print(outside[1])
PYCONFIG
)
[[ ${#cfg[@]} == 5 ]] || exit 1
server=${cfg[0]};gateway=${cfg[1]};prefix=${cfg[2]};old_ip=${cfg[3]};retained=${cfg[4]}
docker run -d --name "$container" --network none --cap-drop ALL  --cap-add NET_ADMIN --cap-add NET_RAW --cap-add NET_BIND_SERVICE --cap-add SETUID --cap-add SETGID  -v "$tmp/dnsmasq.conf:/tmp/dnsmasq.conf:ro" "$image" python3 -c 'import time;time.sleep(3600)' >/dev/null
pid=$(docker inspect -f '{{.State.Pid}}' "$container")
ip netns add "$ns"
ip link add "ndfs$$" type veth peer name "ndfc$$"
ip link set "ndfs$$" netns "$pid"
nsenter -t "$pid" -n ip link set "ndfs$$" name eth0
nsenter -t "$pid" -n ip addr add "$server/$prefix" dev eth0
nsenter -t "$pid" -n ip link set eth0 up
ip link set "ndfc$$" netns "$ns"
ip -n "$ns" link set "ndfc$$" name eth0
ip -n "$ns" link set eth0 address 02:00:00:00:00:01
ip -n "$ns" link set eth0 up
ip -n "$ns" link set lo up
docker exec "$container" touch /tmp/dhcp.hosts
docker exec -d "$container" sh -c 'dnsmasq --keep-in-foreground --conf-file=/tmp/dnsmasq.conf > /tmp/dhcp-start.log 2>&1'
sleep 1
args=(--expected-server "$server" --expected-gateway "$gateway" --expected-dns "$gateway" --prefix "$prefix")
ip netns exec "$ns" env NDF_ISOLATED_DHCP_TEST=1 python3 scripts/dhcp_probe.py "${args[@]}" --old-ip "$old_ip" --exchange --release
printf '02:00:00:00:00:01,%s,12h\n' "$retained" > "$tmp/retained.hosts"
docker cp "$tmp/retained.hosts" "$container:/tmp/dhcp.hosts"
docker exec "$container" sh -c 'kill -HUP $(cat /var/run/dnsmasq.pid)'
ip netns exec "$ns" env NDF_ISOLATED_DHCP_TEST=1 python3 scripts/dhcp_probe.py "${args[@]}" --request-ip "$retained" --release
echo 'PASS: isolated old-lease NAK, DISCOVER/ACK gateway+DNS, retained-address INIT-REBOOT ACK'
