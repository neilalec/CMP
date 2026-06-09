import { useSocketStore } from '../socketStore'

export async function runStoreSocketAction(store, options) {
  const {
    event,
    payload = {},
    setLoading = true,
    onSuccess = null,
    validate = null,
    fallbackMessage = 'Request failed',
    swallowError = false
  } = options

  if (setLoading) {
    store.loading = true
  }

  try {
    const socketStore = useSocketStore()
    const response = await socketStore.emit(event, payload)

    if (validate) {
      validate(response)
    }

    if (onSuccess) {
      await onSuccess(response)
    }

    store.error = null
    return response
  } catch (error) {
    store.error = error.message || fallbackMessage
    if (!swallowError) {
      throw error
    }
    return null
  } finally {
    if (setLoading) {
      store.loading = false
    }
  }
}
