# Faction Label Investigation

Live lobby team headers currently fall back to `BLUFOR` and `OPFOR`.

`ShowServerInfo` exposes `TeamOne_s` and `TeamTwo_s`, but this has not proven reliable enough for display. On Kokan Skirmish v1, the bridge reported:

```json
{
  "teamOne": "GFI_S_CombinedArms_Skirmish",
  "teamTwo": "MEI_S_CombinedArms_Skirmish"
}
```

The observed in-game order was `MEI` and `GFI`, so using those fields directly can show wrong labels.

The next likely source to test is `ListSquads`, because it includes team ID headers:

```text
Team ID: 1 (...)
Team ID: 2 (...)
```

Only re-enable faction labels in the lobby UI after we can prove the source maps reliably to Team ID 1 and Team ID 2 during the live layer.
