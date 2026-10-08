"""Separate configured policy, DHCP allocation, and observed gateway connections."""
import threading
import time


def valid_leases(text, now=None):
    now = time.time() if now is None else now
    leases = set()
    for line in text.splitlines():
        fields = line.split()
        try:
            if len(fields) >= 4 and (int(fields[0]) == 0 or int(fields[0]) > now):
                leases.add((fields[1].lower(), fields[2]))
        except ValueError:
            continue
    return leases


class AccessStatus:
    def __init__(self):
        self.lock = threading.Lock()
        self.seen = {}

    def sample(self, connections, owners, now=None):
        now = time.time() if now is None else now
        with self.lock:
            self.seen = {key: value for key, value in self.seen.items() if now - value < 180}
            for connection in connections:
                ip = connection.get('metadata', {}).get('sourceIP')
                mac = owners.get(ip)
                if mac:
                    self.seen[(mac, ip)] = now

    def status(self, device, leases, now=None):
        now = time.time() if now is None else now
        key = (device['mac'], device.get('ip'))
        with self.lock:
            seen = self.seen.get(key, 0)
        return {'dhcp_assigned': key in leases,
                'gateway_observed': bool(seen and now - seen < 180),
                'gateway_last_seen': seen}
