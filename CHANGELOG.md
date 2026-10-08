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
