# OpenAI subscription routing / OpenAI 专用订阅

Use two saved subscriptions at the same time: one for OpenAI destinations, one for other proxy traffic. This applies to every device with smart routing enabled. Devices with the switch OFF still use direct access.

## Set it up

1. Add both Clash/Mihomo YAML subscriptions under **Subscriptions & nodes**. Give them names you can recognize.
2. Switch the usual subscription to the one you want for ordinary foreign traffic, for example Bangkok.
3. In **OpenAI subscription**, select your US subscription and choose **Save purpose**.
4. Enable smart routing for the devices that should use these rules. Verify new requests to both an OpenAI site and an unrelated foreign site.

The panel shows the usual node and OpenAI node separately. A subscription name or node name does not prove its exit country: verify the actual egress. The dedicated group selects within that subscription; provide only suitable US nodes if you need a US exit consistently.

The OpenAI selection survives usual-subscription changes and controller restarts. **Refresh subscriptions in use** updates both providers. A subscription assigned to OpenAI cannot be deleted until its assignment is cleared. Choose **Follow usual subscription** and save to return to one-subscription routing. Existing connections can retain their previous route; reopen the application to test new connections.

## What is matched

Routing uses destination domains visible to Mihomo, rather than the application process on a phone or computer. The current dedicated rules match these domains and their subdomains:

- `openai.com`
- `chatgpt.com`
- `oaistatic.com`
- `oaiusercontent.com`
- `oaistatsig.com`

The exact hostname `cdn.openaimerge.com` is also included. These first-party domains are based on [OpenAI network recommendations](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps). Shared third-party destinations, such as verification, payment and analytics services, follow the usual rules. Pure-IP voice endpoints and traffic bypassing the IPv4 gateway are outside this domain-based selection.

Dedicated rules run before domestic/default rules, inside the existing enabled-device whitelist. Domestic destinations retain direct routing. The OpenAI group contains only its dedicated provider: it does not fall back to the usual provider, and rejects requests if it has no usable proxy members. Failed setting changes restore the previous assignment/configuration. See Mihomo's [providers](https://wiki.metacubex.one/config/proxy-providers/), [groups](https://wiki.metacubex.one/config/proxy-groups/) and [rule matching](https://wiki.metacubex.one/config/rules/) documentation.

## Upgrade

Update the controller image to `ghcr.io/azbuilddev/nas-device-flow-controller:0.2.1` while retaining your runtime mounts and networks. Do not rerun setup. Existing deployments keep their single-subscription behavior until an administrator assigns an OpenAI subscription. Device switches, DHCP settings and stored credentials remain in the existing private runtime.

## 中文操作

在「订阅与节点设置」中添加两份订阅，将曼谷切换为**常用订阅**；再在**OpenAI 专用订阅**选择美国订阅，点击**保存用途**。所有已开启智能分流的设备访问上述 OpenAI、ChatGPT、Codex 相关域名时使用专用订阅，其他国外代理流量使用常用订阅，国内保持直连；关闭设备开关仍全部直连。

面板分别显示两个用途的当前节点。名称不能证明出口地区，需要实际验证；如要求固定美国出口，专用订阅应只包含适用的美国节点。系统按目标域名识别用途，不识别终端进程；共享第三方域名、纯 IP 语音端点及绕过 IPv4 网关的流量不承诺走专用订阅。

专用选择会保存，切换常用订阅不会覆盖它。「更新已用订阅」同时更新两份。删除专用订阅前，先选择「跟随常用订阅」并保存。修改失败会恢复旧配置；专用组没有可用代理成员时拒绝对应请求，不自动改走常用订阅。已有长连接可能沿用旧出口，重新打开应用后验证。

升级只更新控制器镜像，保留 runtime 挂载和原网络，不重新运行安装向导。未设置专用订阅的已有用户维持原行为。
