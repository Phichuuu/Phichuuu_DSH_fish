# One-pass health check for the QQ bot stack, with optional self-repair.
# Called by watchdog-loop.cmd every few minutes and right after DSH starts.
# ASCII only: Windows PowerShell 5.1 reads .ps1 as ANSI, so any non-ASCII
# byte in a string literal can break the parser. Keep every message English.
#
#   -Repair   restart the stack (start-bots.cmd is idempotent) when anything is down
#   -Quiet    only write to the log, print nothing

param([switch]$Repair, [switch]$Quiet)

$ErrorActionPreference = 'SilentlyContinue'

$StateDir = 'F:\qq-bridge\state'
$HealthFile = Join-Path $StateDir 'health.json'
$HealthLog = Join-Path $StateDir 'health.log'
$BootScript = '(Split-Path $PSScriptRoot -Parent)\start-bots.cmd'
$ConfigFile = 'F:\qq-bridge\config.json'

function Write-HealthLog([string]$m) {
    if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Force -Path $StateDir | Out-Null }
    Add-Content -Path $HealthLog -Value ('[' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '] ' + $m) -Encoding UTF8
}

function Test-Port([int]$port) {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($c) { return 1 } else { return 0 }
}

function Get-DshPortFromConfig {
    try {
        $cfg = Get-Content $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $u = [string]$cfg.dsh.baseUrl
        if ($u -match ':(\d+)') { return [int]$Matches[1] }
    } catch { }
    return 0
}

function Find-DshPort {
    # DSH picks a random port each launch; the bridge config is kept in sync by
    # sync-dsh-port.ps1, so trust it but verify something actually listens.
    $p = Get-DshPortFromConfig
    if ($p -gt 0 -and (Test-Port $p) -eq 1) { return $p }
    return 0
}

$result = [ordered]@{}
$result.time = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

$dshPort = Find-DshPort
$result.dshPort = $dshPort
$result.dsh = ($dshPort -gt 0)

$result.qq = ((Get-Process QQ -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0)
$result.snowluma = ((Test-Port 5099) -eq 1)
$result.onebotHttp = ((Test-Port 3000) -eq 1)
$result.onebotWs = ((Test-Port 3001) -eq 1)
$result.console = ((Test-Port 3100) -eq 1)

$bridge = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'bridge\.js' })
$result.bridge = ($bridge.Count -ge 1)

$result.voiceMinimax = ((Test-Port 8851) -eq 1)
$result.voiceMimo = ((Test-Port 8850) -eq 1)
$result.voiceRvc = ((Test-Port 8848) -eq 1)

# Required for the bot to answer at all; voice is nice-to-have (falls back on failure).
$required = @('dsh', 'qq', 'snowluma', 'onebotHttp', 'onebotWs', 'console', 'bridge')
$missing = @()
foreach ($k in $required) {
    if (-not $result[$k]) { $missing += $k }
}
$result.ok = ($missing.Count -eq 0)
$result.missing = $missing

$result | ConvertTo-Json -Depth 4 | Set-Content -Path $HealthFile -Encoding UTF8

if ($result.ok) {
    Write-HealthLog ('ok dsh=' + $dshPort + ' voice=' + [int]$result.voiceMinimax + [int]$result.voiceMimo + [int]$result.voiceRvc)
    if (-not $Quiet) { Write-Output ('OK  dsh=' + $dshPort + '  qq/snowluma/onebot/bridge all up') }
} else {
    Write-HealthLog ('down missing=' + ($missing -join ',') + ' dsh=' + $dshPort)
    if (-not $Quiet) { Write-Output ('DOWN missing: ' + ($missing -join ', ')) }
    if ($Repair) {
        Write-HealthLog 'repair: running start-bots.cmd'
        if (-not $Quiet) { Write-Output '  -> restarting the whole stack' }
        Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c', "`"$BootScript`"") -WindowStyle Hidden
    }
}

exit 0
