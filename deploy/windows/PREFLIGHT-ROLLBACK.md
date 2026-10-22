# Windows preflight and offline recovery / Windows 预检与离线恢复

## English

Run from the repository in Windows PowerShell. Inspect scripts before using a process-local execution-policy override; Group Policy still takes precedence. No permanent execution policy is changed.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File deploy/windows/preflight.ps1
```

This reads OS/CPU virtualization, optional features, physical and virtual adapters and bindings, addresses, routes, DHCP lease metadata, DNS origin, firewall profiles/rule summaries, Hyper-V switches/VM state, relevant VPN services, installed virtualization executables and current sleep settings. It enables nothing, starts no services and sends no network probes. Missing privileged queries produce warnings, not fabricated success. A detected wired adapter is not proof that an external switch or multiple guest MAC addresses will work. Router DHCP pool, other DHCP responders, IPv6 RA/RDNSS, bridge restrictions, address collisions and gateway traffic remain unverified by this host-only inventory.

Private snapshots contain infrastructure identifiers and must never be committed, pasted into issues or uploaded. Default output is Git-ignored `runtime/windows-preflight/<unique-id>/`; access is restricted to the current user, local Administrators and SYSTEM before writing. Do not override `-SnapshotRoot` to a public/shared or tracked directory. No passwords, subscription content, Wi-Fi profiles or VPN credentials are requested or captured. Firewall snapshots are inventory only, not a full security-policy backup. Back up private application runtime and `.env` separately before deployment, without putting either in Git.

Copy the entire snapshot folder, which includes a standalone recovery script, to local offline storage accessible to the administrator. It does not need NAS, DNS, Internet, this repository or the panel. It restores only saved IPv4 addressing/default gateway and IPv4 DNS for one exact adapter GUID. It never guesses an adapter from its display name, changes another adapter, recreates a virtual switch, imports firewall rules or alters VPN, IPv6 or sleep settings. If a physical adapter is rebound to a virtual switch and its GUID disappears, use the manual steps below. This preview does not create switches, so automatic switch removal would be unsafe.

```powershell
# In the copied snapshot folder: listing and validation only
.\restore-host-network.ps1
.\restore-host-network.ps1 -InterfaceGuid '<original-adapter-guid>'
# Safe dry run, after review; apply requires a local elevated terminal and prompts
.\restore-host-network.ps1 -InterfaceGuid '<original-adapter-guid>' -Apply -WhatIf
.\restore-host-network.ps1 -InterfaceGuid '<original-adapter-guid>' -Apply
```

Run recovery from the local console: an active connection may drop. The DHCP branch restores DHCP mode and removes manual IPv4 overrides on only that adapter; it does not force lease renewal or affect all clients. Renew that one adapter manually only if needed. An expired DHCP lease cannot be recreated from saved data; the original DHCP authority must still be available. Static mode restores saved manual addresses/routes and removes manual IPv4 addresses/default routes absent from the snapshot on that adapter. These operations are idempotent but are not transactional; if a command fails, inspect the local error and use the manual settings. Validate actual gateway, DNS and a direct-access website afterwards. A successful command exit is not proof of recovered Internet.

Manual basic connectivity recovery: use a local console or a separate management device; open `ncpa.cpl`, select the original wired adapter and open IPv4 Properties. Restore automatic address/DNS if the saved interface used DHCP; otherwise enter the saved IPv4 address, prefix/netmask, upstream gateway and DNS from the private snapshot. Keep the original upstream router reachable. If later bridge changes have been explicitly approved, use their separately recorded switch undo procedure before restoring physical-adapter settings. Do not remove unrelated switches or reset network/firewall. This preview supplies no DHCP service and never disables the main router's DHCP. Should a future approved deployment have enabled VM DHCP, first stop that specific DHCP service, verify it stopped, then restore the original authority using the recorded router procedure; do not run both. Reconnect only the consenting test client, without renewing the entire household.

Restore basic direct connectivity before attempting proxy recovery. Proxy recovery then means repairing VM/core configuration, validating Mihomo and subscriptions, and testing one isolated client's direct/proxy switch, DNS, UDP and IPv6 path before another handover. Do not re-advertise an unavailable gateway. Router/DHCP recovery requires its own offline saved settings; a Windows interface snapshot cannot restore a router.

Validation status: host snapshot and plan-only recovery can be tested without disruption. `-Apply -WhatIf` proves the mutation boundary, not actual network restoration. Full restore, sleep/reboot recovery, bridge teardown and external-client connectivity require an isolated test adapter/network and remain unverified until explicitly recorded. Never claim production readiness from this inventory.

## 简体中文

在仓库目录使用 Windows PowerShell 执行上面的预检命令。先查看脚本；`-ExecutionPolicy Bypass` 仅影响这一个进程，不改变系统执行策略，组策略限制仍有效。脚本只读采集系统和 CPU 虚拟化、Windows 功能、网卡及绑定、IP/路由、DHCP 租约、DNS 来源、防火墙摘要、Hyper-V 交换机/虚拟机、相关 VPN 服务、虚拟化程序位置及睡眠设置，不启用功能、启动服务或改变网络。权限不足会显示警告。检测到有线网卡不代表桥接、多 MAC、DHCP 唯一性、IPv6、地址无冲突或真实转发已通过。

默认写入 Git 忽略的 `runtime/windows-preflight/<唯一编号>/`，写入前将目录权限限制为当前用户、Administrators 和 SYSTEM。快照包含网络标识，不能提交、公开或上传；不要将输出目录改到公开共享目录或受 Git 跟踪的目录。脚本不读取密码、订阅、Wi-Fi 配置或 VPN 凭据。防火墙信息只是盘点，不能用于完整恢复安全策略。部署前还需单独备份私有 `runtime` 和 `.env`，不要提交。

将整个快照目录（包括恢复脚本）保存到本机离线可用的位置。恢复脚本不依赖 NAS、互联网、DNS、面板或源码仓库。先不带 `-Apply` 查看，再用 `-Apply -WhatIf` 演练；真实执行需本机管理员终端并确认。它只恢复所选原始 GUID 网卡的 IPv4 地址、默认网关和 IPv4 DNS，不按名称猜测、不改其他网卡、IPv6、VPN、防火墙、睡眠或虚拟交换机。执行可能中断连接，务必从本机控制台进行。若桥接更改使原网卡 GUID 消失，脚本拒绝替换；按此前批准的交换机专属回退步骤操作，再恢复物理网卡。

DHCP 模式恢复自动取址并清理该网卡的手动 IPv4 覆盖，不强制所有终端续租；必要时只手动续租该网卡。过期租约不能靠快照重建，原 DHCP 服务器必须可用。静态模式恢复已保存的手动地址/默认路由，并清理该网卡后来添加的手动地址/默认路由。操作可重复但不是事务，失败后检查本机错误并手动恢复。打开 `ncpa.cpl` → 原有线网卡 → IPv4 属性：原来自动取址就恢复自动 IP/DNS，否则根据私有快照恢复地址、掩码、上级网关和 DNS。完成后实际核对网关、DNS 和直连网站，不能仅凭命令返回成功判断恢复。

本预览不启动 DHCP、不关闭主路由 DHCP、不创建交换机。如后续正式获准启用了 VM DHCP，先停止且核实该服务已停，再按事先保存的路由器步骤恢复原 DHCP 权威，不能同时运行两个未协调的 DHCP。不要重置路由器、防火墙或整个家庭网络，也不要让全部终端同时续租。路由器设置须另存离线回退记录，Windows 快照不能恢复路由器。

先恢复基本直连，再修复代理：恢复虚拟机/核心配置、校验 Mihomo 和订阅，在隔离网络用单个终端验证直连/代理开关、DNS、UDP、IPv6 后才能再次接管。不得继续下发不可用网关。只读预检、恢复计划和 WhatIf 可以无中断验证；真实恢复、重启/睡眠、桥接撤销、终端端到端网络尚须隔离环境实测。不能把计划通过报告为恢复通过。
