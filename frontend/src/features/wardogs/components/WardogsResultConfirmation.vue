<script setup>
import { computed, reactive, ref, watch } from 'vue';

const props = defineProps({
  match: { type: Object, required: true },
  canConfirm: { type: Boolean, default: false },
  confirming: { type: Boolean, default: false },
  correcting: { type: Boolean, default: false },
  resultHistory: { type: Array, default: () => [] },
  historyError: { type: String, default: '' }
});
const emit = defineEmits(['confirm', 'correct']);
const status = ref('completed_win');
const winnerFaction = ref('');
const note = ref('');
const correctionReason = ref('');
const correctionMode = ref(false);
const scores = reactive({ valkyra: '', lonestar: '', manticore: '' });
const successfulObservation = computed(() => Boolean(props.match.observation?.observedAt));
const observedScores = computed(() => props.match.scores || {});
const currentRevision = computed(() => props.resultHistory.at(-1) || null);
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
const resultLabel = (value) => ({
  completed_win: 'Completed win', tie: 'Tie', incomplete: 'Incomplete / abandoned', void: 'Void / cancelled'
})[value] || value;

const fillObservedScores = () => {
  for (const id of Object.keys(scores)) {
    const value = props.match.scores?.[id];
    scores[id] = successfulObservation.value && Number.isInteger(value) ? String(value) : '';
  }
};
const useObservedScores = () => {
  if (!successfulObservation.value) return;
  for (const id of Object.keys(scores)) {
    const value = observedScores.value[id];
    if (Number.isInteger(value)) scores[id] = String(value);
  }
};
watch(() => [props.match.id, props.match.observation?.observedAt], fillObservedScores, { immediate: true });

const beginCorrection = () => {
  if (!currentRevision.value) return;
  correctionMode.value = true;
  status.value = props.match.result.status;
  winnerFaction.value = props.match.result.winnerFaction || '';
  note.value = currentRevision.value.note || '';
  correctionReason.value = '';
  for (const id of Object.keys(scores)) {
    const score = props.match.result.scores?.[id];
    scores[id] = Number.isInteger(score) ? String(score) : '';
  }
};
const cancelCorrection = () => {
  correctionMode.value = false;
  correctionReason.value = '';
  fillObservedScores();
};
watch(() => [props.match.id, props.match.result?.revisionNumber], ([lobbyId, revision], [previousLobbyId, previousRevision]) => {
  if (previousLobbyId && (lobbyId !== previousLobbyId ||
      (previousRevision && revision && revision > previousRevision))) {
    correctionMode.value = false;
    correctionReason.value = '';
    fillObservedScores();
  }
});
const submit = () => {
  if (!outcomeValid.value) return;
  const result = { status: status.value, winnerFaction: null, scores: null, note: note.value };
  if (status.value === 'completed_win') {
    result.scores = numericScores.value;
    result.winnerFaction = winnerFaction.value;
  } else if (status.value === 'tie') {
    result.scores = numericScores.value;
  }
  if (correctionMode.value) {
    if (!currentRevision.value || !correctionReason.value.trim()) return;
    emit('correct', {
      expectedRevisionId: currentRevision.value.revisionId,
      correctionReason: correctionReason.value,
      result
    });
  } else {
    emit('confirm', result);
  }
};
</script>

<template>
  <section v-if="canConfirm && (match.result?.status === 'unconfirmed' || correctionMode)" class="window-panel wardogs-result-confirmation" aria-label="Confirm WARDOGS result">
    <div class="window-titlebar"><span>{{ correctionMode ? `Correct result · revision ${(match.result.revisionNumber || 1) + 1}` : 'Referee result confirmation' }}</span><span class="window-titlebar-meta">ADMIN</span></div>
    <p v-if="correctionMode">A new immutable revision will supersede the current result. The previous revision remains in history.</p>
    <p v-else>Live scores are evidence only. Confirm the final outcome explicitly; CMP will not infer completion or a winner.</p>
    <div v-if="successfulObservation" class="wardogs-result-note">
      <strong>Latest live observation · {{ match.observation.state }}</strong>
      <small>{{ match.observation.observedAt }}</small>
      <span v-for="faction in match.factions" :key="faction.id">{{ faction.name }}: {{ observedScores[faction.id] ?? '—' }}</span>
    </div>
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
    <button v-if="correctionMode && successfulObservation && (status === 'completed_win' || status === 'tie')" type="button" @click="useObservedScores">Use latest observed scores</button>
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
    <label v-if="correctionMode" class="wardogs-result-field">
      <span>Required correction reason</span>
      <textarea v-model="correctionReason" maxlength="1000" rows="2" required />
    </label>
    <label class="wardogs-result-field">
      <span>{{ correctionMode ? 'Updated referee note (optional)' : 'Referee note (optional)' }}</span>
      <textarea v-model="note" maxlength="1000" rows="2" />
    </label>
    <div class="wardogs-result-actions">
      <button type="button" :disabled="confirming || correcting || !outcomeValid || (correctionMode && !correctionReason.trim())" @click="submit">
        {{ correcting ? 'Saving revision…' : correctionMode ? 'Confirm new revision' : 'Confirm authoritative result' }}
      </button>
      <button v-if="correctionMode" type="button" :disabled="correcting" @click="cancelCorrection">Cancel</button>
    </div>
  </section>
  <section v-else-if="match.result?.status !== 'unconfirmed'" class="window-panel wardogs-confirmed-result" aria-label="Referee confirmed result">
    <div class="window-titlebar"><span>Referee confirmed result</span><span class="window-titlebar-meta">AUTHORITATIVE · REVISION {{ match.result.revisionNumber }}</span></div>
    <strong>{{ resultLabel(match.result.status) }}</strong>
    <p v-if="match.result.status === 'completed_win'">{{ match.factions.find((faction) => faction.id === match.result.winnerFaction)?.name }} won.</p>
    <p v-else-if="match.result.status === 'tie'">The referee confirmed a tie.</p>
    <p v-if="match.result.corrected">Result corrected by an administrator.</p>
    <div v-if="match.result.scores" class="wardogs-result-score-summary">
      <span v-for="faction in match.factions" :key="faction.id">{{ faction.name }}: {{ match.result.scores[faction.id] }}</span>
    </div>
    <small>Confirmed {{ match.result.confirmedAt }}</small>
    <button v-if="canConfirm && !correctionMode" type="button" :disabled="!currentRevision" @click="beginCorrection">Correct result</button>
    <p v-if="canConfirm && !currentRevision" class="wardogs-result-note">Loading administrator revision history…</p>
  </section>
  <section v-if="canConfirm && resultHistory.length" class="window-panel wardogs-result-history" aria-label="WARDOGS result revision history">
    <div class="window-titlebar"><span>Result revision history</span></div>
    <p v-if="historyError" role="alert">{{ historyError }}</p>
    <article v-for="revision in resultHistory" :key="revision.revisionId" class="wardogs-result-revision">
      <div><strong>Revision {{ revision.revisionNumber }} · {{ revision.revisionType === 'confirmation' ? 'Original confirmation' : 'Correction' }}</strong>
        <span v-if="revision.authoritative" class="wardogs-current-revision">CURRENT AUTHORITATIVE</span></div>
      <span>{{ resultLabel(revision.status) }}</span>
      <span v-if="revision.winnerFaction">Winner: {{ match.factions.find((faction) => faction.id === revision.winnerFaction)?.name }}</span>
      <span v-for="faction in match.factions" v-if="revision.scores" :key="faction.id">{{ faction.name }}: {{ revision.scores[faction.id] }}</span>
      <small>{{ revision.confirmedAt }} · {{ revision.actorId }}</small>
      <p v-if="revision.note">{{ revision.note }}</p>
      <p v-if="revision.correctionReason"><strong>Correction reason:</strong> {{ revision.correctionReason }}</p>
      <small v-if="revision.observation?.available">Observation {{ revision.observation.observedAt }} · {{ revision.observation.differsFromObservation ? 'scores differed' : 'scores matched' }}</small>
    </article>
  </section>
  <p v-if="canConfirm && historyError && !resultHistory.length" role="alert">{{ historyError }}</p>
</template>
