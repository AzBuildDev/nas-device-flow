# 0.2.1

- Rename any saved subscription directly in its list row, including the default and OpenAI-assigned subscriptions.
- Add inline Save/Cancel controls, Escape cancellation and translated labels/status in all six panel languages. Automatic list refresh pauses while editing.
- Validate trimmed names at 1–60 characters and save metadata atomically with authentication/CSRF protection. Renaming preserves IDs, URLs, assignments and provider caches, without reloading Mihomo.
- Validation: 123 source tests; browser checks and final CI evidence are recorded in release-readiness.md.
- Upgrade impact: update the controller image, preserve runtime mounts/networks and do not rerun setup. Existing names and routing remain unchanged until edited; hardware/IPv4 support limits are unchanged.

# 0.2.0

- Use two saved subscriptions together: an optional OpenAI subscription for first-party OpenAI/ChatGPT/Codex domains, and the usual subscription for other proxy traffic.
- Keep service rules inside the enabled-device whitelist. OFF devices and infrastructure remain direct; existing domestic rules stay in place.
- Add a subscription-purpose selector and separate OpenAI node status in all six panel languages, within the existing collapsed subscription section.
- Persist assignments across restarts and usual-subscription changes. Refresh both providers, protect referenced subscriptions from deletion, and restore previous configuration on failed changes.
- Isolate node names and provider caches. The dedicated group has no usual-provider fallback and uses REJECT when empty.
- Validation: 119 local source tests, JavaScript syntax and live browser checks pass. Installed Mihomo v1.19.32 passed an isolated empty-group REJECT check; original LAN requests returned US for OpenAI and Thailand for ordinary foreign traffic. Final container/CI checks are recorded separately.
- Upgrade impact: update the controller image while preserving mounts/networks; no setup rerun. Dedicated routing is opt-in, with existing device policies and DHCP retained. Domain matching does not identify application processes or cover every third-party/pure-IP endpoint. Hardware and IPv4 support limits are unchanged.

# 0.1.0

- First regular release, retaining the documented Linux/x86-64, IPv4 and hardware-validation limits.
- Add Korean to the panel language selector, browser locale detection and all 216 translated messages; six languages ship in one package. The installer remains Chinese/English.
- Remove the Huawei fallback from device provenance. Display actual adapter sources or a generic Router label. Clear stale router metadata after adapter changes, disabling or failed synchronization, while retaining manual device names and policies.
- Clarify NAS-management-IP installer access versus the production macvlan panel: validate the panel from another device on the same LAN.
- Stop pre-filling suggested core/panel/DHCP addresses. Keep detected host network values and require explicit address choices, with bilingual field explanations and conflict checks.
- Validation: 105 tests, browser Korean checks, complete CI and public image verification are required before publication.
- Upgrade impact: no installation rerun or policy migration. GUI deployments update only the controller image reference, keeping runtime and networking. Old versions remain immutable. Other NAS fresh-LAN deployments, IPv6 and failover remain unverified or unsupported.

# 0.1.0-rc.5

- Add a temporary browser installer for manual NAS Docker-GUI deployment, with Chinese/English instructions and a setup access code.
- Detect wired, bonded and bridge LAN interfaces, actual IPv4 prefixes and gateways; suggest addresses and probe ARP conflicts. Sleeping devices and DHCP reservations still require operator verification.
- Generate private runtime and a standalone production Compose file with absolute NAS mounts, including Mihomo and the controller; no SSH, host Python, JSON editing or image build is required for this path.
- Refuse existing state, stage configuration writes privately and serialize competing installers. DHCP remains OFF during setup.
- Add authenticated, CSRF-protected automatic-joining controls to panel Settings with client-test, router-DHCP-off and sole-server confirmations, plus recovery instructions in all five panel languages.
- Allow the core and controller to read private 0700/0600 runtime created by a non-root NAS account using scoped DAC_OVERRIDE in their containers; no Docker socket or host-root mount is added.
- Retain the manual initializer and add an optional Docker-based terminal wizard with preflight and retry-start modes.
- Publish a versioned x86-64 controller image after tag CI passes. Correct the previous Compose image-label mismatch; published older tags remain unchanged.
- Validation: 102 source tests pass locally; browser demo checks configuration, export and bilingual steps. Container and final CI results are recorded separately in release-readiness.md.
- Upgrade impact: existing state and policies are retained. Existing operators do not rerun setup; GUI installs update image references while retaining network and runtime mounts. No automatic DHCP handover, IPv6 routing or failover is added. Fresh deployment on another real LAN remains unverified.

# 0.1.0-rc.4

- Add Japanese, Spanish and French alongside Chinese and English in the same installation package.
- Translate login, settings, device status, subscriptions, errors, help and confirmation text, including appearance controls in every language.
- Detect regional browser language preferences and fall back to English for unsupported languages; remember manual selection locally.
- Add system, light and dark appearance modes in Settings; remember the choice in the browser, follow system changes in automatic mode and synchronize changes across tabs.
- Apply the initial theme before painting and adapt traffic chart colors and the fictional demo banner.
- Preserve the existing layout, device names, user content and routing/DNS behavior.
- Validation: 82 tests cover language and appearance behavior; full CI checks Compose, image build, offline startup and isolated DHCP migration. Original NAS deployment was verified separately without publishing private data.
- Upgrade impact: no server configuration migration; existing device policies are retained, and language/appearance choices are browser-local. Fresh generic LAN installation, IPv6 and failover remain unverified or unimplemented.

# 0.1.0-rc.3

- Add a settings gear with General, Password, Access/Statistics and subscription shortcut.
- Ship Chinese/English UI in one package, following browser language initially and remembering manual selection, including before login.
- Add a private default policy for future devices; defaults OFF/direct, preserves existing switches and does not match identity by device name.
- Add in-page password change with current-password verification, confirmation, 16–256 characters, CSRF/rate limiting, separate core secret and invalidation of all sessions.
- Show read-only access/version/traffic-start information; ordinary settings do not edit DHCP or LAN addressing.
- Update fictional demonstrations and bilingual installation/update guidance.
- Fresh generic LAN installation, IPv6, failover, password reset and regional presets remain outside this release.

# 0.1.0-rc.2

- Separate configured policy, valid MAC/IP DHCP lease, and core connections observed within three minutes. A switch no longer implies proxy success.
- Document first migration from old DHCP leases and multi-interface clients.
- DHCP authoritative defaults OFF; enabling it requires confirming the controller is the sole LAN DHCP server.
- Add isolated, parameterized DHCP protocol tests for invalid-old-lease NAK followed by DISCOVER/ACK and retained-address INIT-REBOOT ACK.
- Stop the controller gracefully before recreating it, allowing traffic counters to persist. Controller stop grace is 30 seconds.
- Original environment: the user confirmed iPad rejoining with only the Wi-Fi password worked. Its changed private MAC was explicitly enabled; no cross-MAC automatic identity/authorization is claimed.
- Correct tested-router identity to Huawei TC7102, firmware 10.0.5.61 SP3C30. Clarify initialization-only password setup and Chinese-only UI; language switching and regional presets are future work.
- 64 source tests, image/offline checks and isolated protocol checks are required for this update. Fresh generic networked installation remains unverified.

# 0.1.0-rc.1 (superseded)

Initial experimental source release, with per-device routing, subscription management, sampled decimal-MB traffic, separate panel/core credentials and default-off DHCP. Use rc.2 for current installation.
