$LogPath = Join-Path $env:LOCALAPPDATA "SquadGame\Saved\Logs\SquadGame.log"

if (-not (Test-Path $LogPath)) {
  Write-Error "Squad log not found at $LogPath"
  exit 1
}

$lines = Get-Content $LogPath
$sessionId = $null
$connectAddress = $null

for ($i = $lines.Count - 1; $i -ge 0; $i--) {
  $line = $lines[$i]

  if (-not $connectAddress -and $line -match "traveling to ([0-9\.]+:\d+)") {
    $connectAddress = $matches[1]
  }

  if (-not $sessionId -and $line -match "RedpointEOSRoomId=Session:([0-9a-f]{32})") {
    $sessionId = $matches[1]
  }

  if ($sessionId -and $connectAddress) {
    break
  }
}

if (-not $sessionId -and -not $connectAddress) {
  Write-Error "No recent Squad join session found in $LogPath"
  exit 1
}

if ($sessionId) {
  Write-Output ("EOS_SESSION_ID=" + $sessionId)
  Write-Output ("REDPOINT_EOS_ROOM_ID=Session:" + $sessionId)
}

if ($connectAddress) {
  Write-Output ("CONNECT_ADDRESS=" + $connectAddress)
}
