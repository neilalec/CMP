const trimTrailingSlash = (value) => value.replace(/\/+$/, '');

const defaultApiBaseUrl = 'http://localhost:5000';

export const API_BASE_URL = trimTrailingSlash(
  import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl
);

export const SOCKET_URL = trimTrailingSlash(
  import.meta.env.VITE_SOCKET_URL || API_BASE_URL
);
