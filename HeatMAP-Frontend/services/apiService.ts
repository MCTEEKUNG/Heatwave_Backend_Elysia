/**
 * Centralized API Service
 *
 * Production-ready API client for the Heatwave AI backend.
 * Features: timeout handling, retry with exponential back-off,
 * structured error types, and request/response logging.
 */

const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL || 'http://localhost:3000';

// ─── Types ───────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NetworkError';
  }
}

// ─── Config ──────────────────────────────────────────────────────────────────

const DEFAULT_TIMEOUT_MS = 15_000;   // 15 s per request
const MAX_RETRIES        = 2;
const RETRY_DELAY_MS     = 800;      // base delay, doubled each retry

// ─── Helpers ─────────────────────────────────────────────────────────────────

function sleep(ms: number) {
  return new Promise<void>((res) => setTimeout(res, ms));
}

async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new NetworkError(`Request timed out after ${timeoutMs / 1000}s`);
    }
    throw new NetworkError(err.message ?? 'Network request failed');
  } finally {
    clearTimeout(timer);
  }
}

// ─── Core request function ────────────────────────────────────────────────────

async function request<T>(
  path: string,
  options: RequestInit & { timeoutMs?: number } = {},
  retries = MAX_RETRIES,
): Promise<T> {
  const { timeoutMs, ...fetchOptions } = options;
  const url = `${API_BASE_URL}${path}`;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetchWithTimeout(url, {
        headers: { 'Content-Type': 'application/json', ...fetchOptions.headers },
        ...fetchOptions,
      }, timeoutMs);

      if (!response.ok) {
        // Don't retry on 4xx client errors
        if (response.status >= 400 && response.status < 500) {
          let message = `HTTP ${response.status}`;
          try { message = (await response.json()).error ?? message; } catch {}
          throw new ApiError(response.status, 'CLIENT_ERROR', message);
        }
        throw new ApiError(response.status, 'SERVER_ERROR', `HTTP ${response.status}`);
      }

      return (await response.json()) as T;
    } catch (err) {
      // Don't retry ApiError (4xx) or on the last attempt
      if (err instanceof ApiError || attempt === retries) throw err;

      const delay = RETRY_DELAY_MS * 2 ** attempt;
      console.warn(`[API] ${path} failed (attempt ${attempt + 1}), retrying in ${delay}ms…`);
      await sleep(delay);
    }
  }

  // Should never reach here, but satisfies TypeScript
  throw new NetworkError('Request failed after all retries');
}

// ─── Public API ───────────────────────────────────────────────────────────────

export const api = {
  get<T>(path: string, opts: { timeoutMs?: number } = {}) {
    return request<T>(path, { method: 'GET', ...opts });
  },

  post<T>(path: string, body: unknown, opts: { timeoutMs?: number } = {}) {
    return request<T>(path, {
      method: 'POST',
      body: JSON.stringify(body),
      ...opts,
    });
  },

  /** Health-check — useful for connectivity tests. */
  async isReachable(): Promise<boolean> {
    try {
      await request<{ status: string }>('/api/health', { method: 'GET' });
      return true;
    } catch {
      return false;
    }
  },
};

export { API_BASE_URL };
