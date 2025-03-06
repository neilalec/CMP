export const getEnvConfig = () => {
    if (process.env.NODE_ENV === 'test') {
        return {
            VITE_SOCKET_URL: process.env.VITE_SOCKET_URL || 'http://localhost:5000'
        };
    }
    
    return {
        VITE_SOCKET_URL: import.meta.env.VITE_SOCKET_URL || 'http://localhost:5000'
    };
}; 