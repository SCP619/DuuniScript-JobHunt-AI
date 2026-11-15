import { USE_MOCKS } from "./http";
import { mockApi } from "./mock";
import { realApi } from "./real";
import type { ApiService } from "./service";

/** The single entry point for all backend access. Switched only by VITE_USE_MOCKS. */
export const api: ApiService = USE_MOCKS ? mockApi : realApi;
export { USE_MOCKS };
export * from "./errors";
export type * from "./types";
