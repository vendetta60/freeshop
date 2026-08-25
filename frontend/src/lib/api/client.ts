/**
 * The single HTTP entry point. No component calls `fetch` directly.
 *
 * Centralising it is what makes the error envelope (plan.md 6.1), the
 * language header, the bearer token and refresh-and-retry a single change
 * rather than a search-and-replace across the app.
 */

// import.meta.env is typed as `any` for custom keys unless declared, so the
// cast is what keeps this file free of implicit any.
const BASE: string = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api/v1';

/** The server's uniform error shape (plan.md 6.1). */
export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    field: string | null;
    details: Record<string, unknown>;
  };
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly field: string | null;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: Partial<ApiErrorBody>) {
    const error = body.error;
    super(error?.message ?? `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    // The frontend prefers its own translation of `code`; `message` is the
    // fallback for codes it does not know yet.
    this.code = error?.code ?? 'INTERNAL_ERROR';
    this.field = error?.field ?? null;
    this.details = error?.details ?? {};
  }
}

/**
 * The access token lives in memory only, never in localStorage: anything
 * readable by JavaScript is exfiltratable by an XSS bug. Durability comes
 * from the httpOnly refresh cookie instead (plan.md 6.3).
 */
let accessToken: string | null = null;
let onSessionLost: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

/** Called when refreshing fails, so the UI can drop back to signed-out. */
export function setSessionLostHandler(handler: (() => void) | null): void {
  onSessionLost = handler;
}

type RequestOptions = {
  method?: string | undefined;
  body?: unknown;
  signal?: AbortSignal | undefined;
  lang?: string | undefined;
  headers?: Record<string, string> | undefined;
  /** Internal: prevents a refresh loop. */
  retrying?: boolean | undefined;
};

/**
 * A single in-flight refresh, shared by every caller.
 *
 * Without this, a page that fires four requests on load and gets four 401s
 * would start four refreshes - and since refreshing ROTATES the token, three
 * would present an already-used token and trip reuse detection, signing the
 * user out for doing nothing wrong.
 */
let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!response.ok) return false;
      const body = (await response.json()) as { access_token: string };
      accessToken = body.access_token;
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, lang = 'az', headers: extra } = options;

  // FormData sets its own multipart Content-Type, including the boundary.
  // Setting ours would produce a body the server cannot parse.
  const isForm = body instanceof FormData;

  const headers: Record<string, string> = { 'Accept-Language': lang, ...extra };
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json';
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const init: RequestInit = { method, headers, credentials: 'include' };
  if (body !== undefined) init.body = isForm ? body : JSON.stringify(body);
  if (signal) init.signal = signal;

  const response = await fetch(`${BASE}${path}`, init);

  if (response.status === 204) return undefined as T;

  const payload: unknown = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new ApiError(response.status, payload as Partial<ApiErrorBody>);

    // An expired access token is recoverable: refresh once, then replay the
    // original request. Retried exactly once, so a dead session cannot loop.
    if (error.code === 'TOKEN_EXPIRED' && !options.retrying) {
      if (await refreshSession()) {
        return request<T>(path, { ...options, retrying: true });
      }
      accessToken = null;
      onSessionLost?.();
    }

    throw error;
  }

  return payload as T;
}

/** Restores the session on boot from the httpOnly cookie. */
export async function hydrateSession(): Promise<boolean> {
  return refreshSession();
}

/** Builds a query string, omitting empty values so URLs stay clean. */
export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

/** `error.details.reason` as a string. `details` is `unknown`-valued, so a
 *  bare String() would happily stringify an object into `[object Object]`. */
export function reasonOf(error: unknown): string {
  if (!(error instanceof ApiError)) return '';
  const reason = error.details.reason;
  return typeof reason === 'string' ? reason : '';
}
