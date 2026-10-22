# Standalone PowerShell regression: every network read/write command is mocked.
$ErrorActionPreference='Stop'
$global:ndfTestMutations=New-Object 'System.Collections.Generic.List[string]'
$fixtureGuid='11111111-1111-1111-1111-111111111111'
function Get-NetAdapter { param([switch]$IncludeHidden) [pscustomobject]@{InterfaceGuid=$fixtureGuid;ifIndex=7;Name='isolated-mock'} }
function Get-NetIPAddress { [CmdletBinding()]param($InterfaceIndex,$IPAddress,$AddressFamily) if(-not $IPAddress){[pscustomobject]@{IPAddress='192.0.2.99';PrefixOrigin='Manual'}} }
function Get-NetRoute { [CmdletBinding()]param($InterfaceIndex,$DestinationPrefix,$NextHop) if(-not $NextHop){[pscustomobject]@{NextHop='192.0.2.99';Protocol='NetMgmt'}} }
function Get-DnsClientServerAddress { param($InterfaceIndex,$AddressFamily) [pscustomobject]@{InterfaceIndex=$InterfaceIndex;AddressFamily=$AddressFamily} }
function Set-NetIPInterface { param($InterfaceIndex,$AddressFamily,$Dhcp) $global:ndfTestMutations.Add("dhcp:$Dhcp") }
function New-NetIPAddress { param($InterfaceIndex,$IPAddress,$PrefixLength,$SkipAsSource) $global:ndfTestMutations.Add("address:$IPAddress/$PrefixLength") }
function Set-NetIPAddress { param($InterfaceIndex,$IPAddress,$PrefixLength,$SkipAsSource) $global:ndfTestMutations.Add("set-address:$IPAddress/$PrefixLength") }
function New-NetRoute { param($InterfaceIndex,$DestinationPrefix,$NextHop,$RouteMetric) $global:ndfTestMutations.Add("gateway:$NextHop") }
function Set-NetRoute { param($InterfaceIndex,$DestinationPrefix,$NextHop,$RouteMetric) $global:ndfTestMutations.Add("set-gateway:$NextHop") }
function Remove-NetRoute { [CmdletBinding(SupportsShouldProcess=$true)]param([Parameter(ValueFromPipeline=$true)]$InputObject) process {$global:ndfTestMutations.Add('remove-drift-route')} }
function Remove-NetIPAddress { [CmdletBinding(SupportsShouldProcess=$true)]param([Parameter(ValueFromPipeline=$true)]$InputObject) process {$global:ndfTestMutations.Add('remove-drift-address')} }
function Set-DnsClientServerAddress { param([Parameter(ValueFromPipeline=$true)]$InputObject,$ServerAddresses,[switch]$ResetServerAddresses) process {$global:ndfTestMutations.Add("dns:$($ServerAddresses -join ',')") } }
$fixture=@{SchemaVersion=1;Adapters=@(@{InterfaceGuid=$fixtureGuid;ifIndex=7;HardwareInterface=$true});Interfaces=@(@{InterfaceIndex=7;AddressFamily=2;Dhcp=0});Addresses=@(@{InterfaceIndex=7;AddressFamily=2;PrefixOrigin=1;IPAddress='192.0.2.10';PrefixLength=24;SkipAsSource=$false});Routes=@(@{InterfaceIndex=7;DestinationPrefix='0.0.0.0/0';NextHop='192.0.2.1';RouteMetric=10});DNS=@(@{InterfaceIndex=7;AddressFamily=2;ServerAddresses=@('192.0.2.53')});DNSMode=@(@{InterfaceGuid=$fixtureGuid;StaticIPv4Dns=$true})}
$temp=Join-Path ([IO.Path]::GetTempPath()) ('ndf-restore-test-'+[guid]::NewGuid().ToString('N')+'.json')
$restore=Join-Path $PSScriptRoot '../deploy/windows/restore-host-network.ps1'
try {
    $fixture | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temp -Encoding UTF8
    & $restore -Snapshot $temp -InterfaceGuid $fixtureGuid | Out-Null
    if($global:ndfTestMutations.Count){throw 'Plan mutated network'}
    $refused=$false
    try { & $restore -Snapshot $temp -InterfaceGuid '22222222-2222-2222-2222-222222222222' | Out-Null } catch { $refused=$true }
    if(-not $refused -or $global:ndfTestMutations.Count){throw 'Wrong GUID did not safely refuse'}
    & $restore -Snapshot $temp -InterfaceGuid $fixtureGuid -Apply -WhatIf | Out-Null
    if($global:ndfTestMutations.Count){throw 'WhatIf mutated network'}
    & $restore -Snapshot $temp -InterfaceGuid $fixtureGuid -Apply -Confirm:$false | Out-Null
    foreach($expected in @('dhcp:Disabled','address:192.0.2.10/24','gateway:192.0.2.1','dns:192.0.2.53','remove-drift-route','remove-drift-address')) {
        if($expected -notin $global:ndfTestMutations){throw "Missing mocked recovery operation: $expected"}
    }
    'PASS: plan is inert; wrong GUID refuses; WhatIf is inert; mocked static address, gateway and DNS restore removes drift. No live network commands executed.'
} finally { Remove-Item -LiteralPath $temp -ErrorAction SilentlyContinue }
