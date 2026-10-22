#!/bin/sh
# Uses upstream backend/Compose. No DHCP handover or host networking changes.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"
action=${1:-check}
case "$action" in
    check) sh deploy/windows/guest-check.sh ;;
    prepare) sh deploy/windows/guest-check.sh; sh scripts/install.sh --prepare-only ;;
    start)
        [ "${NDF_VERIFIED_BRIDGED_LAB:-}" = yes ] || { echo 'First verify isolated wired L2 lab and address exclusions; then explicitly set NDF_VERIFIED_BRIDGED_LAB=yes' >&2; exit 1; }
        [ -f .env ] && [ -f runtime/config.yaml ] || { echo 'Run prepare first' >&2; exit 1; }
        [ ! -e runtime/control-center/dhcp.enabled ] || { echo 'DHCP marker present: preview refuses startup. Disable via panel on existing running installation before retrying.' >&2; exit 1; }
        sh deploy/windows/guest-check.sh
        docker compose config --quiet
        # Validate before service replacement; preserve the working config on failure.
        docker compose run --rm --no-deps mihomo -t -f /root/.config/mihomo/config.yaml
        docker compose up -d --build
        echo 'Started; configured policy is not verified routing. Keep DHCP OFF and test one isolated client.'
        ;;
    status) docker compose ps ;;
    stop)
        [ ! -e runtime/control-center/dhcp.enabled ] || { echo 'Restore client gateways and stop DHCP through the panel before shutdown.' >&2; exit 1; }
        docker compose stop
        ;;
    *) echo 'Usage: sh deploy/windows/guest-install.sh check|prepare|start|status|stop' >&2; exit 2 ;;
esac
