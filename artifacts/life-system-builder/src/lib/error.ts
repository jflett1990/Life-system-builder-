export function extractApiError(err: unknown, fallback = "An unexpected error occurred."): string {
  if (!err) return fallback;
  const e = err as Record<string, any>;
  return e?.body?.detail ?? e?.body?.message ?? e?.detail ?? e?.message ?? fallback;
}
