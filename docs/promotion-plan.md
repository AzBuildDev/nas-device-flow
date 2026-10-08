# Developer-led sharing

Use the maintainer's developer identity, not an official project brand. Keep personal social accounts separate. GitHub uses the existing AzBuildDev account.

Start with the repository and an English developer write-up. Share why the tool was built, show fictional devices and a switch, describe the architecture and limits, and link to the code. Avoid claims of universal compatibility or a stable release.

For r/selfhosted, a separate developer Reddit account is enough. Its current rules require projects under three months old to be shared only in the current New Project Megathread, with English content. Recheck the rules at posting time. Source checked 2026-10-08: https://www.reddit.com/r/selfhosted/about/rules.json

No Chinese-platform promotion, personal-account posts, direct messages or mass outreach are planned. External testers are optional feedback after release, not a prerequisite. The release clearly states that fresh networked installation remains unverified.

First two weeks: respond to reproducible issues, improve the installation/recovery documentation, and publish a short update only when there is a concrete fix or verified compatibility result. Track successful installs and recurring failures rather than stars alone.

## Suggested English introduction

I built a small NAS web panel because I wanted to decide which device on my home LAN uses smart routing without installing a proxy client on every device.

The main screen is a device list with one switch per device. New devices default to direct access; enabled devices enter domestic-direct / proxy rules. A separate Mihomo container handles traffic, while the controller discovers devices, applies rules and shows sampled traffic counters.

The original setup runs on my UGREEN NAS with a bonded interface and a Huawei AX3. This is an experimental RC: the generalized installer has offline tests, but a fresh networked DHCP cutover is still unverified. IPv6 and automatic failover are not implemented.

Code: https://github.com/AzBuildDev/nas-device-flow

I would welcome feedback on the installation guide and device routing behavior. Please do not share real subscriptions, passwords or unredacted network logs.
