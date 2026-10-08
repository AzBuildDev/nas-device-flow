# 🧭 NAS Device Flow

**在一个网页里，控制每台设备的智能分流。**

[🌐 English](README.md) · 简体中文 · [部署说明](docs/installation.md) · [发布版本](https://github.com/Azusagawa0409/nas-device-flow/releases)

给手机、电脑、平板分别打开或关闭分流，查看设备代理流量，管理订阅。日常最常用的设备开关放在主页面，其他选项收进小齿轮设置。

完成 DHCP 接管后，设备保持自动 IP/DNS，输入 Wi-Fi 密码即可接入。面板与 Mihomo 一起运行在 Linux NAS 上，两个服务通过同一份 Docker Compose 部署。

![虚构设备演示，未连接真实网络](docs/images/demo.png)

## ✨ 可以做什么

- **按设备分流。** 选择直连或智能分流；MAC 不变时保留原来的开关。
- **看网络流量。** 实时上传下载、趋势图、活跃连接，以及每台设备的代理流量采样累计。
- **管理订阅。** 添加、切换和更新 Clash/Mihomo YAML 订阅。
- **设置自己的默认值。** 齿轮菜单提供中英切换、新设备默认策略、管理密码修改和接入信息。
- **发现联网设备。** 通过 DHCP、邻居记录和 mDNS 收集名称，可选路由器适配器补充设备信息。

新设备默认直连，也可以在设置里改为智能分流。修改默认值只影响之后首次发现的设备，已有开关保持不变。私人 MAC 改变也算新设备，按当前默认策略处理，不根据同名自动继承原设备授权。

界面语言保存在当前浏览器。分流规则和 DNS 单独配置；初始化的“中国直连、其他目的地代理”规则来自中国大陆使用场景，海外部署应按当地网络调整。

## 👀 先看演示

```sh
python3 scripts/demo.py
```

打开 http://127.0.0.1:9088/。设备与流量都是虚构的，不读取部署凭据，也不修改真实网络。

## 🚀 部署到 Linux NAS

需要 Linux Docker Compose、支持 macvlan 的有线接口，以及可以配置 DHCP 的主路由。NAS 与客户端应位于同一局域网。

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp examples/settings.json config.local.json
# 按实际网络填写所有地址和 panel_origin。
# 将下面的 eth0 换成 NAS 的实际有线接口名。
.venv/bin/python scripts/initialize.py --settings config.local.json --parent eth0

docker compose config --quiet
docker compose up -d --build
```

初始化时设置并二次确认管理密码，再输入订阅链接。Mihomo 核心密钥独立随机生成；密码、订阅和设备记录保存在被 Git 忽略的私有运行目录中。

DHCP 默认关闭。先按[安装与恢复说明](docs/installation.md)验收一台设备，再接管 DHCP。已有设备可能需要一次忽略原 Wi-Fi 并重新加入，才能替换旧租约。

macOS、Windows、手机和平板通过浏览器使用面板。网关服务运行在 Linux 上；Docker Desktop 不支持这套 macvlan 网关部署。[Docker 平台说明](https://docs.docker.com/engine/network/drivers/macvlan/)

## 🧪 当前状态

这是实验性预发布版本。原部署运行在绿联 DXP4800、UGOS Pro、聚合网口和 Huawei TC7102 环境。通用包已有源码测试与隔离容器/DHCP 检查，其他局域网的全新部署仍需实机验收；OpenWrt 与 MikroTik 名称适配器目前只有模拟测试。

开关开启表示策略已配置，不证明设备正在使用 NAS 网关，也不保证网站可达。查看[接入诊断](docs/diagnostics.md)与[兼容说明](docs/compatibility.md)。

目前接管 IPv4，NAS 停机时没有自动故障切换。公网 IPv6 可能绕过 IPv4 分流；面板和核心 API 应仅在局域网内开放。

流量使用十进制单位：1 MB = 1,000,000 字节。设备流量是持久化的采样估算，不能代替订阅账单；图表统计经过 Mihomo 的流量，不代表全局域网总流量。查看[统计定义](docs/metrics.md)。

## 🤝 一起完善

```sh
.venv/bin/python -m unittest discover -s tests -v
```

欢迎[反馈问题](https://github.com/Azusagawa0409/nas-device-flow/issues)或提交兼容报告。附上 NAS、Linux、Docker 和路由器版本，用虚构 IP/MAC 举例，并去掉凭据与敏感日志。请注明结果来自实机还是模拟测试。

[贡献指南](CONTRIBUTING.md) · [安全说明](SECURITY.md) · [发布检查](docs/release-readiness.md)

自己的控制器和网页采用 [MIT 许可证](LICENSE)。Mihomo 和系统组件保留各自许可，见[依赖说明](THIRD_PARTY_NOTICES.md)。本项目与 OpenClash、绿联及路由器厂商无隶属关系。
