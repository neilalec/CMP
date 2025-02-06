import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export const useQueueStore = defineStore('queue', () => {
  const playersInQueue = ref(0)
  const inQueue = ref(false)
  const queueList = ref([])
  const lastUpdated = ref(null)

  // Update queue state
  function updateQueueState(data) {
    playersInQueue.value = data.playersInQueue || 0
    inQueue.value = data.inQueue || false
    queueList.value = data.queue || []
    lastUpdated.value = data.timestamp || Date.now()
    console.log('Queue state updated:', {
      playersInQueue: playersInQueue.value,
      inQueue: inQueue.value,
      queueList: queueList.value,
      lastUpdated: lastUpdated.value
    })
  }

  // Reset queue state
  function resetQueue() {
    playersInQueue.value = 0
    inQueue.value = false
    queueList.value = []
    lastUpdated.value = null
    console.log('Queue state reset')
  }

  return { 
    playersInQueue, 
    inQueue, 
    queueList,
    lastUpdated,
    updateQueueState,
    resetQueue
  }
})
