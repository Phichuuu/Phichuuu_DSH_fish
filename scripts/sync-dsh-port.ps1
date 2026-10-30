# Keep qq-bridge's dsh.baseUrl in sync with the DSH desktop app's web port.
#
# Why: the DSH desktop app picks a random web port on every launch (50995, 63457 ...),
# while qq-bridge config.json stores a fixed dsh.baseUrl. After a DSH restart the
# bridge silently loses the DSH connection until the URL is updated.
#
# How the web port is identified: the DSH main process listens on two ports; the web
# one answers "/" with 401 (auth required), the other one (host apiproxy) with 404.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File sync-dsh-port.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File sync-dsh-port.ps1 -RestartIfChanged
#
# ASCII only on purpose: Windows PowerShell 5.1 reads .ps1 as ANSI, so UTF-8 comments
# and messages break parsing.

param(
    [switch]$RestartIfChanged
)

$ErrorActionPreference = 'SilentlyContinue'

$ConfigPath = 'F:\qq-bridge\config.json'
$BridgeVbs  = '(Split-Path $PSScriptRoot -Parent)\start-bridge-hidden.vbs'
$LogPath    = '$env:USERPROFILE\.dsh\memory\dsh-port.log'

function Write-SyncLog([string]$msg) {
    $dir = Split-Path $LogPath -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $line = '[' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '] ' + $msg
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
}

try {
    $dshPids = @()
    foreach ($p in Get-Process 'DeepSeek Harness' -ErrorAction SilentlyContinue) { $dshPids += $p.Id }
    if (-not $dshPids.Count) {
        Write-SyncLog 'DSH not running, skip'
        exit 0
    }

    $ports = @()
    foreach ($c in Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue) {
        if ($dshPids -contains $c.OwningProcess) { $ports += [int]$c.LocalPort }
    }
    $ports = $ports | Sort-Object -Unique
    if (-not $ports.Count) {
        Write-SyncLog 'DSH has no listening port yet'
        exit 0
    }

    $webPort = $null
    foreach ($p in $ports) {
        try {
            Invoke-WebRequest ('http://127.0.0.1:' + $p + '/') -TimeoutSec 4 -UseBasicParsing | Out-Null
        } catch {
            $code = $null
            if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
            if ($code -eq 401) { $webPort = $p; break }
        }
    }
    if (-not $webPort) {
        Write-SyncLog ('no web port among candidates: ' + ($ports -join ','))
        exit 0
    }

    $raw = Get-Content $ConfigPath -Raw -Encoding UTF8
    $cfg = $raw | ConvertFrom-Json
    $current = [string]$cfg.dsh.baseUrl
    $wanted = 'http://127.0.0.1:' + $webPort

    if ($current -eq $wanted) {
        Write-SyncLog ('port unchanged: ' + $wanted)
        exit 0
    }

    $cfg.dsh.baseUrl = $wanted
    $json = $cfg | ConvertTo-Json -Depth 20
    [System.IO.File]::WriteAllText($ConfigPath, $json, [System.Text.UTF8Encoding]::new($false))
    Write-SyncLog ('port changed: ' + $current + ' -> ' + $wanted + ' (config.json updated)')

    if ($RestartIfChanged) {
        $bridge = Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
            Where-Object { $_.CommandLine -match 'bridge\.js' }
        foreach ($b in $bridge) { Stop-Process -Id $b.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 3
        Start-Process -FilePath 'wscript.exe' -ArgumentList @('//nologo', $BridgeVbs) -WindowStyle Hidden
        Write-SyncLog 'bridge restarted'
    }

    exit 0
} catch {
    Write-SyncLog ('error: ' + $_.Exception.Message)
    exit 0
}
