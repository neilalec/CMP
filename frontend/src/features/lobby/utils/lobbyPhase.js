export const getLobbyPhaseTitle = ({ step, loading }) => {
  if (loading) return 'Loading Lobby...'
  if (step === 2) return 'Map Voting'
  if (step === 3) return 'Match Ready'
  if (step === 4) return 'Server Details'
  if (step === 5) return 'Score'
  return 'Lobby'
}
