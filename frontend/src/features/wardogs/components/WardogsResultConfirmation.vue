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
const note = ref('');
const correctionReason = ref('');
const correctionMode = ref(false);
const scores = reactive({ valkyra: '', lonestar: '', manticore: '' });
const placementRanks = reactive({ valkyra: '', lonestar: '', manticore: '' });
const successfulObservation = computed(() => Boolean(props.match.observation?.observedAt));
const observedScores = computed(() => props.match.scores || {});
const currentRevision = computed(() => props.resultHistory.at(-1) || null);
const numericScores = computed(() => Object.fromEntries(
  Object.entries(scores).map(([id, value]) => [id, value === '' ? null : Number(value)])
));
const allPlacementsChosen = computed(() => Object.values(placementRanks).every((value) => value !== ''));
const completeScores = computed(() => Object.values(numericScores.value).every((value) =>
  Number.isInteger(value) && value >= 0
));
const placementGroups = computed(() => {
  const values = Object.values(placementRanks);
  if (values.some((value) => !['1', '2', '3'].includes(String(value)))) return null;
  const orderedRanks = [...new Set(values.map(Number))].sort((a, b) => a - b);
  if (orderedRanks.some((rank, index) => rank !== index + 1)) return null;
  return orderedRanks.map((rank) => props.match.factions.map((faction) => faction.id)
    .filter((id) => Number(placementRanks[id]) === rank));
});
const placementValid = computed(() => {
  const groups = placementGroups.value;
  if (!groups || (status.value === 'completed_win' && groups[0].length !== 1) ||
      (status.value === 'tie' && groups[0].length < 2)) return false;
  if (!completeScores.value) return false;
  return groups.every((group) => group.every((id) => numericScores.value[id] === numericScores.value[group[0]])) &&
    groups.every((group, index) => index === 0 || numericScores.value[groups[index - 1][0]] > numericScores.value[group[0]]);
});
const outcomeValid = computed(() => ['completed_win', 'tie'].includes(status.value)
  ? completeScores.value && placementValid.value : true);
const differs = computed(() => successfulObservation.value && completeScores.value &&
  Object.keys(scores).some((id) => numericScores.value[id] !== observedScores.value[id]));
const resultLabel = (value) => ({
  completed_win: 'Completed win', tie: 'Tie for first', incomplete: 'Incomplete / abandoned', void: 'Void / cancelled'
})[value] || value;
const ordinal = (rank) => ({ 1: '1st', 2: '2nd', 3: '3rd' })[rank] || `${rank}th`;
const placementRows = (result) => {
  if (!Array.isArray(result?.placementGroups)) return [];
  let rank = 1;
  return result.placementGroups.map((group) => {
    const row = {
      rank,
      factions: group.map((id) => props.match.factions.find((faction) => faction.id === id)?.name || id)
    };
    rank += group.length;
    return row;
  });
};

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
  note.value = currentRevision.value.note || '';
  correctionReason.value = '';
  for (const id of Object.keys(scores)) {
    const score = props.match.result.scores?.[id];
    scores[id] = Number.isInteger(score) ? String(score) : '';
  }
  for (const id of Object.keys(placementRanks)) placementRanks[id] = '';
  (props.match.result.placementGroups || []).forEach((group, index) => {
    for (const id of group) placementRanks[id] = String(index + 1);
  });
};
const cancelCorrection = () => {
  correctionMode.value = false;
  correctionReason.value = '';
  for (const id of Object.keys(placementRanks)) placementRanks[id] = '';
  fillObservedScores();
};
watch(() => [props.match.id, props.match.result?.revisionNumber], ([lobbyId, revision], [previousLobbyId, previousRevision]) => {
  if (previousLobbyId && (lobbyId !== previousLobbyId ||
      (previousRevision && revision && revision > previousRevision))) {
    correctionMode.value = false;
    correctionReason.value = '';
    for (const id of Object.keys(placementRanks)) placementRanks[id] = '';
    fillObservedScores();
  }
});
const submit = () => {
  if (!outcomeValid.value) return;
  const result = { status: status.value, winnerFaction: null, placementGroups: null, scores: null, note: note.value };
  if (['completed_win', 'tie'].includes(status.value)) {
    result.scores = numericScores.value;
    result.placementGroups = placementGroups.value;
    if (status.value === 'completed_win') result.winnerFaction = placementGroups.value[0][0];
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
    <p v-else>Live scores are evidence only. Enter the placement explicitly; CMP will not infer completion or ranking from scores.</p>
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
      <label v-for="faction in match.factions" :key="`place-${faction.id}`" class="wardogs-result-field">
        <span>{{ faction.name }} placement group</span>
        <select v-model="placementRanks[faction.id]" required>
          <option disabled value="">Choose placement</option>
          <option value="1">1st</option>
          <option value="2">2nd</option>
          <option value="3">3rd</option>
        </select>
      </label>
      <small>Choose the same place for factions tied together. All three factions must be placed.</small>
    </div>
    <button v-if="correctionMode && successfulObservation && (status === 'completed_win' || status === 'tie')" type="button" @click="useObservedScores">Use latest observed scores</button>
    <p v-if="differs" class="wardogs-result-note">Submitted final scores differ from the latest observed server scores.</p>
    <p v-if="completeScores && ['completed_win', 'tie'].includes(status) && placementGroups && !placementValid" class="wardogs-result-note">
      Placement and scores must agree. Tied factions need equal scores, and each higher placement group needs a higher score.
    </p>
    <p v-if="['completed_win', 'tie'].includes(status) && allPlacementsChosen && !placementGroups" class="wardogs-result-note">
      Placement groups must use consecutive places with no gaps.
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
    <div v-if="placementRows(match.result).length" class="wardogs-confirmed-placement" aria-label="Confirmed placement">
      <div v-for="row in placementRows(match.result)" :key="`${row.rank}-${row.factions.join('-')}`">
        <strong>{{ ordinal(row.rank) }}</strong> {{ row.factions.join(' / ') }}
      </div>
    </div>
    <p v-else-if="match.result.placementUnavailable" class="wardogs-result-note">Placement is unavailable for this older result and needs administrator review.</p>
    <p v-else-if="match.result.status === 'incomplete' || match.result.status === 'void'">No competitive placement was recorded.</p>
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
      <div v-if="placementRows(revision).length" class="wardogs-confirmed-placement">
        <div v-for="row in placementRows(revision)" :key="`${revision.revisionId}-${row.rank}-${row.factions.join('-')}`">
          <strong>{{ ordinal(row.rank) }}</strong> {{ row.factions.join(' / ') }}
        </div>
      </div>
      <span v-else-if="revision.placementUnavailable" class="wardogs-result-note">Placement unavailable; review required.</span>
      <span v-for="faction in match.factions" v-if="revision.scores" :key="faction.id">{{ faction.name }}: {{ revision.scores[faction.id] }}</span>
      <small>{{ revision.confirmedAt }} · {{ revision.actorId }}</small>
      <p v-if="revision.note">{{ revision.note }}</p>
      <p v-if="revision.correctionReason"><strong>Correction reason:</strong> {{ revision.correctionReason }}</p>
      <small v-if="revision.observation?.available">Observation {{ revision.observation.observedAt }} · {{ revision.observation.differsFromObservation ? 'scores differed' : 'scores matched' }}</small>
    </article>
  </section>
  <p v-if="canConfirm && historyError && !resultHistory.length" role="alert">{{ historyError }}</p>
</template>
