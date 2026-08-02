$LogPath = Join-Path $env:LOCALAPPDATA "SquadGame\Saved\Logs\SquadGame.log"

if (-not (Test-Path $LogPath)) {
  New-Item -ItemType File -Path $LogPath -Force | Out-Null
}

$patterns = @(
  "4K War Server",
  "FilterLobbies",
  "ADVERTISEDSESSIONID_s",
  "SERVERNAME_s",
  "RedpointEOSRoomId_s",
  "Session:",
  "accepted room invite",
  "FindSessionById",
  "SetODKSession"
)

Write-Host "Watching $LogPath"
Write-Host "Press Ctrl+C to stop."

Get-Content $LogPath -Wait |
  Select-String -Pattern $patterns -SimpleMatch |
  ForEach-Object { $_.Line }
