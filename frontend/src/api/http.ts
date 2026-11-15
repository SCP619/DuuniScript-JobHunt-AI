import { ApiError, BACKEND_UNREACHABLE } from "./errors";
import type { ErrorResponse } from "./types";
import { getToken, signalAuthRequired } from "./auth-token";

/** Headers for every API request, including downloads: adds the sign-in token when there is one. */
export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const t = getToken();
  return t ? { ...extra, Authorization: `Bearer ${t}` } : extra;
}

function failure(status: number, data: unknown): ApiError {
  if (data && typeof data === "object" && "error" in data) {
    const err = ApiError.fromResponse(status, data as ErrorResponse);
    if (status === 401 && err.code === "auth_required") signalAuthRequired();
    return err;
  }
  return new ApiError(status, "unexpected_response", `The backend answered with status ${status}.`);
}

export const API_BASE_URL = (
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) || "http://127.0.0.1:8000"
).replace(/\/$/, "");

export const USE_MOCKS = String(import.meta.env["VITE_USE_MOCKS"] ?? "true").toLowerCase() !== "false";

export type QueryValue = string | number | boolean | string[] | null | undefined;

export function buildQuery(query?: Record<string, QueryValue>) {
  const p = new URLSearchParams();
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null || v === "") continue;
      if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
      else p.append(k, String(v));
    }
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

interface RequestOptions {
  query?: Record<string, QueryValue>;
  body?: unknown;
  form?: FormData;
  timeoutMs?: number;
}

export async function request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
  return (await requestWithStatus<T>(method, path, opts)).data;
}

export async function requestWithStatus<T>(method: string, path: string, opts: RequestOptions = {}): Promise<{ status: number; data: T }> {
  const url = `${API_BASE_URL}${path}${buildQuery(opts.query)}`;
  const init: RequestInit = { method, headers: authHeaders({ Accept: "application/json" }) };
  if (opts.form) init.body = opts.form;
  else if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  const controller = opts.timeoutMs ? new AbortController() : null;
  if (controller) init.signal = controller.signal;
  const timer = controller ? setTimeout(() => controller.abort(), opts.timeoutMs) : null;
  try {
    let res: Response;
    try { res = await fetch(url, init); }
    catch {
      if (controller?.signal.aborted) throw new ApiError(408, "timeout", "Reading took too long. Please try again.");
      throw new ApiError(0, BACKEND_UNREACHABLE, "Can't reach the DuuniScript backend. Is it running?");
    }
    if (res.status === 204) return { status: 204, data: undefined as T };
    let data: unknown = null;
    try { data = await res.json(); } catch {
      if (controller?.signal.aborted) throw new ApiError(408, "timeout", "Reading took too long. Please try again.");
    }
    if (!res.ok) throw failure(res.status, data);
    return { status: res.status, data: data as T };
  } finally { if (timer !== null) clearTimeout(timer); }
}

/** Filename from Content-Disposition; prefers RFC 5987 filename* (UTF-8). */
export function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const star = /filename\*\s*=\s*([^']*)'[^']*'([^;]+)/i.exec(header);
  if (star?.[2]) {
    try { return decodeURIComponent(star[2].trim().replace(/^"|"$/g, "")); } catch { /* fall through */ }
  }
  const plain = /filename\s*=\s*("([^"]*)"|[^;]+)/i.exec(header);
  const v = plain?.[2] ?? plain?.[1];
  return v ? v.trim() : fallback;
}

export async function requestBlob(path: string, fallbackName: string): Promise<{ blob: Blob; filename: string }> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders() });
  } catch {
    throw new ApiError(0, BACKEND_UNREACHABLE, "Can't reach the DuuniScript backend. Is it running?");
  }
  if (!res.ok) {
    let data: unknown = null;
    try { data = await res.json(); } catch { data = null; }
    throw failure(res.status, data);
  }
  return { blob: await res.blob(), filename: filenameFromDisposition(res.headers.get("Content-Disposition"), fallbackName) };
}
