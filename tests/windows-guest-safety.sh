#!/bin/sh
# Isolated mocked-command integration; no real Docker or network access.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp/deploy/windows" "$tmp/runtime/control-center" "$tmp/bin"
cp "$root/deploy/windows/guest-install.sh" "$tmp/deploy/windows/"
printf 'exit 0\n' > "$tmp/deploy/windows/guest-check.sh"
touch "$tmp/.env" "$tmp/runtime/config.yaml"
cat > "$tmp/bin/docker" <<'MOCK'
#!/bin/sh
printf '%s\n' "$*" >> "$NDF_TEST_LOG"
case "$*" in *'mihomo -t'*) exit "${NDF_TEST_VALIDATION_EXIT:-0}" ;; esac
exit 0
MOCK
chmod +x "$tmp/bin/docker"
export PATH="$tmp/bin:$PATH" NDF_TEST_LOG="$tmp/commands"
run() { sh "$tmp/deploy/windows/guest-install.sh" start > "$tmp/output" 2>&1; }
if run; then echo 'Missing lab confirmation accepted' >&2; exit 1; fi
[ ! -e "$NDF_TEST_LOG" ]
export NDF_VERIFIED_BRIDGED_LAB=yes
touch "$tmp/runtime/control-center/dhcp.enabled"
if run; then echo 'DHCP-enabled state accepted' >&2; exit 1; fi
[ ! -e "$NDF_TEST_LOG" ]
rm "$tmp/runtime/control-center/dhcp.enabled"
original=$(cksum "$tmp/runtime/config.yaml")
export NDF_TEST_VALIDATION_EXIT=1
if run; then echo 'Invalid core accepted' >&2; exit 1; fi
! grep -q 'up -d' "$NDF_TEST_LOG"
[ "$original" = "$(cksum "$tmp/runtime/config.yaml")" ]
export NDF_TEST_VALIDATION_EXIT=0
run
grep -q 'up -d --build' "$NDF_TEST_LOG"
echo 'PASS: confirmation/DHCP gates; invalid core prevents replacement; valid core starts reused Compose.'
