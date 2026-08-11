import { computed, onMounted, ref, watch } from 'vue'

const THEME_STORAGE_KEY = 'cmp-theme'
const THEMES = ['light', 'dark', 'legacy']
const THEME_LABELS = {
  light: 'Light Theme',
  dark: 'Dark Theme',
  legacy: 'Legacy Theme'
}
const THEME_ICONS = {
  light: 'L',
  dark: 'D',
  legacy: 'G'
}

const normalizeTheme = (theme) => (THEMES.includes(theme) ? theme : 'light')

export function useThemeMode() {
  const theme = ref('light')

  const applyTheme = (nextTheme) => {
    const normalizedTheme = normalizeTheme(nextTheme)
    document.documentElement.classList.toggle('dark-mode', normalizedTheme === 'dark')
    document.documentElement.classList.toggle('legacy-mode', normalizedTheme === 'legacy')
  }

  onMounted(() => {
    const storedTheme = localStorage.getItem(THEME_STORAGE_KEY)
    theme.value = normalizeTheme(storedTheme)
    applyTheme(theme.value)
  })

  watch(theme, (nextTheme) => {
    const normalizedTheme = normalizeTheme(nextTheme)
    if (theme.value !== normalizedTheme) {
      theme.value = normalizedTheme
      return
    }
    applyTheme(normalizedTheme)
    localStorage.setItem(THEME_STORAGE_KEY, normalizedTheme)
  })

  const cycleTheme = () => {
    const currentIndex = THEMES.indexOf(theme.value)
    theme.value = THEMES[(currentIndex + 1) % THEMES.length]
  }

  return {
    theme,
    themeLabel: computed(() => THEME_LABELS[theme.value] || THEME_LABELS.light),
    themeIcon: computed(() => THEME_ICONS[theme.value] || THEME_ICONS.light),
    nextThemeLabel: computed(() => {
      const currentIndex = THEMES.indexOf(theme.value)
      const nextTheme = THEMES[(currentIndex + 1) % THEMES.length]
      return THEME_LABELS[nextTheme] || THEME_LABELS.light
    }),
    cycleTheme
  }
}
