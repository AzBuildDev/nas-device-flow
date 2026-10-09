#!/bin/sh
# Optional SSH installer; NAS GUI users start setup.compose.yaml instead.
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project"
lang=zh
mode=install
previous=
for argument in "$@"; do
    if [ "$previous" = lang ]; then
        case "$argument" in zh|en) lang=$argument ;; *) echo 'Use --lang zh or en' >&2; exit 1 ;; esac
        previous=
        continue
    fi
    case "$argument" in
        --lang) previous=lang ;;
        --check|--prepare-only|--start)
            [ "$mode" = install ] || { echo 'Choose one installation mode' >&2; exit 1; }
            mode=${argument#--} ;;
        --help|-h) echo 'sh scripts/install.sh [--lang zh|en] [--check|--prepare-only|--start]'; exit 0 ;;
        *) echo 'Unknown option. Use --help.' >&2; exit 1 ;;
    esac
done
[ -z "$previous" ] || { echo 'Use --lang zh or en' >&2; exit 1; }
say() { if [ "$lang" = en ]; then echo "$2"; else echo "$1"; fi; }
fail() { say "$1" "$2" >&2; exit 1; }
[ "$(uname -s)" = Linux ] || fail '网关须在 Linux NAS 上安装；macOS/Windows 请使用浏览器管理。' 'Install the gateway on a Linux NAS; use a browser on macOS/Windows.'
[ "$(uname -m)" = x86_64 ] || fail '当前发布镜像面向 x86-64；ARM NAS 尚未验收。' 'The release image targets x86-64; ARM NAS is not validated.'
command -v docker >/dev/null 2>&1 || fail '请先在 NAS 应用中心安装 Docker／容器管理应用。' 'Install the NAS Docker/container app first.'
docker info >/dev/null 2>&1 || fail '无法连接 Docker；请启动 NAS 的容器应用，并检查账户权限。' 'Docker is unavailable. Start the NAS container app and check account permissions.'
docker compose version >/dev/null 2>&1 || fail '需要 Docker Compose v2 或更新版。' 'Docker Compose v2 or newer is required.'
endpoint=${DOCKER_HOST:-$(docker context inspect --format '{{.Endpoints.docker.Host}}')}
case "$endpoint" in unix://*) ;; *) fail '请在 NAS 本机运行；安装不支持远程 Docker context。' 'Run on the NAS itself; remote Docker contexts are not supported.' ;; esac
case "$(docker info --format '{{json .SecurityOptions}}')" in *rootless*) fail 'macvlan 需要普通 Docker，不能使用 rootless 模式。' 'macvlan needs rootful Docker, not rootless mode.' ;; esac
[ -c /dev/net/tun ] || fail '缺少 /dev/net/tun，请在 NAS 上启用 TUN 支持。' 'Missing /dev/net/tun. Enable NAS TUN support.'
image=ghcr.io/azbuilddev/nas-device-flow-controller:0.1.0
start() {
    [ -f .env ] && [ -d runtime ] || fail '尚未初始化，请先运行安装向导。' 'Not initialized. Run the installer first.'
    docker compose config --quiet || fail 'Compose 配置无效，请检查 .env。' 'Invalid Compose configuration. Check .env.'
    docker compose up -d --build || fail '启动未完成，配置已保留。检查镜像下载／Docker 网络后，用 --start 重试。' 'Startup failed; configuration was retained. Check image download/networking and retry with --start.'
    ready=no
    attempt=0
    while [ "$attempt" -lt 20 ]; do
        if docker compose exec -T controller python3 -c 'from urllib.request import urlopen; urlopen("http://127.0.0.1:9080/health",timeout=2); from server import core; core("/version")' >/dev/null 2>&1; then ready=yes; break; fi
        attempt=$((attempt + 1))
        sleep 3
    done
    [ "$ready" = yes ] || fail '服务尚未就绪，DHCP 仍关闭。请在 NAS Docker 界面查看两个容器的日志。' 'Services are not ready; DHCP remains OFF. Inspect both container logs in the NAS Docker app.'
    say '面板与核心已启动。这只验证服务连通，仍需用一台设备验证分流。' 'Panel and core are up. Test routing with one client before DHCP handover.'
    docker run --rm --network none --cap-drop ALL --mount "type=bind,src=$project,dst=/workspace,readonly" --entrypoint python3 "$image" /app/install.py --project /workspace --lang "$lang" --guide
}
if [ "$mode" = start ]; then start; exit 0; fi
if [ "$mode" != check ] && { [ -e .env ] || [ -e runtime ]; }; then
    fail '已有部署，不会覆盖。启动用 --start；升级用 sh scripts/update.sh。' 'Existing state will not be overwritten. Use --start or sh scripts/update.sh to upgrade.'
fi
say '准备安装镜像；Python 和依赖在 Docker 内运行，无需在 NAS 安装。' 'Preparing the installer image. Python and dependencies run inside Docker.'
docker build -t "$image" . || fail '镜像构建失败，请检查 NAS 下载网络和存储空间。' 'Image build failed. Check download connectivity and storage.'
if [ "$mode" = check ]; then
    docker run --rm --network host --cap-drop ALL --entrypoint python3 "$image" /app/install.py --lang "$lang" --check
    exit 0
fi
[ -t 0 ] || fail '需要交互终端，请通过 NAS SSH 登录，或使用浏览器安装项目。' 'Use an interactive NAS SSH terminal or the browser setup project.'
set -- --project /workspace --lang "$lang"
[ "$mode" != prepare-only ] || set -- "$@" --prepare-only
result=0
docker run --rm -it --network host --cap-drop ALL --cap-add NET_RAW --cap-add DAC_OVERRIDE --cap-add CHOWN \
    --security-opt no-new-privileges:true --env "NDF_INSTALL_UID=$(id -u)" --env "NDF_INSTALL_GID=$(id -g)" \
    --mount "type=bind,src=$project,dst=/workspace" --entrypoint python3 "$image" /app/install.py "$@" || result=$?
case "$result" in 0) exit 0 ;; 10) start ;; *) exit "$result" ;; esac
