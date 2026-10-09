# Manual installation through the NAS GUI

English · [简体中文](nas-gui-install.zh-CN.md)

You do not need an AI agent connected to the NAS, SSH, host Python, JSON editing or an image build. Start a temporary Compose setup project, complete its browser wizard, then import the generated production project.

The published image targets x86-64 Linux NAS systems. Your NAS needs a Docker Compose project interface, host and macvlan networking, and `/dev/net/tun`. The main router must allow DHCP to be disabled. Keep NAS and clients on the same LAN. Compose support alone does not establish hardware compatibility.

## Create an installation folder

Create a folder on the NAS and keep it after installation. `/volume1/docker/nas-device-flow` is an example for UGREEN or Synology; QNAP may use `/share/Container/...`. Use the actual Docker-host path on your system, not an SMB path or a folder on your computer. These vendor path examples are not compatibility test results.

Keep a fixed NAS management IP with the main router as its gateway. Preserve existing bonded interfaces. Back up router DHCP settings and retain a recovery client. Public LAN IPv6/RA needs to be disabled or handled separately; this installer configures IPv4 only.

## Import the setup project

Download `setup.compose.yaml` from the release. Import it, or paste its contents, into a new NAS Docker Compose project named `nas-device-flow-setup`.

Change this single path at the top to your NAS folder:

```yaml
x-project-path: &project-path /volume1/docker/nas-device-flow
```

Keep `&project-path` and `*project-path` unchanged. Start the project and wait for the image download. If the NAS cannot reach GHCR, download the release controller-amd64.tar.gz image archive and import it through the NAS Docker Images interface first; no build is required. Mihomo still needs a Docker Hub download. If port 9088 is occupied, change `NDF_SETUP_PORT` and use that port in the browser. Downloads require access to GHCR and Docker Hub.

Open the setup container logs in the NAS app. Copy the `Setup access code`. The code protects the temporary installer, changes after every container restart and is separate from the panel password.

## Complete the browser wizard

Open `http://NAS-IPv4-address:9088` and enter the setup code. Use the numeric NAS IPv4 address; custom domains and HTTPS reverse proxies are not supported for this temporary entry point. The installer supports Chinese and English.

Select the wired, bonded or bridge interface. The wizard detects its subnet, NAS address and default gateway, then leaves core, panel and future DHCP addresses blank for your confirmed selections.

Verify the router IP. Exclude core and panel IPs from router DHCP and confirm no static or sleeping device uses them. ARP checks detect responding devices; absence of a response is not a guarantee that an address is unused. Enter other static IPs so the future pool avoids them. All NAS addresses within this LAN are excluded automatically.

Check the configuration. A conflict requires a different address. If ARP checking is unavailable, verify addresses on the router and static devices before selecting the additional confirmation.

Set a separate panel password of 16–256 characters without leading/trailing spaces and enter a Clash/Mihomo YAML subscription URL. Generic Base64 subscriptions are not YAML providers. The initial routing/DNS preset comes from mainland China; overseas operators need to adjust it for their network. Changing interface language does not change the regional preset.

Save. The wizard creates private runtime, .env and deployment.compose.yaml in the NAS folder. Existing state is never overwritten and DHCP stays OFF. After an interrupted save, reopen the wizard to check whether it completed; do not delete runtime to retry.

## Start the production project

Download deployment.compose.yaml. Stop the setup project in the NAS app, keeping its mounted data. Create the production project `nas-device-flow`, import the downloaded file and start it. Both the panel and Mihomo are included; there are no environment variables or build instructions to edit.

Open the panel address from another LAN device. The panel has its own IP, rather than the NAS host IP. Linux restricts host-to-macvlan communication, so testing only from the NAS host can give misleading results.[Docker documentation](https://docs.docker.com/engine/network/drivers/macvlan/)

Wait for core, subscription and rule data. Core connectivity alone does not prove usable nodes or successful routing.

## Test, then enable automatic joining

First assign one client an unused LAN IP, with gateway and DNS set to the core IP. Disable local VPN/system proxies. Test direct and smart-routing switches with actual destinations.

After this succeeds, disable main-router and other DHCP services. In panel Settings → Network & stats → Automatic joining setup, confirm the three conditions and enable joining. No container terminal is required. The server checks the core API, but cannot verify your router settings or successful browsing for you.

Restore automatic client IP/DNS, renew leases and verify gateway/DNS match the core. If clients retain old leases, forget and rejoin Wi-Fi. New devices initially default direct; the settings menu can change the default for future devices.

## Recovery and updates

Stop NAS DHCP in the panel, wait at least three seconds and verify it stopped, then enable router DHCP and renew leases. Restore manually configured clients to automatic IP/DNS. Stop the production project after clients have a working route. If the NAS is unavailable, recover using a client configured with the main router gateway/DNS. Automatic failover is not implemented.

Back up the NAS installation folder privately before updates. GUI deployments update the production image references according to the new release instructions while keeping addresses, networking and runtime mounts. Do not rerun setup over existing state or replace your configuration with another network's exported file.

Do not share the installation folder: it contains passwords, subscriptions and device records. Report NAS/system/Docker versions with fictional addresses and redacted logs.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No Compose project interface | NAS container app/version; use the optional terminal installer if unavailable |
| Image download fails | NAS connectivity to GHCR/Docker Hub |
| Setup page unavailable | Setup container, port conflict, firewall; numeric NAS IPv4 URL |
| No LAN candidates | Wired connection, host networking, private /22–/29 IPv4; Wi-Fi and tunnels are excluded |
| Production startup fails | Container logs, macvlan parent, TUN support, conflicting fixed IPs |
| Switch has no effect | Client gateway/DNS, old leases, local VPN/proxy and IPv6 |

See [validation status](release-readiness.md). Other vendors have not completed real NAS-GUI installation testing.

## Installer versus production panel / 安装入口与正式面板

The installer uses the NAS management IPv4 address and port 9088, and reads interfaces from the NAS container host. The production panel uses its own macvlan IP. Test that panel from another device on the same LAN: NAS-host-to-macvlan communication is restricted, so a failure from the NAS browser does not establish a failure from other clients. Do not change the NAS gateway to work around this. Suggested addresses are not proof that they are unused.

安装向导通过 NAS 管理 IP 的 9088 端口访问，从 NAS 宿主网络读取接口。正式面板使用独立的 macvlan IP，应在同一局域网的另一台设备上验证；NAS 宿主机访问 macvlan 受限制，宿主浏览器访问失败不等于其他设备访问失败，不要为此更改 NAS 网关。自动建议地址也不是空闲保证。

Only interface, NAS IP, subnet and upstream gateway are detected. Core and panel are two distinct, confirmed-unused static addresses; the future DHCP range allocates client addresses and must exclude all infrastructure and static assignments. No working default IP is promised. The browser and terminal installers require these addresses explicitly.

仅接口、NAS IP、网段与上级网关来自检测。核心与面板是两个不同且经确认未占用的固定地址；未来 DHCP 范围用于分配客户端地址，必须避开基础设施和固定地址。浏览器与终端安装均要求明确填写，不再提供看似可用的默认地址。
