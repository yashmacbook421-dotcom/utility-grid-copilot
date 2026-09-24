const TTL_MS = 300_000;

const store = new Map<string, { expiresAt: number; value: unknown }>();

export function cacheGet<T>(key: string): T | null {
  const entry = store.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    store.delete(key);
    return null;
  }
  return entry.value as T;
}

export function cacheSet(key: string, value: unknown): void {
  store.set(key, { expiresAt: Date.now() + TTL_MS, value });
}

export function makeKey(...parts: string[]): string {
  return parts.join("|");
}
