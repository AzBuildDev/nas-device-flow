# 安装、验收与恢复

此候选版本面向会管理 Linux 网络与 Docker 的试用者。请先备份主路由 DHCP 设置，保留一台可手动设 IP 的管理设备。

## 先准备网络

记录现有网段、网关、有线接口或聚合接口名。保留聚合，不创建替代原聚合的 LinuxBridge。确认交换机/AP 允许同一接口出现多个 MAC，关闭客户端隔离。

核心和面板各占一个未使用的固定 IPv4。DHCP 地址池避开主路由、NAS、核心、面板及静态设备。NAS 的管理 IP 应设为固定且上级网关保持主路由；否则 NAS 可能把自己接管而失去管理路径。配置中的 infrastructure 只用于排除设备分流，不会替 NAS 设置静态 IP。

编辑 config.local.json 的每个地址，包括 panel_origin（精确的浏览器访问地址）。容器 interface 保持 eth0；initialize 的 --parent 填宿主接口，如 bond0。MAC 保留偏好不能防伪造，不是网络准入认证。

IPv4 是当前接管范围。主路由若下发公网 IPv6，客户端可能绕过 IPv4 策略；启用前关闭 LAN IPv6/RA，或自行完成独立的 IPv6 接管。不要宣称已实现完整 IPv6 分流。

## 初始化和启动

在项目目录执行 README 的初始化命令，使用独立的 16 字符以上面板密码。核心 API 密钥随机生成，浏览器无需记住。runtime、.env、*.local.json 都不应上传。

可选基础设施 DHCP 保留文件的格式：

```text
02:00:00:00:00:10,set:infrastructure,192.168.50.10,infinite
```

这是虚构地址，实际 IP 必须在 infrastructure 中。用 --fixed-hosts /path/to/private.hosts 导入。也可以保持 NAS 自己的静态 IP，避免使用该文件。

执行 docker compose config --quiet 后启动。控制面板地址使用配置的 panel_origin。初次启动需要下载镜像、规则数据库和订阅，等待 /api/devices 显示核心正常。DHCP 默认关闭。

## 用一台设备试用

暂时给测试设备设置同网段空闲 IP，网关和 DNS 指向核心 IP，关闭它的本机 VPN/系统代理。面板出现设备后，分别验证直连和智能分流开关。观察 /api/stats 数据、设备累计流量及订阅切换。验证国内站点可访问、选定代理站点实际经过代理，并在关闭后验证直连行为。应用长连接可能需要重开。

## 自动接入

仅在单设备验收通过后关闭主路由 DHCP，再执行：

```sh
docker compose exec controller python3 /app/dhcp.py enable --confirm-main-router-dhcp-off
```

恢复客户端自动 IP/DNS并更新 DHCP 租约。确认网关和 DNS 都是核心 IP，再逐台开启代理。新设备初始默认直连；后续可通过设置选择首次发现设备的默认策略。启用脚本只能验证核心 API 可访问，无法自动证明主路由 DHCP 已关闭或所有线路正常。

公网不要映射面板、DNS、混合代理和核心 API 端口。局域网管理使用 HTTP，密码在局域网链路上没有 TLS 保护；有需要可自行加 HTTPS 反向代理并同步修改 panel_origin。未提供自动 TLS 配置。

## 恢复到主路由

```sh
docker compose exec controller python3 /app/dhcp.py disable
```

等待至少 3 秒确认旁路 DHCP 停止，再开启主路由 DHCP，客户端更新租约。手动设置过 IP/DNS 的设备也要恢复自动获取。必要时先在管理设备手动设主路由网关/DNS。

最后执行 docker compose down。不要先停核心再让全部设备等 DHCP 过期；没有自动故障接管。删除 runtime 会失去设备偏好、订阅和流量记录。

## 更新

备份 runtime 和 .env 到私有位置，拉取新版本后 docker compose up -d --build。不要重复 initialize 覆盖原部署。固定版本更新需要重新验收；回退代码/镜像时还原兼容的 runtime 备份。

## 首次迁移的旧租约

关闭主路由 DHCP 不会立即改写已连接客户端的旧默认网关。接管后设备仍应保持自动 IP/DNS；若重连仍保留旧租约，可忽略该 Wi-Fi 后重新输入密码加入。服务器无法立即强制修改客户端本地配置。

`dhcp_authoritative` 默认 false。只有管理员确认 NAS 是同一 LAN 的唯一 DHCP 服务（已关闭主路由及其他服务）后，才可用于拒绝过期/无效旧租约，促使客户端重新获取。它不保证所有客户端立即重新接入，也不能代替实机验收。

若选择启用：先关闭本控制器 DHCP 并等待停止，再将私有 runtime/control-center/settings.json 的 dhcp_authoritative 改为 true，然后使用以下命令。脚本重新生成 dnsmasq 配置；改变其他网络字段需要按部署步骤重新验收。

```sh
docker compose exec controller python3 /app/dhcp.py enable --confirm-main-router-dhcp-off --confirm-sole-dhcp-server
```

设备状态区分有效租约与最近三分钟核心连接。租约不证明设备使用该网关，核心连接也可能是直连或本机代理请求，不能证明国外站点已代理成功。见[接入诊断](diagnostics.md)。

原运行环境已由用户确认 iPad 忽略旧 Wi-Fi 后仅输入密码重入并成功访问。重入时私人 MAC 改变，现场为新记录重新开启分流。这验证自动网络配置，不表示跨 MAC 自动继承开关。MAC变化仍作为新设备，使用当前新设备默认策略（初始直连）；不能凭设备名称继承授权。通用发布包干净安装仍待验收。

## 从 rc.1 更新

私下备份 runtime 和 .env，获取 rc.2 后执行 `sh scripts/update.sh`。先构建，再给控制器 30 秒正常退出时间，最后仅重建控制器；退出时保存流量，核心及网络保持运行。不要用强制删除替代正常停止。更新不会自动开启 authoritative DHCP。

## Updating to rc.4 / 更新到 rc.4

Back up runtime and .env privately, fetch rc.4, and run `sh scripts/update.sh`. The controller stops gracefully before recreation. Existing device switches, subscriptions and sampled totals remain in runtime. Missing preferences.json defaults to direct only for newly discovered devices. The new settings menu allows language, future-device defaults and password changes; no DHCP/subnet migration is performed automatically.

更新前私下备份 runtime 和 .env，获取 rc.4 后运行 `sh scripts/update.sh`。已有设备开关保持，新设备初始默认直连；网页改密后需重新登录。普通设置不会变更 DHCP/网段。

rc.4 adds Japanese, Spanish and French plus System/Light/Dark appearance in the same package. Language and theme choices remain local to the browser; the layout and network configuration workflow are preserved. rc.3 remains available as its own release.

rc.4 在同一包中新增日语、西班牙语、法语与跟随系统/浅色/深色外观，设置保存在浏览器。现版布局与网络配置流程保留；rc.3 独立版本仍保留下载。
