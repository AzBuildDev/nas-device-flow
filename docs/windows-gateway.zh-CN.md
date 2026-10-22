# Windows 局域网旁路由开发预览

版本：**0.2.3-windows-preview.1**，基于 NAS Device Flow v0.2.2。[English](windows-gateway.en.md)

Windows 长期开机，在本机 Linux 虚拟机内运行既有控制器和 Mihomo，为其他局域网设备分流，独立于 NAS。当前交付是开发预览，尚未验收为全屋可用产品，也没有证明本机网卡支持所需桥接。安装不包含生产路由器、DHCP、DNS、现用网卡或 NAS 的变更。

## 可行性与选定架构

现场只读结果：Windows 11 Pro for Workstations，CPU 虚拟化已启用，Hyper-V 尚未启用；有两块活动 Realtek USB 2.5GbE 网卡，以及 Tailscale、Cisco/TAP 虚拟网卡。仅能确认部分先决条件，尚未证明外部交换机、额外 MAC、容器网络和真实流量路径可用。

候选架构为 Hyper-V 第二代 x86-64 Linux VM，经**另行确认的有线外部交换机**接入 LAN，Linux 内使用 rootful Docker Engine 和 Compose v2，复用原有 macvlan 容器后端。Docker Desktop/WSL 的 NAT 不等于局域网网关；面板能打开不能证明客户端流量被接管。启用 Hyper-V、重启、创建交换机、修改物理绑定均须单独说明风险和确认，交付脚本不执行这些操作。Windows Home 或其他虚拟化平台没有经过验证的替代路线。

外部交换机、USB 网卡驱动、上游交换机/AP 必须允许 VM 及两个容器的多个 MAC。仅启用 Hyper-V MAC spoofing 不代表验收通过。无线桥接、无线客户端隔离、VLAN、端口安全以及 Linux 宿主访问 macvlan 限制均可能阻断。需要从另一台 LAN 设备实测；不得桥接 VPN/TAP，或仅凭网卡显示名称选接口。

| 组件 | 地址和职责 |
| --- | --- |
| Windows | 保留管理地址和主路由网关/DNS，不是流量转发核心 |
| Linux VM | 独立且经查重的管理地址，管理网关/DNS 保持主路由，运行 Docker |
| Mihomo | 独立且经查重的 LAN 地址，作为测试终端 IPv4 网关/DNS，执行直连与规则代理 |
| 控制器/面板 | 另一独立 LAN 地址，管理和发现设备，不承担客户端网关角色 |
| 主路由 | 保持上游出口，预览期间始终保留现有唯一 DHCP 权威 |

路径为测试终端 → Mihomo 地址/MAC → 直接转发或规则代理 → 主路由 → 互联网，回包经核心返回。DNS 使用核心配置的解析路径。设备关闭代理仍依赖 VM 正常转发；Windows 睡眠、VM 停机或核心不可用都会影响使用此网关的设备。IPv6 是另一条路径，可能绕过全部 IPv4 策略。

固定地址必须核对主路由 DHCP 池、保留项、静态设备、邻居观察和目标 LAN 主动冲突检测，并从 DHCP 分配中排除；ping 不通不能证明无人占用。文档示例不推荐任何现场固定地址。

## 一、只读预检与离线准备

先读仓库指令、[兼容性](compatibility.md)、[安全边界](../SECURITY.md)和[既有安装流程](nas-gui-install.md)。先查看 Windows 脚本帮助，原始诊断输出仅私下保存。

运行 `powershell -File .\deploy\windows\preflight.ps1`，在被 Git 忽略的 runtime/ 下保存带时间戳的私有盘点和离线恢复助手；仅读取网络状态并写证据。运行副本 `restore-host-network.ps1` 且不加 `-Apply` 可验证/查看计划；真实恢复仍未实测，必须先在隔离环境演练。助手仅恢复原 GUID 匹配的一块 IPv4 接口，不恢复交换机、IPv6、VPN、防火墙或电源状态；不要对正常生产接口执行 `-Apply`。随后盘点 Windows 版本、虚拟化/Hyper-V 状态、已有虚拟化平台、网卡 GUID/驱动/链路、交换机绑定、IPv4/IPv6 地址、默认路由及 metric、DNS、DHCP 服务器和租约、IPv6 RA/RDNSS、防火墙、VPN。核对实际有线上联，不关闭现有 Tailscale、Cisco、TAP、UU 或其他代理来“排除问题”。两块网卡不等于可安全桥接或单连接 5Gbps。

在任何变更前，私下保存网卡、路由、DNS、DHCP、交换机、VM、防火墙和应用配置，另存可离线读取的原网关/DNS、路由器管理入口及回退清单。状态快照不等于已验证恢复脚本。应保留绕过测试链路的管理通道；管理只依赖将被修改链路时不得继续。

## 二、准备虚拟机，不接管网络

从 Linux 发行版官方取得 x86-64 ISO，独立核对官方校验值。启用 Hyper-V/重启前单独确认；有线外部交换机及物理绑定须管理员制定具体方案后再确认，会中断宿主网络和 VPN 会话。

导入器只接受**已经存在**的有线外部交换机和核验 ISO，创建**关机** VM 并对变更请求确认；不会创建交换机、开启 Hyper-V、下载镜像、安装 Linux 或启动 VM：

```powershell
Get-Help .\deploy\windows\Import-GatewayVM.ps1 -Full
```

按帮助填写必填参数，确认物理网卡 GUID、交换机和 ISO SHA256。MAC spoofing 仅为 macvlan 候选架构的必要许可，不证明兼容。隔离和管理路径未准备好前保持 VM 关机。源码 ZIP 不是可启动虚拟机，不附带 ISO/客户机系统。

经 VM 控制台安装 Linux，按官方文档安装 rootful Docker Engine 和 Compose v2。VM 管理网关/DNS 保持主路由，不使用自己的核心。宿主睡眠策略、更新重启、USB 网卡断开均可能造成网关故障；如需调整电源策略，须明确审阅，脚本不静默修改。

## 三、客户机安装和浏览器设置

将干净源码复制进 VM，不迁移 NAS runtime、密码、订阅或设备清单。在源码根目录执行：

```sh
sh deploy/windows/guest-check.sh
sh deploy/windows/guest-install.sh check
sh deploy/windows/guest-install.sh prepare
```

检查只读；prepare 委托共享安装器交互生成私有配置，服务和 DHCP 保持关闭。按提示输入实际 Linux 父接口、经查重的地址、独立强面板密码及私有订阅。设备开关、白名单、新设备默认、订阅/重命名、统计、登录、语言、深色模式沿用同一个 Linux 后端/API，不另写 Windows 行为副本。

也可在 Linux 内使用[浏览器安装](nas-gui-install.md)，把 NAS 路径替换为 VM 路径；设置访问码属于凭据，生产启动前停止设置服务。**不要照抄该文档的 DHCP 接管步骤到本预览。**

本地核对私有配置，确认 DHCP 没有启用后：

```sh
NDF_VERIFIED_BRIDGED_LAB=yes sh deploy/windows/guest-install.sh start
sh deploy/windows/guest-install.sh status
```

只有实际验证隔离有线二层路径和地址排除后才能设 NDF_VERIFIED_BRIDGED_LAB=yes；该变量是人工确认，不是诊断。start 在替换服务前校验 Mihomo 配置。包装脚本拒绝 DHCP 已开启的部署，不授权接管；共享面板仍提供 DHCP 控件，务必保持关闭，包装器并不是持续策略锁。健康检查不证明流量分流成功；启动、订阅下载或配置校验失败时，保持主路由/DHCP 不变，仅私下查看日志，修正再重试。不要把订阅地址、访问码或未脱敏日志提交公开。

从第二台 LAN 设备打开设定面板地址。首次设置生成管理密码，登录、改密沿用共享实现；修改 API 需会话、CSRF 和 Origin 校验。会话 Cookie 为 HttpOnly、SameSite=Strict，HTTPS origin 时设置 Secure。面板密码和核心密钥保存在私有运行文件，应限制文件权限并加密备份，绝不进入 Git。

优先使用有效可信证书的反向代理 HTTPS，并匹配 panel_origin；本预览不自动部署证书。HTTP 会在 LAN 明文传输凭据和会话流量。不要绕过证书校验，不要将面板、DNS、混合代理或核心 API 开到公网。

## 四、隔离试运行和明确验收门槛

先在隔离有线测试 LAN/VLAN 验证上游、额外 MAC、异常 DHCP/RA，并保留独立管理路径。仅为一台同意参与测试的客户端手动设置经查重地址及核心网关/DNS；不改 Windows 正常网卡，不强制全网续租。

检查客户端实际路由、解析器和流量来源。开关表示策略已配置；租约或采样连接只是观测，均不证明代理网站访问成功。开启后验证国内直连、指定海外目标走代理；关闭后验证直接转发。另测 DNS、UDP、IPv6 和长连接，不仅看图表。证据必须脱敏。

MAC 才是设备身份。同 MAC 换 IP 应保留策略；私有 MAC 变化视为新未知设备，遵循新设备默认（初始直连），不按名称继承代理。保留未知及旧记录供人工识别；目前不承诺自动合并/归档界面，手工迁移必须明确、私下备份、可恢复。

**DHCP 门槛：**预览始终保留原 DHCP 为唯一权威。隔离协议测试不能证明家庭 LAN 仅有一个 DHCP。未来接管前，必须验证替代服务、原配置备份、测试客户端流量、真实 offers/租约、核心故障行为和回退演练，并针对“停旧服务/启新服务”的具体切换另行确认。禁止双 DHCP 未协调运行。共享后端的核心 API 检查不能证明互联网连通，也无自动故障切换；网关不可用时不得让 DHCP 继续发放该地址。

**IPv6 门槛：**先盘点 RA/RDNSS 和客户端 IPv6 默认路由/DNS。共享后端仅处理 IPv4；不要静默关闭 IPv6、RA 或修改生产 DNS。在 IPv6 策略经测试，或对隔离客户端限制经明确同意之前，IPv6 策略接管**不受支持**，不能验收全屋接管。

| 验收项目 | 当前证据/剩余工作 |
| --- | --- |
| 登录、权限、CSRF、改密/会话 | 已有自动测试覆盖；实际运行结果见本次测试报告 |
| 配置重载或订阅切换失败回滚 | 已有回归测试；仍需真实核心故障注入 |
| 开关、新设备默认、IP 复用、私有 MAC | 已有策略模拟测试；仍需真实租约和客户端 |
| 订阅更新保留规则 | 已有自动测试；仍需真实订阅更新 |
| 本机多 MAC 有线桥接、核心/面板可达 | 尚未验证 |
| 国内/海外、DNS、UDP、IPv6 真实路径 | 尚未端到端验证 |
| DHCP 唯一性及切换 | 未进行生产切换 |
| 睡眠/重启、核心崩溃、VM/网卡失效、订阅中断 | 本机故障恢复尚未验收 |
| 卸载后客户端正常直连 | 真实客户端/Windows 恢复尚未验证，须隔离演练 |
| 吞吐量、链路聚合、SMB 多通道 | 未实测，不声称单连接 5Gbps |

## 五、恢复、升级和卸载

**先恢复基本上网：**把测试客户端恢复为记录的原网关/DNS，或从仍运行的原 DHCP 获取自动配置。SSH 不通时使用离线回退清单和 VM 控制台。验证直接 DNS/浏览成功后再停 VM，不把旧静态配置盲目恢复到已变化的接口，只操作明确选定的测试客户端。

`sh deploy/windows/guest-install.sh stop` 仅停止预览服务，不能恢复仍以核心为网关的客户端。未来另行批准的 DHCP 部署中，应先停替代 DHCP 并验证，再恢复原 DHCP，仅对约定客户端续租。不得盲启双服务、删网卡、重置路由器或关闭防火墙/安全软件。

**再恢复代理：**修复 VM/桥接，验证核心配置和 DNS，启动服务，重测一台客户端后再选择网关。没有自动故障切换，面板打开不能当作已恢复代理。

升级前私下备份 runtime/.env、VM 和原版本，审阅目标代码/Compose。不要重新初始化，不盲目导入 NAS 状态。审阅版本后使用共享 `sh scripts/update.sh`，它优雅更新控制器并保留状态，不证明 VM/核心迁移可用。保留旧源码、镜像、私有备份以便审阅后回退，并重新验证流量。

卸载前先恢复测试客户端原路径并验证直连，再停服务、关机 VM，经确认后仅删除专用预览 VM/资源。保留备份直至恢复验收。不得顺带删除共享交换机、改宿主绑定、清空防火墙规则或关闭 Hyper-V。

可重现源码打包入口为 `deploy/windows/build-package.py`，先查看帮助。准备 Python 环境后执行 `python -m unittest discover -s tests -v`。Linux 容器/网络/DHCP 测试只能在隔离 Linux 实验环境运行，禁止生产 LAN DHCP 探测。扩展支持前记录 OS、网卡/驱动、虚拟化、Linux/kernel、Docker/Mihomo 版本与实际结果。
