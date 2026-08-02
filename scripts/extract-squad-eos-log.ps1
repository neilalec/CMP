$LogPath = Join-Path $env:LOCALAPPDATA "SquadGame\Saved\Logs\SquadGame.log"

if (-not (Test-Path $LogPath)) {
  Write-Error "Squad log not found at $LogPath"
  exit 1
}

$patterns = @(
  "ClientId=",
  "ClientSecret",
  "TokenGrant",
  "FilterLobbies",
  "4K War Server",
  "ADVERTISEDSESSIONID_s",
  "SERVERNAME_s",
  "RedpointEOSRoomId_s",
  "Session:"
)

Get-Content $LogPath |
  Select-String -Pattern $patterns -SimpleMatch |
  ForEach-Object { $_.Line }
