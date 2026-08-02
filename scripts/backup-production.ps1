param(
    [string]$OutputDir = ".\backups"
)

$ErrorActionPreference = "Stop"

function Invoke-DockerCompose {
    param(
        [string[]]$Arguments
    )

    & docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $OutputDir "cmp-backup-$timestamp"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$containerBackupPath = "/app/data/app-backup-$timestamp.db"
$backupCommand = "import os, sqlite3; source = os.environ.get('DATABASE_PATH', '/app/data/app.db'); target = os.environ['CMP_BACKUP_TARGET']; source_conn = sqlite3.connect(source); target_conn = sqlite3.connect(target); source_conn.backup(target_conn); target_conn.close(); source_conn.close()"
try {
    Invoke-DockerCompose -Arguments @("exec", "-T", "-e", "CMP_BACKUP_TARGET=$containerBackupPath", "backend", "python", "-c", $backupCommand)
    Invoke-DockerCompose -Arguments @("cp", "backend:$containerBackupPath", (Join-Path $backupRoot "app.db"))
} finally {
    $cleanupCommand = "import os; path = os.environ['CMP_BACKUP_TARGET']; os.path.exists(path) and os.remove(path)"
    try {
        Invoke-DockerCompose -Arguments @("exec", "-T", "-e", "CMP_BACKUP_TARGET=$containerBackupPath", "backend", "python", "-c", $cleanupCommand) | Out-Null
    } catch {
        Write-Warning "Could not remove temporary container backup: $($_.Exception.Message)"
    }
}

if (Test-Path ".\.env") {
    Copy-Item ".\.env" (Join-Path $backupRoot "root.env")
}

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
