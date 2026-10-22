# Creates an OFF VM only. Network takeover is deliberately not implemented here.
[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_-]{1,48}$')][string]$Name,
    [Parameter(Mandatory=$true)][string]$ExternalSwitch,
    [Parameter(Mandatory=$true)][string]$IsoPath,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$IsoSha256,
    [Parameter(Mandatory=$true)][string]$VmDirectory,
    [ValidateRange(2,16)][int]$MemoryGB=4,
    [ValidateRange(20,256)][int]$DiskGB=32
)
$ErrorActionPreference='Stop'
if (-not (Get-Command Get-VM -ErrorAction SilentlyContinue)) { throw 'Hyper-V unavailable. Enable it manually only after reviewing restart/network risks.' }
$iso=(Resolve-Path -LiteralPath $IsoPath).Path
if ((Get-FileHash -LiteralPath $iso -Algorithm SHA256).Hash -ne $IsoSha256) { throw 'ISO SHA256 mismatch. Use the Linux vendor published checksum.' }
$switch=Get-VMSwitch -Name $ExternalSwitch -ErrorAction Stop
if ($switch.SwitchType -ne 'External') { throw 'An existing wired External switch is required; Default/NAT/Internal is not a LAN gateway.' }
$physical=@(Get-NetAdapter -Physical | Where-Object InterfaceDescription -eq $switch.NetAdapterInterfaceDescription)
if ($physical.Count -ne 1 -or $physical[0].Status -ne 'Up' -or $physical[0].NdisPhysicalMedium -notin @(14,'802.3')) { throw 'Cannot verify a single active wired Ethernet uplink. Wi-Fi/teaming/unknown uplinks need manual validation.' }
$existing=Get-VM -Name $Name -ErrorAction SilentlyContinue
if ($existing) { throw 'VM already exists; refusing to alter it. Inspect existing settings manually.' }
$directory=[IO.Path]::GetFullPath($VmDirectory)
if (Test-Path -LiteralPath $directory) { throw 'Use a new VM directory; existing data will not be overwritten.' }
if ($PSCmdlet.ShouldProcess($Name,'Create OFF Linux VM on existing wired switch and permit its macvlan source MACs (no host switch/binding changes)')) {
    New-Item -ItemType Directory -Path $directory | Out-Null
    New-VM -Name $Name -Generation 2 -MemoryStartupBytes ($MemoryGB*1GB) -NewVHDPath (Join-Path $directory "$Name.vhdx") -NewVHDSizeBytes ($DiskGB*1GB) -Path $directory -SwitchName $ExternalSwitch | Out-Null
    Set-VM -Name $Name -AutomaticStartAction Nothing -AutomaticStopAction ShutDown
    Set-VMProcessor -VMName $Name -Count 2
    Set-VMFirmware -VMName $Name -EnableSecureBoot On -SecureBootTemplate MicrosoftUEFICertificateAuthority
    Add-VMDvdDrive -VMName $Name -Path $iso
    Set-VMFirmware -VMName $Name -FirstBootDevice (Get-VMDvdDrive -VMName $Name)
    Set-VMNetworkAdapter -VMName $Name -MacAddressSpoofing On
    Write-Output 'VM created OFF. Install Linux via VM console; verify multiple-MAC LAN reachability before any client changes. DHCP remains unconfigured.'
}
