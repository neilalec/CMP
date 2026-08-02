param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $Force) {
    $answer = Read-Host "Promote the current workspace source to the public stable stack? Type PROMOTE to continue"
    if ($answer -ne "PROMOTE") {
        Write-Host "Promotion cancelled."
        exit 1
    }
}

$env:CMP_DEV_MODE = "1"
$env:DATABASE_PATH = Join-Path $root "backend\promote-check.db"
try {
    & backend\venv\Scripts\python.exe -m pytest backend\tests\unit\test_live_roll.py backend\tests\unit\test_bridge.py -q
}
finally {
    Remove-Item -Force backend\promote-check.db -ErrorAction SilentlyContinue
    Remove-Item -Force backend\promote-check.db-journal -ErrorAction SilentlyContinue
    Remove-Item Env:\CMP_DEV_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:\DATABASE_PATH -ErrorAction SilentlyContinue
}

Push-Location frontend
try {
    npm run build
}
finally {
    Pop-Location
}

docker compose build backend frontend squadjs
docker compose up -d backend frontend squadjs caddy
docker compose ps

Write-Host ""
Write-Host "Current workspace source has been promoted to the public stable stack."
