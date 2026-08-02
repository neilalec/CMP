$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$squadjs = Join-Path $root "squadjs"

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Start-CmpJob($name, $workingDirectory, $scriptBlock) {
    Write-Host "Starting $name..." -ForegroundColor Cyan
    Start-Job -Name $name -ArgumentList $workingDirectory -ScriptBlock $scriptBlock
}

if (-not (Test-Command "npm")) {
    throw "npm was not found on PATH."
}

if (-not (Test-Command "node")) {
    throw "node was not found on PATH."
}

$pythonCommand = if (Test-Command "python") { "python" } elseif (Test-Command "py") { "py" } else { $null }
if (-not $pythonCommand) {
    throw "Neither python nor py was found on PATH."
}

$jobs = @()

try {
    $jobs += Start-CmpJob "backend" $backend {
        param($workingDirectory)
        Set-Location $workingDirectory
        $env:CMP_DEV_MODE = "1"
        $env:FRONTEND_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
        $env:BACKEND_PUBLIC_URL = "http://localhost:5000"
        $env:DATABASE_PATH = Join-Path $workingDirectory "app.db"
        $env:SQUADJS_BRIDGE_URL = "http://127.0.0.1:3001"
        & $using:pythonCommand app.py
    }

    $jobs += Start-CmpJob "frontend" $frontend {
        param($workingDirectory)
        Set-Location $workingDirectory
        npm run dev
    }

    $jobs += Start-CmpJob "squadjs" $squadjs {
        param($workingDirectory)
        Set-Location $workingDirectory
        node index.js
    }

    Write-Host ""
    Write-Host "CMP local dev is starting. Frontend should appear at http://localhost:5173" -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop all processes." -ForegroundColor Yellow
    Write-Host ""

    while ($true) {
        foreach ($job in $jobs) {
            $jobErrors = @()
            Receive-Job -Job $job -ErrorAction SilentlyContinue -ErrorVariable jobErrors | ForEach-Object {
                "[$($job.Name)] $_"
            }
            $jobErrors | ForEach-Object {
                "[$($job.Name)] $_"
            }

            if ($job.State -in @("Failed", "Stopped", "Completed")) {
                Write-Host "[$($job.Name)] exited with state $($job.State)." -ForegroundColor Yellow
                $finalErrors = @()
                Receive-Job -Job $job -ErrorAction SilentlyContinue -ErrorVariable finalErrors | ForEach-Object {
                    "[$($job.Name)] $_"
                }
                $finalErrors | ForEach-Object {
                    "[$($job.Name)] $_"
                }
                throw "$($job.Name) stopped."
            }
        }

        Start-Sleep -Milliseconds 500
    }
}
finally {
    Write-Host ""
    Write-Host "Stopping CMP local dev processes..." -ForegroundColor Yellow
    foreach ($job in $jobs) {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }
}
