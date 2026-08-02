# Workspace Notes

## VS Code Remote + RTK

This workspace sets `XDG_DATA_HOME` in [.vscode/settings.json](/mnt/c/Users/neila/Desktop/CMP_dev/.vscode/settings.json:1) so `rtk` can write its tracking database inside the repo instead of under the default home-directory path, which is not writable in this Codex remote session.

Open a new VS Code integrated terminal after changing workspace settings, then verify with:

```bash
echo "$XDG_DATA_HOME"
rtk gain --history
```

## Git Safe Directory Helper

This repo lives on a Windows-mounted path in WSL, so some Git commands may fail with a "dubious ownership" or `safe.directory` error.

Use the helper script:

```bash
./scripts/git-safe.sh status
./scripts/git-safe.sh ls-files
```

It runs:

```bash
git -c safe.directory=/mnt/c/Users/neila/Desktop/CMP_dev ...
```

If you prefer a global fix for your own shell outside this workspace, run:

```bash
git config --global --add safe.directory /mnt/c/Users/neila/Desktop/CMP_dev
```
