import process from "node:process";

import dotenv from "dotenv";
import SteamTotp from "steam-totp";
import SteamUser from "steam-user";

dotenv.config();

const accountName = String(process.env.STEAM_USERNAME || "").trim();
const password = String(process.env.STEAM_PASSWORD || "").trim();
const sharedSecret = String(process.env.STEAM_SHARED_SECRET || "").trim();
const guardCode = String(process.env.STEAM_GUARD_CODE || "").trim();
const appId = Number.parseInt(String(process.env.STEAM_APP_ID || "393380").trim(), 10);

if (!accountName || !password) {
  console.error("STEAM_USERNAME and STEAM_PASSWORD are required.");
  process.exit(1);
}

if (!Number.isInteger(appId) || appId <= 0) {
  console.error("STEAM_APP_ID must be a valid integer.");
  process.exit(1);
}

const client = new SteamUser({
  autoRelogin: false,
  enablePicsCache: false,
  saveAppTickets: false
});

let finished = false;

function finish(code) {
  if (finished) return;
  finished = true;
  try {
    client.logOff();
  } catch {}
  setTimeout(() => process.exit(code), 250);
}

client.on("error", (error) => {
  console.error(error?.message || String(error));
  finish(1);
});

client.on("steamGuard", (domain, callback, lastCodeWrong) => {
  if (sharedSecret) {
    callback(SteamTotp.generateAuthCode(sharedSecret));
    return;
  }

  if (guardCode) {
    callback(guardCode);
    return;
  }

  const label = domain
    ? `Enter the Steam email code sent to ${domain}: `
    : "Enter your Steam Guard code: ";

  if (lastCodeWrong) {
    process.stdout.write("Previous Steam Guard code was rejected.\n");
  }
  process.stdout.write(label);
  process.stdin.resume();
  process.stdin.setEncoding("utf8");
  process.stdin.once("data", (input) => {
    callback(String(input || "").trim());
  });
});

client.on("loggedOn", async () => {
  try {
    const { sessionTicket } = await client.createAuthSessionTicket(appId);
    process.stdout.write(`EOS_STEAM_SESSION_TICKET_HEX=${sessionTicket.toString("hex")}\n`);
    finish(0);
  } catch (error) {
    console.error(error?.message || String(error));
    finish(1);
  }
});

client.logOn({
  accountName,
  password,
  twoFactorCode: sharedSecret ? SteamTotp.generateAuthCode(sharedSecret) : undefined,
  authCode: !sharedSecret && guardCode ? guardCode : undefined
});
