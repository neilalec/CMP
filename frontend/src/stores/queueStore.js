import { defineStore } from 'pinia'
import { useAuthStore } from './authStore'
import { useSocketStore } from './socketStore'
import { SOCKET_EVENTS } from '../constants/socketEvents'
import {
  createDefaultMatchAcceptState,
  createDefaultQueueModes,
  createDefaultQueueState
} from './state/queueState'
import { runStoreSocketAction } from './helpers/storeSocketAction'

export const useQueueStore = defineStore('queue', {
  state: () => createDefaultQueueState(),

  getters: {
    currentQueueConfig: (state) => (
      state.queueMode ? state.queueModes[state.queueMode] || null : null
    )
  },

  actions: {
    updateQueueState(data) {
      if (!data) return
      const authStore = useAuthStore()

      const mergedQueueModes = createDefaultQueueModes()
      const payloadModes = data.queueModes || {}
      for (const [modeId, modePayload] of Object.entries(payloadModes)) {
        mergedQueueModes[modeId] = {
          ...(mergedQueueModes[modeId] || {}),
          ...modePayload,
          queue: Array.isArray(modePayload.queue) ? modePayload.queue : [],
          playersInQueue: modePayload.playersInQueue || 0,
          inQueue: !!modePayload.inQueue,
          enabled: modePayload.enabled !== false && !modePayload.disabled,
          disabled: modePayload.enabled === false || !!modePayload.disabled
        }
      }

      this.queueModes = mergedQueueModes
      this.inQueue = !!data.inQueue
      this.queueMode = data.queueMode || null
      this.serverCapacity = Number(data.serverCapacity) || 1
      this.serverAvailable = data.serverAvailable !== false
      this.serverAvailabilityReason = data.serverAvailabilityReason || 'available'
      this.activeLobbyCount = Number(data.activeLobbyCount) || 0
      this.activePendingMatchCount = Number(data.activePendingMatchCount) || 0

      const activeMode = this.queueMode ? this.queueModes[this.queueMode] : null
      this.maxPlayers = activeMode?.maxPlayers || data.maxPlayers || 0
      this.playersInQueue = activeMode?.playersInQueue || data.playersInQueue || 0
      this.queueList = Array.isArray(activeMode?.queue) ? activeMode.queue : (Array.isArray(data.queue) ? data.queue : [])
      this.countdown = data.countdown || null

      if (data.matchAccept?.active) {
        this.matchAccept = {
          active: true,
          cancelled: false,
          cancelReason: '',
          queueMode: data.matchAccept.queueMode || null,
          players: Array.isArray(data.matchAccept.players) ? data.matchAccept.players : [],
          playerProfiles: data.matchAccept.playerProfiles || data.matchAccept.player_profiles || {},
          acceptedPlayers: Array.isArray(data.matchAccept.acceptedPlayers) ? data.matchAccept.acceptedPlayers : [],
          acceptedCount: data.matchAccept.acceptedCount || 0,
          requiredCount: data.matchAccept.requiredCount || 0,
          countdown: data.matchAccept.countdown ?? null,
          finalizingLobby: !!data.matchAccept.finalizingLobby,
          hasAccepted: Array.isArray(data.matchAccept.acceptedPlayers)
            ? data.matchAccept.acceptedPlayers.includes(authStore.username)
            : !!data.matchAccept.hasAccepted
        }
      } else {
        this.resetMatchAccept()
      }

      this.error = null
      this.lastSync = Date.now()
    },

    resetMatchAccept() {
      this.matchAccept = createDefaultMatchAcceptState()
    },

    setMatchAcceptCancelled(reason = 'Match cancelled') {
      this.matchAccept = {
        ...createDefaultMatchAcceptState(),
        cancelled: true,
        cancelReason: reason
      }
    },

    updateOpenLobbies(list) {
      this.openLobbies = Array.isArray(list) ? list : []
    },

    updateActiveLobbies(list) {
      this.activeLobbies = Array.isArray(list) ? list : []
    },

    async joinQueue(username, queueMode) {
      return runStoreSocketAction(this, {
        event: SOCKET_EVENTS.QUEUE.JOIN,
        payload: { username, queueMode },
        fallbackMessage: 'Failed to join queue',
        onSuccess: (response) => {
          this.updateQueueState(response)
        }
      })
    },

    async leaveQueue(username, queueMode = null) {
      return runStoreSocketAction(this, {
        event: SOCKET_EVENTS.QUEUE.LEAVE,
        payload: { username, queueMode },
        fallbackMessage: 'Failed to leave queue',
        onSuccess: (response) => {
          this.updateQueueState(response)
        }
      })
    },

    async syncWithServer(username, options = {}) {
      const { resetOnFailure = false } = options
      const response = await runStoreSocketAction(this, {
        event: SOCKET_EVENTS.QUEUE.STATUS,
        payload: { username },
        setLoading: false,
        swallowError: true,
        fallbackMessage: 'Failed to sync queue',
        onSuccess: (response) => {
          this.updateQueueState(response)
        }
      })

      if (!response && resetOnFailure) {
        this.resetQueue()
      }
    },

    resetQueue() {
      Object.assign(this, createDefaultQueueState())
    },

    async acceptMatch(username) {
      this.loading = true
      try {
        const authStore = useAuthStore()
        const socketStore = useSocketStore()
        const response = await socketStore.emit(SOCKET_EVENTS.QUEUE.ACCEPT_MATCH, { username })
        if (!response?.success) {
          throw new Error(response?.message || 'Failed to accept match')
        }
        if (response.matchAccept?.active) {
          this.matchAccept = {
            active: true,
            cancelled: false,
            cancelReason: '',
            queueMode: response.matchAccept.queueMode || this.matchAccept.queueMode,
            players: Array.isArray(response.matchAccept.players) ? response.matchAccept.players : this.matchAccept.players,
            playerProfiles: response.matchAccept.playerProfiles || response.matchAccept.player_profiles || this.matchAccept.playerProfiles,
            acceptedPlayers: Array.isArray(response.matchAccept.acceptedPlayers) ? response.matchAccept.acceptedPlayers : this.matchAccept.acceptedPlayers,
            acceptedCount: response.matchAccept.acceptedCount ?? this.matchAccept.acceptedCount,
            requiredCount: response.matchAccept.requiredCount ?? this.matchAccept.requiredCount,
            countdown: response.matchAccept.countdown ?? this.matchAccept.countdown,
            finalizingLobby: !!response.finalizingLobby,
            hasAccepted: Array.isArray(response.matchAccept.acceptedPlayers)
              ? response.matchAccept.acceptedPlayers.includes(authStore.username)
              : true
          }
        } else {
          this.matchAccept.hasAccepted = true
          this.matchAccept.finalizingLobby = !!response.finalizingLobby
        }
        return response
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.loading = false
      }
    },

    async seedQueue(count, queueMode) {
      return runStoreSocketAction(this, {
        event: SOCKET_EVENTS.QUEUE.SEED,
        payload: { count, queueMode },
        fallbackMessage: 'Failed to seed queue',
        validate: (response) => {
          if (!response?.success) {
            throw new Error(response?.message || 'Failed to seed queue')
          }
        },
        onSuccess: (response) => {
          this.updateQueueState(response)
        }
      })
    },

    async clearQueue(queueMode = null) {
      return runStoreSocketAction(this, {
        event: SOCKET_EVENTS.QUEUE.CLEAR,
        payload: { queueMode },
        fallbackMessage: 'Failed to clear queue',
        validate: (response) => {
          if (!response?.success) {
            throw new Error(response?.message || 'Failed to clear queue')
          }
        },
        onSuccess: (response) => {
          this.updateQueueState(response)
        }
      })
    },

    async setQueueEnabled(queueMode, enabled) {
      return runStoreSocketAction(this, {
        event: SOCKET_EVENTS.QUEUE.SET_ENABLED,
        payload: { queueMode, enabled },
        fallbackMessage: 'Failed to update queue availability',
        validate: (response) => {
          if (!response?.success) {
            throw new Error(response?.message || 'Failed to update queue availability')
          }
        },
        onSuccess: (response) => {
          this.updateQueueState(response)
        }
      })
    }
  }
})
