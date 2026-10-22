# macOS gateway development preview

[简体中文](macos.zh-CN.md)

This preview prepares a Mac to host the NAS Device Flow gateway in a bridged Linux virtual machine. The intended setup manages devices across the LAN without a NAS. The Mac runs the VM; Linux runs the controller, DHCP service and Mihomo. The existing web panel remains the management interface.

This is a development path, not a finished standalone installer. The current additions inventory the Mac and generate a Lima VM configuration. No physical LAN gateway, DHCP handover, Apple silicon deployment or Intel deployment has been validated end to end. The generator's architecture tests check configuration output only. Running the preparation tools does not enable DHCP or change the main router.

## Requirements

Use a Mac that can remain powered on and awake, a wired LAN connection, Python 3, Lima, and a user-configured `socket_vmnet` bridged network. The bridge must support the extra MAC addresses used by the Linux macvlan containers. Wi-Fi bridging and client-isolated networks are not an accepted substitute. Docker Desktop alone does not establish this capability.

The required bridged VM environment is the current deployment blocker. These scripts do not install Lima, configure a privileged network helper, create the bridge socket, or change a physical network interface. Configure those prerequisites using the virtualization project's instructions, and review the security and network effects before continuing. Confirm the bridge socket belongs to the wired LAN you intend to use.

## Inspect and generate

From the repository root, run the read-only preflight:

```sh
sh scripts/macos/preflight.sh
```

It reports network interfaces, the default gateway, Docker availability and virtualization tools. It does not prove that a bridge works. Keep reports private because they include local IP addresses.

Use an absolute path to your existing bridge socket and a private output directory. The paths below are placeholders; replace them before running:

```sh
python3 scripts/macos/vm-config.py --help
python3 scripts/macos/vm-config.py \
  --bridge-socket /absolute/path/to/your-bridge.sock \
  --output /private/path/ndf-macos.yaml \
  --source "$PWD"
```

The generator accepts `--arch aarch64` or `--arch x86_64` when an explicit target is needed, and `--check-only` for validation without writing. Generating either configuration is not a hardware compatibility claim. Inspect the generated file before starting it.

```sh
limactl start --name=ndf-macos /private/path/ndf-macos.yaml
limactl shell ndf-macos
```

The VM uses rootful Docker. Rootless Docker does not satisfy the macvlan gateway requirements. The repository is mounted read-only at `/mnt/ndf-source`. Before deployment, identify the bridged wired interface. The generated configuration names it `ndflan`; confirm with `ip -br address` and `ip route`.

The guest bootstrap is an explicit preparation step. It requires root, accepts x86-64 and ARM64 guests, checks the private bridged address and default route, rejects a NAT default or rootless Docker, and refuses to overwrite an existing destination. Replace the destination below with a new private directory:

```sh
sudo bash /mnt/ndf-source/scripts/macos/guest-bootstrap.sh \
  --source /mnt/ndf-source \
  --destination "$HOME/nas-device-flow" \
  --interface ndflan --check-only
sudo bash /mnt/ndf-source/scripts/macos/guest-bootstrap.sh \
  --source /mnt/ndf-source \
  --destination "$HOME/nas-device-flow" \
  --interface ndflan
cd "$HOME/nas-device-flow"
```

This copies an allowlist of public source paths and builds the local controller image `ndfcontroller:0.3.0-rc.1`. It does not start services, enable DHCP or change network settings. It does not silently install missing guest dependencies. Follow the error's dependency instructions first; Docker and Compose need to be installed separately using their distribution instructions. The local image tag labels this experimental packaging, not a backend version upgrade.

Keep runtime data, credentials and subscriptions in this private guest copy. Do not write them into the shared source checkout or upload them to GitHub.

## Install inside Linux, with DHCP off

Follow the manual [Linux installation and recovery guide](installation.en.md) from the writable guest copy. Check that the guest has Python with virtual-environment support, rootful Docker, Compose v2 and `/dev/net/tun`. Identify the bridged guest interface with `ip -br address` and `ip route`; do not assume it is `eth0`. NAT connectivity or a working Docker daemon does not prove LAN reachability.

The existing `scripts/install.sh` wrapper rejects ARM because the published controller image targets amd64. On Apple silicon, use the bootstrap's controller source build for the guest architecture and the manual initialization path. Do not use the amd64 image as evidence of native ARM support. A source build is still unverified on hardware in this preview.

After choosing unused addresses outside the existing DHCP pool and editing a private `config.local.json`, the manual flow is:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Create and review config.local.json from examples/settings.json first.
# Replace GUEST_LAN_INTERFACE with the actual bridged guest interface.
.venv/bin/python scripts/initialize.py --settings config.local.json --parent GUEST_LAN_INTERFACE
# Set CONTROLLER_IMAGE=ndfcontroller:0.3.0-rc.1 in the private .env.
docker compose config --quiet
docker compose up -d
```

Review the selected Mihomo image's architecture support too. Keep DHCP disabled. From a separate LAN device, check that the panel is reachable, then test one manually configured client with the VM-hosted core as gateway and DNS. Verify both direct and proxied destinations, device toggles, DNS, and recovery. Linux restricts host-to-macvlan access, so failure to reach a container from the Mac or guest alone is not a complete LAN test.

Only plan automatic joining after that test passes. Back up router DHCP and IPv6 settings, record existing leases, confirm a single DHCP authority, and prepare a management device that can use the main router directly. The macOS preparation tools do not switch these settings. The current gateway is IPv4 only; IPv6 needs a separate explicit plan. Do not silently change IPv6 or enable a second DHCP server.

## Operation and rollback

There is no automatic failover. If the Mac sleeps, shuts down, loses its wired connection, or the VM stops, clients using this gateway can lose Internet access. Agree on power and sleep settings before handover. After restarting the Mac, start the VM with `limactl start ndf-macos`, then verify bridge connectivity and service health before relying on it. Container restart policies do not start a stopped VM.

If DHCP was never handed over, restore the test client's original automatic IP/DNS settings. If it was handed over, stop the controller's DHCP first and verify it stopped, then restore the main router's DHCP and renew client leases. Restore manually configured clients to a working main-router gateway/DNS. Use the detailed recovery commands in the Linux guide. Do not stop the VM while the rest of the LAN still depends on its gateway.

Keep backups of the private guest configuration and the original router settings. A working Mac browser, passing unit tests or two linked Ethernet ports does not establish whole-LAN operation, automatic recovery or 5 Gbps throughput. Those checks remain release requirements.
