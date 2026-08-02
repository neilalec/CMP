<script setup>
import { reactive, ref } from 'vue'
import { API_BASE_URL } from '../../../config'
import { useAuthStore } from '../../../stores/authStore'
import { useRootStore } from '../../../stores/rootStore'
import {
  formatJoinStrategy,
  formatLookupStep,
  getServerDiscovery,
  getServerJoinStrategy
} from '../utils/serverDiscovery'

const props = defineProps({
  submitPath: {
    type: String,
    required: true
  },
  testPath: {
    type: String,
    required: true
  },
  submitLabel: {
    type: String,
    default: 'Submit Server'
  },
  helperText: {
    type: String,
    default: ''
  },
  successMessage: {
    type: String,
    default: 'Server submitted.'
  }
})

const emit = defineEmits(['submitted'])

const authStore = useAuthStore()
const rootStore = useRootStore()

const createEmptyForm = () => ({
  display_name: '',
  owner_label: '',
  steam_lobby_id: '',
  connect_address: '',
  join_password: '',
  bridge_url: '',
  bridge_token: ''
})

const serverForm = reactive(createEmptyForm())
const submitting = ref(false)
const testing = ref(false)
const testResult = ref(null)
const success = ref('')

const formatJson = (value) => JSON.stringify(value ?? null, null, 2)

const apiFetch = async (path, options = {}) => {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${authStore.token}`,
      ...(options.headers || {})
    }
  })
  const payload = await response.json()
  if (!response.ok || !payload?.success) {
    throw new Error(payload?.message || 'Request failed')
  }
  return payload
}

const resetForm = () => {
  Object.assign(serverForm, createEmptyForm())
}

const runServerTest = async () => {
  testing.value = true
  success.value = ''
  testResult.value = null
  try {
    const payload = await apiFetch(props.testPath, {
      method: 'POST',
      body: JSON.stringify(serverForm)
    })
    testResult.value = payload.result || null
  } catch (error) {
    rootStore.setError(error.message || 'Server test failed')
  } finally {
    testing.value = false
  }
}

const submitServer = async () => {
  submitting.value = true
  success.value = ''
  try {
    const payload = await apiFetch(props.submitPath, {
      method: 'POST',
      body: JSON.stringify(serverForm)
    })
    resetForm()
    testResult.value = null
    success.value = props.successMessage
    emit('submitted', payload.server || null)
  } catch (error) {
    rootStore.setError(error.message || 'Failed to submit server')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="server-form">
    <p v-if="helperText" class="server-helper">{{ helperText }}</p>
    <input v-model="serverForm.display_name" type="text" placeholder="Display name" />
    <input v-model="serverForm.owner_label" type="text" placeholder="Owner label" />
    <input v-model="serverForm.steam_lobby_id" type="text" placeholder="Steam lobby ID (optional)" />
    <input v-model="serverForm.connect_address" type="text" placeholder="Connect address" />
    <input v-model="serverForm.join_password" type="text" placeholder="Join password" />
    <input v-model="serverForm.bridge_url" type="text" placeholder="Bridge URL" />
    <input v-model="serverForm.bridge_token" type="password" placeholder="Bridge token" />
    <div class="server-form-actions">
      <button type="button" @click="runServerTest" :disabled="testing || submitting">
        {{ testing ? 'Testing...' : 'Test Server' }}
      </button>
      <button type="button" @click="submitServer" :disabled="submitting">
        {{ submitting ? 'Submitting...' : submitLabel }}
      </button>
    </div>
    <p v-if="success" class="server-success">{{ success }}</p>
    <div v-if="getServerDiscovery(testResult)" class="discovery-panel">
      <div class="data-row">
        <span>Bridge lookup</span>
        <strong>{{ formatLookupStep(getServerDiscovery(testResult)?.bridge) }}</strong>
      </div>
      <div class="data-row">
        <span>A2S lookup</span>
        <strong>{{ formatLookupStep(getServerDiscovery(testResult)?.a2s) }}</strong>
      </div>
      <div class="data-row">
        <span>Steam web lookup</span>
        <strong>{{ formatLookupStep(getServerDiscovery(testResult)?.steamWebApi, 'No Steam Web API match') }}</strong>
      </div>
      <div class="data-row">
        <span>Join method</span>
        <strong>{{ formatJoinStrategy(getServerJoinStrategy(testResult)) }}</strong>
      </div>
      <div class="data-row" v-if="getServerJoinStrategy(testResult)?.target">
        <span>Join target</span>
        <strong>{{ getServerJoinStrategy(testResult)?.target }}</strong>
      </div>
    </div>
    <pre v-if="testResult" class="payload-panel">{{ formatJson(testResult) }}</pre>
  </div>
</template>

<style scoped>
.server-form {
  display: grid;
  gap: 10px;
}

.server-helper,
.server-success {
  margin: 0;
}

.server-helper {
  color: var(--text-muted);
}

.server-success {
  color: var(--accent-strong);
  font-weight: 700;
}

.server-form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

@media (max-width: 640px) {
  .data-row,
  .server-form-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
