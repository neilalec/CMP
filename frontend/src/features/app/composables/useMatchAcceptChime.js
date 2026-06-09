import { ref, watch } from 'vue'

export function useMatchAcceptChime({ queueStore, authStore, isMatchAcceptParticipant }) {
  const matchAcceptChimeBucket = ref(null)
  let matchAcceptAudioContext = null

  const getAudioContext = async () => {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext
    if (!AudioContextClass) return null

    if (!matchAcceptAudioContext) {
      matchAcceptAudioContext = new AudioContextClass()
    }

    if (matchAcceptAudioContext.state === 'suspended') {
      await matchAcceptAudioContext.resume()
    }

    return matchAcceptAudioContext
  }

  const playMatchAcceptChime = async () => {
    try {
      const audioContext = await getAudioContext()
      if (!audioContext) return

      const now = audioContext.currentTime
      const gain = audioContext.createGain()
      gain.gain.setValueAtTime(0.0001, now)
      gain.gain.exponentialRampToValueAtTime(0.08, now + 0.03)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.85)
      gain.connect(audioContext.destination)

      ;[523.25, 659.25].forEach((frequency, index) => {
        const oscillator = audioContext.createOscillator()
        oscillator.type = 'sine'
        oscillator.frequency.setValueAtTime(frequency, now + index * 0.16)
        oscillator.connect(gain)
        oscillator.start(now + index * 0.16)
        oscillator.stop(now + 0.7 + index * 0.16)
      })
    } catch (error) {
      // Browsers may block audio until the user has interacted with the page.
    }
  }

  watch(
    () => ({
      active: queueStore.matchAccept.active,
      cancelled: queueStore.matchAccept.cancelled,
      countdown: queueStore.matchAccept.countdown,
      hasAccepted: queueStore.matchAccept.hasAccepted,
      isParticipant: isMatchAcceptParticipant.value,
      players: queueStore.matchAccept.players,
      username: authStore.username
    }),
    ({ active, cancelled, countdown, hasAccepted, isParticipant, players, username }) => {
      const isListedPlayer = Array.isArray(players) && !!username && players.includes(username)
      const shouldChime = active && !cancelled && !hasAccepted && isParticipant && isListedPlayer
      const seconds = Number(countdown)

      if (!shouldChime || !Number.isFinite(seconds) || seconds <= 0) {
        matchAcceptChimeBucket.value = null
        return
      }

      const bucket = Math.ceil(seconds / 10)
      if (bucket !== matchAcceptChimeBucket.value) {
        matchAcceptChimeBucket.value = bucket
        playMatchAcceptChime()
      }
    },
    { immediate: true }
  )
}
