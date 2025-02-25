export class AppError extends Error {
  constructor(message, code, context) {
    super(message);
    this.code = code;
    this.context = context;
  }
}

export const handleError = (error, context) => {
  console.error(`[${context}]:`, error);
  
  if (error instanceof AppError) {
    return error;
  }
  
  return new AppError(
    error.message || 'An unexpected error occurred',
    error.code || 'UNKNOWN_ERROR',
    context
  );
}; 