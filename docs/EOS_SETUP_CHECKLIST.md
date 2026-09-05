# EOS Setup Checklist

Use this checklist exactly in order.

## Goal

Get a live `EOS_ACCESS_TOKEN` into the backend so CMP can test EOS matchmaking lookup for the auto-connect button.

## Checklist

- [ ] 1. Open `backend/.env`.
- [ ] 2. Copy the lines from `backend/.env.eos.example` into the bottom of `backend/.env`.
- [ ] 3. Fill in `EOS_CLIENT_ID` if you have it.
- [ ] 4. Fill in `EOS_CLIENT_SECRET` if you have it.
- [ ] 5. Fill in `EOS_STEAM_SESSION_TICKET_HEX` if you have it.
- [ ] 6. If you already have a live bearer token from another tool, paste it into `EOS_ACCESS_TOKEN` and skip to step 10.
- [ ] 7. Copy `tools/steam-ticket/.env.example` to `tools/steam-ticket/.env`.
- [ ] 8. Fill in `STEAM_USERNAME` and `STEAM_PASSWORD`.
- [ ] 9. If you use Steam mobile authenticator and know your shared secret, fill in `STEAM_SHARED_SECRET`. Otherwise leave it blank.
- [ ] 10. Open a terminal in the repository root.
- [ ] 11. Run:

```powershell
cd tools\steam-ticket
npm run get-ticket
```

- [ ] 12. If prompted for a Steam Guard code, enter it.
- [ ] 13. If the command succeeds, copy the printed value that starts with `EOS_STEAM_SESSION_TICKET_HEX=`.
- [ ] 14. Paste that value into `EOS_STEAM_SESSION_TICKET_HEX` inside `backend/.env`.
- [ ] 15. Run:

```powershell
backend\venv\Scripts\python.exe backend\scripts\exchange_eos_token.py
```

- [ ] 16. If the command succeeds, copy the printed value that starts with `EOS_ACCESS_TOKEN=`.
- [ ] 17. Paste that full token value into `EOS_ACCESS_TOKEN` inside `backend/.env`.
- [ ] 18. Restart the backend.
- [ ] 19. Open Admin and confirm the `EOS` card no longer says `Missing Token`.
- [ ] 20. Run `Health Check / Re-test` on `4K War Server`.
- [ ] 21. If `EOS matchmaking` still does not resolve, copy the JSON block and paste it back here.

## If A Step Fails

- If step 11 fails:
  - copy the exact error and paste it here.
- If step 15 fails because `EOS_CLIENT_ID` or `EOS_CLIENT_SECRET` is missing:
  - stop and tell me exactly that.
- If step 15 fails because `EOS_STEAM_SESSION_TICKET_HEX` is missing:
  - stop and tell me that.
- If step 15 returns an HTTP error from Epic:
  - copy the exact error text and paste it here.

## Important

- Do not paste your Steam username or password into chat.
- `EOS_ACCESS_TOKEN` is temporary. We may need to refresh it later.
- Right now, the most likely blocker is obtaining `EOS_CLIENT_ID`, `EOS_CLIENT_SECRET`, and/or `EOS_STEAM_SESSION_TICKET_HEX`.
