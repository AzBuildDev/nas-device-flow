# macOS 独立网关开发预览

[English](macos.en.md)

本预览为 Mac 准备桥接到局域网的 Linux 虚拟机，由 Mac 承载 NAS Device Flow 网关。目标是不依赖 NAS，管理同一局域网中各设备的分流。Mac 运行虚拟机，Linux 运行控制面板、DHCP 服务和 Mihomo，管理入口继续使用现有网页。

这仍是开发路线，不是已经完成的独立安装器。目前新增工具只做 Mac 环境盘点和 Lima 虚拟机配置生成。尚未完成真实局域网网关、DHCP 交接、Apple 芯片或 Intel 整机部署验收。生成器的架构测试只验证配置输出，不能代表硬件兼容性。运行准备工具不会启用 DHCP，也不会修改主路由。

## 先决条件

需要一台能持续开机并保持唤醒的 Mac、有线局域网连接、Python 3、Lima，以及由用户明确配置的 `socket_vmnet` 桥接网络。桥接链路必须允许 Linux macvlan 容器使用额外 MAC 地址。不能用 Wi-Fi 桥接或设备隔离网络代替已验证的有线桥接；仅安装 Docker Desktop 也不能证明这条网络路径可用。

桥接虚拟机环境是当前实际部署的阻塞项。这些脚本不会安装 Lima、配置需要权限的网络辅助服务、创建桥接 socket 或修改物理网卡。请按虚拟化项目的说明准备环境，在继续前了解其权限和网络影响，并确认 socket 桥接到正确的有线局域网。

## 只读检查与配置生成

在仓库根目录运行：

```sh
sh scripts/macos/preflight.sh
```

它检查网卡、默认网关、Docker 和虚拟化工具，不会证明桥接已经可用。报告含有局域网 IP，应保存在私人目录中。

为已有桥接 socket 提供绝对路径，并将配置输出到私人目录。下面路径都是占位符，运行前必须替换：

```sh
python3 scripts/macos/vm-config.py --help
python3 scripts/macos/vm-config.py \
  --bridge-socket /absolute/path/to/your-bridge.sock \
  --output /private/path/ndf-macos.yaml \
  --source "$PWD"
```

需要明确目标时可指定 `--arch aarch64` 或 `--arch x86_64`；`--check-only` 只校验、不写文件。能够生成某架构的配置不等于已经支持该硬件。启动前先检查生成内容。

```sh
limactl start --name=ndf-macos /private/path/ndf-macos.yaml
limactl shell ndf-macos
```

虚拟机使用 rootful Docker，rootless Docker 不满足当前 macvlan 网关要求。仓库以只读方式挂载到 `/mnt/ndf-source`。先通过 `ip -br address` 和 `ip route` 确认有线桥接网卡；生成配置将它命名为 `ndflan`，仍须核对实际状态。

guest bootstrap 是需要用户明确运行的准备步骤。它要求 root 权限，接受 x86-64 和 ARM64 虚拟机，检查桥接网卡的私有地址和默认路由，拒绝 NAT 默认路由或 rootless Docker，也不会覆盖已有目标目录。下面目标路径应替换为一个新的私人目录：

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

这个步骤只复制允许清单中的公开源码，并构建本地控制器镜像 `ndfcontroller:0.3.0-rc.1`，不会启动服务、启用 DHCP 或修改网络设置。缺少依赖时会停止，不会静默安装；先按错误说明准备依赖，Docker 和 Compose 须按发行版对应说明单独安装。本地镜像标签用于标识实验部署打包，不代表后端版本升级。

运行数据、密码和订阅应保存在这个私人副本中，不要写入共享源码目录，也不要上传 GitHub。

## 在 Linux 内安装，先不开 DHCP

从虚拟机中的可写副本，按 [Linux 手动安装与恢复指南](installation.md) 继续。先确认虚拟机具备支持 venv 的 Python、rootful Docker、Compose v2 和 `/dev/net/tun`。通过 `ip -br address` 和 `ip route` 确认桥接网卡，不要假定它叫 `eth0`。NAT 能上网或 Docker 正常运行，都不能代替局域网可达性验证。

现有 `scripts/install.sh` 包装脚本会拒绝 ARM，因为当前发布的控制器镜像面向 amd64。Apple 芯片应使用 bootstrap 为虚拟机目标架构从源码构建的控制器，使用手动初始化路线；不要把能运行 amd64 镜像当作原生 ARM 支持。这个源码构建路线在当前预览中也尚未通过硬件验收。

先选择不在现有 DHCP 地址池内、经过冲突检查的地址，并从示例创建和核对私有 `config.local.json`，再执行：

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# 先从 examples/settings.json 创建并检查 config.local.json。
# 将 GUEST_LAN_INTERFACE 替换为实际的虚拟机桥接网卡名。
.venv/bin/python scripts/initialize.py --settings config.local.json --parent GUEST_LAN_INTERFACE
# 在私人 .env 中设置 CONTROLLER_IMAGE=ndfcontroller:0.3.0-rc.1。
docker compose config --quiet
docker compose up -d
```

同时核对所选 Mihomo 镜像的目标架构。保持 DHCP 关闭，先从另一台局域网设备访问面板，再让一台测试设备手动使用虚拟机中的核心地址作为网关和 DNS。验证国内直连、海外代理、设备开关、DNS 和恢复。Linux 对宿主访问 macvlan 容器有限制，仅 Mac 或虚拟机自己连不上容器，并不能说明局域网设备也无法连接。

单设备验证成功后，才能安排自动接入。先备份路由器的 DHCP 和 IPv6 设置，记录租约，确认只有一个 DHCP 权威，并准备能直接使用主路由上网的管理设备。macOS 准备工具不会代为切换。现有网关只处理 IPv4，IPv6 必须另行规划，不要静默改动 IPv6，也不要直接启用第二个 DHCP 服务。

## 运行与回退

目前没有自动故障切换。Mac 睡眠、关机、有线网络断开或虚拟机停止，都可能使使用该网关的终端断网。正式接管前先确认电源与睡眠安排。Mac 重启后可用 `limactl start ndf-macos` 启动虚拟机，但仍须核对桥接和服务健康；容器的自动重启策略不会启动一台已停止的虚拟机。

如果尚未交接 DHCP，只需将测试终端恢复为原来的自动 IP/DNS。如果已交接，应先停止并确认控制器 DHCP 退出，再恢复主路由 DHCP，让终端续租；手动设置过的终端也要恢复到可用的主路由网关和 DNS。具体恢复命令见 Linux 指南。其他设备仍依赖虚拟机网关时，不要直接停虚拟机。

保留虚拟机私人配置和路由器原设置的备份。本机浏览器能打开、单元测试通过或双网口已连接，都不能证明全局域网可用、可自动恢复或达到 5 Gbps。上述实测仍属于正式发布前的验收项。
