param(
    [Parameter(Mandatory = $true)]
    [string]$BackupZip,
    [switch]$RestoreConfig
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

if (-not (Test-Path $BackupZip)) {
    throw "Backup zip not found: $BackupZip"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$restoreRoot = Join-Path $env:TEMP "cmp-restore-$timestamp"
New-Item -ItemType Directory -Force -Path $restoreRoot | Out-Null

try {
    Expand-Archive -Path $BackupZip -DestinationPath $restoreRoot -Force
    $databaseBackup = Join-Path $restoreRoot "app.db"
    if (-not (Test-Path $databaseBackup)) {
        throw "Backup does not contain app.db"
    }

    Write-Host "Stopping CMP stack..."
    Invoke-DockerCompose -Arguments @("down")

    Write-Host "Creating backend container and data volume..."
    Invoke-DockerCompose -Arguments @("create", "backend")

    Write-Host "Restoring backend database..."
    Invoke-DockerCompose -Arguments @("cp", $databaseBackup, "backend:/app/data/app.db")

    if ($RestoreConfig) {
        $rootEnv = Join-Path $restoreRoot "root.env"
        $backendEnv = Join-Path $restoreRoot "backend.env"
        $squadjsConfig = Join-Path $restoreRoot "squadjs-config.json"
        $caddyFile = Join-Path $restoreRoot "Caddyfile"

        if (Test-Path $rootEnv) {
            Copy-Item $rootEnv ".\.env" -Force
        }
        if (Test-Path $backendEnv) {
            Copy-Item $backendEnv ".\backend\.env" -Force
        }
        if (Test-Path $squadjsConfig) {
            Copy-Item $squadjsConfig ".\squadjs\config.json" -Force
        }
        if (Test-Path $caddyFile) {
            Copy-Item $caddyFile ".\deploy\Caddyfile" -Force
        }
    }

    Write-Host "Starting CMP stack..."
    Invoke-DockerCompose -Arguments @("up", "-d", "--build")
    Write-Host "Restore complete. Check status with: docker compose ps"
} finally {
    if (Test-Path $restoreRoot) {
        Remove-Item -Recurse -Force $restoreRoot
    }
}
