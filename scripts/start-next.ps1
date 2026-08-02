$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

docker compose -f docker-compose.next.yml -p cmp_next up -d --build
docker compose -f docker-compose.next.yml -p cmp_next ps

Write-Host ""
Write-Host "Next candidate is running at http://localhost:8081"
Write-Host "Next backend health is at http://localhost:5100/health"
Write-Host "This stack uses its own database and does not run SquadJS/RCON control."
