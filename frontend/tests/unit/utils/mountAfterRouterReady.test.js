import { mountAfterRouterReady } from '@/utils/mountAfterRouterReady'

describe('application mount routing readiness', () => {
  test('waits for the initial route to resolve before mounting the app', async () => {
    let markReady
    const app = { mount: jest.fn() }
    const router = {
      isReady: jest.fn(() => new Promise((resolve) => { markReady = resolve }))
    }

    const mounting = mountAfterRouterReady(app, router, '#app')

    expect(router.isReady).toHaveBeenCalledTimes(1)
    expect(app.mount).not.toHaveBeenCalled()

    markReady()
    await mounting

    expect(app.mount).toHaveBeenCalledTimes(1)
    expect(app.mount).toHaveBeenCalledWith('#app')
  })
})
