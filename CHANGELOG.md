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
