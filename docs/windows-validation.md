# Windows preview validation

Version: 0.2.3-windows-preview.1; base: v0.2.2 / 7e5d880.

## Executed on Windows

- Three new Python safety tests: PASS.
- Shell parser checks and isolated mocked-command integration: PASS. Missing lab acknowledgement and an existing DHCP marker block start; rejected Mihomo validation prevents compose up and leaves the configuration unchanged; valid mock validation reaches startup.
- PowerShell parser checks for importer, preflight and restore: PASS.
- Read-only preflight: PASS, private ACL-restricted snapshot saved under ignored runtime/.
- Offline restore plan and mocked apply: PASS. Default plan/WhatIf made no mutations; wrong GUID refused; simulated apply restored static address, gateway and DNS and removed fixture drift. All network commands were mocked. Real physical restore remains unverified.
- Full upstream suite with Python UTF-8 mode: 114 tests, 4 failures and 4 errors (106 passed). Four failures concern POSIX chmod 0600 semantics on Windows; bootstrap/installer modules cannot import Linux/POSIX fcntl; two runtime language tests fail on Windows subprocess command length. These limitations existed before deployment changes. A later language-only retry was interrupted; it is not counted as a passing test.
- Two independently built staged-source archives have matching SHA256 (reproducible packaging PASS). No shared backend or NAS Compose behavior changed. Full Linux guest/container suite remains required; do not suppress the failures to claim acceptance.

## Independent POSIX review

The complete branch suite passed on macOS with the pinned requirements: 139 tests (136 backend tests plus three Windows-preview tests). Shell syntax and mocked guest startup guards also passed. This POSIX result does not erase the Windows-host failures above or replace Linux/container CI and physical acceptance.

## Required isolated acceptance (NOT executed)

Real Linux VM installation and external wired/multiple-MAC reachability; real core syntax/rollback with providers; client gateway/DNS capture; domestic/overseas/DNS/UDP paths; real switch effects on traffic; DHCP uniqueness and DHCP fail-stop on core/VM failure; leases/private MAC changes; subscription rule retention in a running core; reboot and NIC replacement; HTTPS/certificate deployment; physical rollback/uninstall proving direct Internet recovery; IPv6 RA/RDNSS and bypass control; throughput and LAG/SMB checks.

No test claims automatic LAN takeover. No switch was created, Hyper-V was not enabled, DHCP was not started, and no production NAS/router/network adapter was changed.

## Gate

BLOCKED FOR PRODUCTION. Ship source development preview for review, not a validated all-home gateway installer. First obtain approval for the exact Hyper-V/reboot/external-switch plan and validate on an isolated wired network with a second client and an independent management path. Existing DHCP supervisor does not stop advertising on core failure; production takeover must wait for that safety work and its Linux regression tests.