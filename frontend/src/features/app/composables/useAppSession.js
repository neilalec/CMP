import { onBeforeUnmount, onMounted, watch, ref, computed } from 'vue'
import { SOCKET_EVENTS } from '../../../constants/socketEvents'
import { PASSWORD_AUTH_ENABLED } from '../../../config'
import { routeForCurrentMatch } from '../utils/currentMatch'
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
  const isSessionlessRoute = () => (
    route.meta?.prototype === true
    || (typeof window !== 'undefined' && window.location.pathname.startsWith('/prototype/'))
  )
  const shouldSkipSessionBootstrap = () => (
    isSessionlessRoute()
    || (!PASSWORD_AUTH_ENABLED && route.meta?.guest === true)
  )
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
  let skipNextAuthWatch = false

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
      const createdMatch = data.current_match || {
        gameType: data.game_type || 'squad',
        lobbyId: data.lobby_id
      }
      const matchRoute = routeForCurrentMatch(createdMatch)
      if (!matchRoute) return
      if (createdMatch.gameType === 'wardogs') {
        queueStore.resetQueue()
        router.push(matchRoute)
        return
      }
      lobbyStore.reset()
      lobbyStore.updateLobbyState(data)
      setCurrentLobbyId(data.lobby_id)
      queueStore.resetQueue()
      router.push(matchRoute)
    }
  }

  const routeToLobby = (lobbyId) => {
    if (!lobbyId) return false
    currentLobbyId.value = lobbyId
    setCurrentLobbyId(lobbyId)
    const matchRoute = routeForCurrentMatch({ gameType: 'squad', lobbyId })
    if (!route.path.startsWith(matchRoute)) {
      router.push(matchRoute)
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
        if (routeForCurrentMatch(profile?.current_match)
          || profile?.active_lobby
          || isInLobby.value) return
      } catch (error) {
        // Lobby-created is the primary path; this retry is just a fallback.
      }
      if (attempt < 8) {
        waitForFinalizedLobby(attempt + 1)
      }
    }, Math.min(5000, 350 * attempt))
  }

  const handleActiveLobbySync = (data) => {
    const activeMatch = data?.current_match
      || (data?.lobby_id ? { gameType: 'squad', lobbyId: data.lobby_id } : null)
    const matchRoute = routeForCurrentMatch(activeMatch)

    if (matchRoute) {
      if (activeMatch.gameType === 'squad') {
        currentLobbyId.value = activeMatch.lobbyId
        setCurrentLobbyId(activeMatch.lobbyId)
      } else {
        lobbyStore.leaveLobby()
        clearCurrentLobby()
        currentLobbyId.value = null
      }
      if (queueStore.matchAccept.players?.includes(authStore.username)) {
        queueStore.resetQueue()
      }
      if (!route.path.startsWith(matchRoute)) {
        router.push(matchRoute)
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
    const currentMatch = profile?.current_match
      || (profile?.active_lobby ? { gameType: 'squad', lobbyId: profile.active_lobby } : null)
    const matchRoute = routeForCurrentMatch(currentMatch)

    if (matchRoute) {
      if (currentMatch.gameType === 'squad') {
        currentLobbyId.value = currentMatch.lobbyId
        setCurrentLobbyId(currentMatch.lobbyId)
      } else {
        lobbyStore.leaveLobby()
        clearCurrentLobby()
        currentLobbyId.value = null
      }
      if (queueStore.matchAccept.players?.includes(authStore.username)) {
        queueStore.resetQueue()
      }
      if (!route.path.startsWith(matchRoute)) {
        router.push(matchRoute)
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
        const matchRoute = routeForCurrentMatch({
          gameType: response.gameType,
          lobbyId: response.lobbyId
        })
        if (matchRoute) {
          if (response.gameType === 'squad') {
            routeToLobby(response.lobbyId)
          } else {
            router.push(matchRoute)
          }
        }
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
    if (shouldSkipSessionBootstrap()) {
      socketStore.cleanupSocket()
      rootStore.clearError()
      return
    }
    console.log('App mounted, initializing base socket connection...')
    try {
      const isAuthenticated = authStore.restoreAuth()
      // A Steam callback can set auth before this parent mount hook runs. The
      // initial restore below owns socket startup in that case; skip the
      // reactive auth watcher for the same transition.
      skipNextAuthWatch = isAuthenticated

      // The callback view owns the transition from Steam's redirect payload
      // to persisted frontend auth. Do not connect anonymously or send it to
      // /auth while that callback is still establishing the session.
      if (!isAuthenticated && route.meta?.steamCallback) return

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
    if (shouldSkipSessionBootstrap()) return
    if (skipNextAuthWatch) {
      skipNextAuthWatch = false
      return
    }
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
    () => {
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
