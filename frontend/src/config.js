const trimTrailingSlash = (value) => value.replace(/\/+$/, '');

const browserOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:5000';
const defaultApiBaseUrl = `${browserOrigin}/api`;
const defaultSocketUrl = browserOrigin;

const resolveConfiguredUrl = (value, fallback) => {
  if (!value || value === 'auto' || value === 'same-origin') {
    return trimTrailingSlash(fallback);
  }

  return trimTrailingSlash(value);
};

export const API_BASE_URL = resolveConfiguredUrl(
  import.meta.env.VITE_API_BASE_URL,
  defaultApiBaseUrl
);

export const SOCKET_URL = resolveConfiguredUrl(
  import.meta.env.VITE_SOCKET_URL,
  defaultSocketUrl
);

export const PASSWORD_AUTH_ENABLED = import.meta.env.VITE_PASSWORD_AUTH_ENABLED === '1';
