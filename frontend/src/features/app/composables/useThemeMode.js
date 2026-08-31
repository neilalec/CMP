import { computed, onMounted, ref, watch } from 'vue'

const THEME_STORAGE_KEY = 'cmp-theme'
const WIP_THEME_ENABLED = false
const THEMES = WIP_THEME_ENABLED
  ? ['light', 'legacy', 'dark']
  : ['light', 'legacy']
const THEME_LABELS = WIP_THEME_ENABLED
  ? { light: 'Light Theme', legacy: 'Dark Theme', dark: 'Dark WIP' }
  : { light: 'Light Theme', legacy: 'Dark Theme' }
const THEME_ICONS = WIP_THEME_ENABLED
  ? { light: 'L', legacy: 'D', dark: 'W' }
  : { light: 'L', legacy: 'D' }

const normalizeTheme = (theme) => {
  if (!WIP_THEME_ENABLED && theme === 'dark') {
    return 'legacy'
  }

  return THEMES.includes(theme) ? theme : 'light'
}

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
