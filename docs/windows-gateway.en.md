# Windows LAN gateway development preview

Version: **0.2.3-windows-preview.1**, based on NAS Device Flow v0.2.2. [中文](windows-gateway.zh-CN.md)

This runs the existing Linux controller and Mihomo inside a Linux VM on an always-on Windows computer. It is a local gateway for other LAN devices, independent of the NAS. It is a development preview, not an accepted whole-home deployment or a promise that this hardware supports bridging. No production router, DHCP, DNS, adapter or NAS change is part of installation.

## Feasibility and architecture

The observed Windows edition is Windows 11 Pro for Workstations with CPU virtualization enabled; Hyper-V is not enabled. Two active Realtek USB 2.5GbE adapters and Tailscale plus Cisco/TAP adapters require route and driver review. This is evidence of prerequisites only. No VM, external switch, multi-MAC bridge or end-to-end gateway has been accepted on this machine.

Chosen candidate: Hyper-V Generation 2 x86-64 Linux VM, a separately approved **wired external switch**, rootful Docker Engine and Compose v2 inside Linux, then the existing macvlan Compose services. Docker Desktop/WSL NAT is not a substitute: a reachable web panel does not make clients' packets pass through it. Hyper-V enabling/reboot, switch creation and physical bindings require a separate, concrete confirmation; supplied tools never perform them. Windows Home and other hypervisors have no validated fallback in this preview.

An external switch must pass the VM MAC and both container MACs. Hyper-V MAC spoofing permission alone does not prove the USB NIC driver, upstream switch or AP accepts them. Wi-Fi bridging, client isolation, VLANs, switch port security and host-to-macvlan restrictions can block the design. Test from a second LAN device. Do not bridge VPN/TAP adapters or choose an adapter solely by its display name.

| Component | Address and role |
| --- | --- |
| Windows host | Existing management address, main router gateway/DNS; not the packet forwarding engine |
| Linux VM | Own unused management address; main router gateway/DNS; runs Docker and remains reachable independently |
| Mihomo core | Distinct unused LAN address; selected clients' IPv4 gateway and DNS; forwarding, China-direct/other-destinations policy |
| Controller/panel | Distinct unused LAN address; browser management and discovery; no gateway role |
| Main router | Existing upstream Internet gateway; existing DHCP remains sole authority throughout preview |

Packet path: test client → core LAN MAC/address → direct forwarding or rule-selected proxy → main router → Internet; replies return through the core. DNS queries use the core's configured resolver path. Proxy OFF still requires healthy forwarding in the VM; shutting down Windows/VM breaks clients using that gateway. IPv6 is a separate path and can bypass all these IPv4 rules.

Choose actual addresses only after checking router DHCP pool/reservations, static infrastructure, ARP/neighbor observations and active conflict probes from the target LAN. A failed ping is not proof of a free address. Exclude all fixed addresses from DHCP before assigning them; no example address is a deployment recommendation.

## 1. Read-only preflight

Read repository instructions, [compatibility](compatibility.md), [security](../SECURITY.md) and the existing [installer](nas-gui-install.md). Inspect the Windows tooling help before using it. Preserve private output outside source control.

Run `powershell -File .\deploy\windows\preflight.ps1` to save a timestamped private inventory and offline restore helper under ignored runtime/. This reads network state and writes evidence only. Run the copied `restore-host-network.ps1` without `-Apply` to validate/inspect its plan; actual restore remains untested and must be rehearsed in isolation. The helper restores one original GUID-matched IPv4 interface only, not virtual switches, IPv6, VPN, firewall or power state. Do not invoke `-Apply` against a working production interface. Then review Windows version, CPU virtualization/Hyper-V availability, installed platforms, NIC driver/link/interface GUID, vSwitch bindings, IPv4/IPv6 addresses, gateways, route metrics, DNS, DHCP server/leases, IPv6 RA/RDNSS, firewall and VPN state. Identify the actual LAN uplink; two links are not automatically a safe bridge or 5Gbps connection. Review Tailscale, Cisco, TAP, UU and other VPN/proxy routes without disabling them. Separate management and test paths where possible.

Save an offline copy of the current adapter, route, DNS, DHCP, switch, VM and firewall state plus private application configuration. A snapshot describes state; it is not proof a restore works. Keep the original router management method, original client gateway/DNS and a locally accessible rollback sheet. Do not proceed if management depends only on the link being changed.

## 2. Prepare a VM without switching the network

Use a Linux x86-64 installation ISO from its publisher and independently verify its published checksum. Install Hyper-V only after explicit approval of the feature change/restart. Have an administrator design a wired external switch and approve its binding changes separately; they can interrupt host connectivity and VPN sessions.

The importer accepts an **existing** external wired switch and verified ISO, creates an **OFF** VM and requests confirmation for mutation. It does not create a switch, enable Hyper-V, download media, install Linux or start the VM. Read its exact mandatory parameters:

```powershell
Get-Help .\deploy\windows\Import-GatewayVM.ps1 -Full
```

Review the selected physical adapter GUID, vSwitch and ISO SHA256 before confirming. MAC spoofing is required for this macvlan candidate, not a compatibility certification. Keep the VM off until the isolation and management plan is ready. No ISO or guest OS is bundled; the source ZIP is not a bootable appliance.

Install Linux through the VM console and rootful Docker Engine/Compose v2 using their official instructions. Keep guest management gateway/DNS on the original router. Do not use the core as the guest's own management gateway. Disable automatic guest suspend only through an explicitly reviewed power policy; host sleep, update reboot and USB NIC loss must be treated as gateway outages.

## 3. Guest installation and browser setup

Transfer a clean copy of this source into the VM; do not transfer NAS runtime, credentials, subscriptions or device inventory. Run from the source root:

```sh
sh deploy/windows/guest-check.sh
sh deploy/windows/guest-install.sh check
sh deploy/windows/guest-install.sh prepare
```

Guest check is read-only. Prepare delegates to the shared installer and retains its first-setup behavior; it creates private configuration and leaves services/DHCP off. Follow its interactive prompts for unused addresses, actual Linux parent interface, a strong separate panel password and private subscription. Use the same Linux controller/API, device policy, subscription registry, statistics, languages and dark mode; there is no alternate Windows backend.

The existing browser setup route remains available through [NAS GUI installer](nas-gui-install.md) **inside Linux**, replacing NAS paths with VM paths. Treat the setup access code as a credential and stop setup before starting production. Do not copy that guide's DHCP handover actions into this preview.

Before start, inspect private configuration locally and confirm DHCP is absent/off. Then:

```sh
NDF_VERIFIED_BRIDGED_LAB=yes sh deploy/windows/guest-install.sh start
sh deploy/windows/guest-install.sh status
```

Set NDF_VERIFIED_BRIDGED_LAB=yes only after actually verifying the isolated wired L2 path and address exclusions; the variable is a human attestation, not a diagnostic. Start checks Mihomo syntax before replacing services. The wrapper refuses a DHCP-enabled deployment and never authorizes takeover. The shared panel still exposes DHCP controls: leave them OFF; the wrapper is not a persistent policy lock. A service health response is not a routing test. If startup/download/configuration fails, keep existing DHCP/router unchanged, inspect private logs locally, correct the cause and retry; never publish raw subscription URLs or logs.

Open the selected panel origin from a second LAN device. First setup provisions the admin password; login/password changes use the shared controller. API mutations require session, CSRF and Origin checks. Session cookies are HttpOnly/SameSite=Strict; Secure is set with HTTPS origins. Password/core secrets remain in private runtime files: protect them with filesystem permissions and encrypted backups, never Git.

Prefer a reverse proxy with a valid, trusted certificate and matching panel_origin. HTTPS is operator provisioned, not automated here. HTTP sends credentials/session traffic without encryption on the LAN. Never bypass TLS validation or expose the panel, DNS, mixed proxy or core API to the public Internet.

## 4. Isolated trial and acceptance gates

First use an isolated wired test LAN/VLAN with no production clients; verify upstream reachability and absence of unexpected DHCP/RA. Preserve a management path that bypasses the test gateway. Configure one consenting test client manually with conflict-checked address and core gateway/DNS; do not change Windows' working adapter or mass-renew leases.

Confirm its actual route, resolver and traffic source. A configured switch is only policy intent; a lease or sampled connection is observation, neither proves successful proxy browsing. Proxy ON should produce China-direct and selected overseas proxy behavior; OFF should produce direct forwarding. Exercise DNS/UDP, IPv6 and persistent connections explicitly. Capture only redacted evidence.

Device identity is MAC-based. Same MAC/new IP should retain policy; a private/new MAC is a new unknown device and uses the new-device default (initially direct), regardless of the name. Keep unknown and historical records visible. No automatic name-based merge or archive workflow is promised; any manual migration must be explicit, privately backed up and recoverable.

**DHCP gate:** leave the existing DHCP server authoritative throughout this preview. Isolated protocol tests are not proof of sole authority on the household LAN. Before any later handover, prove replacement readiness, original DHCP configuration backup, one-client routing, actual DHCP offers/leases, core failure behavior, and a rehearsed rollback. Obtain separate approval for the specific old-service stop/new-service start; never run uncoordinated servers. The shared backend's core API health check cannot prove end-to-end Internet health and provides no automatic failover. Never enable DHCP if the gateway can be unavailable.

**IPv6 gate:** inventory actual RA/RDNSS, client IPv6 defaults and DNS first. The shared backend is IPv4-only. Do not silently disable IPv6, router RA or alter production DNS. Until a tested IPv6 policy or explicitly approved isolated-client restriction exists, IPv6 policy enforcement is **unsupported** and whole-home acceptance is blocked.

| Verification | Preview evidence / remaining work |
| --- | --- |
| Login, CSRF, password/session protection | Existing backend automated tests; see current test report for run results |
| Failed config reload / subscription switch | Existing rollback tests; live core fault injection still required |
| Rules, defaults, IP reuse, new/private MAC | Existing mocked policy tests; real leases/client paths still required |
| Subscription update keeps rules | Existing automated tests; real provider update still required |
| Multi-MAC wired bridge, core/panel reachability | Not verified on this Windows host |
| ON/OFF domestic/overseas/DNS/UDP and IPv6 | End-to-end not verified |
| Single DHCP authority and safe handover | Production handover intentionally not performed |
| Sleep/reboot, core crash, VM/NIC loss, subscription outage | Recovery/failure scenarios not verified on this host |
| Uninstall restores direct Internet | Real client/Windows restore not verified; must be rehearsed in isolation |
| Throughput, aggregation, SMB multichannel | Not measured; no 5Gbps single-flow claim |

## 5. Recovery, upgrade and removal

For basic Internet recovery, first restore the test client's recorded original gateway/DNS or automatic configuration from the still-running original DHCP authority. Use the offline sheet and VM console if network SSH is unavailable; verify direct DNS and browsing before stopping the VM. Do not restore all static settings blindly onto a changed adapter. Only the explicitly selected test client is altered.

Stop preview services with `sh deploy/windows/guest-install.sh stop`. This is not a full gateway rollback for clients still pointing to the core. In a future separately approved DHCP deployment, stop and verify replacement DHCP is gone before restoring original DHCP; then renew only agreed clients. Never start both blindly, delete NICs, reset the router or disable security software/firewall.

Restoring proxy comes after restoring basic Internet: repair VM/bridge, verify core config and resolver, start services, retest one client, then reselect it as gateway. There is no automatic failover. Do not advertise readiness merely because the panel loads.

Before upgrades, privately back up runtime/.env and the VM plus current release. Review code and Compose changes. Do not rerun initialization or import NAS state blindly. Use the shared `sh scripts/update.sh` only after reviewing the target version; it gracefully updates the controller while preserving state. This does not certify a core/VM migration. Retain the old source/image and backup for an explicitly reviewed rollback; revalidate routing before any handover.

For uninstall, restore the test client's original route/DNS first, verify direct browsing, stop services, shut down the VM, then remove only the dedicated preview VM/resources after confirmation. Keep private backups until recovery is accepted. Removing a VM does not justify removing a shared switch, changing the host adapter, deleting all firewall rules or disabling Hyper-V.

Reproducible source packaging is supplied by `deploy/windows/build-package.py`; consult its help. Run `python -m unittest discover -s tests -v` in a prepared Python environment. Linux network/container/DHCP tests require an isolated Linux lab; never run DHCP probes on production. Record exact OS, NIC/driver, hypervisor, guest/kernel, Docker/core versions and observed outcomes before expanding support.
