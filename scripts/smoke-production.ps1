param(
    [string]$PublicUrl = "https://squadcm.duckdns.org",
    [switch]$RequireReady,
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"

$baseUrl = $PublicUrl.TrimEnd("/")
$results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param(
        [string]$Name,
        [ValidateSet("PASS", "WARN", "FAIL")]
        [string]$Status,
        [string]$Details
    )

    $results.Add([pscustomobject]@{
        Name = $Name
        Status = $Status
        Details = $Details
    }) | Out-Null
}

function Read-WebExceptionBody {
    param($Response)

    if (-not $Response) {
        return ""
    }

    $stream = $Response.GetResponseStream()
    if (-not $stream) {
        return ""
    }

    $reader = New-Object System.IO.StreamReader($stream)
    try {
        return $reader.ReadToEnd()
    } finally {
        $reader.Dispose()
    }
}

function Invoke-HttpProbe {
    param(
        [string]$Name,
        [string]$Url,
        [int[]]$AcceptStatus = @(200),
        [switch]$Json,
        [switch]$AllowDegraded
    )

    $statusCode = $null
    $content = ""

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15
        $statusCode = [int]$response.StatusCode
        $content = [string]$response.Content
    } catch {
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
            $content = Read-WebExceptionBody $_.Exception.Response
        } else {
            Add-Result $Name "FAIL" $_.Exception.Message
            return
        }
    }

    $details = "HTTP $statusCode"
    $jsonPayload = $null

    if ($Json -and $content) {
        try {
            $jsonPayload = $content | ConvertFrom-Json
            if ($jsonPayload.status) {
                $details = "$details, status=$($jsonPayload.status)"
            }
            if ($jsonPayload.database -and $jsonPayload.database.ok -ne $null) {
                $details = "$details, database=$($jsonPayload.database.ok)"
            }
            if ($jsonPayload.squadjsBridge -and $jsonPayload.squadjsBridge.ok -ne $null) {
                $details = "$details, bridge=$($jsonPayload.squadjsBridge.ok)"
            }
        } catch {
            Add-Result $Name "FAIL" "HTTP $statusCode but JSON parsing failed"
            return
        }
    }

    if ($AcceptStatus -contains $statusCode) {
        Add-Result $Name "PASS" $details
        return
    }

    if ($AllowDegraded -and $statusCode -eq 503) {
        Add-Result $Name "WARN" $details
        return
    }

    Add-Result $Name "FAIL" $details
}

function Test-DockerCompose {
    if ($SkipDocker) {
        Add-Result "Docker Compose" "WARN" "Skipped by -SkipDocker"
        return
    }

    $composeOutput = @()
    try {
        $composeOutput = docker compose ps --format json 2>$null
    } catch {
        Add-Result "Docker Compose" "FAIL" $_.Exception.Message
        return
    }

    $jsonText = ($composeOutput -join "`n").Trim()
    if (-not $jsonText) {
        Add-Result "Docker Compose" "FAIL" "No compose containers found"
        return
    }

    try {
        if ($jsonText.StartsWith("[")) {
            $containers = @($jsonText | ConvertFrom-Json)
        } else {
            $containers = @(
                foreach ($line in $composeOutput) {
                    if ($line.Trim()) {
                        $line | ConvertFrom-Json
                    }
                }
            )
        }
    } catch {
        Add-Result "Docker Compose" "FAIL" "Could not parse docker compose ps JSON"
        return
    }

    foreach ($serviceName in @("backend", "frontend", "squadjs", "caddy")) {
        $service = $containers | Where-Object { $_.Service -eq $serviceName } | Select-Object -First 1
        if (-not $service) {
            Add-Result "Container: $serviceName" "FAIL" "Not found"
            continue
        }

        $state = [string]$service.State
        $health = [string]$service.Health
        $status = [string]$service.Status
        $details = (@($state, $health, $status) | Where-Object { $_ }) -join ", "

        if ($state -ne "running") {
            Add-Result "Container: $serviceName" "FAIL" $details
        } elseif ($health -eq "unhealthy") {
            Add-Result "Container: $serviceName" "FAIL" $details
        } elseif ($health -eq "starting") {
            Add-Result "Container: $serviceName" "WARN" $details
        } else {
            Add-Result "Container: $serviceName" "PASS" $details
        }
    }

    try {
        $containerIds = @(docker compose ps -q 2>$null)
        if (-not $containerIds.Count) {
            return
        }

        $restartLines = @()
        foreach ($containerId in $containerIds) {
            $restartLines += docker inspect --format '{{.Name}}|{{.RestartCount}}' $containerId 2>$null
        }

        $restarted = @(
            foreach ($line in $restartLines) {
                $parts = $line -split "\|", 2
                if ($parts.Count -eq 2 -and [int]$parts[1] -gt 0) {
                    "$($parts[0].TrimStart('/'))=$($parts[1])"
                }
            }
        )

        if ($restarted.Count) {
            Add-Result "Container restarts" "WARN" ($restarted -join ", ")
        } else {
            Add-Result "Container restarts" "PASS" "No restarts reported"
        }
    } catch {
        Add-Result "Container restarts" "WARN" "Could not inspect restart counts"
    }
}

Write-Host "CMP production smoke test: $baseUrl"

Invoke-HttpProbe "Public frontend" "$baseUrl/" -AcceptStatus @(200)
Invoke-HttpProbe "Public backend live" "$baseUrl/api/health/live" -AcceptStatus @(200) -Json
Invoke-HttpProbe "Public backend readiness" "$baseUrl/api/health" -AcceptStatus @(200) -Json -AllowDegraded:(!$RequireReady)
Invoke-HttpProbe "Local Caddy health" "http://127.0.0.1/healthz" -AcceptStatus @(200)
Test-DockerCompose

Write-Host ""
foreach ($result in $results) {
    $color = switch ($result.Status) {
        "PASS" { "Green" }
        "WARN" { "Yellow" }
        "FAIL" { "Red" }
    }
    Write-Host ("[{0}] {1}: {2}" -f $result.Status, $result.Name, $result.Details) -ForegroundColor $color
}

$failures = @($results | Where-Object { $_.Status -eq "FAIL" })
$warnings = @($results | Where-Object { $_.Status -eq "WARN" })

Write-Host ""
Write-Host "Manual checks still needed: Steam login, socket/queue live update, admin diagnostics page, and server info from the admin page."

if ($failures.Count) {
    exit 1
}

if ($warnings.Count) {
    exit 0
}

exit 0
