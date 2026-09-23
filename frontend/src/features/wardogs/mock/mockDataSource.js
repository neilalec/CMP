import { scenarios, scenarioOptions } from './scenarios';

// The UI consumes this boundary through the store. A future CMP source must
// normalize its own payload into the WARDOGS domain shape before returning it.
export const mockWardogsDataSource = {
  listScenarios() {
    return scenarioOptions;
  },
  async loadScenario(key) {
    const scenario = scenarios.find((entry) => entry.key === key);
    if (!scenario) throw new Error(`Unknown WARDOGS scenario: ${key}`);
    return JSON.parse(JSON.stringify(scenario.match));
  }
};
