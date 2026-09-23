import { mount } from '@vue/test-utils';
import JoinState from '../../../src/features/wardogs/components/JoinState.vue';

const render = (join) => mount(JoinState, { props: { join } });

describe('WARDOGS join state', () => {
  test('waiting lobby has no join action', () => {
    const wrapper = render({ state: 'waiting_for_server' });
    expect(wrapper.text()).toContain('Waiting for a WARDOGS server');
    expect(wrapper.find('a').exists()).toBe(false);
  });

  test('allocated server without verified join has no action or admin details', () => {
    const wrapper = render({ state: 'server_allocated_join_unavailable',
      serverName: 'Test server', directJoinUrl: 'http://admin.local:7776',
      instructions: 'secret' });
    expect(wrapper.text()).toContain('Test server');
    expect(wrapper.text()).toContain('Verified player join instructions are not available');
    expect(wrapper.text()).not.toContain('secret');
    expect(wrapper.find('a').exists()).toBe(false);
  });

  test('manual instructions and direct action require explicit states', () => {
    const manual = render({ state: 'manual_join_available',
      serverName: 'Test server', instructions: 'Use the verified server browser listing.' });
    expect(manual.text()).toContain('Use the verified server browser listing.');
    expect(manual.find('a').exists()).toBe(false);
    const direct = render({ state: 'direct_join_available',
      serverName: 'Test server', directJoinUrl: 'steam://connect/127.0.0.1:1234' });
    expect(direct.find('a').attributes('href')).toBe('steam://connect/127.0.0.1:1234');
  });
});
