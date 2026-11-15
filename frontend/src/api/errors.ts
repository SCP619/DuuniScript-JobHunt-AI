import type { ErrorResponse } from "./types";

export const BACKEND_UNREACHABLE = "backend_unreachable";

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;
  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details ?? {};
  }
  static fromResponse(status: number, body: ErrorResponse) {
    return new ApiError(status, body.error.code, body.error.message, body.error.details);
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

export function isOffline(e: unknown) {
  return isApiError(e) && e.code === BACKEND_UNREACHABLE;
}

export function errorMessage(e: unknown) {
  if (isOffline(e)) return "Can't reach the DuuniScript backend. Is it running?";
  if (isApiError(e)) return e.message;
  return "Something unexpected happened.";
}

/** Map validation_error details.fields to { fieldName: msg } using the last loc segment. */
export function fieldErrors(e: unknown): Record<string, string> {
  if (!isApiError(e) || e.code !== "validation_error") return {};
  const fields = (e.details["fields"] as { loc: string[]; msg: string }[] | undefined) ?? [];
  const out: Record<string, string> = {};
  for (const f of fields) {
    const key = [...f.loc].reverse().find((p) => typeof p === "string" && p !== "body" && p !== "query");
    if (key && !out[key]) out[key] = f.msg;
  }
  return out;
}
