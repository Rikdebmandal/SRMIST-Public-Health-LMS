/**
 * API client.
 *
 * The access token lives in memory only. The refresh token is an httpOnly
 * cookie the browser sends automatically, so a page reload silently restores
 * the session without ever exposing a long-lived credential to JavaScript.
 */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

const API_ROOT = `${API_BASE}/api/v1`;

let accessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;
const listeners = new Set<(token: string | null) => void>();

export function setAccessToken(token: string | null) {
  accessToken = token;
  listeners.forEach((listener) => listener(token));
}

export function getAccessToken() {
  return accessToken;
}

export function onTokenChange(listener: (token: string | null) => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export interface ApiErrorShape {
  code: string;
  message: string;
  details?: Record<string, string[] | string>;
}

export class ApiError extends Error {
  status: number;
  code: string;
  details?: Record<string, string[] | string>;

  constructor(status: number, payload: ApiErrorShape) {
    super(payload.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = payload.code;
    this.details = payload.details;
  }

  /** Flatten field errors into a readable list for forms. */
  get fieldMessages(): string[] {
    if (!this.details) return [];
    return Object.entries(this.details).flatMap(([field, value]) => {
      const messages = Array.isArray(value) ? value : [String(value)];
      return messages.map((message) =>
        field === 'non_field_errors' ? message : `${field}: ${message}`,
      );
    });
  }
}

async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_ROOT}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!response.ok) {
        setAccessToken(null);
        return null;
      }
      const data = await response.json();
      setAccessToken(data.access);
      return data.access as string;
    } catch {
      setAccessToken(null);
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  /** Skip the automatic refresh-and-retry (used by auth calls themselves). */
  skipRetry?: boolean;
  raw?: boolean;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, skipRetry, raw, headers, ...rest } = options;
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;

  const send = async (token: string | null): Promise<Response> =>
    fetch(`${API_ROOT}${path}`, {
      ...rest,
      credentials: 'include',
      headers: {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(headers as Record<string, string>),
      },
      body: isFormData ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined,
    });

  let response = await send(accessToken);

  // One transparent retry after refreshing an expired access token.
  if (response.status === 401 && !skipRetry) {
    const token = await refreshAccessToken();
    if (token) response = await send(token);
  }

  if (response.status === 204) return undefined as T;

  if (raw) return response as unknown as T;

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const payload: ApiErrorShape = data?.error ?? {
      code: 'error',
      message: response.statusText || 'Request failed.',
    };
    throw new ApiError(response.status, payload);
  }

  return data as T;
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: 'DELETE' }),
  refresh: refreshAccessToken,
};

/** Trigger a browser download for an authenticated export endpoint. */
export async function downloadFile(path: string, filename: string) {
  const response = await apiFetch<Response>(path, { raw: true });
  if (!response.ok) {
    const text = await response.text();
    let message = 'The export could not be generated.';
    try {
      message = JSON.parse(text)?.error?.message ?? message;
    } catch {
      /* keep the default message */
    }
    throw new ApiError(response.status, { code: 'export_failed', message });
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export interface Paginated<T> {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** Endpoints return either a page object or a bare array; normalise both. */
export function toList<T>(payload: Paginated<T> | T[] | undefined | null): T[] {
  if (!payload) return [];
  return Array.isArray(payload) ? payload : payload.results ?? [];
}
