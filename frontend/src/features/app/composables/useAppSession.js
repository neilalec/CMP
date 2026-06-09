import { onBeforeUnmount, onMounted, watch, ref, computed } from 'vue'
import { SOCKET_EVENTS } from '../../../constants/socketEvents'
import {
  clearCurrentLobby,
  getCurrentLobbyCaptains,
  getCurrentLobbyId,
  isLobbyRoute,
  setCurrentLobbyCaptains,
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
  const currentLobbyCaptains = ref(null)

  currentLobbyCaptains.value = getCurrentLobbyCaptains()

  const canReturnToLobby = computed(() => !!currentLobbyId.value && !isInLobby.value)
  const activeLobbyId = computed(() => {
    return route.params.lobbyId || lobbyStore.lobbyId || currentLobbyId.value
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

  const handleQueueUpdate = (data) => {
    queueStore.updateQueueState(data)
  }

  const handleMatchAcceptCancelled = (data) => {
    queueStore.setMatchAcceptCancelled(data?.reason || 'Match acceptance cancelled')
  }

  const handleGroupUpdate = (data) => {
    groupStore.handleUpdate(data)
  }

  const handleLobbyCreated = (data) => {
    const isParticipant = data?.players?.includes(authStore.username)
    if (!isParticipant) return
    if (data?.lobby_id) {
      lobbyStore.reset()
      lobbyStore.updateLobbyState(data)
      setCurrentLobbyId(data.lobby_id)
      queueStore.resetQueue()
      router.push(`/lobby/${data.lobby_id}`)
    }
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
    currentLobbyCaptains.value = null
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
    } else if (getCurrentLobbyId()) {
      lobbyStore.leaveLobby()
      clearCurrentLobby()
      currentLobbyId.value = null
      currentLobbyCaptains.value = null
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
        currentLobbyCaptains.value = null
      }
    } catch (error) {
      // Ignore transient errors during reconnects
    }
  }

  const registerSocketListeners = () => {
    socketStore.on(SOCKET_EVENTS.CONNECTION.CONNECT, syncLobbyPresence)
    socketStore.on(SOCKET_EVENTS.QUEUE.UPDATE, handleQueueUpdate)
    socketStore.on(SOCKET_EVENTS.QUEUE.MATCH_ACCEPT_CANCELLED, handleMatchAcceptCancelled)
    socketStore.on(SOCKET_EVENTS.GROUP.UPDATE, handleGroupUpdate)
    socketStore.on(SOCKET_EVENTS.LOBBY.CREATED, handleLobbyCreated)
    socketStore.on(SOCKET_EVENTS.LOBBY.ACTIVE_SYNC, handleActiveLobbySync)
  }

  const unregisterSocketListeners = () => {
    socketStore.off(SOCKET_EVENTS.CONNECTION.CONNECT, syncLobbyPresence)
    socketStore.off(SOCKET_EVENTS.QUEUE.UPDATE, handleQueueUpdate)
    socketStore.off(SOCKET_EVENTS.QUEUE.MATCH_ACCEPT_CANCELLED, handleMatchAcceptCancelled)
    socketStore.off(SOCKET_EVENTS.GROUP.UPDATE, handleGroupUpdate)
    socketStore.off(SOCKET_EVENTS.LOBBY.CREATED, handleLobbyCreated)
    socketStore.off(SOCKET_EVENTS.LOBBY.ACTIVE_SYNC, handleActiveLobbySync)
  }

  const initAuthenticatedState = async () => {
    registerSocketListeners()
    if (authStore.username) {
      await syncActiveLobbyFromProfile()
      await syncLobbyPresence()
      await queueStore.syncWithServer(authStore.username)
      await groupStore.syncStatus(authStore.username)
    }
  }

  const handleLogout = async () => {
    try {
      await socketStore.cleanupSocket()
      queueStore.resetQueue()
      lobbyStore.reset()
      groupStore.resetGroup()
      clearCurrentLobby()
      authStore.logout()
      currentLobbyId.value = null
      currentLobbyCaptains.value = null
      await socketStore.initSocket()
      router.replace('/auth')
    } catch (error) {
      rootStore.setError('Logout failed')
    }
  }

  const handleLeaveLobby = async () => {
    if (!route.params.lobbyId) return
    try {
      const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.LEAVE, {
        lobby_id: route.params.lobbyId,
        username: authStore.username
      })
      if (response?.success) {
        lobbyStore.leaveLobby()
        clearCurrentLobby()
        currentLobbyId.value = null
        currentLobbyCaptains.value = null
        router.push('/')
      } else {
        throw new Error(response?.message || 'Failed to leave lobby')
      }
    } catch (error) {
      rootStore.setError('Failed to leave lobby')
    }
  }

  const handleReturnToLobby = async () => {
    if (!currentLobbyId.value) return
    router.push(`/lobby/${currentLobbyId.value}`)
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
      if (response?.allAccepted) {
        await new Promise((resolve) => setTimeout(resolve, 150))
        await syncActiveLobbyFromProfile()
      }
    } catch (error) {
      rootStore.setError(error.message || 'Failed to accept match')
    }
  }

  const syncAcceptedMatchLobby = async () => {
    if (lobbySyncPending.value || isInLobby.value) return
    const matchAccept = queueStore.matchAccept
    const acceptedCount = matchAccept.acceptedCount || 0
    const requiredCount = matchAccept.requiredCount || 0
    if (!matchAccept.active || !requiredCount || acceptedCount < requiredCount) return

    lobbySyncPending.value = true
    try {
      await new Promise((resolve) => setTimeout(resolve, 150))
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
        await socketStore.initSocket(authStore.token, authStore.username)
      } else {
        await socketStore.initSocket()
      }

      if (!isAuthenticated) {
        router.replace('/auth')
        clearCurrentLobby()
        currentLobbyId.value = null
        currentLobbyCaptains.value = null
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
      currentLobbyCaptains.value = null
    }
  })

  watch(
    [() => route.path, activeLobbyId],
    ([path, lobbyId]) => {
      if ((path === '/queue' || path === '/play') && lobbyId) {
        router.replace(`/lobby/${lobbyId}`)
      }
    },
    { immediate: true }
  )

  watch(() => lobbyStore.captains, (captains) => {
    if (captains?.team1 && captains?.team2) {
      currentLobbyCaptains.value = captains
      setCurrentLobbyCaptains(captains)
    }
  }, { deep: true })

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
    socketStore.cleanupSocket()
  })

  return {
    isInLobby,
    currentLobbyId,
    currentLobbyCaptains,
    canReturnToLobby,
    activeLobbyId,
    playRoute,
    isMatchAcceptParticipant,
    isMatchAcceptCancelled,
    handleLogout,
    handleLeaveLobby,
    handleReturnToLobby,
    handleProfile,
    handleGroup,
    handleAcceptMatch,
    handleCloseMatchAccept,
    handleDismissMatchAccept
  }
}
