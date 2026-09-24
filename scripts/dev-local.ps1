param(
    [ValidateSet("local", "wardogs", "squad")]
    [string]$DevelopmentTarget = "local",
    [string]$SquadJsConfigPath = "config.dev-local.json"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$squadjs = Join-Path $root "squadjs"

function Set-CmpUtf8Output {
    $utf8 = [System.Text.UTF8Encoding]::new()
    [Console]::OutputEncoding = $utf8
    $script:OutputEncoding = $utf8
}

Set-CmpUtf8Output

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Resolve-CmpPython {
    if (-not (Test-Command "py")) {
        throw "The Windows Python launcher (py) was not found. Install Python 3.12 and ensure py.exe is available on PATH."
    }

    $pythonOutput = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
    $pythonExitCode = $LASTEXITCODE
    $pythonPath = ($pythonOutput | Select-Object -First 1).Trim()
    if ($pythonExitCode -ne 0 -or -not $pythonPath -or -not (Test-Path -LiteralPath $pythonPath)) {
        throw "Python 3.12 was not found. Install it, then run: py -3.12 -m pip install -r backend\\requirements.txt"
    }

    return $pythonPath
}

function Start-CmpJob($name, $workingDirectory, $scriptBlock) {
    Write-Host "Starting $name..." -ForegroundColor Cyan
    Start-Job -Name $name -ArgumentList $workingDirectory -ScriptBlock $scriptBlock
}

function Test-PortAvailable($port) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return -not $listener
}

if (-not (Test-Command "npm")) {
    throw "npm was not found on PATH."
}

if (-not (Test-Command "node")) {
    throw "node was not found on PATH."
}

$pythonCommand = Resolve-CmpPython

$startSquadJs = $false
if ($DevelopmentTarget -eq "squad") {
    $startSquadJs = $env:CMP_START_SQUADJS -ne "0"
} elseif ($DevelopmentTarget -eq "local") {
    $startSquadJs = $env:CMP_START_SQUADJS -eq "1"
}

$requiredPorts = if ($DevelopmentTarget -eq "squad" -and $startSquadJs) { @(5000, 5173, 3001) } else { @(5000, 5173) }
foreach ($port in $requiredPorts) {
    if (-not (Test-PortAvailable $port)) {
        throw "CMP local development port $port is already in use. Stop the existing process before starting."
    }
}

$jobs = @()
$frontendUrl = "http://127.0.0.1:5173"
$backendUrl = "http://127.0.0.1:5000"
function Test-TcpReady($port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $result = $client.BeginConnect("127.0.0.1", $port, $null, $null)
        return $result.AsyncWaitHandle.WaitOne(500) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Test-FrontendReady {
    try {
        $response = Invoke-WebRequest -Uri "$frontendUrl/auth" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

try {
    if ($DevelopmentTarget -eq "wardogs") {
        Write-Host "CMP WARDOGS local development starting" -ForegroundColor Green
        Write-Host "Target: WARDOGS | Dev harness: enabled | WARDOGS observation: enabled | Squad integration: disabled"
        Write-Host "Frontend: $frontendUrl | Backend: $backendUrl"
    }
    if ($DevelopmentTarget -eq "squad") {
        Write-Host "CMP Squad local development starting" -ForegroundColor Green
        Write-Host "Target: SQUAD | Legacy participant UI: enabled | SquadJS: $(if ($startSquadJs) { 'enabled' } else { 'disabled' })"
        Write-Host "Frontend: $frontendUrl | Backend: $backendUrl"
    }

    $jobs += Start-CmpJob "backend" $backend {
        param($workingDirectory)
        function Set-CmpUtf8Output {
            $utf8 = [System.Text.UTF8Encoding]::new()
            [Console]::OutputEncoding = $utf8
            $script:OutputEncoding = $utf8
        }
        Set-CmpUtf8Output
        Set-Location $workingDirectory
        $env:CMP_DEV_MODE = "1"
        $env:CMP_DEV_GAME = $using:DevelopmentTarget
        $env:CMP_SQUADJS_ENABLED = if ($using:startSquadJs) { "1" } else { "0" }
        $env:DEV_SOLO_ELO_SMOKE_ENABLED = if ($using:DevelopmentTarget -eq "wardogs") { "0" } else { "1" }
        if ($using:DevelopmentTarget -ne "wardogs") {
            $env:DEV_SOLO_ELO_SMOKE_USERNAME = "neil"
        }
        $env:FRONTEND_ORIGINS = "http://127.0.0.1:5173,http://localhost:5173,http://localhost:5174,http://127.0.0.1:5174"
        $env:BACKEND_PUBLIC_URL = "http://127.0.0.1:5000"
        $env:BACKEND_HOST = "127.0.0.1"
        $env:BACKEND_PORT = "5000"
        $env:DATABASE_PATH = Join-Path $workingDirectory "app.db"
        $env:SQUADJS_BRIDGE_URL = "http://127.0.0.1:3001"
        if ($using:DevelopmentTarget -eq "wardogs") {
            $env:WARDOGS_POLL_INTERVAL_SECONDS = "5"
        }
        & $using:pythonCommand app.py
    }

    $jobs += Start-CmpJob "frontend" $frontend {
        param($workingDirectory)
        function Set-CmpUtf8Output {
            $utf8 = [System.Text.UTF8Encoding]::new()
            [Console]::OutputEncoding = $utf8
            $script:OutputEncoding = $utf8
        }
        Set-CmpUtf8Output
        Set-Location $workingDirectory
        $env:VITE_CMP_DEV_TARGET = $using:DevelopmentTarget
        npm run dev
    }

    if ($startSquadJs) {
        $jobs += Start-CmpJob "squadjs" $squadjs {
            param($workingDirectory)
            function Set-CmpUtf8Output {
                $utf8 = [System.Text.UTF8Encoding]::new()
                [Console]::OutputEncoding = $utf8
                $script:OutputEncoding = $utf8
            }
            Set-CmpUtf8Output
            Set-Location $workingDirectory
            $env:CMP_DEV_MODE = "1"
            node index.js $using:SquadJsConfigPath
        }
    }

    Write-Host ""
    if ($DevelopmentTarget -eq "local") {
        Write-Host "CMP local dev is starting. Frontend: $frontendUrl | Backend: $backendUrl" -ForegroundColor Green
    }
    if ($DevelopmentTarget -eq "squad" -and -not $startSquadJs) {
        Write-Host "Squad UI is available for comparison. SquadJS is disabled by CMP_START_SQUADJS=0." -ForegroundColor Yellow
    }
    if (-not $startSquadJs -and $DevelopmentTarget -eq "local") {
        Write-Host "SquadJS is disabled; set CMP_START_SQUADJS=1 to include it for Squad testing." -ForegroundColor Yellow
    }
    if ($DevelopmentTarget -eq "squad" -and $startSquadJs) {
        Write-Host "SquadJS config: $SquadJsConfigPath" -ForegroundColor Cyan
        if ($SquadJsConfigPath -eq "config.dev-local.json") {
            Write-Host "Using the loopback-only config; it will not connect to a game server." -ForegroundColor Cyan
        } else {
            Write-Host "This explicitly selected config may connect to its configured game server." -ForegroundColor Yellow
        }
    }
    Write-Host "Waiting for backend and frontend readiness..." -ForegroundColor Cyan

    $readyDeadline = (Get-Date).AddSeconds(90)
    $backendReady = $false
    $frontendReady = $false
    $squadJsReady = -not $startSquadJs
    while ((Get-Date) -lt $readyDeadline -and (-not $backendReady -or -not $frontendReady -or -not $squadJsReady)) {
        foreach ($job in $jobs) {
            if ($job.State -in @("Failed", "Stopped", "Completed")) {
                $jobOutput = Receive-Job -Job $job -ErrorAction SilentlyContinue | Out-String
                throw "$($job.Name) stopped before startup was ready. $jobOutput"
            }
        }
        $backendReady = Test-TcpReady 5000
        $frontendReady = (Test-TcpReady 5173) -and (Test-FrontendReady)
        if ($startSquadJs) { $squadJsReady = Test-TcpReady 3001 }
        if (-not $backendReady -or -not $frontendReady -or -not $squadJsReady) { Start-Sleep -Milliseconds 500 }
    }
    if (-not $backendReady -or -not $frontendReady -or -not $squadJsReady) {
        throw "CMP startup readiness timed out. Backend ready: $backendReady; frontend /auth ready: $frontendReady; SquadJS bridge ready: $squadJsReady."
    }

    Write-Host "CMP backend is listening at $backendUrl" -ForegroundColor Green
    Write-Host "Frontend /auth is responding at $frontendUrl/auth" -ForegroundColor Green
    if ($startSquadJs) { Write-Host "SquadJS bridge is listening at http://127.0.0.1:3001" -ForegroundColor Green }
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
