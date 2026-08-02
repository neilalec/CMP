/* eslint-env node */
module.exports = {
  root: true,
  env: {
    browser: true
  },
  'extends': [
    'plugin:vue/vue3-essential',
    'eslint:recommended'
  ],
  overrides: [
    {
      files: ['src/views/*.vue'],
      rules: {
        'vue/multi-word-component-names': 'off'
      }
    },
    {
      files: ['tests/**/*.{js,cjs}', 'jest.config.js'],
      env: {
        jest: true,
        node: true
      }
    }
  ],
  parserOptions: {
    ecmaVersion: 'latest'
  }
}
