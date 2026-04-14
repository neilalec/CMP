## SquadJS Local Setup For Oasis Test

This is the first milestone setup:

- run SquadJS on your machine
- connect it to your Oasis-hosted Squad server
- confirm RCON works
- manually change the layer while you are connected to the server

### 1. What you need from Oasis

You said Oasis is your host, so you need these values from their panel/support:

- server IP / host
- query port
- RCON port
- RCON password
- SFTP or FTP credentials
- remote path to the Squad log directory

SquadJS needs both:

- RCON access to issue commands
- log access via SFTP/FTP so it can parse live server events

### 2. Prepare config

1. Copy `config.oasis-template.json` to `config.json`
2. Fill in the placeholders

If Oasis only gives FTP and not SFTP:

- change `"logReaderMode": "sftp"` to `"ftp"`
- fill the `ftp` block instead of `sftp`

If you want to do a temporary RCON-only test first:

- set `"disableLogParser": true` in `server`

That bypasses FTP/SFTP log watching so SquadJS can stay up long enough to test the
manual layer-change command. Turn it back to `false` once your log access details are ready.

### 3. Install dependencies

Run from the `squadjs` folder:

```powershell
corepack enable
corepack yarn install --ignore-engines
```

### 4. Start SquadJS

```powershell
node index.js
```

If the config is correct, SquadJS should connect to:

- the server over RCON
- the log directory over SFTP/FTP

### 5. Test layer commands in game

This repo includes a tiny custom plugin: `CmpLayerTest`.

While connected to the server as an admin, use in all-chat:

```text
!cmpserver
```

This warns you back with:

- the server name SquadJS is attached to
- the current layer
- the next layer

To change the current layer immediately:

```text
!cmpchange Gorodok_RAAS_v1
```

This sends:

```text
AdminChangeLayer Gorodok_RAAS_v1
```

To set the next layer instead of changing immediately:

```text
!cmpnext Gorodok_RAAS_v1
```

This sends:

```text
AdminSetNextLayer Gorodok_RAAS_v1
```

If the layer requires faction arguments, include them after the layer:

```text
!cmpchange Narva_AAS_v1 USA RGF
```

### 6. What success looks like

For this first milestone, success is:

- SquadJS starts without config/auth errors
- you can join the server
- typing `!cmpchange ...` causes the server to change layer

### 7. Notes

- `AdminChangeLayer` changes immediately. Use this for testing.
- `AdminSetNextLayer` only changes the next layer.
- The exact layer string must match Squad's expected layer name.
- If Oasis blocks log access, SquadJS setup will not be usable there and the fallback is:
  - run a local/dev Squad server on your machine, or
  - move SquadJS to a VPS that can reach Oasis logs and RCON
