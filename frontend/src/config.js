const trimTrailingSlash = (value) => value.replace(/\/+$/, '');

const browserOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:5000';
const defaultApiBaseUrl = `${browserOrigin}/api`;

export const API_BASE_URL = trimTrailingSlash(
  import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl
);

export const SOCKET_URL = trimTrailingSlash(
  import.meta.env.VITE_SOCKET_URL || browserOrigin
);
