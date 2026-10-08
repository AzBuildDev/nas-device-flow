#!/usr/bin/env python3
"""Explicit DHCP switch. Run inside the controller container."""
import argparse,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
# Docker copies this script to /app alongside server.py.
from server import DATA,core,SETTINGS,atomic

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['enable','disable','status'])
    parser.add_argument('--confirm-main-router-dhcp-off',action='store_true')
    parser.add_argument('--confirm-sole-dhcp-server',action='store_true')
    args=parser.parse_args();marker=DATA/'dhcp.enabled'
    if args.action=='status':print('enabled' if marker.exists() else 'disabled');return
    if args.action=='disable':marker.unlink(missing_ok=True);print('DHCP stopping within 3 seconds');return
    if not args.confirm_main_router_dhcp_off:parser.error('First disable main-router DHCP, then pass --confirm-main-router-dhcp-off')
    if SETTINGS.dhcp_authoritative and not args.confirm_sole_dhcp_server:parser.error('Authoritative DHCP requires confirming this is the sole LAN DHCP server')
    core('/version')
    atomic(DATA/'dnsmasq.conf',SETTINGS.dnsmasq(DATA))
    fd=os.open(marker,os.O_WRONLY|os.O_CREAT,0o600);os.close(fd)
    print('DHCP starting within 3 seconds. Verify client gateway after renewing its lease.')
if __name__=='__main__':main()
