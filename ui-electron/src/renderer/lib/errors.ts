export interface ApiError {
  ok: false;
  error: string;
  message: string;
  details?: Record<string, unknown>;
}

export class AiplError extends Error {
  readonly code: string;
  readonly details?: Record<string, unknown>;

  constructor(message: string, code: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "AiplError";
    this.code = code;
    this.details = details;
  }

  static fromApiError(apiError: ApiError): AiplError {
    return new AiplError(apiError.message, apiError.error, apiError.details);
  }
}

const ERROR_MESSAGES: Record<string, string> = {
  WORKSPACE_ERROR: "Workspace error",
  POLICY_ERROR: "Policy error",
  VERIFICATION_ERROR: "Verification failed",
  COMMAND_ERROR: "Command failed",
  ENGINE_ERROR: "Engine error",
  NETWORK_ERROR: "Network error",
  UNKNOWN_ERROR: "Unknown error"
};

export function getErrorMessage(error: unknown): string {
  if (error instanceof AiplError) {
    return ERROR_MESSAGES[error.code] || error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
}
