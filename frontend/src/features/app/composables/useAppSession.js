import { onBeforeUnmount, onMounted, watch, ref, computed } from 'vue'
import { SOCKET_EVENTS } from '../../../constants/socketEvents'
import {
  clearCurrentLobby,
  getCurrentLobbyId,
  isLobbyRoute,
  setCurrentLobbyId
} from '../../../utils/lobbyPersistence'

export function useAppSession({
  router,
  route,
  authStore,
  socketStore,
  rootStore,
  lobbyStore,
  queueStore,
  groupStore
}) {
  const isInLobby = computed(() => isLobbyRoute(route.path))
  const currentLobbyId = ref(getCurrentLobbyId())
  const activeLobbyId = computed(() => {
    return route.params.lobbyId || currentLobbyId.value || null
  })
  const playRoute = computed(() => {
    return activeLobbyId.value ? `/lobby/${activeLobbyId.value}` : '/play'
  })
  const isMatchAcceptParticipant = computed(() => {
    const players = Array.isArray(queueStore.matchAccept.players)
      ? queueStore.matchAccept.players
      : []
    return (
      (queueStore.matchAccept.active || queueStore.matchAccept.cancelled)
      && !isInLobby.value
      && !!authStore.username
      && players.includes(authStore.username)
    )
  })
  const isMatchAcceptCancelled = computed(() => queueStore.matchAccept.cancelled)
  const lobbySyncPending = ref(false)
  const finalizingLobbySyncTimer = ref(null)

  const handleQueueUpdate = (data) => {
    queueStore.updateQueueState(data)
  }

  const handleMatchAcceptCancelled = (data) => {
    queueStore.setMatchAcceptCancelled(data?.reason || 'Match acceptance cancelled')
  }

  const syncQueuePresence = async () => {
    if (!authStore.username) return
    await queueStore.syncWithServer(authStore.username)
  }

  const syncSessionPresence = async () => {
    if (!authStore.username) return
    await syncActiveLobbyFromProfile()
    await syncLobbyPresence()
    await syncQueuePresence()
  }

  const handleGroupUpdate = (data) => {
    groupStore.handleUpdate(data)
  }

  const handleLobbyCreated = (data) => {
    const isParticipant = data?.players?.includes(authStore.username)
    if (!isParticipant) return
    if (data?.lobby_id) {
      clearFinalizingLobbySyncTimer()
      lobbyStore.reset()
      lobbyStore.updateLobbyState(data)
      setCurrentLobbyId(data.lobby_id)
      queueStore.resetQueue()
      router.push(`/lobby/${data.lobby_id}`)
    }
  }

  const routeToLobby = (lobbyId) => {
    if (!lobbyId) return false
    currentLobbyId.value = lobbyId
    setCurrentLobbyId(lobbyId)
    if (!route.path.startsWith(`/lobby/${lobbyId}`)) {
      router.push(`/lobby/${lobbyId}`)
    }
    return true
  }

  const clearFinalizingLobbySyncTimer = () => {
    if (!finalizingLobbySyncTimer.value) return
    clearTimeout(finalizingLobbySyncTimer.value)
    finalizingLobbySyncTimer.value = null
  }

  const waitForFinalizedLobby = (attempt = 1) => {
    clearFinalizingLobbySyncTimer()
    finalizingLobbySyncTimer.value = setTimeout(async () => {
      if (isInLobby.value || !authStore.username) return
      try {
        const profile = await syncActiveLobbyFromProfile()
        if (profile?.active_lobby || isInLobby.value) return
      } catch (error) {
        // Lobby-created is the primary path; this retry is just a fallback.
      }
      if (attempt < 8) {
        waitForFinalizedLobby(attempt + 1)
      }
    }, Math.min(5000, 350 * attempt))
  }

  const handleActiveLobbySync = (data) => {
    const activeLobby = data?.lobby_id || null

    if (activeLobby) {
      currentLobbyId.value = activeLobby
      setCurrentLobbyId(activeLobby)
      if (!route.path.startsWith(`/lobby/${activeLobby}`)) {
        router.push(`/lobby/${activeLobby}`)
      }
      return
    }

    lobbyStore.leaveLobby()
    clearCurrentLobby()
    currentLobbyId.value = null
    if (route.path.startsWith('/lobby/')) {
      router.push('/')
    }
  }

  const syncActiveLobbyFromProfile = async () => {
    if (!authStore.username) return null
    const profile = await authStore.syncProfile()
    const activeLobby = profile?.active_lobby || null

    if (activeLobby) {
      currentLobbyId.value = activeLobby
      setCurrentLobbyId(activeLobby)
      if (!route.path.startsWith(`/lobby/${activeLobby}`)) {
        router.push(`/lobby/${activeLobby}`)
      }
    } else if (getCurrentLobbyId() || lobbyStore.lobbyId || currentLobbyId.value) {
      lobbyStore.leaveLobby()
      clearCurrentLobby()
      currentLobbyId.value = null
    }

    return profile
  }

  const syncLobbyPresence = async () => {
    if (!currentLobbyId.value || !socketStore.isConnected) return
    try {
      const response = await socketStore.emit(SOCKET_EVENTS.OPEN_LOBBIES.STATUS)
      const openLobbies = response?.openLobbies || []
      const activeLobbies = response?.activeLobbies || []
      const exists = [...openLobbies, ...activeLobbies].some(
        lobby => lobby.lobby_id === currentLobbyId.value
      )
      if (!exists) {
        lobbyStore.leaveLobby()
        clearCurrentLobby()
        currentLobbyId.value = null
      }
    } catch (error) {
      // Ignore transient errors during reconnects
    }
  }

  const registerSocketListeners = () => {
    socketStore.on(SOCKET_EVENTS.CONNECTION.CONNECT, syncSessionPresence)
    socketStore.on(SOCKET_EVENTS.QUEUE.UPDATE, handleQueueUpdate)
    socketStore.on(SOCKET_EVENTS.QUEUE.MATCH_ACCEPT_CANCELLED, handleMatchAcceptCancelled)
    socketStore.on(SOCKET_EVENTS.GROUP.UPDATE, handleGroupUpdate)
    socketStore.on(SOCKET_EVENTS.LOBBY.CREATED, handleLobbyCreated)
    socketStore.on(SOCKET_EVENTS.LOBBY.ACTIVE_SYNC, handleActiveLobbySync)
  }

  const unregisterSocketListeners = () => {
    socketStore.off(SOCKET_EVENTS.CONNECTION.CONNECT, syncSessionPresence)
    socketStore.off(SOCKET_EVENTS.QUEUE.UPDATE, handleQueueUpdate)
    socketStore.off(SOCKET_EVENTS.QUEUE.MATCH_ACCEPT_CANCELLED, handleMatchAcceptCancelled)
    socketStore.off(SOCKET_EVENTS.GROUP.UPDATE, handleGroupUpdate)
    socketStore.off(SOCKET_EVENTS.LOBBY.CREATED, handleLobbyCreated)
    socketStore.off(SOCKET_EVENTS.LOBBY.ACTIVE_SYNC, handleActiveLobbySync)
  }

  const initAuthenticatedState = async () => {
    registerSocketListeners()
    if (authStore.username) {
      await syncSessionPresence()
      await groupStore.syncStatus(authStore.username)
    }
  }

  const handleProfile = () => {
    router.push('/profile')
  }

  const handleGroup = () => {
    router.push('/group')
  }

  const handleAcceptMatch = async () => {
    try {
      const response = await queueStore.acceptMatch(authStore.username)
      if (response?.lobbyId) {
        routeToLobby(response.lobbyId)
        return
      }
      if (response?.allAccepted && !response?.finalizingLobby) {
        await syncActiveLobbyFromProfile()
      } else if (response?.finalizingLobby) {
        waitForFinalizedLobby()
      }
    } catch (error) {
      rootStore.setError(error.message || 'Failed to accept match')
    }
  }

  const syncAcceptedMatchLobby = async () => {
    if (lobbySyncPending.value || isInLobby.value) return
    if (queueStore.matchAccept.finalizingLobby) return
    const matchAccept = queueStore.matchAccept
    const acceptedCount = matchAccept.acceptedCount || 0
    const requiredCount = matchAccept.requiredCount || 0
    if (!matchAccept.active || !requiredCount || acceptedCount < requiredCount) return

    lobbySyncPending.value = true
    try {
      await syncActiveLobbyFromProfile()
    } finally {
      lobbySyncPending.value = false
    }
  }

  const handleDismissMatchAccept = () => {
    queueStore.resetMatchAccept()
  }

  const handleCloseMatchAccept = async () => {
    if (isMatchAcceptCancelled.value) {
      handleDismissMatchAccept()
      return
    }

    try {
      const queueMode = queueStore.matchAccept.queueMode || queueStore.queueMode || null
      await queueStore.leaveQueue(authStore.username, queueMode)
    } catch (error) {
      rootStore.setError(error.message || 'Failed to cancel match acceptance')
    }
  }

  onMounted(async () => {
    console.log('App mounted, initializing base socket connection...')
    try {
      const isAuthenticated = authStore.restoreAuth()

      if (isAuthenticated) {
        try {
          await socketStore.initSocket(authStore.token, authStore.username)
        } catch (error) {
          authStore.logout()
          clearCurrentLobby()
          currentLobbyId.value = null
          await socketStore.cleanupSocket()
          await socketStore.initSocket()
          router.replace('/auth')
          return
        }
      } else {
        await socketStore.initSocket()
      }

      if (!isAuthenticated) {
        router.replace('/auth')
        clearCurrentLobby()
        currentLobbyId.value = null
        return
      }

      await initAuthenticatedState()
    } catch (error) {
      console.error('Failed to initialize socket:', error)
      rootStore.setError('Failed to connect to server')
    }
  })

  watch(() => authStore.isLoggedIn, async (isLoggedIn) => {
    if (isLoggedIn && authStore.token) {
      try {
        rootStore.setLoading(true)
        await socketStore.cleanupSocket()
        await socketStore.initSocket(authStore.token, authStore.username)
        await initAuthenticatedState()
      } catch (error) {
        rootStore.setError('Failed to connect to server')
        clearCurrentLobby()
        queueStore.resetQueue()
        lobbyStore.reset()
        groupStore.resetGroup()
        authStore.logout()
      } finally {
        rootStore.setLoading(false)
      }
    }
  })

  watch(() => lobbyStore.lobbyId, (id) => {
    if (id) {
      currentLobbyId.value = id
      setCurrentLobbyId(id)
    } else if (!getCurrentLobbyId()) {
      currentLobbyId.value = null
    }
  })

  watch(
    [() => route.path, activeLobbyId],
    ([path, lobbyId]) => {
      if ((path === '/queue' || path === '/play') && lobbyId) {
        router.replace(`/lobby/${lobbyId}`)
      }
      if (authStore.isLoggedIn && authStore.username && socketStore.isConnected) {
        syncQueuePresence()
      }
    },
    { immediate: true }
  )

  watch(
    () => [
      queueStore.matchAccept.active,
      queueStore.matchAccept.acceptedCount,
      queueStore.matchAccept.requiredCount
    ],
    syncAcceptedMatchLobby
  )

  onBeforeUnmount(() => {
    unregisterSocketListeners()
    clearFinalizingLobbySyncTimer()
    socketStore.cleanupSocket()
  })

  return {
    isInLobby,
    currentLobbyId,
    playRoute,
    isMatchAcceptParticipant,
    isMatchAcceptCancelled,
    handleProfile,
    handleGroup,
    handleAcceptMatch,
    handleCloseMatchAccept,
    handleDismissMatchAccept
  }
}
