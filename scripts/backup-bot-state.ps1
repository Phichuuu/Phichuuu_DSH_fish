# Snapshot the bot's "soul": memory, persona card, and config.
# Why: 2026-10-27 a series of session resets wiped social-v2.json (topics +
# impressions) and there was no backup. This makes that impossible to repeat.
# ASCII only: Windows PowerShell 5.1 reads .ps1 as ANSI.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File backup-bot-state.ps1
#   ... -Force     # snapshot even when nothing changed since last time

param([switch]$Force)

$ErrorActionPreference = 'SilentlyContinue'

$DestRoot = 'F:\qq-bridge\backups'
$StateFile = Join-Path $DestRoot 'last-hash.txt'
$Keep = 120

# file -> subfolder inside the snapshot
$Items = @(
    @{ Path = 'F:\qq-bridge\state\social-v2.json';            Dir = 'state' },
    @{ Path = 'F:\qq-bridge\state\sessions.json';             Dir = 'state' },
    @{ Path = 'F:\qq-bridge\state\stickers.json';             Dir = 'state' },
    @{ Path = 'F:\qq-bridge\config.json';                     Dir = 'config' },
    @{ Path = '$env:USERPROFILE\.dsh\memory\shared.md';         Dir = 'memory' },
    @{ Path = '$env:USERPROFILE\.dsh\memory\current-role.json'; Dir = 'memory' }
)

function Write-Log([string]$m) {
    $log = Join-Path $DestRoot 'backup.log'
    Add-Content -Path $log -Value ('[' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '] ' + $m) -Encoding UTF8
}

try {
    if (-not (Test-Path $DestRoot)) { New-Item -ItemType Directory -Force -Path $DestRoot | Out-Null }

    # 1) hash everything that matters; skip if unchanged (unless -Force)
    $sb = New-Object System.Text.StringBuilder
    foreach ($item in $Items) {
        if (Test-Path $item.Path) {
            $h = (Get-FileHash -LiteralPath $item.Path -Algorithm SHA256).Hash
            [void]$sb.Append((Split-Path $item.Path -Leaf) + ':' + $h + ';')
        }
    }
    # diary folder: hash the sorted file list + sizes
    $diary = '$env:USERPROFILE\.dsh\memory\diary'
    if (Test-Path $diary) {
        Get-ChildItem $diary -File | Sort-Object Name | ForEach-Object {
            [void]$sb.Append($_.Name + ':' + $_.Length + ';')
        }
    }

    $hash = [System.BitConverter]::ToString(
        [System.Security.Cryptography.SHA256]::Create().ComputeHash(
            [System.Text.Encoding]::UTF8.GetBytes($sb.ToString())
        )
    ).Replace('-', '')

    if (-not $Force -and (Test-Path $StateFile)) {
        $prev = (Get-Content $StateFile -Raw).Trim()
        if ($prev -eq $hash) {
            exit 0   # nothing changed, stay quiet
        }
    }

    # 2) snapshot
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $dest = Join-Path $DestRoot $stamp
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $copied = 0
    foreach ($item in $Items) {
        if (Test-Path $item.Path) {
            $target = Join-Path $dest $item.Dir
            if (-not (Test-Path $target)) { New-Item -ItemType Directory -Force -Path $target | Out-Null }
            Copy-Item -LiteralPath $item.Path -Destination $target -Force
            $copied++
        }
    }
    # roles/*.md: 人格卡文件名是中文，在 $Items 里硬编码会被 PowerShell 5.1 按 ANSI
    # 读坏成乱码路径 —— 所以整个目录按通配符拷
    $rolesDir = 'F:\qq-bridge\roles'
    if (Test-Path $rolesDir) {
        $target = Join-Path $dest 'roles'
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Copy-Item "$rolesDir\*.md" -Destination $target -Force -ErrorAction SilentlyContinue
        $copied++
    }
    if (Test-Path $diary) {
        $target = Join-Path $dest 'diary'
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Copy-Item "$diary\*" -Destination $target -Recurse -Force -ErrorAction SilentlyContinue
    }

    Set-Content -Path $StateFile -Value $hash -Encoding UTF8
    Write-Log ("snapshot " + $stamp + " files=" + $copied)

    # 3) retention
    $all = Get-ChildItem $DestRoot -Directory | Sort-Object Name -Descending
    if ($all.Count -gt $Keep) {
        $all | Select-Object -Skip $Keep | ForEach-Object {
            Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
        Write-Log ('pruned to ' + $Keep + ' snapshots')
    }

    exit 0
} catch {
    Write-Log ('error: ' + $_.Exception.Message)
    exit 0
}
