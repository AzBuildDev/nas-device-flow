# NAS Device Flow

A small web panel I built to turn smart routing on or off for individual devices on my home LAN. New devices default to direct access. Preferences follow the MAC address when an IP changes.

[中文](README.md) | [Installation and recovery](docs/installation.en.md)

![Fictional demo; no real network connected](docs/images/demo.png)

## What it does

- Discovers devices through DHCP, neighbor records and mDNS; supports manual names.
- Sends enabled devices through domestic-direct / proxy routing rules while leaving other devices direct.
- Shows core upload/download rates, connection count and sampled per-device proxy usage.
- Adds, switches and refreshes Clash/Mihomo YAML subscriptions.

This is a Linux Docker controller with a separate Mihomo process. It is not an OpenClash or router vendor product. The UI is currently Chinese; the demo uses fictional devices.

## Status

**0.1.0-rc.1 is an experimental prerelease.** The original running setup was used on a UGREEN DXP4800 with UGOS Pro, a bonded interface and a Huawei AX3. The generalized installer has passed 54 tests, Compose validation, an isolated image build, and offline startup/login checks. A fresh networked installation with DHCP cutover has not yet been validated. OpenWrt and MikroTik name adapters have mock tests only.

Linux Docker with macvlan is required for gateway deployment. macOS and Windows use the browser as clients; Docker Desktop cannot provide this macvlan gateway. [Docker documentation](https://docs.docker.com/engine/network/drivers/macvlan/)

## Try the fictional demo

```sh
python3 scripts/demo.py
```

Open http://127.0.0.1:9088/. It does not load runtime credentials or change networking. Switches only change the in-memory examples.

## Install

Read the installation/recovery guide before changing DHCP. Choose unused addresses in your own LAN, preserve a direct management path to your router, and test one client first.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp examples/settings.json config.local.json
# Edit all LAN addresses and panel_origin for your network.
.venv/bin/python scripts/initialize.py --settings config.local.json --parent eth0
docker compose config --quiet
docker compose up -d --build
```

Initialization asks for a new panel password and a subscription URL. Credentials and device records live in ignored runtime files. DHCP is OFF by default; the core API key is random and separate from the panel password.

This version handles IPv4 only. Public IPv6 may bypass routing. There is no automatic failover when the NAS or core stops. Do not expose the panel or core ports to the Internet.

## Traffic units

1 MB = 1,000,000 bytes. Core totals reset on core restart. Device proxy totals are sampled deltas, persisted approximately every 30 seconds. Short-lived connections and downtime can be missed; these figures are not billing data. The graphs describe traffic through the core, not the whole LAN or purchased bandwidth.

## Development

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Report reproducible issues with NAS/Linux/Docker/router versions and fictional IP/MAC examples. Never upload runtime, subscription URLs, passwords or unredacted logs. Compatibility information is welcome; please distinguish hardware tests from mocks.

## License

Our controller and page use MIT. Mihomo and system packages retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md).
