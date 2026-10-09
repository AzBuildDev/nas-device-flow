#!/usr/bin/env python3
"""Interactive first-install wizard. No Docker socket or DHCP/network mutations."""
import argparse
import getpass
import ipaddress
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from initialize import Settings, bootstrap
from subscriptions import validate_url

RFC1918 = tuple(ipaddress.ip_network(x) for x in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


def ip_json(*args):
    result = subprocess.run(['ip', '-j', *args], capture_output=True, text=True, timeout=8, check=True)
    return json.loads(result.stdout)


def usable_lans(addresses, routes, sys_net=Path('/sys/class/net')):
    """Use active LAN L3 interfaces; keep bond/bridge/VLAN parents, exclude tunnels."""
    lans = []
    for entry in addresses:
        name = entry.get('ifname', '').split('@')[0]
        kind = entry.get('linkinfo', {}).get('info_kind', '')
        if (not name or entry.get('link_type') != 'ether' or 'UP' not in entry.get('flags', [])
                or (sys_net / name / 'wireless').exists()
                or kind in ('veth', 'tun', 'wireguard', 'vxlan', 'macvlan', 'ipvlan')
                or name.startswith(('docker', 'veth', 'br-', 'virbr'))):
            continue
        for address in entry.get('addr_info', []):
            if address.get('family') != 'inet' or address.get('scope') != 'global':
                continue
            lan = ipaddress.ip_interface(f"{address['local']}/{address['prefixlen']}")
            if not 22 <= lan.network.prefixlen <= 29 or not any(lan.network.subnet_of(n) for n in RFC1918):
                continue
            gateways = [r['gateway'] for r in routes if r.get('dev') == name and r.get('dst') == 'default'
                        and r.get('gateway') and ipaddress.ip_address(r['gateway']) in lan.network]
            lans.append({'parent': name, 'subnet': str(lan.network), 'nas_ip': str(lan.ip),
                         'upstream': gateways[0] if gateways else '',
                         'dynamic': address.get('dynamic', False),
                         'ipv6': any(a.get('family') == 'inet6' and a.get('scope') == 'global'
                                      for a in entry.get('addr_info', []))})
    return sorted(lans, key=lambda lan: (not bool(lan['upstream']), lan['parent'], lan['nas_ip']))


def occupied_addresses(addresses, neighbors):
    known = {a['local'] for e in addresses for a in e.get('addr_info', []) if a.get('family') == 'inet'}
    known.update(e['dst'] for e in neighbors if e.get('dst') and e.get('lladdr'))
    return known


def suggest_addresses(subnet, reserved):
    hosts = [str(ip) for ip in ipaddress.ip_network(subnet).hosts() if str(ip) not in reserved]
    if len(hosts) < 4:
        raise ValueError('Not enough LAN addresses')
    # Candidates only: sleeping devices and the router DHCP pool cannot be inferred.
    return hosts[-2], hosts[-1]


def suggest_pool(subnet, excluded):
    runs, current = [], []
    for ip in ipaddress.ip_network(subnet).hosts():
        if str(ip) in excluded:
            if current:
                runs.append(current)
            current = []
        else:
            current.append(str(ip))
    if current:
        runs.append(current)
    if not runs:
        raise ValueError('No DHCP range available')
    longest = max(runs, key=len)
    return longest[-min(70, len(longest))], longest[-1]


def address_available(parent, address, known):
    if address in known:
        return False
    try:
        result = subprocess.run(['arping', '-D', '-I', parent, '-c', '2', '-w', '3', address],
                                capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return {0: True, 1: False}.get(result.returncode)


class Wizard:
    def __init__(self, language='zh', ask=input, secret=getpass.getpass, output=print):
        self.language, self.ask, self.secret, self.output = language, ask, secret, output

    def say(self, zh, en):
        self.output(en if self.language == 'en' else zh)

    def prompt(self, zh, en, default=''):
        label = en if self.language == 'en' else zh
        return self.ask(label + (f' [{default}]' if default else '') + ': ').strip() or default

    def confirm(self, zh, en, default=False):
        while True:
            value = self.prompt(zh + ' (y/n)', en + ' (y/n)', 'y' if default else 'n').lower()
            if value in ('y', 'yes'):
                return True
            if value in ('n', 'no'):
                return False
            self.say('请输入 y 或 n。', 'Enter y or n.')

    def ip(self, zh, en, default, network, excluded=(), probe=None):
        while True:
            value = self.prompt(zh, en, default)
            try:
                ip = ipaddress.IPv4Address(value)
                if ip not in network or ip in (network.network_address, network.broadcast_address) or value in excluded:
                    raise ValueError()
            except ValueError:
                self.say('请输入本网段内未被保留的有效 IPv4 地址。', 'Enter a usable, unreserved IPv4 address in this subnet.')
                continue
            if probe:
                status = probe(value)
                if status is False:
                    self.say('该地址已有设备使用，请换一个。', 'This address is already in use. Choose another.')
                    continue
                if status is None:
                    self.say('ARP 检查未完成，请先在主路由确认地址未占用。', 'ARP check could not complete. Check this address on the router.')
                    if not self.confirm('已确认地址未占用，继续', 'I verified this address is unused; continue'):
                        continue
            return str(ip)

    def collect(self, lans, known, probe=address_available):
        if not lans:
            raise ValueError('No active wired private IPv4 LAN (/22 to /29) detected')
        self.say('\n1. 选择 NAS 所在局域网（保留现有聚合或桥接接口）',
                 '\n1. Select the NAS LAN (keep the existing bond or bridge)')
        for i, lan in enumerate(lans, 1):
            self.output(f"  {i}. {lan['parent']}   NAS {lan['nas_ip']}   {lan['subnet']}")
        while True:
            selection = self.prompt('接口编号', 'Interface number', '1')
            if selection.isdigit() and 1 <= int(selection) <= len(lans):
                break
        lan = lans[int(selection) - 1]
        network = ipaddress.ip_network(lan['subnet'])
        gateway = self.ip('主路由 IP', 'Main router IP', lan['upstream'], network, [lan['nas_ip']])
        if lan['dynamic']:
            self.say('检测到 NAS 使用动态 IP，请先在 NAS 上设固定 IP，或在主路由绑定地址。',
                     'The NAS has a dynamic IP. Set a fixed NAS address or router reservation first.')
        if not self.confirm('NAS 管理地址已固定，上级网关保持主路由',
                            'NAS management IP is fixed and its gateway remains the main router'):
            raise ValueError('Fix NAS management addressing before installation')
        self.say('\n2. 给核心和面板选择两个固定 IP。请自行输入在路由器和固定设备配置中确认未用的地址。',
                 '\n2. Choose two fixed IPs for the core and panel. Enter addresses confirmed unused in router and static-device settings.')
        self.say('请先在主路由 DHCP 地址池中排除这两个 IP。ARP 无法发现关机设备。',
                 'Exclude these IPs from the router DHCP pool. ARP cannot detect powered-off devices.')
        self.say('核心 IP 用作客户端网关和 DNS；面板 IP 用于网页管理，安装后从另一台局域网设备访问。',
                 'Core IP is the client gateway and DNS; panel IP is for web management, accessed from another LAN device.')
        reserved = known | {gateway}
        core = self.ip('Mihomo 核心 IP', 'Mihomo core IP', '', network, reserved,
                       lambda ip: probe(lan['parent'], ip, known))
        panel = self.ip('网页面板 IP', 'Panel IP', '', network, reserved | {core},
                        lambda ip: probe(lan['parent'], ip, known))
        if not self.confirm('已在主路由排除这两个 IP，也未给其他静态设备使用',
                            'These IPs are excluded from router DHCP and other static devices'):
            raise ValueError('Reserve the two addresses on the main router first')
        self.say('\n3. 设置 NAS 将来接管后的 DHCP 地址池（此刻不会开启）',
                 '\n3. Set the future NAS DHCP pool (it will stay OFF)')
        self.say('输入其他固定设备 IP，用逗号分隔；NAS 和主路由已自动排除。',
                 'Enter other static device IPs separated by commas; NAS and router are already excluded.')
        while True:
            value = self.prompt('其他固定 IP，可留空', 'Other static IPs, or leave empty')
            try:
                extras = [str(ipaddress.IPv4Address(x.strip())) for x in value.split(',') if x.strip()]
                if any(ipaddress.ip_address(x) not in network or x in (str(network.network_address), str(network.broadcast_address))
                       for x in extras):
                    raise ValueError()
                break
            except ValueError:
                self.say('固定 IP 必须是本网段内的有效地址。', 'Static IPs must be usable addresses in this subnet.')
        infrastructure = sorted(set([lan['nas_ip'], *extras]) - {gateway, core, panel})
        excluded = set(infrastructure + [gateway, core, panel])
        self.say('未来 DHCP 范围用于给客户端分配地址，安装时保持关闭；整个范围须避开主路由、NAS、核心、面板和固定设备。',
                 'The future DHCP pool allocates client addresses; DHCP stays off during installation. Exclude router, NAS, core, panel and static devices from the entire range.')
        while True:
            start = self.ip('DHCP 起始 IP', 'DHCP first IP', '', network, excluded)
            end = self.ip('DHCP 结束 IP', 'DHCP last IP', '', network, excluded)
            config = {'subnet': lan['subnet'], 'upstream': gateway, 'core_ip': core, 'panel_ip': panel,
                      'infrastructure': infrastructure, 'panel_origin': f'http://{panel}:9080',
                      'dhcp_start': start, 'dhcp_end': end, 'dhcp_authoritative': False}
            try:
                Settings(**config)
                break
            except ValueError:
                self.say('地址池顺序不正确，或包含固定设备地址，请重新输入。',
                         'The pool is reversed or includes reserved addresses. Enter a different range.')
        self.say('当前预设：中国大陆目的地直连，其余目的地代理。语言不会改变分流地区。',
                 'Current preset: mainland China destinations direct, others proxied. Language does not change routing.')
        if lan['ipv6']:
            self.say('检测到全局 IPv6 地址。本向导只配置 IPv4，请另行处理 LAN IPv6/RA。',
                     'Global IPv6 detected. This wizard configures IPv4 only; handle LAN IPv6/RA separately.')
        return config, lan['parent']

    def credentials(self):
        self.say('\n4. 设置面板密码和订阅（输入不会显示）', '\n4. Set panel password and subscription (hidden input)')
        while True:
            password = self.secret('Panel password (16-256 characters): ')
            if not 16 <= len(password) <= 256 or password != password.strip():
                self.say('密码需要 16 到 256 个字符。', 'Password must contain 16 to 256 characters.')
                continue
            if password == self.secret('Confirm password: '):
                break
            self.say('两次密码不同，请重新输入。', 'Passwords differ. Try again.')
        while True:
            url = self.secret('Clash/Mihomo YAML subscription URL: ').strip()
            try:
                validate_url(url)
                break
            except ValueError:
                self.say('订阅 URL 无效，请输入完整的 HTTP/HTTPS YAML 订阅地址。',
                         'Invalid subscription URL. Enter the full HTTP/HTTPS YAML subscription address.')
        return password, url

    def summary(self, config, parent):
        self.say('\n5. 确认安装配置', '\n5. Review installation')
        self.output(f"  LAN: {config['subnet']}    interface: {parent}")
        self.output(f"  Router: {config['upstream']}    core: {config['core_ip']}")
        self.output(f"  Panel: {config['panel_origin']}")
        self.output(f"  Future DHCP: {config['dhcp_start']} - {config['dhcp_end']}")
        self.say('  DHCP：关闭；新设备：直连；不会修改主路由或 NAS 网卡。',
                 '  DHCP: OFF; new devices: DIRECT; router and NAS interfaces will not be changed.')

    def guide(self, config):
        self.say('\n下一步：用另一台局域网设备打开面板', '\nNext: open the panel from another LAN device')
        self.output('  ' + config['panel_origin'])
        self.say('先给一台测试设备设置本网段空闲 IP，网关和 DNS 都填：',
                 'First give one test client an unused LAN IP, with gateway and DNS set to:')
        self.output('  ' + config['core_ip'])
        self.say('确认直连与智能分流均可用后，关闭主路由 DHCP，再执行：',
                 'After direct and smart routing work, disable main-router DHCP, then run:')
        self.output('  docker compose exec controller python3 /app/dhcp.py enable --confirm-main-router-dhcp-off')
        self.say('客户端恢复自动 IP/DNS 并更新租约。若仍保留旧网关，忽略 Wi-Fi 后重新加入。',
                 'Restore automatic client IP/DNS and renew leases. If the old gateway persists, forget and rejoin Wi-Fi.')
        self.say('恢复：先停止 NAS DHCP，等待至少 3 秒，再开启主路由 DHCP。',
                 'Recovery: stop NAS DHCP, wait at least 3 seconds, then re-enable router DHCP.')
        self.output('  docker compose exec controller python3 /app/dhcp.py disable')


def restore_owner(project):
    """The short-lived root installer returns generated files to the invoking user."""
    if 'NDF_INSTALL_UID' not in os.environ:
        return
    uid, gid = int(os.environ['NDF_INSTALL_UID']), int(os.environ['NDF_INSTALL_GID'])
    for path in [project / '.env', project / '.ndf-install.lock', project / 'runtime', *(project / 'runtime').rglob('*')]:
        os.chown(path, uid, gid, follow_symlinks=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lang', choices=('zh', 'en'), default='zh')
    parser.add_argument('--project', type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--prepare-only', action='store_true')
    mode.add_argument('--guide', action='store_true')
    args = parser.parse_args(argv)
    wizard = Wizard(args.lang)
    project = args.project.resolve()
    if args.guide:
        config = json.loads((project / 'runtime/control-center/settings.json').read_text())
        Settings(**config)
        wizard.guide(config)
        return 0
    if not args.check and any(os.path.lexists(project / name) for name in ('.env', 'runtime')):
        wizard.say('已有部署，安装不会覆盖。启动用 --start；升级用 sh scripts/update.sh。',
                   'Existing deployment will not be overwritten. Use --start to start, or sh scripts/update.sh to upgrade.')
        return 1
    addresses = ip_json('-d', 'address', 'show')
    routes = ip_json('-4', 'route', 'show', 'default')
    neighbors = ip_json('-4', 'neighbor', 'show')
    lans = usable_lans(addresses, routes)
    if args.check:
        wizard.say('可用有线局域网（只检查，不创建配置、不启动服务）：',
                   'Available wired LANs (check only; no configuration or services created):')
        for lan in lans:
            wizard.output(f"  {lan['parent']}  {lan['nas_ip']}  {lan['subnet']}  router: {lan['upstream'] or '?'}")
        if not lans:
            wizard.say('未识别到 /22 至 /29 的私有 IPv4 有线网段。', 'No private wired IPv4 subnet with /22 to /29 prefix found.')
            return 1
        return 0
    if not sys.stdin.isatty():
        wizard.say('需要交互终端，请通过 NAS SSH 登录后运行安装命令。',
                   'An interactive terminal is required. Log into the NAS through SSH.')
        return 1
    wizard.say('NAS Device Flow 安装向导。随时按 Ctrl+C 退出。', 'NAS Device Flow installer. Press Ctrl+C to cancel.')
    config, parent = wizard.collect(lans, occupied_addresses(addresses, neighbors))
    password, url = wizard.credentials()
    wizard.summary(config, parent)
    if not wizard.confirm('保存配置', 'Save this configuration'):
        wizard.say('已取消，未创建运行配置。', 'Cancelled; no runtime configuration created.')
        return 0
    bootstrap(project, config, password, url, parent)
    restore_owner(project)
    wizard.say('配置已保存；DHCP 仍关闭。', 'Configuration saved; DHCP remains OFF.')
    wizard.guide(config)
    if not args.prepare_only and wizard.confirm('现在下载并启动两个服务', 'Download and start both services now', True):
        return 10  # The host wrapper owns Docker; the wizard never sees its socket.
    wizard.say('稍后启动：sh scripts/install.sh --start', 'Start later: sh scripts/install.sh --start')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled / 已取消。', file=sys.stderr)
        raise SystemExit(130)
    except (OSError, ValueError, subprocess.SubprocessError):
        # Never echo subscription URLs, passwords or subprocess output on errors.
        print('Installation could not complete. Check LAN settings, directory permissions and Docker. '
              'Existing state is not overwritten. / 安装未完成，请检查网络、目录权限和 Docker；不会覆盖已有配置。', file=sys.stderr)
        raise SystemExit(1)
