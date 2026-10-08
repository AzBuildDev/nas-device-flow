# 接入诊断 / Connection diagnostics

开关记录期望策略，设备发现和规则加载都不证明设备已接入 NAS。

1. 在客户端确认实际出网接口的 IPv4、MAC、默认网关和 DNS。网关与 DNS 应指向配置中的核心地址，而不是面板地址。不要只凭设备名称判断。
2. 电脑同时连接有线/Wi-Fi时，每个接口可能是单独的列表条目。核对当前默认路由使用的接口，再开启对应条目；需要两个接口都受控时分别开启。IPv6、VPN、系统代理或多个默认路由也可能改变路径。
3. 客户端恢复自动 IP/DNS并更新租约后，再核对实际网关。没有 NAS DHCP 租约不代表一定没有接入（可能是静态 IP），但也不能宣称已自动接入。
4. 生成新的测试连接，查看是否有对应来源 IP 的核心连接、实际代理链和近期流量增长。历史累计只能说明过去采到流量，不能证明当前接入。不要把直连连接算成代理成功。
5. 无流量或规则命中为零时，先标记“接入待确认”；空闲、短连接、采样漏计都可能导致零值。DNS正常也不能证明网站走了代理。若有实际代理连接但网站仍失败，再检查节点、DNS、规则和应用错误。

不要把连接目标、订阅、真实 MAC 或完整连接响应公开贴到 Issues。

近期原运行环境实机验收：双网卡电脑启用实际出网接口后已观察到代理连接。iPad 先前持有旧主路由租约，用户确认忽略原 Wi-Fi 后仅输入密码重新加入，国外网页已可打开；现场检测到直连与代理连接。该结果验证原环境的自动网络配置迁移，不能替代通用发布包的干净安装验收。

iPad 重入时私人 MAC 改变，生成了新记录。现场按用户原来的代理意愿为新记录开启分流，并停用旧记录。这不是跨随机 MAC 自动继承授权。自动加入网络与身份持久化分开：IP/DNS自动获取；MAC不变时保持开关；MAC变化时按当前新设备默认策略处理（初始直连），设备同名不能证明同一设备。

## Status semantics

An enabled switch is a configured preference, not proof of attachment or successful browsing. Device discovery, a loaded rule, or a running DHCP server alone cannot prove the client's gateway/DNS.

For computers with Ethernet and Wi-Fi, check the active default-route interface and its IP/MAC. Each interface can appear separately. Enable each intended interface independently. Check IPv6, VPN and system proxy paths too.

Renew DHCP and inspect the client gateway/DNS. Static clients may have no NAS lease. Generate fresh traffic and look for matching core source IP, actual proxy chain and recent counter increments. Old totals do not prove current routing. No hits or sampled traffic means attachment is unconfirmed, not necessarily a proven failure.

## 后续诊断状态设计

分开显示“策略已启用”“近期发现”“有租约”“近期采到核心流量”“近期采到代理流量”。未知字段显示待确认，不合并为笼统的“网络正常”。只有用户核对或有可靠客户端证据才能展示实际网关/DNS。默认网关与 DNS 不能由邻居表推断；本地候选已实现有效 MAC/IP 租约与最近三分钟采样核心连接状态，仍无法证明实际默认网关/DNS和代理目标成功。

## Updating to rc.3 / 更新到 rc.3

Back up runtime and .env privately, fetch rc.3, and run `sh scripts/update.sh`. The controller stops gracefully before recreation. Existing device switches, subscriptions and sampled totals remain in runtime. Missing preferences.json defaults to direct only for newly discovered devices. The new settings menu allows language, future-device defaults and password changes; no DHCP/subnet migration is performed automatically.

更新前私下备份 runtime 和 .env，获取 rc.3 后运行 `sh scripts/update.sh`。已有设备开关保持，新设备初始默认直连；网页改密后需重新登录。普通设置不会变更 DHCP/网段。
