import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getLogParserDisableReason,
  isLogParserDisabled,
  shouldSuppressLogParsingInDev
} from '../squad-server/utils/log-parser-policy.js';

test('local dev suppresses log parsing unless full live logs are explicitly enabled', () => {
  const options = { disableLogParser: false };

  assert.equal(isLogParserDisabled(options, { CMP_DEV_MODE: '1' }), true);
  assert.equal(getLogParserDisableReason(options, { CMP_DEV_MODE: '1' }), 'local dev mode');
  assert.equal(
    isLogParserDisabled(options, { CMP_DEV_MODE: '1', CMP_SQUAD_LIVE_LOGS: '1' }),
    false
  );
});

test('config can still explicitly disable log parsing in live-log mode', () => {
  assert.equal(
    isLogParserDisabled(
      { disableLogParser: true },
      { CMP_DEV_MODE: '1', CMP_SQUAD_LIVE_LOGS: '1' }
    ),
    true
  );
  assert.equal(
    getLogParserDisableReason(
      { disableLogParser: true },
      { CMP_DEV_MODE: '1', CMP_SQUAD_LIVE_LOGS: '1' }
    ),
    'config'
  );
});

test('production log-parser behavior does not depend on the dev-only override', () => {
  assert.equal(shouldSuppressLogParsingInDev({ CMP_DEV_MODE: '0' }), false);
  assert.equal(shouldSuppressLogParsingInDev({ CMP_SQUAD_LIVE_LOGS: '1' }), false);
  assert.equal(isLogParserDisabled({ disableLogParser: false }, {}), false);
  assert.equal(
    isLogParserDisabled({ disableLogParser: false }, { CMP_SQUAD_LIVE_LOGS: '1' }),
    false
  );
  assert.equal(isLogParserDisabled({ disableLogParser: true }, {}), true);
});
