# 支持范围

| 组件 | 当前证据 | 说明 |
| --- | --- | --- |
| 绿联 DXP4800 / UGOS Pro / 聚合接口 | 原运行版实机使用 | 保留聚合；新安装脚本仍需干净环境试装 |
| Huawei TC7102，固件 10.0.5.61(SP3C30) | 原适配器实机读取 | 私有登录/读取 API，其他固件不保证兼容 |
| Linux Docker macvlan | 发布方案 | 交换机/AP/宿主防火墙也影响通信 |
| OpenWrt ubus | 模拟测试 | 需管理账户和 file.read DHCP 租约权限；未实机验收 |
| MikroTik RouterOS REST | 模拟测试 | 需启用相应 HTTPS 服务与最小权限账户；未实机验收 |
| 其他 NAS / ARM64 | 未验收 | 不列为正式支持 |
| macOS / Windows 浏览器 | 管理客户端 | 无需本地安装；不提供 Docker Desktop 网关版 |

默认 runtime/control-center/router-adapter.json 是 {"type":"none"}，不读取主路由。DHCP、邻居和 mDNS 仍提供设备发现；可手动命名。安装向导不会自动选择或配置适配器，也没有默认读取主路由的账户权限。需要补充路由器名称时，管理员另行配置适配器及私有凭据；这些来源不保证返回精确型号。

适配器配置字段以 app/router_adapters.py 为准。凭据仅放私有 runtime。即使公开 API，也可能随版本或权限配置变化；新增适配器需提交脱敏响应 fixture、模拟测试及实机版本信息。

设备名称不是唯一标识。MAC 改变会出现新的设备；MAC 不变、IP 改变会保留偏好。最近在线指近期网络响应，不保证此刻在线。主路由展示的型号可能只是厂商判断或用户备注，不等同于硬件身份认证。

参考：[Docker macvlan](https://docs.docker.com/engine/network/drivers/macvlan/)、[OpenWrt ubus](https://openwrt.org/docs/techref/ubus)、[MikroTik REST API](https://manual.mikrotik.com/docs/developer-guides/rest-api/)。

## NAS 手动安装入口

当前版本提供通用 Compose 安装项目与中英文浏览器向导。当前预构建镜像为 linux/amd64；NAS Docker GUI 需要允许 host、macvlan、TUN 与绝对目录挂载。保留有线聚合或桥接接口。绿联 UGOS Pro 项目创建和导入入口已核对，既有 bond0 的只读识别及 ARP 占用检测已实机验证；完整另一 LAN 的 GUI 干净安装仍待验收。群晖、威联通等文档路径示例并不代表正式支持或实机通过。ARM NAS 暂未提供已验收预构建镜像。
