const WINDOW_MS = 60_000;
const MAX_REQUESTS = 10;

interface BucketEntry {
  timestamps: number[];
}

const store = new Map<string, BucketEntry>();

export function rateLimitCheck(key: string): void {
  const now = Date.now();
  let entry = store.get(key);
  if (!entry) {
    entry = { timestamps: [] };
    store.set(key, entry);
  }
  entry.timestamps = entry.timestamps.filter((t) => now - t < WINDOW_MS);
  if (entry.timestamps.length >= MAX_REQUESTS) {
    const retryAfter = Math.max(1, Math.ceil((WINDOW_MS - (now - entry.timestamps[0])) / 1000));
    throw new RateLimitError(retryAfter);
  }
  entry.timestamps.push(now);
}

export class RateLimitError extends Error {
  status: number;
  retryAfter: number;
  constructor(retryAfter: number) {
    super(`Rate limit exceeded: max ${MAX_REQUESTS} requests per ${WINDOW_MS / 1000}s.`);
    this.status = 429;
    this.retryAfter = retryAfter;
  }
}
