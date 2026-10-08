# 🧭 NAS Device Flow

**Per-device smart routing for your home network.**

English · [🌐 简体中文](README.zh-CN.md) · [Installation guide](docs/installation.en.md) · [Releases](https://github.com/Azusagawa0409/nas-device-flow/releases)

Give each device a direct or smart-routing switch. See its proxy traffic, manage subscriptions, and keep everyday controls in one small web panel.

After DHCP setup, clients can join Wi-Fi with automatic IP and DNS. The panel runs on your Linux NAS alongside Mihomo; both services are defined in the same Docker Compose file.

![Fictional device demo; no real network connected](docs/images/demo.png)

## ✨ What you can do

- **Control each device.** Choose direct access or smart routing, with preferences retained while its MAC stays the same.
- **See network activity.** Live upload/download rates, a traffic chart, active connections and sampled proxy usage per device.
- **Manage subscriptions.** Add, switch and refresh Clash/Mihomo YAML subscriptions.
- **Choose your defaults.** A settings gear holds Chinese/English selection, the new-device default policy, admin password changes and connection details.
- **Find your devices.** DHCP, neighbor records and mDNS provide discovery and names. Optional router adapters can add device information.

New devices default to direct access. You can change this to smart routing in Settings; existing switches stay unchanged. A changed private MAC counts as a new device and follows that default, even if its name is familiar.

Language selection is saved in your browser. Routing rules and DNS are configured separately: the initial China-direct / other-destinations-proxy rules reflect the original mainland-China setup.

## 👀 Try the demo

```sh
python3 scripts/demo.py
```

Open http://127.0.0.1:9088/. Devices and traffic are fictional. The demo does not read deployment credentials or change your network.

## 🚀 Deploy on a Linux NAS

You need Linux Docker Compose, a wired interface that supports macvlan, and a main router whose DHCP service you can configure. Clients and the NAS must share the same LAN.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp examples/settings.json config.local.json
# Edit LAN addresses and panel_origin for your network.
# Replace eth0 below with your NAS's actual wired interface.
.venv/bin/python scripts/initialize.py --settings config.local.json --parent eth0

docker compose config --quiet
docker compose up -d --build
```

Initialization asks you to set and confirm an admin password and enter your subscription URL. The Mihomo API key is generated separately. Private credentials and device records stay in ignored runtime files.

DHCP starts **off**. Follow the [installation and recovery guide](docs/installation.en.md), test one client, then complete the DHCP handover. Existing clients may need to forget and rejoin Wi-Fi once to replace an old lease.

macOS, Windows, phones and tablets use the browser as clients. The gateway service runs on Linux; Docker Desktop does not provide this macvlan deployment. [Docker platform documentation](https://docs.docker.com/engine/network/drivers/macvlan/)

## 🧪 Project status

This is an experimental prerelease. The original setup is running on a UGREEN DXP4800 with UGOS Pro, a bonded interface and a Huawei TC7102. Source tests and isolated container/DHCP checks cover the generalized package; a fresh networked installation on another LAN still needs validation. OpenWrt and MikroTik device-name adapters have mock tests only.

A switch means a policy is configured. It does not prove the client is using the NAS gateway or that a website is reachable. See [connection diagnostics](docs/diagnostics.md) and [compatibility notes](docs/compatibility.md).

IPv4 only, with no automatic failover if the NAS stops. Public IPv6 can bypass IPv4 rules. Keep the panel and core API on your LAN.

Traffic uses decimal units: 1 MB = 1,000,000 bytes. Per-device totals are sampled, persisted estimates, not subscription billing. Charts describe traffic through Mihomo, not all LAN traffic. See [metric definitions](docs/metrics.md).

## 🤝 Contribute

```sh
.venv/bin/python -m unittest discover -s tests -v
```

[Report an issue](https://github.com/Azusagawa0409/nas-device-flow/issues) with your NAS, Linux, Docker and router versions. Use fictional IP/MAC examples and redact credentials and logs. Hardware compatibility reports are welcome; distinguish real-device results from mocks.

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Release checks](docs/release-readiness.md)

Our controller and web panel use the [MIT license](LICENSE). Mihomo and system packages retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). This project is independent of OpenClash, UGREEN and router vendors.
