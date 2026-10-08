# 依赖与来源

本目录仅整理自己的 Python 模块、页面和测试。没有包含华为固件 JavaScript、真实路由器响应、MetaCubeXD 代码、订阅节点或私有运行配置。

Mihomo 使用上游官方容器，以独立进程通过 HTTP API 通信。[版本源码](https://github.com/MetaCubeX/mihomo/tree/v1.19.32)与[GPLv3 许可证](https://github.com/MetaCubeX/mihomo/blob/v1.19.32/LICENSE)。本项目的许可证不改变它的许可证。

PyYAML 使用 [MIT 许可证](https://github.com/yaml/pyyaml/blob/main/LICENSE)。Dockerfile 从 Debian 仓库安装 Python、dnsmasq、iproute2 等；组件许可保存在镜像 /usr/share/doc/<package>/copyright。发布预构建镜像前另行核验并提供相应源码与许可，不将本次源码候选打包视为二进制分发审核。

本次发布计划仅包含自己的源代码，不上传重打包的 Mihomo 或系统镜像。Docker 镜像仍从各自上游下载。
