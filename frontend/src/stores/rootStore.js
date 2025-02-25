import { defineStore } from 'pinia';

export const useRootStore = defineStore('root', {
  state: () => ({
    errorQueue: [],
    currentError: null,
    loading: false,
    errorTimer: null
  }),
  
  actions: {
    setError(error) {
      this.errorQueue.push(error);
      if (!this.currentError) {
        this.processNextError();
      }
    },
    
    clearError() {
      // Clear current error and timer
      if (this.errorTimer) {
        clearTimeout(this.errorTimer);
        this.errorTimer = null;
      }
      this.currentError = null;
      this.errorQueue = [];
    },
    
    processNextError() {
      if (this.errorQueue.length > 0) {
        this.currentError = this.errorQueue.shift();
        this.errorTimer = setTimeout(() => {
          this.currentError = null;
          this.processNextError();
        }, 5000);
      }
    },
    
    setLoading(status) {
      this.loading = status;
    }
  }
});
