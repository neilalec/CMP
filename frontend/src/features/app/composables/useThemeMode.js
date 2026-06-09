import { onMounted, ref, watch } from 'vue'

const THEME_STORAGE_KEY = 'cmp-theme'

export function useThemeMode() {
  const isDarkMode = ref(false)

  const applyTheme = (enabled) => {
    document.documentElement.classList.toggle('dark-mode', enabled)
  }

  onMounted(() => {
    isDarkMode.value = localStorage.getItem(THEME_STORAGE_KEY) === 'dark'
    applyTheme(isDarkMode.value)
  })

  watch(isDarkMode, (enabled) => {
    applyTheme(enabled)
    localStorage.setItem(THEME_STORAGE_KEY, enabled ? 'dark' : 'light')
  })

  return {
    isDarkMode
  }
}
