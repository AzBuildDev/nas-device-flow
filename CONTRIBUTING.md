# 贡献

先运行 python -m unittest discover -s tests -v。路由器适配请附型号、固件版本、读取 API 的官方文档或脱敏证据，区分模拟测试与实机测试。

不要提交订阅、凭据、真实设备列表、路由器响应全文、runtime 或真实家庭网络截图。复现材料使用 example.invalid、文档地址和虚构 MAC。

第一阶段优先安装失败、设备偏好保留、分流准确性和恢复操作。复杂的节点编辑、手机客户端与订阅市场暂不加入。

## Versioned prereleases

Publish each update with a new version, Git tag, release notes and source archive plus SHA256 checksums. Keep previous releases and their assets available; do not replace an existing release with different source. Update runtime version fields, the source manifest, CI image tag and changelog together. Verify the final commit with the complete CI workflow and privacy checks before publishing.

Any change to a distributed package requires a new version, including fixes. Published tags are immutable: never move a tag or overwrite an old release asset with changed contents. Each changelog section records changes, validation and upgrade impact. Runtime version fields, image tags and the source manifest must agree. Mark the new prerelease as latest while keeping older releases and assets downloadable.
