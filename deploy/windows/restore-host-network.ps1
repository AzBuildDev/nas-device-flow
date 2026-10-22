# Offline, opt-in recovery of ONE original Windows IPv4 interface.
# Default invocation validates evidence and prints a plan only.
[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param([string]$Snapshot, [string]$InterfaceGuid, [switch]$Apply)
$ErrorActionPreference='Stop'
if (-not $Snapshot) { $Snapshot = Join-Path $PSScriptRoot 'snapshot.json' }
$state = Get-Content -LiteralPath $Snapshot -Raw | ConvertFrom-Json
if ($state.SchemaVersion -ne 1) { throw 'Unsupported snapshot schema.' }
if (-not $InterfaceGuid) {
    $state.Adapters | Where-Object HardwareInterface | Select-Object Name, InterfaceGuid, Status
    Write-Output 'Plan only. Select one original interface GUID, inspect private snapshot, then rerun with -InterfaceGuid. No changes made.'
    return
}
$parsedGuid=[guid]$InterfaceGuid
$saved=@($state.Adapters | Where-Object { [guid]$_.InterfaceGuid -eq $parsedGuid })
$current=@(Get-NetAdapter -IncludeHidden | Where-Object { [guid]$_.InterfaceGuid -eq $parsedGuid })
if ($saved.Count -ne 1 -or $current.Count -ne 1) { throw 'Original adapter missing or ambiguous. Do not substitute a similarly named adapter; use manual recovery.' }
$oldIndex=$saved[0].ifIndex
$index=$current[0].ifIndex
$ipInterface=@($state.Interfaces | Where-Object { $_.InterfaceIndex -eq $oldIndex -and $_.AddressFamily -eq 2 })
if ($ipInterface.Count -ne 1) { throw 'Snapshot has no unique IPv4 interface state.' }
$addresses=@($state.Addresses | Where-Object { $_.InterfaceIndex -eq $oldIndex -and $_.AddressFamily -eq 2 -and $_.PrefixOrigin -eq 1 })
$gateways=@($state.Routes | Where-Object { $_.InterfaceIndex -eq $oldIndex -and $_.DestinationPrefix -eq '0.0.0.0/0' })
$dns=@($state.DNS | Where-Object { $_.InterfaceIndex -eq $oldIndex -and $_.AddressFamily -eq 2 })
$mode=@($state.DNSMode | Where-Object { [guid]$_.InterfaceGuid -eq $parsedGuid })
if ($mode.Count -ne 1) { throw 'DNS origin missing; refusing to guess static versus DHCP DNS.' }
foreach ($entry in $addresses) { [void][Net.IPAddress]::Parse($entry.IPAddress); if ($entry.PrefixLength -lt 1 -or $entry.PrefixLength -gt 32) { throw 'Invalid prefix.' } }
foreach ($entry in $gateways) { [void][Net.IPAddress]::Parse($entry.NextHop) }
foreach ($server in @($dns.ServerAddresses)) { [void][Net.IPAddress]::Parse($server) }
$dhcpEnabled=($ipInterface[0].Dhcp -eq 1)
if (-not $dhcpEnabled -and $addresses.Count -eq 0) { throw 'No saved manual IPv4 address; manual recovery required.' }
[pscustomobject]@{ Adapter=$current[0].Name; DHCP=$dhcpEnabled; SavedStaticAddressCount=$addresses.Count; SavedDefaultRouteCount=$gateways.Count; StaticDNS=$mode[0].StaticIPv4Dns; ApplyRequested=[bool]$Apply }
if (-not $Apply) { Write-Output 'Validated plan only; no changes made. -Apply prompts before restoring this one interface.'; return }
$identity=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $identity.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Apply requires a local elevated PowerShell session.' }
if (-not $PSCmdlet.ShouldProcess($current[0].Name, 'Restore saved IPv4 addressing, default gateway and DNS; connectivity may stop')) { return }
# Never delete adapters, virtual switches, firewall rules or other interfaces.
if ($dhcpEnabled) {
    Set-NetIPInterface -InterfaceIndex $index -AddressFamily IPv4 -Dhcp Enabled
    Get-NetRoute -InterfaceIndex $index -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Where-Object Protocol -eq NetMgmt | Remove-NetRoute -Confirm:$false
    Get-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 | Where-Object PrefixOrigin -eq Manual | Remove-NetIPAddress -Confirm:$false
} else {
    Set-NetIPInterface -InterfaceIndex $index -AddressFamily IPv4 -Dhcp Disabled
    foreach ($entry in $addresses) {
        if (-not (Get-NetIPAddress -InterfaceIndex $index -IPAddress $entry.IPAddress -ErrorAction SilentlyContinue)) {
            New-NetIPAddress -InterfaceIndex $index -IPAddress $entry.IPAddress -PrefixLength $entry.PrefixLength -SkipAsSource ([bool]$entry.SkipAsSource) | Out-Null
        } else {
            Set-NetIPAddress -InterfaceIndex $index -IPAddress $entry.IPAddress -PrefixLength $entry.PrefixLength -SkipAsSource ([bool]$entry.SkipAsSource)
        }
    }
    foreach ($entry in $gateways) {
        if (-not (Get-NetRoute -InterfaceIndex $index -DestinationPrefix '0.0.0.0/0' -NextHop $entry.NextHop -ErrorAction SilentlyContinue)) {
            New-NetRoute -InterfaceIndex $index -DestinationPrefix '0.0.0.0/0' -NextHop $entry.NextHop -RouteMetric $entry.RouteMetric | Out-Null
        } else {
            Set-NetRoute -InterfaceIndex $index -DestinationPrefix '0.0.0.0/0' -NextHop $entry.NextHop -RouteMetric $entry.RouteMetric
        }
    }
    # Remove only IPv4 manual state absent from this adapter's saved snapshot.
    Get-NetRoute -InterfaceIndex $index -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Where-Object { $_.Protocol -eq 'NetMgmt' -and $_.NextHop -notin @($gateways.NextHop) } | Remove-NetRoute -Confirm:$false
    Get-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 | Where-Object { $_.PrefixOrigin -eq 'Manual' -and $_.IPAddress -notin @($addresses.IPAddress) } | Remove-NetIPAddress -Confirm:$false
}
if ($mode[0].StaticIPv4Dns) {
    Get-DnsClientServerAddress -InterfaceIndex $index -AddressFamily IPv4 | Set-DnsClientServerAddress -ServerAddresses @($dns.ServerAddresses)
} else { Get-DnsClientServerAddress -InterfaceIndex $index -AddressFamily IPv4 | Set-DnsClientServerAddress -ResetServerAddresses }
Write-Output 'Restore commands completed. Verify gateway, DNS and domestic access locally; this does not prove Internet recovery. DHCP renewal is per-adapter and must be done manually if required. IPv6, switches, firewall, VPN and power settings are unchanged.'
