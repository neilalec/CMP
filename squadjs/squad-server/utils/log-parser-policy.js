export function shouldSuppressLogParsingInDev(env = process.env) {
  return env.CMP_DEV_MODE === '1' && env.CMP_SQUAD_LIVE_LOGS !== '1';
}

export function getLogParserDisableReason(serverOptions = {}, env = process.env) {
  if (serverOptions.disableLogParser) return 'config';
  if (shouldSuppressLogParsingInDev(env)) return 'local dev mode';
  return null;
}

export function isLogParserDisabled(serverOptions = {}, env = process.env) {
  return getLogParserDisableReason(serverOptions, env) !== null;
}
