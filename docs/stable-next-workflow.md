# Stable + Next Workflow

The public stack remains the stable test target at `https://example.com`.

The next/candidate stack runs beside it at `http://localhost:8081`:

```powershell
.\scripts\start-next.ps1
```

Stop it with:

```powershell
.\scripts\stop-next.ps1
```

The next stack has its own backend database volume and does not run SquadJS/RCON control. This avoids two app versions sending live server admin commands at the same time.

When the current workspace is ready to become stable:

```powershell
.\scripts\promote-next.ps1
```

Use `-Force` to skip the confirmation prompt.
