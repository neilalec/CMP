param(
    [string]$OutputDir = ".\backups"
)

$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $OutputDir "cmp-backup-$timestamp"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

docker compose cp backend:/app/data/app.db (Join-Path $backupRoot "app.db")

if (Test-Path ".\backend\.env") {
    Copy-Item ".\backend\.env" (Join-Path $backupRoot "backend.env")
}

if (Test-Path ".\squadjs\config.json") {
    Copy-Item ".\squadjs\config.json" (Join-Path $backupRoot "squadjs-config.json")
}

if (Test-Path ".\deploy\Caddyfile") {
    Copy-Item ".\deploy\Caddyfile" (Join-Path $backupRoot "Caddyfile")
}

Compress-Archive -Path (Join-Path $backupRoot "*") -DestinationPath "$backupRoot.zip" -Force
Remove-Item -Recurse -Force $backupRoot

Write-Host "Backup created: $backupRoot.zip"
