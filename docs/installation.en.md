# Installation and recovery

This RC targets Linux NAS users comfortable with Docker and LAN configuration. Fresh networked installation is still unverified. Do not change DHCP until a single manually configured client works.

## Prepare

Back up main-router DHCP settings. Keep a management device that can use a manually assigned IP and the main router as gateway/DNS. NAS management should have a fixed address outside the DHCP pool and keep the main router as its gateway.

Edit config.local.json: subnet, upstream gateway, unused core/panel addresses, panel_origin, infrastructure addresses and DHCP pool. Container interface stays eth0; --parent is the host's wired or bonded interface (for example bond0). Keep the existing bond. Networks with client isolation or blocked multiple MACs may not work. Host-to-macvlan access is restricted by Linux; use another LAN device to reach the panel.

Disable LAN public IPv6/RA or implement your own IPv6 routing separately. This project only handles IPv4.

## Start and test one client

Run the commands in the English README. Initialization creates private runtime and .env and refuses to overwrite them. Use a separate panel password of at least 16 characters. Open panel_origin in a LAN browser. Initial startup downloads the core, subscription and rule data.

For one test client, assign an unused LAN IP and set gateway/DNS to core_ip. Disable local VPN/system proxy. Verify the client appears, switches work, domestic destinations go direct and a selected proxy destination actually uses a proxy. Close/reopen long-lived applications when switching. DHCP remains off during this test.

## Enable automatic joining

After the single-client test succeeds, disable the main router's DHCP, then run:

```sh
docker compose exec controller python3 /app/dhcp.py enable --confirm-main-router-dhcp-off
```

Restore client automatic IP/DNS and renew leases. Confirm the received gateway/DNS equal core_ip. New devices initially default direct; the settings menu can change the default for future devices. The command only checks the core API; it cannot prove main-router DHCP is off or routing works.

Do not expose panel, DNS, mixed proxy or core API ports publicly. HTTP has no transport encryption; HTTPS reverse proxy setup is left to the operator and requires a matching panel_origin. A trusted panel administrator can supply URLs fetched by the core, so do not share admin access with untrusted users.

## Recovery

```sh
docker compose exec controller python3 /app/dhcp.py disable
```

Wait at least 3 seconds and verify NAS DHCP stopped, then re-enable main-router DHCP and renew client leases. Restore manually configured clients to automatic IP/DNS. If the NAS is unavailable, use the management client with main-router gateway/DNS to recover. Stop the stack only after clients have a working route:

```sh
docker compose down
```

There is no automatic failover. Keep private backups of runtime and .env. Never upload those files. Do not rerun initialize during updates; back up first and rebuild the controller.

## First migration and old leases

Disabling the router DHCP does not immediately replace client-side gateways from existing leases. Keep automatic IP/DNS. If reconnecting retains the old gateway, forget the Wi-Fi network and join again with its password. The server cannot force an immediate client configuration change.

`dhcp_authoritative` defaults to false. Only enable it after confirming this controller is the sole DHCP server on the LAN, with the main router and any other DHCP services disabled. It can reject invalid old leases so clients request a fresh allocation, but cannot guarantee instant migration.

Stop this controller DHCP first and wait for it to stop. If opting in, change dhcp_authoritative to true in private runtime/control-center/settings.json, then run:

```sh
docker compose exec controller python3 /app/dhcp.py enable --confirm-main-router-dhcp-off --confirm-sole-dhcp-server
```

The command regenerates dnsmasq configuration. Device status separately reports a valid lease and connections sampled within three minutes. A lease is configuration evidence; a core connection may be direct or a manually proxied connection. Neither proves successful proxy routing or successful browsing. In the original running environment, the user confirmed an iPad could rejoin by entering only the Wi-Fi password and browse successfully. Its private MAC changed, so the new record was explicitly enabled; this does not implement cross-MAC identity or automatic preference inheritance. Fresh installation of this generalized package remains unverified.

## Updating from rc.1

Back up runtime and .env privately, fetch rc.2, then run `sh scripts/update.sh`. It builds first, stops the controller with a 30-second grace period, and recreates only the controller while leaving the core and network in place. Do not use forced container removal; SIGTERM saves traffic counters. Updates do not automatically opt in to authoritative DHCP.

## Updating to rc.3 / 更新到 rc.3

Back up runtime and .env privately, fetch rc.3, and run `sh scripts/update.sh`. The controller stops gracefully before recreation. Existing device switches, subscriptions and sampled totals remain in runtime. Missing preferences.json defaults to direct only for newly discovered devices. The new settings menu allows language, future-device defaults and password changes; no DHCP/subnet migration is performed automatically.

更新前私下备份 runtime 和 .env，获取 rc.3 后运行 `sh scripts/update.sh`。已有设备开关保持，新设备初始默认直连；网页改密后需重新登录。普通设置不会变更 DHCP/网段。
