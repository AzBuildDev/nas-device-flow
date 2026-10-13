# Settings / 设置

## Language

One package supports Chinese, English, Japanese, Spanish, French and Korean. The gear is accessible before login, so the login screen can be translated too. The initial selection follows the browser; manual selection of any of the six languages or automatic choice is remembered in that browser. It does not change other users' language or routing/DNS.

## Appearance / 外观

Choose System, Light or Dark in General settings, including before login. System is the default and follows changes to the operating system preference. A manual selection takes precedence, is stored locally in the browser and synchronizes between tabs. The theme is applied before the page paints to reduce a light flash, and traffic charts use the selected theme colors. This does not change network settings or other users' preferences.

常规设置提供跟随系统、浅色与深色，登录前也可使用。默认跟随系统并响应系统变化；人工选择保存在当前浏览器，并在同浏览器标签页同步。主题在页面绘制前应用，图表随主题配色，不改变网络配置。

## Future-device default

The initial default is direct (`new_device_proxy: false`). An administrator can choose direct or smart routing for devices first discovered after saving the setting. Existing enabled/disabled switches stay unchanged. A changed private MAC is a new device and receives this default, even when the name matches an old record. Choosing smart means newly discovered devices may use the subscription; this is a global default, not cross-MAC identity matching.

Preferences are kept in private runtime/control-center/preferences.json, written atomically with mode 600. An absent file defaults to false. Updating from rc.2 preserves existing device records and switches; no manual preferences migration is required.

## Password

The initial password is set during bootstrap. Logged-in administrators can now change it in the password tab using the current password, a new 16–256-character password and matching confirmation. Leading/trailing spaces and reuse of the core secret are rejected. The API requires session/CSRF validation and rate-limits wrong current passwords. Success invalidates every session and requires login again; core credentials remain unchanged.

No forgotten-password reset wizard is included. No actual management password was changed as part of testing the release; HTTP tests use fictional credentials in temporary directories.

## Access and statistics

The about tab shows panel/core versions, gateway, upstream, subnet, DHCP state and the device-sampling start. These fields are read-only. The Automatic joining setup section can enable or stop NAS DHCP after operator confirmation. It does not change the router DHCP configuration or renew client leases. Subnet/gateway changes still require deployment configuration. Subscription management is linked from the menu, with device control staying on the main screen.

## 中文要点

小齿轮二级菜单包含常规、管理密码、接入与统计及订阅入口。语言选择保存在当前浏览器；登录前也可切换。新设备初始默认直连，保存新默认只影响此后首次发现的 MAC。已有设备开关不变，随机 MAC 改变也按新默认处理，不按同名继承权限。

改密需当前密码与新密码确认，成功后全部会话退出，核心密钥不变。只读网络信息帮助排查；「自动接入设置」可在确认条件后开启或停止 NAS DHCP；它不会修改主路由 DHCP 或更新客户端租约。网段和网关仍需通过部署配置修改。更改语言不会自动适配其他地区的分流/DNS。

Automatic selection checks browser language preferences in order, including regional variants such as ja-JP, es-MX and fr-CA and ko-KR, and falls back to English if no language is supported. Device names and user content keep their original text.

Device name sources follow the configured adapter (Huawei, OpenWrt or MikroTik). Missing provenance uses a generic Router label; changing or disabling an adapter clears stale router-only metadata without altering manual device names or routing policies. Adapters are optional and are not automatically identified from the router brand.

## Subscription purpose / 订阅用途

Subscriptions & nodes now offers an optional OpenAI subscription independent of the usual subscription. It applies to all enabled devices; selecting it does not enable any device automatically. Both provider statuses are shown separately. See [service routing](service-routing.md) for setup, domain scope, clearing the assignment and upgrade instructions.

「订阅与节点设置」提供独立的 OpenAI 专用订阅，作用于已开启智能分流的设备，不会自动开启设备开关。常用订阅与专用订阅分别显示节点状态；详见[用途分流说明](service-routing.md#中文操作)。

## Rename a subscription / 订阅重命名

Open Subscriptions & nodes, choose Rename beside any subscription, edit its name and Save. Cancel or Escape discards the edit. Names are trimmed and limited to 1–60 characters. The list pauses automatic refresh while you type. Default and OpenAI-assigned subscriptions can also be renamed; the selection is stored by ID, so the change does not reload the core or change routing, credentials or the subscription URL.

打开「订阅与节点设置」，点击对应订阅的「重命名」，输入名称并「保存」。点击「取消」或按 Esc 放弃修改。名称去除首尾空白后需为 1–60 个字符；编辑时自动刷新暂停。常用和 OpenAI 专用订阅也能改名，选择按 ID 保存，改名不会重载核心或修改分流、凭据和订阅链接。
