<script setup>
import ServerSubmissionForm from '../features/server/components/ServerSubmissionForm.vue'
</script>

<template>
  <div class="add-server-page content-panel page-shell">
    <section class="add-server-panel window-panel">
      <div class="window-titlebar">
        <span class="window-titlebar-label">Add Server</span>
        <span class="window-titlebar-meta">Review Queue</span>
      </div>
      <div class="panel-body">
        <div class="add-server-intro">
          <p class="eyebrow">Server Submission</p>
          <strong class="add-server-heading">Submit a server for admin review and approval.</strong>
        </div>

        <ServerSubmissionForm
          submit-path="/servers/submit"
          test-path="/servers/test"
          submit-label="Submit Server"
          helper-text="You can test the bridge connection before sending the server into the approval queue."
          success-message="Server submitted for admin review."
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.add-server-page {
  width: min(100%, 720px);
}

.add-server-panel {
  overflow: hidden;
}

.add-server-intro {
  display: grid;
  gap: 4px;
  margin-bottom: 12px;
}

.add-server-heading {
  font-family: var(--font-display);
  font-size: 1rem;
  line-height: 1.2;
}
</style>
