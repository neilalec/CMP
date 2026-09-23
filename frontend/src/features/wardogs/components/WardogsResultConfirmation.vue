<script setup>
import { computed, reactive, ref, watch } from 'vue';

const props = defineProps({
  match: { type: Object, required: true },
  canConfirm: { type: Boolean, default: false },
  confirming: { type: Boolean, default: false }
});
const emit = defineEmits(['confirm']);
const status = ref('completed_win');
const winnerFaction = ref('');
const note = ref('');
const scores = reactive({ valkyra: '', lonestar: '', manticore: '' });
const successfulObservation = computed(() => Boolean(props.match.observation?.observedAt));
const observedScores = computed(() => props.match.scores || {});
const numericScores = computed(() => Object.fromEntries(
  Object.entries(scores).map(([id, value]) => [id, value === '' ? null : Number(value)])
));
const completeScores = computed(() => Object.values(numericScores.value).every((value) =>
  Number.isInteger(value) && value >= 0
));
const highestScore = computed(() => completeScores.value ? Math.max(...Object.values(numericScores.value)) : null);
const topScoreCount = computed(() => completeScores.value
  ? Object.values(numericScores.value).filter((value) => value === highestScore.value).length : 0);
const outcomeValid = computed(() => status.value === 'completed_win'
  ? completeScores.value && Boolean(winnerFaction.value) && numericScores.value[winnerFaction.value] === highestScore.value && topScoreCount.value === 1
  : status.value === 'tie' ? completeScores.value && topScoreCount.value >= 2 : true);
const differs = computed(() => successfulObservation.value && completeScores.value &&
  Object.keys(scores).some((id) => numericScores.value[id] !== observedScores.value[id]));

watch(() => [props.match.id, props.match.observation?.observedAt], () => {
  for (const id of Object.keys(scores)) {
    const value = props.match.scores?.[id];
    scores[id] = successfulObservation.value && Number.isInteger(value) ? String(value) : '';
  }
  winnerFaction.value = '';
}, { immediate: true });

const submit = () => {
  if (!outcomeValid.value) return;
  const submission = { status: status.value, winnerFaction: null, scores: null, note: note.value };
  if (status.value === 'completed_win') {
    if (!completeScores.value || !winnerFaction.value) return;
    submission.scores = numericScores.value;
    submission.winnerFaction = winnerFaction.value;
  } else if (status.value === 'tie') {
    if (!completeScores.value) return;
    submission.scores = numericScores.value;
  }
  emit('confirm', submission);
};
</script>

<template>
  <section v-if="canConfirm && match.result?.status === 'unconfirmed'" class="window-panel wardogs-result-confirmation" aria-label="Confirm WARDOGS result">
    <div class="window-titlebar"><span>Referee result confirmation</span><span class="window-titlebar-meta">ADMIN</span></div>
    <p>Live scores are evidence only. Confirm the final outcome explicitly; CMP will not infer completion or a winner.</p>
    <p v-if="successfulObservation" class="wardogs-result-note">
      Suggested from live observation at {{ match.observation.observedAt }} ({{ match.observation.state }}). Review and edit every score before confirming.
    </p>
    <p v-else class="wardogs-result-note">No successful live score observation is available. You can enter the result manually.</p>
    <label class="wardogs-result-field">
      <span>Outcome</span>
      <select v-model="status">
        <option value="completed_win">Completed win</option>
        <option value="tie">Tie</option>
        <option value="incomplete">Incomplete / abandoned</option>
        <option value="void">Void / cancelled</option>
      </select>
    </label>
    <div v-if="status === 'completed_win' || status === 'tie'" class="wardogs-result-score-fields">
      <label v-for="faction in match.factions" :key="faction.id" class="wardogs-result-field">
        <span>{{ faction.name }} final score</span>
        <input v-model="scores[faction.id]" type="number" min="0" step="1" required inputmode="numeric">
      </label>
    </div>
    <label v-if="status === 'completed_win'" class="wardogs-result-field">
      <span>Winning faction (choose explicitly)</span>
      <select v-model="winnerFaction" required>
        <option disabled value="">Choose a winner</option>
        <option v-for="faction in match.factions" :key="faction.id" :value="faction.id">{{ faction.name }}</option>
      </select>
    </label>
    <p v-if="differs" class="wardogs-result-note">Submitted final scores differ from the latest observed server scores.</p>
    <p v-if="completeScores && !outcomeValid" class="wardogs-result-note">
      {{ status === 'tie' ? 'A tie needs at least two factions to share the highest submitted score.' : 'The selected winner must have the unique highest submitted score.' }}
    </p>
    <label class="wardogs-result-field">
      <span>Referee note (optional)</span>
      <textarea v-model="note" maxlength="1000" rows="2" />
    </label>
    <button type="button" :disabled="confirming || !outcomeValid" @click="submit">
      {{ confirming ? 'Saving…' : 'Confirm authoritative result' }}
    </button>
  </section>
  <section v-else-if="match.result?.status !== 'unconfirmed'" class="window-panel wardogs-confirmed-result" aria-label="Referee confirmed result">
    <div class="window-titlebar"><span>Referee confirmed result</span><span class="window-titlebar-meta">AUTHORITATIVE</span></div>
    <strong>{{ ({ completed_win: 'Completed win', tie: 'Tie', incomplete: 'Incomplete / abandoned', void: 'Void / cancelled' })[match.result.status] }}</strong>
    <p v-if="match.result.status === 'completed_win'">{{ match.factions.find((faction) => faction.id === match.result.winnerFaction)?.name }} won.</p>
    <p v-else-if="match.result.status === 'tie'">The referee confirmed a tie.</p>
    <div v-if="match.result.scores" class="wardogs-result-score-summary">
      <span v-for="faction in match.factions" :key="faction.id">{{ faction.name }}: {{ match.result.scores[faction.id] }}</span>
    </div>
    <small>Confirmed {{ match.result.confirmedAt }}</small>
  </section>
</template>
