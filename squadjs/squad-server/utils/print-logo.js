import axios from 'axios';

import { SQUADJS_VERSION, COPYRIGHT_MESSAGE } from './constants.js';

function versionOutOfDate(current, latest) {
  const cMatch = current.match(/([0-9]+)\.([0-9]+)\.([0-9]+)/);
  const lMatch = latest.match(/([0-9]+)\.([0-9]+)\.([0-9]+)/);

  cMatch.shift();
  lMatch.shift();

  const [cMajor, cMinor, cPatch] = cMatch;
  const [lMajor, lMinor, lPatch] = lMatch;

  return (
    cMajor < lMajor ||
    (cMajor === lMajor && cMinor < lMinor) ||
    (cMajor === lMajor && cMinor === lMinor && cPatch < lPatch)
  );
}

export default async function () {
  let latestVersion = null;
  let latestVersionColor = '\x1b[33m';
  let latestVersionStatus = 'Latest version unavailable.';

  try {
    const { data } = await axios.get(
      `https://raw.githubusercontent.com/Team-Silver-Sphere/SquadJS/master/package.json`
    );
    latestVersion = data.version;
    const outdated = versionOutOfDate(SQUADJS_VERSION, latestVersion);
    latestVersionColor = outdated ? '\x1b[31m' : '\x1b[32m';
    latestVersionStatus = outdated
      ? '\x1b[31mYour SquadJS version is outdated, please consider updating.'
      : '\x1b[32mYour SquadJS version is up to date.';
  } catch (err) {
    latestVersionStatus = `\x1b[33mUnable to check latest SquadJS version: ${err.message}`;
  }

  console.log(
    `
   _____  ____  _    _         _____   \x1b[33m_\x1b[0m     
  / ____|/ __ \\| |  | |  /\\   |  __ \\ \x1b[33m(_)\x1b[0m    
 | (___ | |  | | |  | | /  \\  | |  | | \x1b[33m_ ___\x1b[0m 
  \\___ \\| |  | | |  | |/ /\\ \\ | |  | |\x1b[33m| / __|\x1b[0m
  ____) | |__| | |__| / ____ \\| |__| |\x1b[33m| \\__ \\\x1b[0m
 |_____/ \\___\\_\\\\____/_/    \\_\\_____\x1b[33m(_) |___/\x1b[0m
                                     \x1b[33m_/ |\x1b[0m    
                                    \x1b[33m|__/\x1b[0m     
${COPYRIGHT_MESSAGE}
GitHub: https://github.com/Team-Silver-Sphere/SquadJS

Latest Version: ${latestVersion ? `${latestVersionColor}${latestVersion}` : '\x1b[33munavailable'}\x1b[0m, Installed Version: \x1b[32m${SQUADJS_VERSION}\x1b[0m
${latestVersionStatus}\x1b[0m

\x1b[33mLooking for ways to help protect your server from harmful players?
Checkout the Squad Community Ban List: https://communitybanlist.com/\x1b[0m
`
  );
}
