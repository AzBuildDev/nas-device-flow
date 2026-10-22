# Read-only host inventory. No feature, adapter, route, DHCP or firewall changes.
[CmdletBinding()]
param([string]$SnapshotRoot)
$ErrorActionPreference = 'Stop'
if (-not $SnapshotRoot) { $SnapshotRoot = Join-Path $PSScriptRoot '../../runtime/windows-preflight' }
if ($env:OS -ne 'Windows_NT') { throw 'Run this script in Windows PowerShell on the intended host.' }
$warnings = New-Object 'System.Collections.Generic.List[string]'
function Read-State([string]$Name, [scriptblock]$Query) {
    try { & $Query } catch { $warnings.Add("$Name unavailable; review locally with administrator rights if needed.") }
}
$root = [IO.Path]::GetFullPath($SnapshotRoot)
# Never overwrite earlier evidence; private output is excluded by runtime/ in .gitignore.
$target = Join-Path $root ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $target -Force | Out-Null
$acl = New-Object System.Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true, $false)
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
foreach ($principal in @($sid.Value, 'S-1-5-18', 'S-1-5-32-544')) {
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule((New-Object System.Security.Principal.SecurityIdentifier($principal)), 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $target -AclObject $acl
$os = Read-State OS { Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture }
$cpu = @(Read-State CPU { Get-CimInstance Win32_Processor | Select-Object Name, VirtualizationFirmwareEnabled, SecondLevelAddressTranslationExtensions, VMMonitorModeExtensions })
$computer = Read-State Hypervisor { Get-CimInstance Win32_ComputerSystem | Select-Object HypervisorPresent }
$adapters = @(Read-State Adapters { Get-NetAdapter -IncludeHidden | Select-Object Name, InterfaceDescription, InterfaceGuid, ifIndex, Status, MacAddress, LinkSpeed, HardwareInterface, MediaType, PhysicalMediaType })
$interfaces = @(Read-State IPInterfaces { Get-NetIPInterface | Select-Object InterfaceIndex, InterfaceAlias, AddressFamily, Dhcp, InterfaceMetric, ConnectionState, Forwarding, RouterDiscovery })
$addresses = @(Read-State Addresses { Get-NetIPAddress | Select-Object InterfaceIndex, InterfaceAlias, AddressFamily, IPAddress, PrefixLength, PrefixOrigin, SuffixOrigin, SkipAsSource })
$routes = @(Read-State Routes { Get-NetRoute | Select-Object InterfaceIndex, InterfaceAlias, AddressFamily, DestinationPrefix, NextHop, RouteMetric, Protocol, PolicyStore })
$dns = @(Read-State DNS { Get-DnsClientServerAddress | Select-Object InterfaceIndex, InterfaceAlias, AddressFamily, ServerAddresses })
$dnsMode = @(Read-State DNSMode {
    Get-NetAdapter | ForEach-Object {
        $guid = ([guid]$_.InterfaceGuid).ToString('B')
        $key = Get-ItemProperty -LiteralPath ("HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\" + $guid) -ErrorAction SilentlyContinue
        [pscustomobject]@{ InterfaceGuid=$guid; StaticIPv4Dns=([bool]$key.NameServer) }
    }
})
$dhcp = @(Read-State DHCP { Get-CimInstance Win32_NetworkAdapterConfiguration -Filter 'IPEnabled=True' | Select-Object InterfaceIndex, DHCPEnabled, DHCPServer, DHCPLeaseObtained, DHCPLeaseExpires, DefaultIPGateway, DNSServerSearchOrder })
$features = @(Read-State Features { Get-WindowsOptionalFeature -Online | Where-Object FeatureName -Match 'Hyper-V|VirtualMachinePlatform|Subsystem-Linux' | Select-Object FeatureName, State })
$switches = @(Read-State Switches { if (Get-Command Get-VMSwitch -ErrorAction SilentlyContinue) { Get-VMSwitch | Select-Object Name, Id, SwitchType, NetAdapterInterfaceDescription, AllowManagementOS } })
$vms = @(Read-State VMs { if (Get-Command Get-VM -ErrorAction SilentlyContinue) { Get-VM | Select-Object Name, Id, State, Generation, AutomaticStartAction, AutomaticStopAction } })
$bindings = @(Read-State Bindings { Get-NetAdapterBinding -AllBindings | Select-Object Name, ComponentID, Enabled })
$firewall = @(Read-State Firewall { Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction, AllowInboundRules, AllowLocalFirewallRules })
$firewallRules = @(Read-State FirewallRules { Get-NetFirewallRule -PolicyStore ActiveStore | Select-Object Name, Enabled, Direction, Action, Profile, PolicyStoreSourceType })
$services = @(Read-State VPNServices { Get-Service | Where-Object { ($_.Name + ' ' + $_.DisplayName) -match 'Tailscale|Cisco|AnyConnect|WireGuard|OpenVPN|Mihomo|Clash|UU|Hyper-V|VBox|VMware' } | Select-Object Name, DisplayName, Status, StartType })
$sleep = @(Read-State Power { & powercfg.exe /query SCHEME_CURRENT SUB_SLEEP; if ($LASTEXITCODE -ne 0) { throw 'powercfg failed' } })
$platforms = @('C:\Program Files\Oracle\VirtualBox\VBoxManage.exe','C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe') | Where-Object { Test-Path -LiteralPath $_ }
$snapshot = [ordered]@{ SchemaVersion=1; CapturedAt=(Get-Date -Format o); OS=$os; CPU=$cpu; Computer=$computer; Adapters=$adapters; Interfaces=$interfaces; Addresses=$addresses; Routes=$routes; DNS=$dns; DNSMode=$dnsMode; DHCP=$dhcp; Features=$features; Switches=$switches; VMs=$vms; Bindings=$bindings; Firewall=$firewall; FirewallRules=$firewallRules; Services=$services; Sleep=$sleep; OtherPlatforms=@($platforms); Warnings=@($warnings) }
$snapshot | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $target 'snapshot.json') -Encoding UTF8
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'restore-host-network.ps1') -Destination $target
$wired = @($adapters | Where-Object { $_.HardwareInterface -and $_.Status -eq 'Up' -and $_.PhysicalMediaType -match '802.3' })
$summary = [ordered]@{ SnapshotDirectory=$target; OS=$os; HypervisorPresent=$computer.HypervisorPresent; ActiveWiredAdapterCount=$wired.Count; VirtualizationFirmwareEnabled=@($cpu | ForEach-Object {$_.VirtualizationFirmwareEnabled}); Warnings=@($warnings); Verdict='PREVIEW ONLY: physical bridge, DHCP authority, address availability, IPv6 and client traffic require isolated validation. No network changes made.' }
$summary | ConvertTo-Json -Depth 5
