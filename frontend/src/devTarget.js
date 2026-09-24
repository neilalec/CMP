// Vite receives this only from the local development launcher. Production uses WARDOGS.
export const developmentTarget = import.meta.env.DEV && import.meta.env.VITE_CMP_DEV_TARGET === 'squad'
  ? 'squad'
  : 'wardogs'
