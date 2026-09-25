export async function mountAfterRouterReady(app, router, mountTarget) {
  await router.isReady()
  app.mount(mountTarget)
}
